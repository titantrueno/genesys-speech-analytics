"""Escritura de summary y main topic en PostgreSQL (FE013, T6; criterios 19, 20, 21 y 28).

El servicio de ingesta es el único que escribe en la base; la API lo llama con su token interno.
"""
import psycopg
import pytest
from fastapi.testclient import TestClient

from app.flows.analysis_writer import IngestionAnalysisWriter, get_analysis_writer
from app.ingestion_client import IngestionClient, get_ingestion_client
from app.main import app as api_app
from ingestion.main import create_app
from ingestion.runs import RunExecutor, create_run
from ingestion.settings import Settings
from tests.flow_fixtures import SAMPLING
from tests.ingestion_helpers import DAY_END, DAY_START, client_factory, create_flow, make_fake
from tests.real_helpers import QS, real_api, seed_real  # noqa: F401  (fixture)
from tests.test_flow_fields import BOTH_OUTPUT, BOTH_PROMPT, _flow
from tests.test_flow_runs import flow_with, run
from tests.test_llm_flows import _finished, llm  # noqa: F401  (fixture)

pytestmark = pytest.mark.pg
TOKEN = "token-interno-de-prueba"
RUN_ID = "1RN-00000000-0000-4000-8000-000000000001"


@pytest.fixture
def service(pg_url):
    seed_real(pg_url)
    app = create_app(Settings(database_url=pg_url, token=TOKEN), scheduler=False)
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield client


def _ids(pg_url, n=2) -> list[str]:
    with psycopg.connect(pg_url) as conn:
        return [r[0] for r in conn.execute("SELECT conversation_id FROM analysis ORDER BY conversation_id LIMIT %s",
                                           (n,)).fetchall()]


def _row(pg_url, cid) -> tuple:
    with psycopg.connect(pg_url) as conn:
        return conn.execute("SELECT status, summary, main_topic, llm_meta FROM analysis WHERE conversation_id = %s",
                            (cid,)).fetchone()


def _write(service, items, overwrite=False):
    response = service.post("/analysis/fields", json={"run_id": RUN_ID, "provider": "gemini",
                                                      "model": "gemini-3.5-flash-lite", "overwrite": overwrite,
                                                      "items": items})
    assert response.status_code == 200, response.text
    return {r["conversation_id"]: r["outcomes"] for r in response.json()["results"]}


def test_an_empty_field_is_written_with_its_trace(service, pg_url):
    cid = _ids(pg_url, 1)[0]
    outcomes = _write(service, [{"conversation_id": cid, "values": {"summary": "Resumen.", "main_topic": "cajeros"}}])
    assert outcomes == {cid: {"summary": "escrito", "main_topic": "escrito"}}
    status, summary, main_topic, meta = _row(pg_url, cid)
    assert (status, summary, main_topic) == ("pendiente", "Resumen.", "cajeros")
    assert set(meta) == {"summary", "main_topic"}
    assert {k: v for k, v in meta["summary"].items() if k != "at"} == {
        "provider": "gemini", "model": "gemini-3.5-flash-lite", "run_id": RUN_ID}
    assert meta["summary"]["at"]


def test_an_existing_value_is_kept_without_overwrite_and_replaced_with_it(service, pg_url):
    cid = _ids(pg_url, 1)[0]
    _write(service, [{"conversation_id": cid, "values": {"summary": "Primero."}}])
    kept = _write(service, [{"conversation_id": cid, "values": {"summary": "Segundo.", "main_topic": "cajeros"}}])
    assert kept == {cid: {"summary": "omitido", "main_topic": "escrito"}}
    assert _row(pg_url, cid)[1] == "Primero."
    replaced = _write(service, [{"conversation_id": cid, "values": {"summary": "Tercero."}}], overwrite=True)
    assert replaced == {cid: {"summary": "escrito"}}
    assert _row(pg_url, cid)[1] == "Tercero."


def test_a_complete_analysis_keeps_its_status(service, pg_url):
    cid = _ids(pg_url, 1)[0]
    with psycopg.connect(pg_url) as conn:
        conn.execute("UPDATE analysis SET status = 'completo' WHERE conversation_id = %s", (cid,))
    _write(service, [{"conversation_id": cid, "values": {"summary": "Resumen."}}])
    assert _row(pg_url, cid)[:2] == ("completo", "Resumen.")


def test_unknown_conversations_and_fields_are_handled(service, pg_url):
    outcomes = _write(service, [{"conversation_id": "1CO-00000000-0000-4000-8000-000000000000",
                                 "values": {"summary": "x"}}])
    assert outcomes == {"1CO-00000000-0000-4000-8000-000000000000": {"summary": "no_encontrada"}}
    bad = service.post("/analysis/fields", json={"run_id": RUN_ID, "provider": "gemini", "model": "m",
                                                 "overwrite": False,
                                                 "items": [{"conversation_id": _ids(pg_url, 1)[0],
                                                            "values": {"status": "completo"}}]})
    assert bad.status_code == 422  # solo los campos destino de la lista blanca
    assert service.post("/analysis/fields", json={}, headers={"Authorization": "Bearer otro"}).status_code == 401


def test_redownloading_with_overwrite_erases_what_the_llm_wrote(service, pg_url):
    cid = _ids(pg_url, 1)[0]
    _write(service, [{"conversation_id": cid, "values": {"summary": "Resumen.", "main_topic": "cajeros"}}])
    flow_id = create_flow(pg_url, overwrite=True)
    run_id = create_run(pg_url, flow_id, "manual", DAY_START, DAY_END, ["voz", "chat"])
    RunExecutor(pg_url, client_factory(make_fake())).execute(run_id)
    assert _row(pg_url, cid) == ("pendiente", None, None, {})


@pytest.fixture
def wired(real_api, pg_url):
    """API con origen `real` → servicio de ingesta real → PostgreSQL."""
    service_app = create_app(Settings(database_url=pg_url, token=TOKEN), scheduler=False)
    with TestClient(service_app) as service_client:
        client = IngestionClient("http://testserver", TOKEN, http=service_client)
        api_app.dependency_overrides[get_ingestion_client] = lambda: client
        api_app.dependency_overrides[get_analysis_writer] = lambda: IngestionAnalysisWriter(client)
        yield real_api
    api_app.dependency_overrides.pop(get_ingestion_client, None)
    api_app.dependency_overrides.pop(get_analysis_writer, None)


def test_a_one_call_flow_writes_both_fields_visible_in_the_next_request(wired, llm, pg_url):
    api = wired
    llm.answer = lambda body: '{"summary": "El cliente consulta un cargo.", "main_topic": "Comisiones"}'
    query = {"from": QS["from"], "to": QS["to"], "root": {"op": "and", "conditions": []}}
    payload = _flow(BOTH_PROMPT, BOTH_OUTPUT)
    payload["nodes"][0]["config"] = {**SAMPLING, "query": query, "size": 4}  # el día de las fixtures de Genesys
    flow = flow_with(api, payload)
    snapshot = _finished(api, flow, run(api, flow)["id"])
    assert snapshot["status"] == "ok", snapshot["nodes"]
    rows = next(iter(snapshot["outputs"].values()))["result"]["rows"]
    assert len(rows) == 4
    # Una conversación sin transcripción no se envía al LLM: queda rechazada y sin escribir (hallazgo de T9).
    empty = [r for r in rows if r["states"]["summary"] == "rechazado"]
    assert all("no tiene transcripción" in r["reason"] for r in empty)
    written = [r["conversation"]["id"] for r in rows if r["states"]["summary"] == "escrito"]
    assert len(llm.requests) == len(written) == 4 - len(empty) > 0
    listed = api.get("/api/conversations", params={**QS, "main_topic": "comisiones", "page_size": 100}).json()
    assert {item["id"] for item in listed["items"]} == set(written)
    detail = api.get(f"/api/conversations/{written[0]}").json()
    assert detail["analysis"]["summary"] == "El cliente consulta un cargo."
    assert detail["analysis"]["main_topic"] == "comisiones"
    assert detail["analysis"]["pending"] is True  # el resto del análisis sigue pendiente
