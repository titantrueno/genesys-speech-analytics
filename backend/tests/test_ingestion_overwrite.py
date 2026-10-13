"""Casilla «Sobrescribir» de los flujos de descarga (FE013, T1; criterios 25, 26, 27 y 28).

Sin «Sobrescribir», una conversación que ya está en la base no se descarga ni se toca. Con «Sobrescribir», se sustituye
entera y su análisis vuelve a `pendiente`, borrando el summary y el main topic generados por el LLM.
"""
import psycopg
import pytest
from fastapi.testclient import TestClient

from ingestion.main import create_app
from ingestion.pipeline.analyze import PendingAnalyzer
from ingestion.pipeline.extract import GenesysNames
from ingestion.pipeline.load import INSERTED, OMITTED, UPDATED, load
from ingestion.pipeline.normalize import normalize
from ingestion.runs import RunExecutor, create_run, get_run, list_log
from ingestion.settings import Settings
from tests.ingestion_helpers import (DAY_END, DAY_START, client_factory, create_flow, fixture, make_fake,
                                     table_counts)

pytestmark = pytest.mark.pg
TOKEN = "token-interno-de-prueba"
CHANNELS = ["voz", "chat"]
DOWNLOAD_PATHS = "/api/v2/speechandtextanalytics/conversations/"
FLOW = {"name": "Descarga diaria", "interval": {"type": "relativo", "unit": "hoy"}, "channels": ["voz", "chat"],
        "schedule": {"type": "desactivada"}, "active": True, "timezone": "Europe/Madrid",
        "author": {"id": "1US-AUTOR", "name": "Autora de prueba"}}


def _run(pg_url, fake, flow_id):
    run_id = create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, CHANNELS, ("1US-PRUEBA", "Admin de prueba"))
    RunExecutor(pg_url, client_factory(fake)).execute(run_id)
    return get_run(pg_url, run_id)


def _downloads(fake) -> list[str]:
    return [path for method, path in fake.calls if path.startswith(DOWNLOAD_PATHS)]


def _write_llm_fields(pg_url) -> tuple[str, str]:
    """Simula lo que escribirá un flujo de insights (criterio 19) en una fila `pendiente` y en otra `completo`."""
    with psycopg.connect(pg_url) as conn:
        pending, done = [r[0] for r in conn.execute(
            "SELECT conversation_id FROM analysis ORDER BY conversation_id LIMIT 2").fetchall()]
        conn.execute("UPDATE analysis SET summary = 'Resumen del LLM', main_topic = 'bloqueo_tarjeta', source = 'llm' "
                     "WHERE conversation_id = %s", (pending,))
        conn.execute("UPDATE analysis SET status = 'completo', source = 'llm', summary = 'Completo', "
                     "main_topic = 'comisiones' WHERE conversation_id = %s", (done,))
    return pending, done


def _analysis(pg_url, conversation_id) -> tuple:
    with psycopg.connect(pg_url) as conn:
        return conn.execute("SELECT status, source, summary, main_topic FROM analysis WHERE conversation_id = %s",
                            (conversation_id,)).fetchone()


def _conversation_ids(pg_url) -> list[str]:
    with psycopg.connect(pg_url) as conn:
        return [r[0] for r in conn.execute("SELECT id FROM conversation ORDER BY genesys_id").fetchall()]


def test_the_flow_stores_overwrite_and_defaults_to_false(pg_url):
    app = create_app(Settings(database_url=pg_url, token=TOKEN), scheduler=False)
    with TestClient(app) as api:
        api.headers["Authorization"] = f"Bearer {TOKEN}"
        created = api.post("/download-flows", json=FLOW)
        assert created.status_code == 201, created.text
        flow = created.json()
        assert flow["overwrite"] is False
        updated = api.put(f"/download-flows/{flow['id']}", json={**FLOW, "overwrite": True}).json()
        assert updated["overwrite"] is True
        assert api.get(f"/download-flows/{flow['id']}").json()["overwrite"] is True
        assert api.post("/download-flows", json={**FLOW, "overwrite": "quizá"}).status_code == 422


def test_without_overwrite_existing_conversations_are_not_downloaded_nor_touched(pg_url):
    flow_id = create_flow(pg_url)
    _run(pg_url, make_fake(), flow_id)
    pending, done = _write_llm_fields(pg_url)
    before = table_counts(pg_url)

    fake = make_fake()
    run = _run(pg_url, fake, flow_id)
    counters = run["counters"]
    assert _downloads(fake) == []
    assert (counters["inserted"], counters["updated"], counters["skipped_existing"], counters["downloaded"]) == (0, 0, 10, 0)
    assert table_counts(pg_url) == before
    assert _analysis(pg_url, pending) == ("pendiente", "llm", "Resumen del LLM", "bloqueo_tarjeta")
    assert _analysis(pg_url, done) == ("completo", "llm", "Completo", "comisiones")
    existing = [e for e in list_log(pg_url, run["id"]) if e["message"] == "Already exists: not downloaded"]
    assert len(existing) == 10 and all(e["level"] == "info" for e in existing)
    assert run["status"] == "completada"  # omitir una conversación que ya existe no es un aviso


def test_with_overwrite_conversations_are_replaced_and_llm_fields_erased(pg_url):
    flow_id = create_flow(pg_url, overwrite=True)
    _run(pg_url, make_fake(), flow_id)
    ids_before = _conversation_ids(pg_url)
    pending, done = _write_llm_fields(pg_url)

    fake = make_fake()
    run = _run(pg_url, fake, flow_id)
    assert _downloads(fake)
    assert (run["counters"]["inserted"], run["counters"]["updated"], run["counters"]["skipped_existing"]) == (0, 10, 0)
    assert _conversation_ids(pg_url) == ids_before
    assert _analysis(pg_url, pending) == ("pendiente", "genesys", None, None)
    assert _analysis(pg_url, done) == ("pendiente", "genesys", None, None)


def test_the_run_keeps_the_overwrite_value_it_started_with(pg_url):
    flow_id = create_flow(pg_url)
    _run(pg_url, make_fake(), flow_id)
    run_id = create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, CHANNELS)
    with psycopg.connect(pg_url) as conn:  # editar el flujo con la ejecución ya creada no la cambia
        conn.execute("UPDATE download_flow SET overwrite = true WHERE id = %s", (flow_id,))
    RunExecutor(pg_url, client_factory(make_fake())).execute(run_id)
    assert get_run(pg_url, run_id)["counters"]["skipped_existing"] == 10


@pytest.mark.parametrize("overwrite", [False, True])
def test_counters_add_up_to_the_conversations_to_download(pg_url, overwrite):
    flow_id = create_flow(pg_url, overwrite=overwrite)
    _run(pg_url, make_fake([fixture("37dcbccf"), fixture("7b94988a")]), flow_id)
    fake = make_fake()
    fake.fail("GET", f"{DOWNLOAD_PATHS}{fixture('8d29170a').id}", *[503] * 4)
    counters = _run(pg_url, fake, flow_id)["counters"]
    to_download = counters["found"] - counters["skipped"]
    assert to_download == counters["inserted"] + counters["updated"] + counters["skipped_existing"] + counters["errors"]
    assert counters["inserted"] == 7 and counters["errors"] == 1
    assert (counters["updated"], counters["skipped_existing"]) == ((2, 0) if overwrite else (0, 2))


def test_load_without_overwrite_never_updates_an_existing_conversation(pg_url):
    create_flow(pg_url)  # aplica las migraciones
    normalized = normalize(fixture("37dcbccf"), GenesysNames(client_factory(make_fake())()))
    with psycopg.connect(pg_url) as conn:
        assert load(conn, normalized, PendingAnalyzer().analyze(normalized), overwrite=False) == INSERTED
        conn.execute("UPDATE analysis SET summary = 'Resumen del LLM'")
        assert load(conn, normalized, PendingAnalyzer().analyze(normalized), overwrite=False) == OMITTED
        assert conn.execute("SELECT summary FROM analysis").fetchone()[0] == "Resumen del LLM"
        assert load(conn, normalized, PendingAnalyzer().analyze(normalized), overwrite=True) == UPDATED
        assert conn.execute("SELECT summary FROM analysis").fetchone()[0] is None


def test_the_overwrite_column_defaults_to_false_for_existing_flows(pg_url):
    flow_id = create_flow(pg_url)
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT overwrite FROM download_flow WHERE id = %s", (flow_id,)).fetchone()[0] is False



def test_runs_from_before_overwrite_existed_have_an_unknown_mode(pg_url):
    # Hallazgo de /test: la migración 0003 dejaba `overwrite = false` en las ejecuciones antiguas, que sin embargo
    # actualizaban las conversaciones existentes; el historial decía «omite» junto a «13 actualizadas».
    from ingestion import db
    flow_id = create_flow(pg_url)
    with psycopg.connect(pg_url) as conn:
        applied = conn.execute("SELECT applied_at FROM schema_migrations WHERE version = '0003_overwrite'").fetchone()[0]
        conn.execute("INSERT INTO download_run (id, flow_id, origin, status, interval_from, interval_to, channels, "
                     "counters, created_at) VALUES ('1RN-00000000-0000-4000-8000-0000000000AA', %s, 'manual', "
                     "'completada', %s, %s, '{voz}', '{}', %s - interval '1 day')",
                     (flow_id, DAY_START, DAY_END, applied))
        conn.execute("DELETE FROM schema_migrations WHERE version = '0005_run_overwrite_unknown'")  # reaplica la corrección
        db.migrate(conn)
    old = get_run(pg_url, "1RN-00000000-0000-4000-8000-0000000000AA")
    assert old["overwrite"] is None and old["counters"]["skipped_existing"] == 0
    new = _run(pg_url, make_fake([fixture("37dcbccf")]), flow_id)
    assert new["overwrite"] is False
