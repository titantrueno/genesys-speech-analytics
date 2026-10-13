"""Ejecución end-to-end con el servicio de ingesta real, PostgreSQL y el Genesys falso (FE017, T4; criterios 4, 6 y 7).

Un flujo «Genesys download → Sampling (All conversations) → Prompt → Guardar en campos» descarga las conversaciones del
día, pasa al Sampling solo las nuevas y escribe el summary únicamente en ellas.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config.store import get_config
from app.flows import runs as flow_runs
from app.flows.analysis_writer import IngestionAnalysisWriter, get_analysis_writer
from app.ingestion_client import IngestionClient, get_ingestion_client
from app.main import app as api_app
from ingestion.main import create_app
from ingestion.settings import Settings
from tests.flow_fixtures import edge, graph, node
from tests.ingestion_helpers import DAY_END, DAY_START, SECRET, client_factory, fixture, fixtures, make_fake
from tests.real_helpers import seed_real
from tests.test_flow_runs import detail, flow_with, run

pytestmark = pytest.mark.pg
TOKEN = "token-interno-de-prueba"
ALREADY_STORED = ["37dcbccf", "8d29170a"]
PROMPT = {"template": "Resume la conversación: {{transcripcion}}", "provider": "simulado", "model": "mock-rapido",
          "temperature": 0.2, "output": {"type": "texto"}}
OUTPUT = {"kind": "campo", "mappings": [{"target": "summary"}]}


def _local(value: datetime) -> str:
    return value.astimezone(ZoneInfo(get_config().general.timezone)).replace(tzinfo=None).isoformat()


@pytest.fixture
def wired(api, pg_url, monkeypatch):
    """API con origen `real` → servicio de ingesta real (descargas síncronas) → PostgreSQL."""
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setattr(flow_runs, "DOWNLOAD_POLL_S", 0)
    seed_real(pg_url, [fixture(short) for short in ALREADY_STORED])
    assert api.put("/api/config/sources", json={"origin": "real"}).status_code == 200
    fake = make_fake()
    service_app = create_app(Settings(database_url=pg_url, token=TOKEN), scheduler=False,
                             client_factory=client_factory(fake), run_in_background=lambda job: job())
    with TestClient(service_app) as service:
        client = IngestionClient("http://testserver", TOKEN, http=service)
        api_app.dependency_overrides[get_ingestion_client] = lambda: client
        api_app.dependency_overrides[get_analysis_writer] = lambda: IngestionAnalysisWriter(client)
        yield api, service, fake
    api_app.dependency_overrides.pop(get_ingestion_client, None)
    api_app.dependency_overrides.pop(get_analysis_writer, None)


def _persist(service, flow: dict) -> None:
    """Con la persistencia de FE015, el flujo ya estaría en `insight_flow`; en los tests la API lo guarda en memoria."""
    body = {"id": flow["id"], "name": flow["name"], "author": {"id": "1US-PRUEBA", "name": "Admin"},
            "graph": flow["graph"], "created_at": flow["created_at"], "updated_at": flow["updated_at"]}
    headers = {"Authorization": f"Bearer {TOKEN}"}
    assert service.put(f"/insight-flows/{flow['id']}", json=body, headers=headers).status_code == 200


def _summaries(pg_url) -> dict[str, str | None]:
    with psycopg.connect(pg_url) as conn:
        return dict(conn.execute("SELECT conversation_id, summary FROM analysis").fetchall())


def test_the_flow_downloads_and_writes_only_in_the_new_conversations(wired, pg_url):
    api, service, fake = wired
    before = set(_summaries(pg_url))
    interval = {"type": "especifico", "from": _local(DAY_START), "to": _local(DAY_END)}
    flow = flow_with(api, graph(
        [node("tmp-d", "descarga", {"interval": interval, "channels": ["voz", "chat"]}),
         node("tmp-s", "sampling", {"size": "all"}, x=300), node("tmp-p", "prompt", PROMPT, x=600),
         node("tmp-o", "output", OUTPUT, x=900)],
        [edge("tmp-d", "tmp-s"), edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")]))
    _persist(service, flow)

    final = detail(api, flow, run(api, flow)["id"])

    assert final["status"] == "ok", final
    after = _summaries(pg_url)
    new = set(after) - before
    assert len(new) == len(fixtures()) - len(ALREADY_STORED)
    assert final["download"]["counters"]["inserted"] == len(new)
    assert final["sample_size"] == len(new)
    rows = next(iter(final["outputs"].values()))["result"]["rows"]
    assert {r["conversation"]["id"] for r in rows} == new
    assert {cid for cid, summary in after.items() if summary} == new
    base = f"/api/flows/{flow['id']}/runs/{final['id']}/download"
    log = api.get(f"{base}/log").json()["items"]
    assert any(e["stage"] == "load" for e in log)
    # Ni el secreto de Genesys ni sus tokens llegan a la ejecución, a su descarga ni a su log (criterio 19).
    outputs = [api.get(f"/api/flows/{flow['id']}/runs/{final['id']}").text, api.get(base).text,
               api.get(f"{base}/log", params={"format": "text"}).text]
    for secret in [SECRET, *fake.issued_tokens]:
        assert all(secret not in output for output in outputs)

    # Repetida sin «Sobrescribir», la descarga no trae nada nuevo: el resto queda omitido y no se escribe nada.
    again = detail(api, flow, run(api, flow)["id"])
    assert again["status"] == "ok"
    assert {again["nodes"][n["id"]]["status"] for n in flow["graph"]["nodes"] if n["type"] != "descarga"} == {"omitido"}
    assert _summaries(pg_url) == after
