"""Los valores esperados se calculan aquí de forma independiente a app/services, sobre el mismo dataset que sirve la API
y con fechas relativas a su fecha de referencia (FE009)."""
import time
from collections import defaultdict
from datetime import date, timedelta
from functools import cache
from statistics import mean

import pytest

from app import ids
from app.data.catalog import AGENT_IDS, MAIN_TOPICS, QUEUE_IDS
from app.data.store import get_dataset
from tests.dates import day_ago, days_ago, default_period, weekday_on_or_before

KPI_CODES = {
    "volume", "aht_s", "sentiment_avg", "negative_pct", "resolution_rate", "escalation_rate", "fcr_rate",
    "csat_avg", "effort_avg", "compliance_rate", "churn_high_pct", "first_response_s", "avg_turns",
}


@cache
def followups() -> dict[str, bool]:
    """Recontacto a 7 días calculado aquí, sin el índice del backend."""
    dataset = get_dataset()

    def has_followup(conv):
        limit = conv.started_at + timedelta(days=7)
        return any(o.customer_id == conv.customer_id and conv.started_at < o.started_at <= limit for o in dataset)

    return {c.id: has_followup(c) for c in dataset}


def select(date_from, date_to, channel=None, queues=None, agents=None, topics=None):
    return [
        c for c in get_dataset()
        if date_from <= c.started_at.date() <= date_to
        and (channel is None or c.channel == channel)
        and (not queues or c.queue_id in queues)
        and (not agents or c.agent_id in agents)
        and (not topics or c.analysis.main_topic in topics)
    ]


def pct(items, predicate):
    return 100 * sum(1 for i in items if predicate(i)) / len(items) if items else None


def avg(values):
    values = list(values)
    return mean(values) if values else None


def expected_kpis(convs):
    chats = [c for c in convs if c.channel == "chat"]
    return {
        "volume": len(convs),
        "aht_s": avg(c.duration_s for c in convs),
        "sentiment_avg": avg(c.analysis.sentiment for c in convs),
        "negative_pct": pct(convs, lambda c: c.analysis.sentiment < -0.3),
        "resolution_rate": pct(convs, lambda c: c.analysis.resolution == "resuelta"),
        "escalation_rate": pct(convs, lambda c: c.analysis.resolution == "escalada"),
        "fcr_rate": pct(convs, lambda c: not followups()[c.id]),
        "csat_avg": avg(c.analysis.csat for c in convs),
        "effort_avg": avg(c.analysis.effort for c in convs),
        "compliance_rate": pct(convs, lambda c: all(v for v in c.analysis.compliance.values() if v is not None)),
        "churn_high_pct": pct(convs, lambda c: c.analysis.churn_risk == "alto"),
        "first_response_s": avg(next(t.offset_s for t in c.turns if t.speaker == "agente") for c in chats),
        "avg_turns": avg(len(c.turns) for c in convs),
    }


def assert_kpis_match(api_kpis, expected):
    for code, value in expected.items():
        got = api_kpis[code]
        if value is None:
            assert got is None, code
        else:
            assert got == pytest.approx(value, abs=0.01), code


def kpi_map(items, field="value"):
    return {k["code"]: k[field] for k in items}


def test_summary_default_period_is_last_30_days(api):
    body = api.get("/api/metrics/summary").json()
    date_from, date_to = default_period()
    previous_to = date_from - timedelta(days=1)
    assert body["period"] == {"from": date_from.isoformat(), "to": date_to.isoformat()}
    assert body["previous_period"] == {"from": (previous_to - (date_to - date_from)).isoformat(),
                                       "to": previous_to.isoformat()}
    assert {k["code"] for k in body["kpis"]} == KPI_CODES
    assert all(k["label"] and k["unit"] for k in body["kpis"])


@pytest.mark.parametrize("params,filters", [
    ({}, {}),
    ({"from": days_ago(88), "to": days_ago(43), "channel": "chat", "main_topic": "cargo_no_reconocido"},
     {"channel": "chat", "topics": ["cargo_no_reconocido"]}),
    ({"from": days_ago(26), "to": days_ago(7), "queue": [QUEUE_IDS["Tarjetas"], QUEUE_IDS["Fraude y seguridad"]]},
     {"queues": [QUEUE_IDS["Tarjetas"], QUEUE_IDS["Fraude y seguridad"]]}),
    ({"from": days_ago(57), "to": days_ago(1), "agent": AGENT_IDS["Irene Vidal"], "channel": "voz"},
     {"agents": [AGENT_IDS["Irene Vidal"]], "channel": "voz"}),
])
def test_summary_matches_independent_calculation(api, params, filters):
    body = api.get("/api/metrics/summary", params=params).json()
    period_from = date.fromisoformat(body["period"]["from"])
    period_to = date.fromisoformat(body["period"]["to"])
    prev_from = date.fromisoformat(body["previous_period"]["from"])
    prev_to = date.fromisoformat(body["previous_period"]["to"])
    assert (period_to - period_from) == (prev_to - prev_from)
    assert prev_to == period_from - timedelta(days=1)

    current = expected_kpis(select(period_from, period_to, **filters))
    previous = expected_kpis(select(prev_from, prev_to, **filters))
    assert_kpis_match(kpi_map(body["kpis"]), current)
    assert_kpis_match(kpi_map(body["kpis"], "previous"), previous)
    for k in body["kpis"]:
        cur, prev = current[k["code"]], previous[k["code"]]
        if cur is None or prev is None:
            assert k["delta"] is None
        else:
            assert k["delta"] == pytest.approx(cur - prev, abs=0.01)
        if cur is None or not prev or k["unit"] == "índice":
            assert k["delta_pct"] is None
        else:
            assert k["delta_pct"] == pytest.approx(100 * (cur - prev) / abs(prev), abs=0.05)


def test_summary_compliance_by_check(api):
    body = api.get("/api/metrics/summary", params={"from": days_ago(88), "to": days_ago(1)}).json()
    convs = select(day_ago(88), day_ago(1))
    by_check = {c["code"]: c for c in body["compliance_by_check"]}
    assert set(by_check) == set(convs[0].analysis.compliance)
    for code, item in by_check.items():
        applicable = [c for c in convs if c.analysis.compliance[code] is not None]
        assert item["label"]
        assert item["value"] == pytest.approx(pct(applicable, lambda c: c.analysis.compliance[code]), abs=0.01)


def test_timeseries_by_day_covers_every_day_and_matches(api):
    params = {"kpi": "volume", "granularity": "day", "from": days_ago(26), "to": days_ago(1), "channel": "voz"}
    body = api.get("/api/metrics/timeseries", params=params).json()
    assert len(body["points"]) == 26
    for point in body["points"]:
        day = date.fromisoformat(point["period_start"])
        assert point["period_end"] == point["period_start"]
        assert point["value"] == len(select(day, day, channel="voz"))
    total = api.get("/api/metrics/summary", params={k: v for k, v in params.items() if k not in ("kpi", "granularity")}).json()
    assert sum(p["value"] for p in body["points"]) == kpi_map(total["kpis"])["volume"]


def test_timeseries_by_week_clips_partial_weeks(api):
    # Empieza un miércoles y acaba el día anterior a la referencia: la primera y la última semana son parciales.
    date_from = weekday_on_or_before(day_ago(25), 2)
    date_to = day_ago(1)
    if date_to.weekday() == 6:  # si acaba en domingo, la última semana sería completa: se recorta un día
        date_to -= timedelta(days=1)
    mondays = [date_from + timedelta(days=d) for d in range(1, (date_to - date_from).days + 1)
               if (date_from + timedelta(days=d)).weekday() == 0]
    starts = [date_from, *mondays]
    ends = [m - timedelta(days=1) for m in mondays] + [date_to]
    params = {"kpi": "csat_avg", "granularity": "week", "from": date_from.isoformat(), "to": date_to.isoformat()}
    points = api.get("/api/metrics/timeseries", params=params).json()["points"]
    assert [p["period_start"] for p in points] == [d.isoformat() for d in starts]
    assert [p["period_end"] for p in points] == [d.isoformat() for d in ends]
    assert starts[0].weekday() == 2 and ends[-1].weekday() != 6
    for point in points:
        convs = select(date.fromisoformat(point["period_start"]), date.fromisoformat(point["period_end"]))
        assert point["value"] == pytest.approx(expected_kpis(convs)["csat_avg"], abs=0.01)


@pytest.mark.parametrize("dimension", ["main_topic", "channel", "queue", "agent"])
def test_breakdown_sums_to_total_and_matches(api, dimension):
    params = {"from": days_ago(74), "to": days_ago(1)}
    body = api.get("/api/metrics/breakdown", params={**params, "dimension": dimension}).json()
    items = body["items"]
    volumes = [i["kpis"]["volume"] for i in items]
    assert volumes == sorted(volumes, reverse=True)
    convs = select(day_ago(74), day_ago(1))
    assert sum(volumes) == len(convs)

    attr = {"main_topic": lambda c: c.analysis.main_topic, "channel": lambda c: c.channel,
            "queue": lambda c: c.queue_id, "agent": lambda c: c.agent_id}[dimension]
    groups = defaultdict(list)
    for c in convs:
        groups[attr(c)].append(c)
    assert {i["key"] for i in items} == set(groups)
    top = items[0]
    assert_kpis_match(top["kpis"], expected_kpis(groups[top["key"]]))
    if dimension == "main_topic":
        assert all(i["label"] == MAIN_TOPICS[i["key"]].name for i in items)
    names = {"queue": {v: k for k, v in QUEUE_IDS.items()}, "agent": {v: k for k, v in AGENT_IDS.items()}}
    if dimension in names:
        assert all(i["label"] == names[dimension][i["key"]] for i in items)


def test_filters_by_main_topic_affect_all_metrics(api):
    params = {"from": days_ago(88), "to": days_ago(1), "main_topic": ["comisiones", "cajeros"]}
    body = api.get("/api/metrics/breakdown", params={**params, "dimension": "main_topic"}).json()
    assert {i["key"] for i in body["items"]} == {"comisiones", "cajeros"}


@pytest.mark.parametrize("path,params", [
    ("/api/metrics/breakdown", {"dimension": "color"}),
    ("/api/metrics/timeseries", {"kpi": "inventado"}),
    ("/api/metrics/timeseries", {"kpi": "volume", "granularity": "hora"}),
    ("/api/metrics/summary", {"from": days_ago(17), "to": days_ago(26)}),
    ("/api/metrics/summary", {"channel": "fax"}),
    ("/api/metrics/summary", {"queue": "Tarjetas"}),
    ("/api/metrics/summary", {"agent": "Irene Vidal"}),
    ("/api/metrics/breakdown", {"dimension": "queue", "queue": QUEUE_IDS["Tarjetas"].replace("1QU", "1AG")}),
])
def test_invalid_parameters_return_422(api, path, params):
    assert api.get(path, params=params).status_code == 422


def test_empty_selection_returns_nulls_not_errors(api):
    body = api.get("/api/metrics/summary", params={"agent": ids.stable_id(ids.AGENT, "Nadie Existe")}).json()
    values = kpi_map(body["kpis"])
    assert values["volume"] == 0
    assert values["csat_avg"] is None


@pytest.mark.parametrize("path,params", [
    ("/api/metrics/summary", {"from": days_ago(89), "to": days_ago(1)}),
    ("/api/metrics/timeseries", {"kpi": "fcr_rate", "granularity": "day", "from": days_ago(89), "to": days_ago(1)}),
    ("/api/metrics/breakdown", {"dimension": "agent", "from": days_ago(89), "to": days_ago(1)}),
])
def test_metrics_respond_under_500ms(api, path, params):
    api.get(path, params=params)
    start = time.perf_counter()
    assert api.get(path, params=params).status_code == 200
    assert time.perf_counter() - start < 0.5
