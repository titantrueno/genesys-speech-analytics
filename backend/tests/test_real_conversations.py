"""Listado, detalle y KPIs con el origen `real` (FE012, T3; criterios 5, 6, 9 y 10)."""
import pytest

from tests.real_helpers import QS, real_api, real_id  # noqa: F401  (fixture)

pytestmark = pytest.mark.pg
VOICE_BOT_AGENT, CHAT_BOT_AGENT, CHAT_UNDELIVERED, VOICE_CONTAINED = "7b94988a", "f7e79502", "9e3ec75a", "37dcbccf"


def _list(api, **params) -> dict:
    response = api.get("/api/conversations", params={**QS, "page_size": 100, **params})
    assert response.status_code == 200, response.text
    return response.json()


def _detail(api, short_id: str) -> dict:
    response = api.get(f"/api/conversations/{real_id(short_id)}")
    assert response.status_code == 200, response.text
    return response.json()


# --- Listado ---

def test_the_list_adds_genesys_columns_and_marks_the_analysis_pending(real_api):
    items = {i["id"]: i for i in _list(real_api)["items"]}
    contained = items[real_id(VOICE_CONTAINED)]
    assert (contained["ani"], contained["external_tag"]) == ("+34675075376", "Javier Del Olmo")
    assert contained["contained_in_bot"] is True and contained["transcript_quality"] == "completa"
    assert contained["analysis_pending"] is True
    assert contained["summary"] == "" and contained["main_topic"] is None and contained["csat"] is None
    handled = items[real_id(VOICE_BOT_AGENT)]
    assert handled["contained_in_bot"] is False and handled["agent"] == "Javier Del Olmo"


@pytest.mark.parametrize("phone", ["+34675075376", "675075376", "+34 675 075 376", "0034675075376"])
def test_search_by_phone_is_exact_with_or_without_the_prefix(real_api, phone):
    found = _list(real_api, phone=phone)["items"]
    assert found and all(i["ani"] == "+34675075376" for i in found)
    assert real_id(VOICE_CONTAINED) in {i["id"] for i in found}


def test_search_by_phone_does_not_match_partial_numbers(real_api):
    assert _list(real_api, phone="67507537")["total"] == 0
    assert _list(real_api, phone="+34675075377")["total"] == 0


def test_search_by_external_tag_is_exact(real_api):
    found = _list(real_api, external_tag="Javier Del Olmo")
    assert found["total"] > 0 and all(i["external_tag"] == "Javier Del Olmo" for i in found["items"])
    assert _list(real_api, external_tag="Javier")["total"] == 0


def test_sorting_by_sentiment_tolerates_conversations_without_it(real_api):
    for order in ("asc", "desc"):
        assert _list(real_api, sort="sentiment", order=order)["total"] == 10


def test_analysis_filters_find_nothing_while_the_analysis_is_pending(real_api):
    assert _list(real_api, resolution="resuelta")["total"] == 0
    assert _list(real_api, churn_risk="alto")["total"] == 0
    assert _list(real_api, compliant="true")["total"] == 0
    assert _list(real_api, repeat_contact="true")["total"] == 0
    assert _list(real_api, main_topic="tarjetas")["total"] == 0


def test_the_catalog_offers_the_real_queues_and_agents(real_api):
    catalog = real_api.get("/api/catalog").json()
    assert {"AIT_Transcription"} <= {q["name"] for q in catalog["queues"]}
    assert "Javier Del Olmo" in {a["name"] for a in catalog["agents"]}


# --- Detalle ---

def test_the_detail_of_a_voice_call_bot_to_agent_carries_the_genesys_analytics(real_api):
    body = _detail(real_api, VOICE_BOT_AGENT)
    genesys = body["genesys"]
    assert [s["kind"] for s in genesys["segments"]] == ["cliente", "ivr", "cola", "agente"]
    assert genesys["derived_to_agent"] is True and genesys["contained_in_bot"] is False
    assert genesys["segments"][3]["wrapup"]["name"] == "Default Wrap-up Code"
    assert {"Conexión", "Saludos"} <= {t["name"] for t in genesys["topics"]}
    assert "bot" in {t["speaker"] for t in body["turns"]} and "agente" in {t["speaker"] for t in body["turns"]}
    assert body["analysis"]["pending"] is True and body["analysis"]["summary"] == ""
    assert body["analysis"]["compliance"] == {} and body["main_topic_label"] is None
    assert genesys["metrics"]["handle_s"] > 0


def test_the_detail_of_a_chat_bot_to_agent(real_api):
    body = _detail(real_api, CHAT_BOT_AGENT)
    assert body["channel"] == "chat"
    assert {"cliente", "bot", "agente"} <= {t["speaker"] for t in body["turns"]}
    assert body["genesys"]["ani"] is None  # un chat no tiene ANI
    assert body["genesys"]["derived_to_agent"] is True


def test_an_undelivered_message_keeps_its_text_and_is_flagged(real_api):
    body = _detail(real_api, CHAT_UNDELIVERED)
    failed = [t for t in body["turns"] if not t["delivered"]]
    assert [t["text"] for t in failed] == ["lo estoy revisando, un segundo"]
    assert body["genesys"]["undelivered_messages"] == 1


def test_an_unknown_real_conversation_is_404(real_api):
    assert real_api.get("/api/conversations/1CO-00000000-0000-4000-8000-000000000000").status_code == 404


# --- KPIs ---

ANALYSIS_KPIS = ["resolution_rate", "escalation_rate", "fcr_rate", "csat_avg", "effort_avg", "compliance_rate",
                 "churn_high_pct"]


def _kpis(api, **params) -> dict:
    response = api.get("/api/metrics/summary", params={**QS, **params})
    assert response.status_code == 200, response.text
    return {k["code"]: k for k in response.json()["kpis"]}


def test_analysis_kpis_are_pending_not_zero(real_api):
    kpis = _kpis(real_api)
    for code in ANALYSIS_KPIS:
        assert kpis[code]["value"] is None and kpis[code]["pending"] is True, code


def test_volume_aht_and_sentiment_are_computed_from_genesys(real_api):
    kpis = _kpis(real_api)
    assert kpis["volume"]["value"] == 10 and kpis["volume"]["pending"] is False
    assert kpis["aht_s"]["value"] > 0 and kpis["aht_s"]["based_on"] < 10  # solo las atendidas por un agente
    sentiment = kpis["sentiment_avg"]
    assert sentiment["value"] is not None and -1 <= sentiment["value"] <= 1
    assert 0 < sentiment["based_on"] <= 10


def test_the_aht_is_the_average_handle_time_of_agent_conversations(real_api):
    from app.data.store import get_dataset
    handled = [c.genesys.metrics["handle_s"] for c in get_dataset() if c.genesys.derived_to_agent
               and "handle_s" in c.genesys.metrics]
    assert _kpis(real_api)["aht_s"]["value"] == pytest.approx(sum(handled) / len(handled), abs=0.01)
    assert _kpis(real_api)["aht_s"]["based_on"] == len(handled)


def test_the_breakdown_by_main_topic_is_pending_and_by_queue_is_not(real_api):
    topic = real_api.get("/api/metrics/breakdown", params={**QS, "dimension": "main_topic"}).json()
    assert topic["pending"] is True and topic["items"] == []
    queue = real_api.get("/api/metrics/breakdown", params={**QS, "dimension": "queue"}).json()
    assert queue["pending"] is True
    assert sum(i["kpis"]["volume"] for i in queue["items"]) == 10
    assert all(i["kpis"]["csat_avg"] is None for i in queue["items"])


def test_the_timeseries_of_volume_is_computed_and_flags_pending_kpis(real_api):
    volume = real_api.get("/api/metrics/timeseries", params={**QS, "kpi": "volume"}).json()
    assert sum(p["value"] for p in volume["points"]) == 10 and volume["pending"] is False
    csat = real_api.get("/api/metrics/timeseries", params={**QS, "kpi": "csat_avg"}).json()
    assert csat["pending"] is True and all(p["value"] is None for p in csat["points"])


def test_the_kpi_drill_down_matches_the_list(real_api):
    """Contrato de FE001: el volumen de un KPI con los filtros del drill-down es el total del listado."""
    queue = real_api.get("/api/catalog").json()["queues"][0]["id"]
    for params in ({}, {"queue": queue}, {"channel": "chat"}, {"channel": "voz"}):
        assert _kpis(real_api, **params)["volume"]["value"] == _list(real_api, **params)["total"]
