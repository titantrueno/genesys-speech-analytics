from collections import Counter

import pytest

from app.data.catalog import MAIN_TOPICS, QUEUE_IDS
from app.data.store import get_dataset
from tests.dates import day_ago, days_ago, default_period

# El mismo dataset que sirve la API, con fechas relativas a su fecha de referencia (FE009).
DATASET = get_dataset()


def in_period(start, end):
    return [c for c in DATASET if start <= c.started_at.date() <= end]


def suggest(api, **params):
    response = api.get("/api/query/suggest", params=params)
    assert response.status_code == 200, response.text
    return response.json()["values"]


def test_main_topic_counts_match_the_interval_and_are_sorted(api):
    values = suggest(api, field="main_topic", **{"from": days_ago(88), "to": days_ago(43)})
    expected = Counter(c.analysis.main_topic for c in in_period(day_ago(88), day_ago(43)))
    assert {v["value"]: v["count"] for v in values} == dict(expected)
    assert [v["count"] for v in values] == sorted((v["count"] for v in values), reverse=True)
    assert all(v["label"] == MAIN_TOPICS[v["value"]].name for v in values)


def test_multi_valued_secondary_topics_count_conversations(api):
    values = suggest(api, field="secondary_topic", **{"from": days_ago(88), "to": days_ago(1)})
    convs = in_period(day_ago(88), day_ago(1))
    expected = Counter(topic for c in convs for topic in set(c.analysis.secondary_topics))
    assert {v["value"]: v["count"] for v in values} == dict(expected)


def test_queue_suggestions_use_identifiers_and_names(api):
    values = suggest(api, field="queue")
    names = {v: k for k, v in QUEUE_IDS.items()}
    expected = Counter(c.queue_id for c in in_period(*default_period()))
    assert {v["value"]: v["count"] for v in values} == dict(expected)
    assert all(v["label"] == names[v["value"]] for v in values)


def test_only_values_present_in_the_interval_are_returned(api):
    values = suggest(api, field="main_topic", **{"from": days_ago(1), "to": days_ago(1)})
    expected = Counter(c.analysis.main_topic for c in in_period(day_ago(1), day_ago(1)))
    assert len(values) == len(expected) < len(MAIN_TOPICS)
    assert all(v["count"] > 0 for v in values)


@pytest.mark.parametrize("params", [
    {"field": "sentiment"}, {"field": "summary"}, {"field": "check:saludo"}, {"field": "color"}, {},
    {"field": "channel", "from": days_ago(17), "to": days_ago(26)},
])
def test_invalid_suggest_requests_return_422(api, params):
    assert api.get("/api/query/suggest", params=params).status_code == 422
