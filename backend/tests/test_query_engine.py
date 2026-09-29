"""Los resultados esperados se calculan aquí de forma independiente al motor (app/query/engine.py)."""
import time
import unicodedata
from datetime import timedelta

import pytest

from app import auth
from app.data.catalog import AGENT_IDS, QUEUE_IDS
from app.data.store import get_dataset
from tests.dates import day_ago, days_ago, default_period

# El mismo dataset que sirve la API, con fechas relativas a su fecha de referencia (FE009).
DATASET = get_dataset()
PERIOD = {"from": days_ago(88), "to": days_ago(1)}
IN_PERIOD = [c for c in DATASET if day_ago(88) <= c.started_at.date() <= day_ago(1)]
DEFAULT_PERIOD = [c for c in DATASET if default_period()[0] <= c.started_at.date() <= default_period()[1]]
SAMPLE_SENTIMENT = IN_PERIOD[5].analysis.sentiment


def _has_followup(conv):
    limit = conv.started_at + timedelta(days=7)
    return any(o.customer_id == conv.customer_id and conv.started_at < o.started_at <= limit for o in DATASET)


FOLLOWUP = {c.id: _has_followup(c) for c in IN_PERIOD}


def norm(text):
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)).casefold()


def said(conv, fragment, speaker=None):
    return any(norm(fragment) in norm(t.text) for t in conv.turns if speaker is None or t.speaker == speaker)


def cond(field, operator, value=None, **extra):
    return {"field": field, "operator": operator, "value": value, **extra}


def run_all(api, root, period=PERIOD):
    ids, page = [], 1
    while True:
        response = api.post("/api/query/run", params={"page": page, "page_size": 100}, json={**period, "root": root})
        assert response.status_code == 200, response.text
        body = response.json()
        ids += [i["id"] for i in body["items"]]
        if page >= max(body["pages"], 1):
            return body["total"], set(ids)
        page += 1


CASES = [
    ("channel is", cond("channel", "is", "chat"), lambda c: c.channel == "chat"),
    ("channel is_not", cond("channel", "is_not", "chat"), lambda c: c.channel != "chat"),
    ("main_topic in", cond("main_topic", "in", ["cajeros", "comisiones"]), lambda c: c.analysis.main_topic in ("cajeros", "comisiones")),
    ("resolution not_in", cond("resolution", "not_in", ["resuelta"]), lambda c: c.analysis.resolution != "resuelta"),
    ("queue is", cond("queue", "is", QUEUE_IDS["Tarjetas"]), lambda c: c.queue == "Tarjetas"),
    ("agent in", cond("agent", "in", [AGENT_IDS["Irene Vidal"], AGENT_IDS["Sergio Molina"]]),
     lambda c: c.agent in ("Irene Vidal", "Sergio Molina")),
    ("secondary is", cond("secondary_topic", "is", "fraude"), lambda c: "fraude" in c.analysis.secondary_topics),
    ("secondary is_not", cond("secondary_topic", "is_not", "fraude"), lambda c: "fraude" not in c.analysis.secondary_topics),
    ("secondary in", cond("secondary_topic", "in", ["fraude", "app móvil"]),
     lambda c: bool({"fraude", "app móvil"} & set(c.analysis.secondary_topics))),
    ("secondary not_in", cond("secondary_topic", "not_in", ["fraude", "app móvil"]),
     lambda c: not {"fraude", "app móvil"} & set(c.analysis.secondary_topics)),
    ("sentiment eq", cond("sentiment", "eq", SAMPLE_SENTIMENT), lambda c: c.analysis.sentiment == SAMPLE_SENTIMENT),
    ("sentiment ne", cond("sentiment", "ne", SAMPLE_SENTIMENT), lambda c: c.analysis.sentiment != SAMPLE_SENTIMENT),
    ("sentiment gt", cond("sentiment", "gt", 0.2), lambda c: c.analysis.sentiment > 0.2),
    ("sentiment gte", cond("sentiment", "gte", 0.2), lambda c: c.analysis.sentiment >= 0.2),
    ("sentiment lt", cond("sentiment", "lt", -0.3), lambda c: c.analysis.sentiment < -0.3),
    ("sentiment lte", cond("sentiment", "lte", -0.3), lambda c: c.analysis.sentiment <= -0.3),
    ("csat between", cond("csat", "between", [2, 3.5]), lambda c: 2 <= c.analysis.csat <= 3.5),
    ("effort gte", cond("effort", "gte", 4), lambda c: c.analysis.effort >= 4),
    ("duration gt", cond("duration", "gt", 300), lambda c: c.duration_s > 300),
    ("turns lte", cond("turns", "lte", 12), lambda c: len(c.turns) <= 12),
    ("check passes", cond("check:verificacion_identidad", "passes"), lambda c: c.analysis.compliance["verificacion_identidad"] is True),
    ("check fails", cond("check:verificacion_identidad", "fails"), lambda c: c.analysis.compliance["verificacion_identidad"] is False),
    ("check n/a", cond("check:bloqueo_preventivo", "not_applicable"), lambda c: c.analysis.compliance["bloqueo_preventivo"] is None),
    ("summary contains sin tildes", cond("summary", "contains", "COMISION"), lambda c: "comision" in norm(c.analysis.summary)),
    ("summary not_contains", cond("summary", "not_contains", "escala"), lambda c: "escala" not in norm(c.analysis.summary)),
    ("transcript contains cliente", cond("transcript", "contains", "no reconozco", speaker="cliente"),
     lambda c: said(c, "no reconozco", "cliente")),
    ("transcript contains agente", cond("transcript", "contains", "PIN", speaker="agente"), lambda c: said(c, "pin", "agente")),
    ("transcript contains cualquiera", cond("transcript", "contains", "bizum"), lambda c: said(c, "bizum")),
    ("transcript not_contains", cond("transcript", "not_contains", "gracias", speaker="cliente"),
     lambda c: not said(c, "gracias", "cliente")),
    ("repeat_contact true", cond("repeat_contact", "is", True), lambda c: FOLLOWUP[c.id]),
    ("repeat_contact false", cond("repeat_contact", "is", False), lambda c: not FOLLOWUP[c.id]),
]


@pytest.mark.parametrize("name,condition,predicate", CASES, ids=[c[0] for c in CASES])
def test_each_operator_matches_independent_filter(api, name, condition, predicate):
    expected = {c.id for c in IN_PERIOD if predicate(c)}
    assert expected, f"caso sin resultados, no prueba nada: {name}"
    assert expected != {c.id for c in IN_PERIOD}, f"caso que no filtra, no prueba nada: {name}"
    total, got = run_all(api, {"op": "and", "conditions": [condition]})
    assert total == len(expected)
    assert got == expected


def test_nested_and_or_groups(api):
    root = {"op": "and", "conditions": [
        cond("channel", "is", "voz"),
        {"op": "or", "conditions": [cond("sentiment", "lt", -0.3), cond("resolution", "is", "escalada")]},
        {"op": "or", "conditions": [cond("main_topic", "is", "cargo_no_reconocido"), cond("check:despedida", "fails")]},
    ]}
    expected = {c.id for c in IN_PERIOD if c.channel == "voz"
                and (c.analysis.sentiment < -0.3 or c.analysis.resolution == "escalada")
                and (c.analysis.main_topic == "cargo_no_reconocido" or c.analysis.compliance["despedida"] is False)}
    assert run_all(api, root)[1] == expected
    or_root = {"op": "or", "conditions": [cond("channel", "is", "chat"), cond("duration", "gt", 400)]}
    assert run_all(api, or_root)[1] == {c.id for c in IN_PERIOD if c.channel == "chat" or c.duration_s > 400}


def test_empty_query_returns_the_whole_default_period(api):
    response = api.post("/api/query/run", json={"root": {"op": "and", "conditions": []}})
    body = response.json()
    assert body["period"] == {"from": default_period()[0].isoformat(), "to": default_period()[1].isoformat()}
    assert body["total"] == len(DEFAULT_PERIOD)


def test_query_equivalent_to_listing_filters_gives_the_same_total_and_kpis(api):
    listing = {"from": days_ago(74), "to": days_ago(7), "channel": "voz", "queue": QUEUE_IDS["Particulares"],
               "main_topic": ["comisiones", "cajeros"], "resolution": "escalada"}
    root = {"op": "and", "conditions": [
        cond("channel", "is", "voz"), cond("queue", "is", QUEUE_IDS["Particulares"]),
        cond("main_topic", "in", ["comisiones", "cajeros"]), cond("resolution", "is", "escalada"),
    ]}
    body = api.post("/api/query/run", json={"from": days_ago(74), "to": days_ago(7), "root": root}).json()
    assert body["total"] == api.get("/api/conversations", params=listing).json()["total"]

    summary_params = {k: v for k, v in listing.items() if k != "resolution"}
    root_no_resolution = {"op": "and", "conditions": root["conditions"][:3]}
    run = api.post("/api/query/run", json={"from": days_ago(74), "to": days_ago(7), "root": root_no_resolution}).json()
    summary = api.get("/api/metrics/summary", params=summary_params).json()
    assert {k["code"]: k["value"] for k in run["kpis"]} == {k["code"]: k["value"] for k in summary["kpis"]}
    assert all(k["label"] and k["unit"] for k in run["kpis"])


def test_items_pagination_and_sorting_match_the_listing(api):
    root = {"op": "and", "conditions": [cond("main_topic", "is", "comisiones")]}
    body = api.post("/api/query/run", params={"sort": "duration", "order": "asc", "page": 2, "page_size": 10},
                    json={**PERIOD, "root": root}).json()
    listing = api.get("/api/conversations", params={**PERIOD, "main_topic": "comisiones", "sort": "duration",
                                                    "order": "asc", "page": 2, "page_size": 10}).json()
    assert body["items"] == listing["items"]
    assert (body["page"], body["page_size"], body["pages"]) == (listing["page"], listing["page_size"], listing["pages"])


def test_invalid_query_returns_422_with_every_error_path(api):
    root = {"op": "and", "conditions": [cond("color", "is", "rojo"), cond("csat", "lt", 9)]}
    response = api.post("/api/query/run", json={"root": root})
    assert response.status_code == 422
    assert {e["path"] for e in response.json()["detail"]} == {"root.conditions[0]", "root.conditions[1]"}


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 500}, {"sort": "color"}, {"order": "up"}])
def test_invalid_pagination_returns_422(api, params):
    assert api.post("/api/query/run", params=params, json={"root": {"op": "and", "conditions": []}}).status_code == 422


def test_run_requires_explorer_permission(api):
    viewer = auth.get_store().find_by_email("viewer@bancohorizonte.demo")
    response = api.post("/api/query/run", json={"root": {"op": "and", "conditions": []}},
                        headers={"Authorization": f"Bearer {auth.create_token(viewer)}"})
    assert response.status_code == 403


def test_run_with_ten_conditions_responds_under_500ms(api):
    root = {"op": "and", "conditions": [
        cond("channel", "in", ["voz", "chat"]),
        cond("sentiment", "between", [-1, 1]),
        cond("csat", "gte", 1),
        cond("effort", "lte", 5),
        cond("duration", "gt", 0),
        cond("turns", "gte", 1),
        cond("summary", "not_contains", "zzzz"),
        cond("transcript", "not_contains", "zzzz", speaker="cliente"),
        {"op": "or", "conditions": [cond("check:saludo", "passes"), cond("check:saludo", "fails")]},
        cond("resolution", "in", ["resuelta", "no_resuelta", "escalada"]),
    ]}
    payload = {"from": days_ago(90), "to": days_ago(1), "root": root}
    api.post("/api/query/run", json=payload)
    start = time.perf_counter()
    assert api.post("/api/query/run", json=payload).status_code == 200
    assert time.perf_counter() - start < 0.5
