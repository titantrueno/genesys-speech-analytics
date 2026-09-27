import time
from datetime import date

import pytest

from app import auth
from app import ids
from app.data.catalog import AGENT_IDS, AGENTS_BY_QUEUE, COMPLIANCE_CHECKS, MAIN_TOPICS, QUEUE_IDS, QUEUES
from app.data.generator import generate_dataset

DATASET = {c.id: c for c in generate_dataset(seed=42, reference_date=date(2026, 9, 27))}
PERIOD = {"from": "2026-07-01", "to": "2026-09-26"}
SAMPLE_ID = list(DATASET)[499]


def kpis(api, **params):
    body = api.get("/api/metrics/summary", params={**PERIOD, **params}).json()
    return {k["code"]: k["value"] for k in body["kpis"]}


def total(api, **params):
    response = api.get("/api/conversations", params={**PERIOD, **params})
    assert response.status_code == 200, response.text
    return response.json()["total"]


def test_default_list_matches_default_summary_volume(api):
    body = api.get("/api/conversations").json()
    volume = next(k["value"] for k in api.get("/api/metrics/summary").json()["kpis"] if k["code"] == "volume")
    assert body["total"] == volume
    assert body["page"] == 1 and body["page_size"] == 25
    assert len(body["items"]) == 25
    dates = [i["started_at"] for i in body["items"]]
    assert dates == sorted(dates, reverse=True)


def test_list_item_has_spec_columns_and_full_summary(api):
    item = api.get("/api/conversations", params=PERIOD).json()["items"][0]
    assert set(item) >= {"id", "started_at", "channel", "queue", "queue_id", "agent", "agent_id", "main_topic",
                         "main_topic_label", "summary", "sentiment", "resolution", "csat", "duration_s"}
    assert ids.is_valid(item["id"], ids.CONVERSATION)
    assert item["queue_id"] == QUEUE_IDS[item["queue"]] and item["agent_id"] == AGENT_IDS[item["agent"]]
    source = DATASET[item["id"]]
    assert item["summary"] == source.analysis.summary
    assert item["main_topic_label"] == MAIN_TOPICS[source.analysis.main_topic].name


@pytest.mark.parametrize("dimension,param", [
    ("main_topic", "main_topic"), ("queue", "queue"), ("agent", "agent"), ("channel", "channel"),
])
def test_list_total_equals_breakdown_volume(api, dimension, param):
    items = api.get("/api/metrics/breakdown", params={**PERIOD, "dimension": dimension}).json()["items"]
    for item in items[:4]:
        assert total(api, **{param: item["key"]}) == item["kpis"]["volume"], item["key"]


def test_list_total_equals_timeseries_point(api):
    points = api.get("/api/metrics/timeseries",
                     params={**PERIOD, "kpi": "volume", "granularity": "week", "main_topic": "cargo_no_reconocido"}).json()["points"]
    for point in points:
        count = total(api, **{"from": point["period_start"], "to": point["period_end"], "main_topic": "cargo_no_reconocido"})
        assert count == point["value"]


def test_kpi_drilldown_filters_match_kpi_values(api):
    k = kpis(api, channel="voz")
    volume = k["volume"]

    def expected(rate):
        return round(volume * rate / 100)

    assert total(api, channel="voz", resolution="escalada") == expected(k["escalation_rate"])
    assert total(api, channel="voz", resolution="resuelta") == expected(k["resolution_rate"])
    assert total(api, channel="voz", churn_risk="alto") == expected(k["churn_high_pct"])
    assert total(api, channel="voz", sentiment_lt=-0.3) == expected(k["negative_pct"])
    assert total(api, channel="voz", compliant="false") == volume - expected(k["compliance_rate"])
    assert total(api, channel="voz", repeat_contact="true") == volume - expected(k["fcr_rate"])


def test_multiple_values_combine_as_or_within_a_field(api):
    both = total(api, resolution=["escalada", "no_resuelta"])
    assert both == total(api, resolution="escalada") + total(api, resolution="no_resuelta")


def test_pagination_covers_every_conversation_once(api):
    first = api.get("/api/conversations", params={**PERIOD, "page_size": 40}).json()
    assert first["pages"] == -(-first["total"] // 40)
    seen = []
    for page in range(1, first["pages"] + 1):
        seen += [i["id"] for i in api.get("/api/conversations", params={**PERIOD, "page_size": 40, "page": page}).json()["items"]]
    assert len(seen) == len(set(seen)) == first["total"]
    beyond = api.get("/api/conversations", params={**PERIOD, "page": first["pages"] + 1, "page_size": 40}).json()
    assert beyond["items"] == []


@pytest.mark.parametrize("sort,order,key", [
    ("duration", "asc", lambda i: i["duration_s"]),
    ("duration", "desc", lambda i: -i["duration_s"]),
    ("sentiment", "asc", lambda i: i["sentiment"]),
    ("date", "asc", lambda i: i["started_at"]),
])
def test_sorting(api, sort, order, key):
    items = api.get("/api/conversations", params={**PERIOD, "sort": sort, "order": order, "page_size": 100}).json()["items"]
    values = [key(i) for i in items]
    assert values == sorted(values)


def test_detail_returns_full_conversation(api):
    conv_id = api.get("/api/conversations", params=PERIOD).json()["items"][3]["id"]
    body = api.get(f"/api/conversations/{conv_id}").json()
    source = DATASET[conv_id]
    assert body["id"] == conv_id
    assert len(body["turns"]) == len(source.turns)
    assert body["turns"][0]["text"] == source.turns[0].text
    assert body["analysis"]["summary"] == source.analysis.summary
    assert body["analysis"]["compliance"] == source.analysis.compliance
    assert body["main_topic_label"] == MAIN_TOPICS[source.analysis.main_topic].name


@pytest.mark.parametrize("value", [
    "CNV-999999", "no-es-un-id", ids.stable_id(ids.CONVERSATION, "no existe"),
    "1CU-" + list(DATASET)[0][4:],
])
def test_detail_unknown_or_malformed_id_returns_404(api, value):
    assert api.get(f"/api/conversations/{value}").status_code == 404


def test_detail_accepts_lowercase_id(api):
    conv_id = list(DATASET)[10]
    response = api.get(f"/api/conversations/{conv_id.lower()}")
    assert response.status_code == 200
    assert response.json()["id"] == conv_id


def test_catalog_lists_filter_values(api):
    body = api.get("/api/catalog").json()
    assert body["queues"] == [{"id": QUEUE_IDS[q], "name": q} for q in QUEUES]
    assert {t["code"]: t["name"] for t in body["main_topics"]} == {c: t.name for c, t in MAIN_TOPICS.items()}
    assert {a["name"] for a in body["agents"]} == {a for agents in AGENTS_BY_QUEUE.values() for a in agents}
    assert all(a["id"] == AGENT_IDS[a["name"]] and a["queue_id"] == QUEUE_IDS[a["queue"]] for a in body["agents"])
    assert {c["code"] for c in body["compliance_checks"]} == set(COMPLIANCE_CHECKS)
    assert {c["code"] for c in body["channels"]} == {"voz", "chat"}
    assert {r["code"] for r in body["resolutions"]} == {"resuelta", "no_resuelta", "escalada"}


def test_catalog_available_to_dashboards_only_role_but_list_is_not(api):
    store = auth.get_store()
    store.roles["solo_dashboards"] = {"dashboards:view"}
    store.users["u-dash"] = auth.User("u-dash", "Solo dashboards", "dash@bancohorizonte.demo", "solo_dashboards")
    headers = {"Authorization": f"Bearer {auth.create_token(store.users['u-dash'])}"}
    assert api.get("/api/catalog", headers=headers).status_code == 200
    assert api.get("/api/conversations", headers=headers).status_code == 403
    assert api.get("/api/conversations/CNV-000001", headers=headers).status_code == 403


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page_size": 500}, {"sort": "color"}, {"order": "up"},
    {"resolution": "quizas"}, {"churn_risk": "enorme"}, {"compliant": "tal vez"},
    {"queue": "Particulares"}, {"agent": "Sergio Molina"},
])
def test_invalid_list_parameters_return_422(api, params):
    assert api.get("/api/conversations", params=params).status_code == 422


@pytest.mark.parametrize("path,params", [
    ("/api/conversations", {"from": "2026-06-30", "to": "2026-09-26", "sort": "sentiment", "page_size": 100}),
    (f"/api/conversations/{SAMPLE_ID}", {}),
    ("/api/catalog", {}),
])
def test_conversation_endpoints_respond_under_500ms(api, path, params):
    api.get(path, params=params)
    start = time.perf_counter()
    assert api.get(path, params=params).status_code == 200
    assert time.perf_counter() - start < 0.5


def test_catalog_exposes_reference_date_used_by_default_periods(api):
    body = api.get("/api/catalog").json()
    assert body["reference_date"] == "2026-09-27"
    summary = api.get("/api/metrics/summary").json()
    assert summary["period"]["to"] == "2026-09-26"
