from datetime import date

import pytest

from app import auth, ids
from app.data.catalog import AGENT_IDS, COMPLIANCE_CHECKS, MAIN_TOPICS, QUEUE_IDS
from app.query.model import QueryError, parse_query

EXPECTED_FIELDS = {
    "channel": "categorical", "queue": "categorical", "agent": "categorical", "main_topic": "categorical",
    "secondary_topic": "categorical", "resolution": "categorical", "churn_risk": "categorical",
    "sentiment": "numeric", "csat": "numeric", "effort": "numeric", "duration": "numeric", "turns": "numeric",
    "summary": "text", "transcript": "text", "repeat_contact": "boolean",
    **{f"check:{code}": "check" for code in COMPLIANCE_CHECKS},
}
OPERATORS = {
    "categorical": {"is", "is_not", "in", "not_in"},
    "numeric": {"eq", "ne", "gt", "gte", "lt", "lte", "between"},
    "check": {"passes", "fails", "not_applicable"},
    "text": {"contains", "not_contains"},
    "boolean": {"is"},
}


def cond(field, operator, value=None, **extra):
    return {"field": field, "operator": operator, "value": value, **extra}


def query(*conditions, op="and", **dates):
    return {**dates, "root": {"op": op, "conditions": list(conditions)}}


def errors_of(payload):
    with pytest.raises(QueryError) as exc:
        parse_query(payload)
    return exc.value.errors


def test_schema_lists_every_field_with_type_and_valid_operators(api):
    body = api.get("/api/query/schema").json()
    fields = {f["key"]: f for f in body["fields"]}
    assert {k: f["type"] for k, f in fields.items()} == EXPECTED_FIELDS
    for f in fields.values():
        assert f["label"]
        assert {o["key"] for o in f["operators"]} == OPERATORS[f["type"]]
        assert all(o["label"] for o in f["operators"])
    assert fields["queue"]["values"] == [{"value": v, "label": k} for k, v in QUEUE_IDS.items()]
    assert {v["value"] for v in fields["agent"]["values"]} == set(AGENT_IDS.values())
    assert {v["value"] for v in fields["main_topic"]["values"]} == set(MAIN_TOPICS)
    assert fields["sentiment"]["min"] == -1 and fields["sentiment"]["max"] == 1
    assert fields["transcript"]["speakers"] == ["cliente", "agente", "bot"]
    assert "speakers" not in fields["summary"]
    assert body["default_period"] == {"from": "2026-08-28", "to": "2026-09-26"}


def test_schema_requires_explorer_permission(api):
    viewer = auth.get_store().find_by_email("viewer@bancohorizonte.demo")
    response = api.get("/api/query/schema", headers={"Authorization": f"Bearer {auth.create_token(viewer)}"})
    assert response.status_code == 403


def test_valid_nested_query_parses_and_applies_default_period():
    parsed = parse_query(query(
        cond("channel", "is", "chat"),
        {"op": "or", "conditions": [
            cond("sentiment", "lt", -0.3),
            cond("resolution", "in", ["escalada", "no_resuelta"]),
            cond("queue", "is", QUEUE_IDS["Tarjetas"].lower()),
        ]},
        cond("check:verificacion_identidad", "fails"),
        cond("transcript", "contains", "no reconozco", speaker="cliente"),
        cond("duration", "between", [60, 300]),
        cond("repeat_contact", "is", True),
    ))
    assert parsed.date_from == date(2026, 8, 28) and parsed.date_to == date(2026, 9, 26)
    assert parsed.root.conditions[1].conditions[2].value == QUEUE_IDS["Tarjetas"]


def test_explicit_period_is_kept():
    parsed = parse_query(query(**{"from": "2026-07-01", "to": "2026-07-31"}))
    assert (parsed.date_from, parsed.date_to) == (date(2026, 7, 1), date(2026, 7, 31))


@pytest.mark.parametrize("payload,path,fragment", [
    (query(cond("color", "is", "rojo")), "root.conditions[0]", "campo"),
    (query(cond("channel", "gt", "chat")), "root.conditions[0]", "operador"),
    (query(cond("channel", "is", "fax")), "root.conditions[0]", "valor"),
    (query(cond("channel", "in", "chat")), "root.conditions[0]", "lista"),
    (query(cond("sentiment", "lt", "abc")), "root.conditions[0]", "número"),
    (query(cond("sentiment", "gt", 2)), "root.conditions[0]", "rango"),
    (query(cond("duration", "between", [300, 60])), "root.conditions[0]", "entre"),
    (query(cond("duration", "between", [60])), "root.conditions[0]", "entre"),
    (query(cond("queue", "is", AGENT_IDS["Irene Vidal"])), "root.conditions[0]", "valor"),
    (query(cond("agent", "in", [AGENT_IDS["Irene Vidal"], "Irene Vidal"])), "root.conditions[0]", "valor"),
    (query(cond("summary", "contains", "  ")), "root.conditions[0]", "texto"),
    (query(cond("summary", "contains", "cargo", speaker="cliente")), "root.conditions[0]", "hablante"),
    (query(cond("transcript", "contains", "cargo", speaker="cajero")), "root.conditions[0]", "hablante"),
    (query(cond("repeat_contact", "is", "sí")), "root.conditions[0]", "booleano"),
    (query(cond("channel", "is", "chat"), {"op": "and", "conditions": [cond("csat", "gte", 6)]}),
     "root.conditions[1].conditions[0]", "rango"),
    (query({"op": "or", "conditions": [{"op": "and", "conditions": [cond("channel", "is", "chat")]}]}),
     "root.conditions[0].conditions[0]", "anidamiento"),
    (query(**{"from": "2026-09-10", "to": "2026-09-01"}), "from", "anterior"),
    ({"root": {"op": "xor", "conditions": []}}, "root", "op"),
    ({"root": {"op": "and", "conditions": [{"valor": 1}]}}, "root.conditions[0]", ""),
    ({}, "root", ""),
])
def test_invalid_queries_report_the_offending_path(payload, path, fragment):
    errors = errors_of(payload)
    assert any(e["path"] == path and fragment in e["message"].lower() for e in errors), errors


def test_all_errors_are_reported_at_once():
    errors = errors_of(query(cond("color", "is", 1), cond("csat", "lt", 9), cond("channel", "is", "chat")))
    assert {e["path"] for e in errors} == {"root.conditions[0]", "root.conditions[1]"}


def test_identifiers_in_values_are_normalized_and_validated_with_ids_module():
    value = ids.stable_id(ids.QUEUE, "Tarjetas").lower()
    parsed = parse_query(query(cond("queue", "in", [value])))
    assert parsed.root.conditions[0].value == [QUEUE_IDS["Tarjetas"]]


def test_query_size_is_limited():
    too_many = query(*[cond("channel", "is", "chat") for _ in range(51)])
    assert any("máximo" in e["message"].lower() and e["path"] == "root" for e in errors_of(too_many))
    parse_query(query(*[cond("channel", "is", "chat") for _ in range(50)]))
    long_list = query(cond("main_topic", "in", ["cajeros"] * 201))
    assert any("200" in e["message"] for e in errors_of(long_list))
