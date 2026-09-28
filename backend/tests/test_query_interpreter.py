import json

import pytest

from app.data.catalog import AGENT_IDS, COMPLIANCE_CHECKS, QUEUE_IDS
from app.query.model import parse_query


def c(field, operator, value=None, **extra):
    return {"field": field, "operator": operator, "value": value, **extra}


def canonical(conditions):
    def key(node):
        if "op" in node:
            return json.dumps({"op": node["op"], "conditions": sorted(key(n) for n in node["conditions"])}, sort_keys=True)
        value = sorted(node["value"]) if isinstance(node.get("value"), list) and node["operator"] in ("in", "not_in") else node.get("value")
        return json.dumps({**{k: v for k, v in node.items() if v is not None}, "value": value}, sort_keys=True)
    return sorted(key(n) for n in conditions)


PHRASES = [
    ("chats negativos de cargos no reconocidos escalados", {}, [
        c("channel", "is", "chat"), c("sentiment", "lt", -0.3),
        c("main_topic", "is", "cargo_no_reconocido"), c("resolution", "is", "escalada")]),
    ("llamadas de la cola de Tarjetas con riesgo de abandono alto", {}, [
        c("channel", "is", "voz"), c("queue", "is", QUEUE_IDS["Tarjetas"]), c("churn_risk", "is", "alto")]),
    ("conversaciones de Irene Vidal que duren más de 5 minutos", {}, [
        c("agent", "is", AGENT_IDS["Irene Vidal"]), c("duration", "gt", 300)]),
    ("quejas sin resolver", {}, [c("main_topic", "is", "reclamacion_queja"), c("resolution", "is", "no_resuelta")]),
    ("clientes insatisfechos con comisiones", {}, [c("csat", "lt", 3), c("main_topic", "is", "comisiones")]),
    ("llamadas sin verificar la identidad", {}, [c("channel", "is", "voz"), c("check:verificacion_identidad", "fails")]),
    ("casos de fraude en los últimos 7 días", {"from": "2026-09-20", "to": "2026-09-26"}, [
        c("main_topic", "is", "cargo_no_reconocido")]),
    ("bizum y transferencias con recontacto", {}, [
        c("main_topic", "is", "transferencias_bizum"), c("repeat_contact", "is", True)]),
    ("chats positivos de hipotecas resueltos", {}, [
        c("channel", "is", "chat"), c("sentiment", "gt", 0.3), c("main_topic", "is", "prestamos_hipotecas"),
        c("resolution", "is", "resuelta")]),
    ("conversaciones donde el agente pidió el PIN", {}, [c("check:no_solicitar_pin", "fails")]),
    ("cajeros y comisiones con esfuerzo alto", {}, [c("main_topic", "in", ["cajeros", "comisiones"]), c("effort", "gte", 4)]),
    ('llamadas que mencionen "cancelar el contrato"', {}, [
        c("channel", "is", "voz"), c("transcript", "contains", "cancelar el contrato")]),
    ("bajas de la cola de empresas esta semana", {"from": "2026-09-21", "to": "2026-09-26"}, [
        c("main_topic", "is", "baja_cancelacion"), c("queue", "is", QUEUE_IDS["Empresas"])]),
    ("conversaciones que incumplen algún check", {}, [
        {"op": "or", "conditions": [c(f"check:{code}", "fails") for code in COMPLIANCE_CHECKS]}]),
    ("clientes que dicen «me han robado»", {}, [c("transcript", "contains", "me han robado", speaker="cliente")]),
]


@pytest.mark.parametrize("phrase,dates,expected", PHRASES, ids=[p[0] for p in PHRASES])
def test_phrases_are_interpreted_into_the_expected_query(api, phrase, dates, expected):
    response = api.post("/api/query/interpret", json={"text": phrase})
    assert response.status_code == 200, response.text
    body = response.json()
    query = body["query"]
    assert {k: query[k] for k in ("from", "to") if k in query} == dates
    assert canonical(query["root"]["conditions"]) == canonical(expected)
    assert query["root"]["op"] == "and"
    parse_query(query)


@pytest.mark.parametrize("phrase", [p[0] for p in PHRASES[:6]])
def test_fully_understood_phrases_report_nothing_unrecognized(api, phrase):
    assert api.post("/api/query/interpret", json={"text": phrase}).json()["unrecognized"] == []


def test_unknown_words_are_reported_and_query_stays_empty(api):
    body = api.post("/api/query/interpret", json={"text": "tráeme lo del zodiaco"}).json()
    assert body["query"]["root"]["conditions"] == []
    assert body["unrecognized"] == ["tráeme", "zodiaco"]


def test_partially_understood_phrase_keeps_known_parts(api):
    body = api.post("/api/query/interpret", json={"text": "chats escalados con arcoíris"}).json()
    assert canonical(body["query"]["root"]["conditions"]) == canonical([c("channel", "is", "chat"), c("resolution", "is", "escalada")])
    assert body["unrecognized"] == ["arcoíris"]


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": "   "}, {"text": "x" * 501}])
def test_invalid_input_returns_422(api, payload):
    assert api.post("/api/query/interpret", json=payload).status_code == 422


@pytest.mark.parametrize("phrase,dates,expected", [
    ("chats de los últimos 0 días", {"from": "2026-09-26", "to": "2026-09-26"}, [c("channel", "is", "chat")]),
    ("quejas de los últimos 1000000000 días", {"from": "2016-09-29", "to": "2026-09-26"},
     [c("main_topic", "is", "reclamacion_queja")]),
    ("llamadas de menos de 1000000000 segundos", {}, [c("channel", "is", "voz"), c("duration", "lt", 86400)]),
    ('chats que mencionen "   "', {}, [c("channel", "is", "chat")]),
])
def test_extreme_numbers_and_empty_quotes_still_give_a_valid_query(api, phrase, dates, expected):
    response = api.post("/api/query/interpret", json={"text": phrase})
    assert response.status_code == 200, response.text
    query = response.json()["query"]
    assert {k: query[k] for k in ("from", "to") if k in query} == dates
    assert canonical(query["root"]["conditions"]) == canonical(expected)
    parse_query(query)


def test_any_combination_of_known_expressions_gives_a_valid_query(api):
    import random
    pieces = ["chats", "llamadas", "negativos", "positivos", "neutros", "escalados", "resueltos", "sin resolver",
              "de fraude", "de bizum", "cajeros", "comisiones", "bajas", "quejas", "cola de tarjetas", "cola de empresas",
              "Irene Vidal", "con recontacto", "incumplen algún check", "sin verificar la identidad", "esta semana", "ayer",
              "en los últimos {n} días", "que duren más de {n} minutos", "de menos de {n} segundos", "riesgo alto",
              "insatisfechos", "con esfuerzo alto", 'que mencionen "{w}"', "clientes que dicen «hola»", "el último mes"]
    rng = random.Random(2026)
    for _ in range(500):
        phrase = " ".join(rng.choice(pieces).format(n=rng.choice([0, 1, 7, 999, 10**9]), w=rng.choice(["x", "  "]))
                          for _ in range(rng.randint(1, 5)))
        response = api.post("/api/query/interpret", json={"text": phrase})
        assert response.status_code == 200, phrase
        parse_query(response.json()["query"])
