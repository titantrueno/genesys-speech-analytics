"""Carga, ejecutor, log y lectura interna del servicio de ingesta (FE011, T4; criterios 2, 6, 10, 11, 17, 18 y 25)."""
import copy
import threading
import time
from datetime import timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

from ingestion.main import create_app
from ingestion.pipeline.analyze import Analysis
from ingestion.runs import RunExecutor, create_run, get_run, list_log
from ingestion.settings import Settings
from tests.ingestion_helpers import (DAY_END, DAY_START, SECRET, client_factory, create_flow, fixture, fixtures,
                                     in_progress, make_fake, spread, table_counts, with_media)

pytestmark = pytest.mark.pg
CHANNELS = ["voz", "chat"]
TOKEN = "token-interno-de-prueba"


def _run(pg_url, fake, flow_id=None, analyzer=None, on_step=None, start=DAY_START, end=DAY_END, channels=CHANNELS,
         secret=SECRET):
    flow_id = flow_id or create_flow(pg_url)
    run_id = create_run(pg_url, flow_id, "manual", start, end, channels, ("1US-PRUEBA", "Admin de prueba"))
    kwargs = {"analyzer": analyzer} if analyzer else {}
    RunExecutor(pg_url, client_factory(fake, secret), on_step=on_step, **kwargs).execute(run_id)
    return get_run(pg_url, run_id), flow_id


def _api(pg_url) -> TestClient:
    client = TestClient(create_app(Settings(database_url=pg_url, token=TOKEN)))
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    return client


def test_a_run_loads_every_conversation_of_the_day(pg_url):
    run, _ = _run(pg_url, make_fake())
    counters = run["counters"]
    assert run["status"] == "completada_con_avisos"  # hay transcripciones parciales y mensajes no entregados
    assert (counters["found"], counters["downloaded"], counters["inserted"], counters["updated"]) == (10, 10, 10, 0)
    assert counters["by_channel"] == {"voz": 4, "chat": 6}
    assert counters["by_quality"] == {"completa": 8, "parcial": 1, "sin_transcripcion": 1}
    assert counters["undelivered_messages"] == 2
    assert table_counts(pg_url)["conversation"] == 10


def test_the_internal_read_returns_the_normalized_conversation(pg_url):
    _run(pg_url, make_fake())
    with _api(pg_url) as api:
        body = api.get("/conversations/37dcbccf-2d89-424e-bc9e-9e53d8494a9a").json()
        assert api.get(f"/conversations/{body['id']}").json() == body  # también por su 1CO
        assert api.get("/conversations/no-existe").status_code == 404
        assert api.get("/conversations/no-existe", headers={"Authorization": "Bearer otro"}).status_code == 401
    speakers = [t["speaker"] for t in body["turns"]]
    assert (len(speakers), speakers.count("bot"), speakers.count("cliente")) == (12, 9, 3)
    assert (body["ani"], body["dnis"], body["external_tag"]) == ("+34675075376", "+34919187266", "Javier Del Olmo")
    assert body["contained_in_bot"] and body["disconnect_type"] == "endpoint"
    assert body["transcript_quality"] == "completa"
    assert [s["kind"] for s in body["segments"]] == ["cliente", "ivr"]
    assert body["segments"][1]["flow"] == {"id": "b0936348-3f34-4701-a439-39a74f728e8a", "name": "Sierra VoiceAgent",
                                           "type": "INBOUNDCALL"}
    assert [t["name"] for t in body["topics"]] == ["Conexión", "Conexión", "Saludos", "Realización de pagos"]
    assert body["analysis"] == {"status": "pendiente", "source": "genesys", "summary": None, "main_topic": None,
                                "secondary_topics": None, "resolution": None, "csat": None, "effort": None,
                                "churn_risk": None, "sentiment": None, "compliance": None, "entities": None,
                                "keywords": None}
    assert body["metrics"]["ivr_s"] == pytest.approx(86.546)


def test_the_read_resolves_queue_agent_and_wrapup_names(pg_url):
    _run(pg_url, make_fake())
    with _api(pg_url) as api:
        body = api.get("/conversations/7b94988a-807b-4a59-8767-ed445ba9f12b").json()
        chat = api.get("/conversations/9e3ec75a-11c8-4df7-9002-339916be2827").json()
    queue, agent = body["segments"][2], body["segments"][3]
    assert queue["queue"]["name"] == "AIT_Transcription"
    assert agent["agent"]["name"] == "Javier Del Olmo" and agent["wrapup"]["name"] == "Default Wrap-up Code"
    assert {t["agent"]["name"] for t in body["turns"] if t["speaker"] == "agente"} == {"Javier Del Olmo"}
    failed = [t for t in chat["turns"] if not t["delivered"]]
    assert [t["text"] for t in failed] == ["lo estoy revisando, un segundo"]


def test_repeating_a_run_duplicates_nothing(pg_url):
    fake = make_fake()
    _, flow_id = _run(pg_url, fake, flow_id=create_flow(pg_url, overwrite=True))
    before = table_counts(pg_url)
    run, _ = _run(pg_url, fake, flow_id=flow_id)
    assert table_counts(pg_url) == before
    assert (run["counters"]["inserted"], run["counters"]["updated"]) == (0, 10)


def test_a_conversation_that_keeps_failing_does_not_stop_the_run(pg_url):
    fake = make_fake()
    failing = fixture("8d29170a").id
    fake.fail("GET", f"/api/v2/speechandtextanalytics/conversations/{failing}", *[503] * 4)
    run, _ = _run(pg_url, fake)
    assert run["status"] == "completada_con_avisos"
    assert (run["counters"]["errors"], run["counters"]["inserted"]) == (1, 9)
    errors = [e for e in list_log(pg_url, run["id"]) if e["level"] == "error"]
    assert [e["genesys_id"] for e in errors] == [failing]


def test_counters_add_up_with_skipped_conversations(pg_url):
    running = in_progress(spread([fixture("7b94988a")], 1, DAY_START + timedelta(hours=3), days=1)[0])
    email = with_media(spread([fixture("687f2225")], 1, DAY_START + timedelta(hours=4), days=1)[0], "email")
    fake = make_fake(fixtures() + [running, email])
    fake.fail("GET", f"/api/v2/speechandtextanalytics/conversations/{fixture('8d29170a').id}", *[503] * 4)
    counters = _run(pg_url, fake, channels=["voz"])[0]["counters"]
    assert counters["found"] == counters["inserted"] + counters["updated"] + counters["skipped"] + counters["errors"]
    assert (counters["skipped_in_progress"], counters["skipped_other_channel"]) == (1, 7)  # 6 chats y el email
    assert counters["errors"] == 0  # el chat que falla ni se descarga: no es del canal pedido


def test_a_partial_transcript_becomes_complete_on_a_later_run(pg_url):
    partial = fixture("7b94988a")
    complete = copy.deepcopy(partial)
    for document in partial.transcripts.values():
        for transcript in document["transcripts"]:
            if any(p.get("userIds") for p in transcript["phrases"]):
                transcript["phrases"] = []  # el tramo del agente aún sin transcribir
    # Para que llegue la transcripción completa hay que volver a descargarla con «Sobrescribir» (FE013).
    _, flow_id = _run(pg_url, make_fake([partial]), flow_id=create_flow(pg_url, overwrite=True))
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT transcript_quality FROM conversation").fetchone()[0] == "parcial"
    run, _ = _run(pg_url, make_fake([complete]), flow_id=flow_id)
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT transcript_quality FROM conversation").fetchone()[0] == "completa"
        assert conn.execute("SELECT count(*) FROM turn").fetchone()[0] == 40
    assert run["counters"]["updated"] == 1


def test_the_log_covers_every_stage_without_turn_text_or_secrets(pg_url):
    fake = make_fake()
    run, _ = _run(pg_url, fake)
    log = list_log(pg_url, run["id"])
    assert {"authentication", "search", "download", "normalization", "analysis", "load"} <= {e["stage"] for e in log}
    warned = {e["genesys_id"] for e in log if e["level"] == "aviso"}
    assert {fixture("687f2225").id, fixture("87a83caa").id, fixture("9e3ec75a").id} <= warned
    text = "\n".join(e["message"] for e in log)
    with psycopg.connect(pg_url) as conn:
        turn_texts = [row[0] for row in conn.execute("SELECT text FROM turn WHERE length(text) > 15")]
    assert turn_texts and not any(t in text for t in turn_texts)
    for secret in [SECRET, *fake.issued_tokens]:
        assert secret not in text
    assert [e["id"] for e in list_log(pg_url, run["id"], after=log[2]["id"])] == [e["id"] for e in log[3:]]
    assert {e["level"] for e in list_log(pg_url, run["id"], level="aviso")} == {"aviso"}


def test_wrong_credentials_end_the_run_in_error(pg_url):
    run, _ = _run(pg_url, make_fake(), secret="otro-secreto")
    assert run["status"] == "error" and run["error"] == "Invalid Genesys credentials"
    assert run["counters"]["found"] == 0 and table_counts(pg_url)["conversation"] == 0
    assert "otro-secreto" not in str(list_log(pg_url, run["id"]))


class FillingAnalyzer:
    def analyze(self, conversation):
        return Analysis(status="completo", source="llm", summary=f"Resumen de {conversation.genesys_id[:8]}",
                        main_topic="cargo_no_reconocido")


def test_an_analyzer_fills_the_analysis_without_changing_the_schema(pg_url):
    _, flow_id = _run(pg_url, make_fake([fixture("37dcbccf")]), analyzer=FillingAnalyzer())
    with _api(pg_url) as api:
        analysis = api.get("/conversations/37dcbccf-2d89-424e-bc9e-9e53d8494a9a").json()["analysis"]
    assert (analysis["status"], analysis["source"], analysis["main_topic"]) == ("completo", "llm", "cargo_no_reconocido")
    assert analysis["summary"] == "Resumen de 37dcbccf"
    _run(pg_url, make_fake([fixture("37dcbccf")]), flow_id=flow_id)  # sin «Sobrescribir», ni se descarga
    with _api(pg_url) as api:
        assert api.get("/conversations/37dcbccf-2d89-424e-bc9e-9e53d8494a9a").json()["analysis"]["status"] == "completo"


def test_progress_is_visible_while_the_run_is_going(pg_url):
    flow_id = create_flow(pg_url)
    run_id = create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, CHANNELS, ("1US-PRUEBA", "Admin de prueba"))
    seen = []

    def on_step(stage: str) -> None:
        if stage == "load":
            seen.append(get_run(pg_url, run_id))

    RunExecutor(pg_url, client_factory(make_fake()), on_step=on_step).execute(run_id)
    assert len(seen) == 10 and {r["status"] for r in seen} == {"en_curso"}
    downloaded = [r["counters"]["downloaded"] for r in seen]
    assert downloaded == sorted(downloaded) and downloaded[0] < downloaded[-1]
    assert get_run(pg_url, run_id)["status"] == "completada_con_avisos"


def test_reads_keep_answering_during_a_run(pg_url):
    _, flow_id = _run(pg_url, make_fake([fixture("37dcbccf")]))
    run_id = create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, CHANNELS, ("1US-PRUEBA", "Admin de prueba"))
    inside, release = threading.Event(), threading.Event()

    def on_step(stage: str) -> None:
        if stage == "load" and not inside.is_set():
            inside.set()
            release.wait(10)

    worker = threading.Thread(target=RunExecutor(pg_url, client_factory(make_fake()), on_step=on_step).execute,
                              args=(run_id,))
    worker.start()
    try:
        assert inside.wait(10)
        with _api(pg_url) as api:
            started = time.perf_counter()
            assert api.get("/conversations/37dcbccf-2d89-424e-bc9e-9e53d8494a9a").status_code == 200
            assert time.perf_counter() - started < 1
    finally:
        release.set()
        worker.join(30)
    assert get_run(pg_url, run_id)["status"] == "completada_con_avisos"


def test_a_thousand_conversations_load_in_under_a_minute(pg_url):
    conversations = spread(fixtures(), 1000, DAY_START, days=1)
    started = time.perf_counter()
    run, _ = _run(pg_url, make_fake(conversations))
    elapsed = time.perf_counter() - started
    assert run["counters"]["inserted"] == 1000 and run["counters"]["errors"] == 0
    assert elapsed < 60, f"{elapsed:.1f} s"


def test_the_log_shows_instants_in_the_flow_timezone_without_microseconds(pg_url):
    run, _ = _run(pg_url, make_fake([fixture("37dcbccf")]))
    messages = [e["message"] for e in list_log(pg_url, run["id"]) if e["stage"] in ("start", "search")]
    start = next(m for m in messages if m.startswith("Run"))
    assert "12/10/2026 00:00 – 13/10/2026 00:00 (Europe/Madrid)" in start, start
    assert not any("+00:00" in m or "." in m.split("(")[0][-8:] for m in messages), messages


def test_no_stored_row_contains_the_secret_a_token_or_a_signed_url(pg_url):
    """Criterio 3: tampoco en la base de datos (respuestas originales, turnos, log…)."""
    fake = make_fake()
    run, _ = _run(pg_url, fake)
    with psycopg.connect(pg_url) as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")]
        dump = "\n".join(str(row[0]) for table in tables
                         for row in conn.execute(f"SELECT row_to_json(t)::text FROM {table} t"))
    assert run["counters"]["inserted"] == 10 and len(dump) > 100_000
    for secret in [SECRET, *fake.issued_tokens, fake.bucket_host, "X-Amz-", "firma-"]:
        assert secret not in dump, secret


def test_a_database_error_never_puts_turn_text_in_the_log(pg_url):
    """Un CHECK que falla devuelve la fila entera en el DETAIL de PostgreSQL: el log solo lleva el mensaje principal."""
    broken = fixture("37dcbccf")
    for document in broken.transcripts.values():
        for transcript in (document or {}).get("transcripts", []):
            for entry in (transcript.get("analytics") or {}).get("sentiment", []) or []:
                entry["sentiment"] = 5.0  # fuera del CHECK (-1..1) de turn.sentiment
            if transcript["phrases"]:
                transcript["analytics"]["sentiment"] = [{
                    "participant": "external", "phrase": "hola mira si tengo un movimiento de tarjeta",
                    "startTimeMs": next(p["startTimeMs"] for p in transcript["phrases"]
                                        if p["participantPurpose"] == "external"), "sentiment": 5.0}]
    run, _ = _run(pg_url, make_fake([broken]))
    errors = [e for e in list_log(pg_url, run["id"]) if e["level"] == "error"]
    assert run["counters"]["errors"] == 1 and len(errors) == 1
    assert "check" in errors[0]["message"].lower()
    assert "movimiento" not in errors[0]["message"] and "Failing row" not in errors[0]["message"]


def test_a_run_that_crashes_outside_its_handlers_ends_in_error(pg_url, monkeypatch):
    from ingestion import runs as runs_module

    flow_id = create_flow(pg_url)
    run_id = create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, CHANNELS)
    monkeypatch.setattr(runs_module._Execution, "run", lambda self: (_ for _ in ()).throw(RuntimeError("fallo raro")))
    RunExecutor(pg_url, client_factory(make_fake())).execute(run_id)
    run = get_run(pg_url, run_id)
    assert run["status"] == "error" and "inesperado" in run["error"]
    monkeypatch.undo()
    assert create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, CHANNELS)  # el flujo no queda bloqueado
