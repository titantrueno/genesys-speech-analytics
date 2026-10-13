"""Valores de cada campo destino, reglas del editor y Output «Guardar en campos» con el análisis completo (FE014, T3;
criterios 4 a 8 y 14 en la API).

Sin PostgreSQL: el origen `real` solo cambia la regla de completitud y la escritura va al doble `FakeWriter`.
"""
import json
from dataclasses import replace

import pytest

from app.config.store import get_config
from app.flows.fields import NO_VALUE, ValueRejected, coerce
from tests.flow_fixtures import edge, node
from tests.test_config_compliance import CHECKS, NEW_CHECK, create
from tests.test_flow_fields import BOTH_PROMPT, TEXT_PROMPT, _codes, _flow, real_origin, writer  # noqa: F401
from tests.test_flow_runs import flow_with, run
from tests.test_llm_flows import _finished, llm  # noqa: F401  (fixture)


def _active(kind: str) -> list:
    return [t for t in getattr(get_config(), kind).values() if t.active]


def _check():
    return next(c for c in get_config().checks.values() if c.active)


# --- Valor de cada destino (criterios 4 y 5) ---

@pytest.mark.parametrize("target, value, stored", [
    ("resolution", "resuelta", "resuelta"),
    ("resolution", "No resuelta", "no_resuelta"),
    ("resolution", " ESCALADA ", "escalada"),
    ("resolution", "no_resuelta", "no_resuelta"),
    ("churn_risk", "Alto", "alto"),
    ("csat", 1, 1.0),
    ("csat", 5, 5.0),
    ("csat", 3.5, 3.5),
    ("effort", 1, 1.0),
    ("sentiment", -1, -1.0),
    ("sentiment", 1, 1.0),
    ("sentiment", 0, 0.0),
    ("keywords", [" tarjeta ", "cargo"], ["tarjeta", "cargo"]),
    ("keywords", [f"p{i}" for i in range(12)], [f"p{i}" for i in range(10)]),
    ("entity:importe", " 120 € ", "120 €"),
    ("summary", " Resumen. ", "Resumen."),
], ids=str)
def test_valid_values_are_stored_normalized(target, value, stored):
    assert coerce(target, value) == stored


@pytest.mark.parametrize("target, value", [
    ("resolution", "pendiente"),
    ("churn_risk", "muy alto"),
    ("csat", 0),
    ("csat", 6),
    ("csat", 5.01),
    ("effort", 0.99),
    ("sentiment", -1.5),
    ("sentiment", 1.01),
    ("csat", True),
    ("csat", "4"),
    ("resolution", 3),
    ("keywords", ["tarjeta", " "]),
    ("keywords", "tarjeta"),
    ("secondary_topics", ["Inventado"]),
    ("compliance:saludo", "a veces"),
    ("compliance:saludo", True),
    ("main_topic", "Inventado"),
    ("summary", "  "),
], ids=str)
def test_invalid_values_are_rejected_with_a_reason(target, value):
    with pytest.raises(ValueRejected) as exc:
        coerce(target, value)
    assert str(exc.value)


def test_secondary_topics_are_stored_by_code_without_duplicates():
    topics = _active("secondary_topics")[:2]
    value = [topics[0].name.upper(), topics[1].code, f" {topics[0].code} "]
    assert coerce("secondary_topics", value) == [topics[0].code, topics[1].code]


def test_an_inactive_secondary_topic_is_rejected(monkeypatch):
    topic = _active("secondary_topics")[0]
    monkeypatch.setitem(get_config().secondary_topics, topic.code, replace(topic, active=False))
    with pytest.raises(ValueRejected):
        coerce("secondary_topics", [topic.code])


@pytest.mark.parametrize("value, stored", [("cumple", True), ("NO_CUMPLE", False), ("No cumple", False),
                                           ("no aplica", None), ("No Aplica", None), ("no_aplica", None)])
def test_compliance_answers_are_stored_as_booleans_or_null(value, stored):
    assert coerce(f"compliance:{_check().code}", value) is stored


def test_an_empty_entity_or_list_means_no_value():
    assert coerce("entity:producto", "") is NO_VALUE
    assert coerce("entity:producto", "   ") is NO_VALUE
    assert coerce("secondary_topics", []) is NO_VALUE
    assert coerce("keywords", []) is NO_VALUE


def test_a_check_that_no_longer_exists_is_rejected():
    with pytest.raises(ValueRejected, match="check"):
        coerce("compliance:no_existe", "cumple")


# --- Reglas del editor (criterios 6, 7 y 8) ---

CHECK = "saludo"
TOPICS = ["Fraude"]  # se sustituye por los nombres activos en `_full_prompt`


def _full_prompt(**overrides) -> dict:
    fields = {
        "resolucion": {"type": "texto", "options": ["Resuelta", "no_resuelta", "escalada"]},
        "riesgo": {"type": "texto", "options": ["bajo", "medio", "alto"]},
        "csat": {"type": "numero"}, "esfuerzo": {"type": "numero"}, "sentimiento": {"type": "numero"},
        "temas": {"type": "lista", "options": [t.name for t in _active("secondary_topics")]},
        "palabras": {"type": "lista"},
        "importe": {"type": "texto"},
        "saludo": {"type": "texto", "options": ["cumple", "no_cumple", "no_aplica"]},
    }
    fields.update(overrides)
    return {**BOTH_PROMPT, "output": {"type": "json", "fields": [
        {"name": name, **spec} for name, spec in fields.items() if spec is not None]}}


FULL_MAPPINGS = [("resolution", "resolucion"), ("churn_risk", "riesgo"), ("csat", "csat"), ("effort", "esfuerzo"),
                 ("sentiment", "sentimiento"), ("secondary_topics", "temas"), ("keywords", "palabras"),
                 ("entity:importe", "importe"), (f"compliance:{CHECK}", "saludo")]


def _output(mappings=FULL_MAPPINGS) -> dict:
    return {"kind": "campo", "overwrite": False, "mappings": [{"target": t, "source": s} for t, s in mappings]}


def test_a_complete_analysis_flow_validates(api, llm, real_origin):
    assert get_config().checks[CHECK].active
    assert not _codes(api, _flow(_full_prompt(), _output()))


@pytest.mark.parametrize("override, target", [
    ({"resolucion": {"type": "texto"}}, "resolution"),  # sin valores permitidos
    ({"resolucion": {"type": "texto", "options": ["Resuelta", "Quizá"]}}, "resolution"),
    ({"riesgo": {"type": "numero"}}, "churn_risk"),
    ({"riesgo": {"type": "texto", "options": ["bajo", "altísimo"]}}, "churn_risk"),
    ({"csat": {"type": "texto"}}, "csat"),
    ({"esfuerzo": {"type": "booleano"}}, "effort"),
    ({"sentimiento": {"type": "lista"}}, "sentiment"),
    ({"temas": {"type": "lista"}}, "secondary_topics"),  # sin valores permitidos
    ({"temas": {"type": "lista", "options": ["Inventado"]}}, "secondary_topics"),
    ({"temas": {"type": "texto"}}, "secondary_topics"),
    ({"palabras": {"type": "texto"}}, "keywords"),
    ({"importe": {"type": "numero"}}, "entity:importe"),
    ({"saludo": {"type": "texto"}}, f"compliance:{CHECK}"),
    ({"saludo": {"type": "texto", "options": ["sí", "no"]}}, f"compliance:{CHECK}"),
], ids=lambda v: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
def test_each_target_needs_a_json_field_of_its_type(api, llm, real_origin, override, target):
    response = api.post("/api/flows/validate", json=_flow(_full_prompt(**override), _output())).json()
    issues = [i for i in response["issues"] if i["code"] == "invalid_mapping"]
    assert len(issues) == 1, response["issues"]
    assert get_label(api, target) in issues[0]["message"]


def get_label(api, target: str) -> str:
    return next(t["label"] for t in api.get("/api/flows/catalog").json()["target_fields"] if t["value"] == target)


@pytest.mark.parametrize("target", ["resolution", "csat", "keywords", "entity:importe", f"compliance:{CHECK}"])
def test_a_text_or_label_prompt_only_feeds_summary_or_main_topic(api, llm, real_origin, target):
    output = {"kind": "campo", "mappings": [{"target": target, "source": None}]}
    assert "invalid_mapping" in _codes(api, _flow(TEXT_PROMPT, output))


def test_a_deleted_or_deactivated_check_blocks_the_run(api, llm, real_origin):
    payload = _flow(_full_prompt(), _output(FULL_MAPPINGS[:-1] + [("compliance:no_existe", "saludo")]))
    assert "unknown_check" in _codes(api, payload)
    item = next(c for c in api.get(CHECKS).json()["items"] if c["code"] == CHECK)
    editable = {k: v for k, v in item.items() if k not in ("id", "evaluation", "builtin")}
    assert api.put(f"{CHECKS}/{item['id']}", json={**editable, "active": False}).status_code == 200
    flow = flow_with(api, _flow(_full_prompt(), _output()))
    started = api.post(f"/api/flows/{flow['id']}/runs")
    assert started.status_code == 422
    assert "unknown_check" in started.text


def test_a_new_custom_check_can_be_a_target(api, llm, real_origin):
    create(api)
    prompt = _full_prompt(oferta={"type": "texto", "options": ["Cumple", "No cumple", "No aplica"]})
    assert not _codes(api, _flow(prompt, _output(FULL_MAPPINGS + [(f"compliance:{NEW_CHECK['code']}", "oferta")])))


def test_duplicates_and_simulated_values_also_apply_to_new_targets(api, llm, real_origin):
    assert "duplicate_target" in _codes(api, _flow(_full_prompt(), _output(FULL_MAPPINGS + [("csat", "esfuerzo")])))
    simulated = {**_full_prompt(), "provider": "simulado", "model": "mock-rapido"}
    assert "simulated_values_to_real_data" in _codes(api, _flow(simulated, _output()))
    payload = _flow(_full_prompt(), _output())
    payload["nodes"].append(node("tmp-o2", "output", _output([("entity:importe", "importe")]), x=600, y=200))
    payload["edges"].append(edge("tmp-p", "tmp-o2"))
    assert "duplicate_target" in _codes(api, payload)


# --- Ejecución: un rechazo solo afecta a su campo (criterios 4 y 14) ---

def _answer(**overrides) -> str:
    data = {"resolucion": "Escalada", "riesgo": "medio", "csat": 4, "esfuerzo": 2, "sentimiento": -0.2,
            "temas": [_active("secondary_topics")[0].name], "palabras": ["tarjeta", "cargo"], "importe": "",
            "saludo": "no_aplica"}
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def test_one_invalid_field_is_rejected_and_the_rest_are_written(api, llm, writer, real_origin):
    llm.answer = lambda body: _answer(csat=7)
    flow = flow_with(api, _flow(_full_prompt(), _output()))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    assert snapshot["status"] == "ok", [n["message"] for n in snapshot["nodes"].values() if n["message"]]
    result = next(iter(snapshot["outputs"].values()))["result"]
    [call] = writer.calls
    item = call["items"][0]
    topic = _active("secondary_topics")[0].code
    assert item["values"] == {"resolution": "escalada", "churn_risk": "medio", "effort": 2.0, "sentiment": -0.2,
                              "secondary_topics": [topic], "keywords": ["tarjeta", "cargo"],
                              f"compliance:{CHECK}": None}
    row = result["rows"][0]
    assert row["states"]["csat"] == "rechazado"
    assert "csat" in row["reasons"] and "5" in row["reasons"]["csat"]
    assert row["states"]["entity:importe"] == "sin_valor"
    assert row["states"]["resolution"] == "escrito"
    total = len(result["rows"])
    assert result["counts"]["csat"] == {"escrito": 0, "omitido": 0, "rechazado": total, "sin_valor": 0, "error": 0}
    assert result["counts"]["entity:importe"]["sin_valor"] == total
    assert all(sum(c.values()) == total for c in result["counts"].values())


def test_skipped_fields_carry_the_reason_from_the_writer(api, llm, writer, real_origin):
    llm.answer = lambda body: _answer()
    writer.reasons = {"sentiment": "Genesys ya da el sentimiento"}
    flow = flow_with(api, _flow(_full_prompt(), _output()))
    snapshot = _finished(api, flow, run(api, flow)["id"])
    row = next(iter(snapshot["outputs"].values()))["result"]["rows"][0]
    assert row["states"]["sentiment"] == "omitido"
    assert row["reasons"]["sentiment"] == "Genesys ya da el sentimiento"
