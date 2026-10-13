"""Lectura campo a campo del análisis de las conversaciones reales (FE014, T4; criterio 12).

El análisis parcial se escribe por SQL, como lo dejaría un flujo de insights: cada campo se muestra y cuenta en cuanto
existe, aunque el resto siga pendiente. Sin nada escrito, el comportamiento de FE012 no cambia (sus tests lo cubren).
"""
import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.config.store import get_config
from tests.real_helpers import QS, real_api, real_id  # noqa: F401  (fixture)
from tests.test_config_compliance import create
from tests.test_real_explorer import cond, run

pytestmark = pytest.mark.pg
# Dos conversaciones de las fixtures de FE011: una con sentimiento de Genesys y otra sin él (se fuerza en el test).
FIRST, SECOND = "7b94988a", "f7e79502"


def _set(pg_url, short_id: str, **columns):
    assignments = ", ".join(f"{c} = %s" for c in columns)
    values = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in columns.values()]
    with psycopg.connect(pg_url) as conn:
        conn.execute(f"UPDATE analysis SET {assignments}, updated_at = now() WHERE conversation_id = %s",
                     [*values, real_id(short_id)])


def _genesys_sentiment(pg_url, short_id: str, value):
    with psycopg.connect(pg_url) as conn:
        conn.execute("UPDATE conversation SET customer_sentiment = %s, updated_at = now() WHERE id = %s",
                     (value, real_id(short_id)))


def _detail(api, short_id: str) -> dict:
    response = api.get(f"/api/conversations/{real_id(short_id)}")
    assert response.status_code == 200, response.text
    return response.json()


def _kpis(api) -> dict:
    response = api.get("/api/metrics/summary", params=QS)
    assert response.status_code == 200, response.text
    return {k["code"]: k for k in response.json()["kpis"]}


def _builtin_checks() -> list:
    return [c for c in get_config().checks.values() if c.active and c.builtin]


# --- Detalle ---

def test_the_detail_shows_each_field_as_soon_as_it_exists(real_api, pg_url):
    check = _builtin_checks()[0]
    _set(pg_url, FIRST, resolution="escalada", compliance={check.code: False}, keywords=["tarjeta"],
         entities={"importe": "30 €"}, secondary_topics=["fraude"])
    analysis = _detail(real_api, FIRST)["analysis"]
    assert (analysis["resolution"], analysis["csat"], analysis["effort"], analysis["churn_risk"]) == (
        "escalada", None, None, None)
    assert analysis["keywords"] == ["tarjeta"] and analysis["secondary_topics"] == ["fraude"]
    assert analysis["entities"] == [{"type": "importe", "value": "30 €"}]
    assert analysis["compliance"] == {check.code: False}
    assert set(analysis["compliance_pending"]) == {c.code for c in _builtin_checks()} - {check.code}
    assert analysis["pending"] is True  # aún faltan otros campos


def test_an_unanalysed_conversation_has_every_check_pending(real_api):
    analysis = _detail(real_api, FIRST)["analysis"]
    assert analysis["compliance"] == {}
    assert set(analysis["compliance_pending"]) == {c.code for c in _builtin_checks()}


def test_a_custom_check_uses_the_llm_result_over_its_phrases(real_api, pg_url):
    created = create(real_api)  # «valore la atención»: ninguna fixture lo dice, así que por frases no cumple
    code = created["code"]
    assert _detail(real_api, FIRST)["analysis"]["compliance"][code] is False
    _set(pg_url, FIRST, compliance={code: True})
    assert _detail(real_api, FIRST)["analysis"]["compliance"][code] is True
    assert code not in _detail(real_api, FIRST)["analysis"]["compliance_pending"]


def test_the_sentiment_is_genesys_first_then_the_llm(real_api, pg_url):
    _genesys_sentiment(pg_url, FIRST, 0.4)
    _genesys_sentiment(pg_url, SECOND, None)
    _set(pg_url, FIRST, sentiment=-0.9)
    _set(pg_url, SECOND, sentiment=-0.5)
    assert _detail(real_api, FIRST)["analysis"]["sentiment"] == pytest.approx(0.4)
    assert _detail(real_api, SECOND)["analysis"]["sentiment"] == pytest.approx(-0.5)


# --- KPIs ---

def test_a_kpi_is_computed_on_the_conversations_that_have_its_field(real_api, pg_url):
    _set(pg_url, FIRST, resolution="resuelta")
    _set(pg_url, SECOND, resolution="escalada", churn_risk="alto")
    kpis = _kpis(real_api)
    assert (kpis["resolution_rate"]["value"], kpis["resolution_rate"]["based_on"]) == (50, 2)
    assert kpis["resolution_rate"]["pending"] is False
    assert (kpis["escalation_rate"]["value"], kpis["escalation_rate"]["based_on"]) == (50, 2)
    assert (kpis["churn_high_pct"]["value"], kpis["churn_high_pct"]["based_on"]) == (100, 1)
    assert kpis["fcr_rate"]["based_on"] == 2 and kpis["fcr_rate"]["pending"] is False
    for code in ("csat_avg", "effort_avg", "compliance_rate"):
        assert kpis[code]["value"] is None and kpis[code]["pending"] is True and kpis[code]["based_on"] == 0, code


def test_compliance_rate_counts_conversations_with_a_check_result(real_api, pg_url):
    first, second = _builtin_checks()[:2]
    _set(pg_url, FIRST, compliance={first.code: True, second.code: None})
    _set(pg_url, SECOND, compliance={first.code: False})
    kpis = _kpis(real_api)
    assert (kpis["compliance_rate"]["value"], kpis["compliance_rate"]["based_on"]) == (50, 2)
    body = real_api.get("/api/metrics/summary", params=QS).json()
    by_check = {c["code"]: c for c in body["compliance_by_check"]}
    assert (by_check[first.code]["value"], by_check[first.code]["applicable"]) == (50, 2)
    assert by_check[second.code]["applicable"] == 0


def test_the_timeseries_and_main_topic_breakdown_use_what_exists(real_api, pg_url):
    _set(pg_url, FIRST, csat=4, main_topic="cajeros")
    csat = real_api.get("/api/metrics/timeseries", params={**QS, "kpi": "csat_avg"}).json()
    assert csat["pending"] is False and [p["value"] for p in csat["points"] if p["value"] is not None] == [4]
    topics = real_api.get("/api/metrics/breakdown", params={**QS, "dimension": "main_topic"}).json()
    assert [(i["key"], i["kpis"]["volume"]) for i in topics["items"]] == [("cajeros", 1)]


# --- Filtros y explorador ---

def test_a_written_field_is_no_longer_empty_and_filters_normally(real_api, pg_url):
    _set(pg_url, FIRST, resolution="resuelta", csat=4.5)
    total = _kpis(real_api)["volume"]["value"]
    assert run(real_api, cond("resolution", "is_empty"))["total"] == total - 1
    assert [i["id"] for i in run(real_api, cond("resolution", "is", "resuelta"))["items"]] == [real_id(FIRST)]
    assert run(real_api, cond("csat", "gte", 4))["total"] == 1
    listed = real_api.get("/api/conversations", params={**QS, "resolution": "resuelta", "page_size": 100}).json()
    assert [i["id"] for i in listed["items"]] == [real_id(FIRST)]


def test_a_check_is_empty_only_while_it_is_pending(real_api, pg_url):
    check = _builtin_checks()[0]
    _set(pg_url, FIRST, compliance={check.code: None})
    total = _kpis(real_api)["volume"]["value"]
    assert run(real_api, cond(f"check:{check.code}", "is_empty"))["total"] == total - 1
    assert [i["id"] for i in run(real_api, cond(f"check:{check.code}", "not_applicable"))["items"]] == [real_id(FIRST)]
    compliant = real_api.get("/api/conversations", params={**QS, "compliant": "true", "page_size": 100}).json()
    assert [i["id"] for i in compliant["items"]] == [real_id(FIRST)]  # sin incumplimientos y con un resultado


def test_the_breakdown_says_which_kpis_are_still_pending(real_api, pg_url):
    # Hallazgo del recorrido de T8: el dashboard ocultaba el desglose por main topic con datos ya escritos.
    _set(pg_url, FIRST, main_topic="cajeros", csat=4)
    topic = real_api.get("/api/metrics/breakdown", params={**QS, "dimension": "main_topic"}).json()
    assert topic["pending"] is False and topic["items"]
    queue = real_api.get("/api/metrics/breakdown", params={**QS, "dimension": "queue"}).json()
    assert "csat_avg" not in queue["pending_kpis"] and "effort_avg" in queue["pending_kpis"]
    assert set(queue["pending_kpis"]) <= {"resolution_rate", "escalation_rate", "fcr_rate", "effort_avg",
                                          "compliance_rate", "churn_high_pct"}
