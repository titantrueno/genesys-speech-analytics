"""Contrato y rendimiento del origen `real` (FE012, T8; criterios 10, 14 y el flujo de insights del 15)."""
import copy
import time
from datetime import timedelta

import psycopg
import pytest

from app.data.store import get_dataset
from app.query.fields import get_fields
from app.routers.search import search_index
from tests.flow_fixtures import PROMPT_LABEL, chained_graph
from tests.ingestion_helpers import DAY_START, fixtures, spread
from tests.real_helpers import QS, real_api, real_id, seed_real  # noqa: F401  (fixture)
from app.services.kpis import KPI_CODES

pytestmark = pytest.mark.pg
THRESHOLD_S = 0.5


def _degrade(pg_url):
    """Datos incompletos a propósito: un contacto sin cliente ni teléfono, sin analítica y con una frase de un turno."""
    with psycopg.connect(pg_url) as conn:
        victim = real_id("7b94988a")
        conn.execute("UPDATE conversation SET customer_id = NULL, ani = NULL, dnis = NULL, external_tag = NULL, "
                     "customer_sentiment = NULL, mos = NULL, metrics = '{}', updated_at = now() WHERE id = %s", (victim,))
        conn.execute("DELETE FROM topic_hit WHERE conversation_id = %s", (victim,))
        conn.execute("DELETE FROM segment WHERE conversation_id = %s AND kind <> 'cliente'", (victim,))
        conn.execute("UPDATE turn SET sentiment = NULL WHERE conversation_id = %s", (victim,))


def _conditions():
    """Una condición por campo y operador del esquema, con un valor válido, para recorrer todo el motor."""
    fields = get_fields()
    for key, field in fields.items():
        for operator in field.operators:
            if operator in ("is_empty", "is_not_empty", "passes", "fails", "not_applicable"):
                value = None
            elif field.type == "categorical":
                first = field.values[0][0] if field.values else "x"
                value = [first] if operator in ("in", "not_in") else first
            elif field.type == "numeric":
                low = field.min or 0
                value = [low, field.max] if operator == "between" else low
            elif field.type == "boolean":
                value = True
            else:
                value = "a"
            yield {"field": key, "operator": operator, "value": value}


def test_no_endpoint_answers_500_with_unanalysed_or_incomplete_conversations(real_api, pg_url):
    _degrade(pg_url)
    calls: list[tuple[str, str, int]] = []

    def check(method, url, **kwargs):
        response = real_api.request(method, url, **kwargs)
        calls.append((method, url, response.status_code))
        assert response.status_code < 500, (method, url, kwargs, response.status_code, response.text[:300])
        return response

    for conv in get_dataset():
        check("GET", f"/api/conversations/{conv.id}")
        check("GET", f"/api/search/similar/{conv.id}")
    for sort in ("date", "duration", "sentiment"):
        for order in ("asc", "desc"):
            check("GET", "/api/conversations", params={**QS, "sort": sort, "order": order})
    check("GET", "/api/conversations", params={**QS, "sentiment_lt": 0, "compliant": True, "repeat_contact": False})
    check("GET", "/api/catalog")
    check("GET", "/api/metrics/summary", params=QS)
    for kpi in KPI_CODES:
        for granularity in ("day", "week"):
            check("GET", "/api/metrics/timeseries", params={**QS, "kpi": kpi, "granularity": granularity})
    for dimension in ("main_topic", "channel", "queue", "agent"):
        check("GET", "/api/metrics/breakdown", params={**QS, "dimension": dimension})
    check("GET", "/api/query/schema")
    for key, field in get_fields().items():
        if field.type == "categorical":
            check("GET", "/api/query/suggest", params={**QS, "field": key})
    for condition in _conditions():
        response = check("POST", "/api/query/run", json={**QS, "root": {"op": "and", "conditions": [condition]}})
        assert response.status_code == 200, (condition, response.text[:300])
    for text in ("conversaciones con tarjeta denegada", "chats de la cola AIT_Transcription sin saludo", "x"):
        check("POST", "/api/query/interpret", json={"text": text})
    for q in ("tarjeta", "Amazon Brasil", "a"):
        check("GET", "/api/search/semantic", params={**QS, "q": q})
    check("POST", "/api/flows/sampling/estimate", json={"query": {**QS, "root": {"op": "and", "conditions": []}}, "size": 5})
    for url in ("/api/config", "/api/config/connectors", "/api/config/taxonomy", "/api/config/compliance-checks",
                "/api/config/audit"):
        check("GET", url)
    assert len(calls) > 150  # recorre de verdad todos los endpoints y cada condición del explorador


def _flow_graph():
    graph = copy.deepcopy(chained_graph())
    for node in graph["nodes"]:
        if node["type"] == "sampling":
            node["config"] = {"query": {**QS, "root": {"op": "and", "conditions": []}}, "method": "aleatorio", "size": 6}
        if node["type"] == "prompt" and node["id"] == "tmp-p1":
            node["config"] = {**PROMPT_LABEL, "template": "Clasifica: {{transcripcion}} {{metadatos}}"}
        if node["type"] == "prompt" and node["id"] == "tmp-p2":
            node["config"] = {**node["config"], "template": "Explica la etiqueta {{resultado_anterior}}: {{metadatos}}"}
    return graph


def test_an_insights_flow_runs_over_real_conversations(real_api):
    flow = real_api.post("/api/flows", json={"name": "Flujo con datos reales"}).json()
    assert real_api.put(f"/api/flows/{flow['id']}/graph", json=_flow_graph()).status_code == 200
    started = real_api.post(f"/api/flows/{flow['id']}/runs")
    assert started.status_code == 202, started.text
    run = real_api.get(f"/api/flows/{flow['id']}/runs/{started.json()['id']}").json()
    assert (run["status"], run["sample_size"]) == ("ok", 6)
    assert {state["status"] for state in run["nodes"].values()} == {"ok"}
    outputs = {out["kind"]: out["result"] for out in run["outputs"].values()}
    assert sum(item["count"] for item in outputs["metrica"]["items"]) == 6
    assert len(outputs["tabla"]["rows"]) == 6
    assert {row["conversation"]["id"] for row in outputs["tabla"]["rows"]} <= {c.id for c in get_dataset()}
    assert "pendiente de análisis" in outputs["informe"]["text"]


def test_endpoints_answer_under_500_ms_with_a_thousand_conversations(real_api, pg_url):
    seed_real(pg_url, spread(fixtures(), 1000, DAY_START - timedelta(days=20), 20), start=DAY_START - timedelta(days=21),
              end=DAY_START + timedelta(days=2))
    real_api.get("/api/conversations", params=QS)  # primera petición: carga la instantánea
    with psycopg.connect(pg_url) as conn:
        assert conn.execute("SELECT count(*) FROM conversation").fetchone()[0] >= 1000
    period = {"from": "2026-09-01", "to": "2026-10-31"}
    requests = [
        ("GET", "/api/conversations", {"params": {**period, "page_size": 25}}),
        ("GET", "/api/conversations", {"params": {**period, "phone": "675075376"}}),
        ("GET", "/api/conversations", {"params": {**period, "sort": "sentiment"}}),
        ("GET", "/api/conversations/" + real_id("7b94988a"), {}),
        ("GET", "/api/metrics/summary", {"params": period}),
        ("GET", "/api/metrics/timeseries", {"params": {**period, "kpi": "volume"}}),
        ("GET", "/api/metrics/breakdown", {"params": {**period, "dimension": "queue"}}),
        ("GET", "/api/query/schema", {}),
        ("POST", "/api/query/run", {"json": {**period, "root": {"op": "and", "conditions": [
            {"field": "gc_derived", "operator": "is", "value": True}]}}}),
        ("POST", "/api/query/run", {"json": {**period, "root": {"op": "and", "conditions": [
            {"field": "transcript", "operator": "contains", "value": "tarjeta"}]}}}),
        ("GET", "/api/search/semantic", {"params": {**period, "q": "Amazon Brasil"}}),
        ("POST", "/api/flows/sampling/estimate", {"json": {"query": {**period, "root": {"op": "and", "conditions": []}}, "size": 50}}),
    ]
    # Una pasada previa calienta los cachés de texto y del índice; se mide la segunda, la de uso normal.
    for method, url, kwargs in requests:
        assert real_api.request(method, url, **kwargs).status_code == 200, (method, url)
    # Mientras se reconstruye el índice en segundo plano compite por el procesador (hasta 2,5 s con 1.000
    # conversaciones, ADR-005): el criterio 14 mide el régimen estable, con el índice ya construido.
    search_index.wait()
    slow = []
    for method, url, kwargs in requests:
        started = time.perf_counter()
        response = real_api.request(method, url, **kwargs)
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        if elapsed >= THRESHOLD_S:
            slow.append((method, url, round(elapsed, 3)))
    assert slow == []
