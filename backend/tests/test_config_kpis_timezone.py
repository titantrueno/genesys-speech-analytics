"""KPIs y objetivos (FE005, criterio 8) y zona horaria en el backend (criterio 5)."""
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from app.data.store import get_dataset
from app.services.kpis import KPI_DEFS
from tests.flow_fixtures import days_ago
from tests.test_config_api import GENERAL, as_role, audit, field_errors

PERIOD = {"from": days_ago(30), "to": days_ago(1)}
DASHBOARDS = {"vision-general", "calidad-y-cumplimiento", "experiencia-de-cliente"}


def kpi_config(api, code: str) -> dict:
    return next(k for k in api.get("/api/config").json()["kpis"] if k["code"] == code)


def editable(item: dict) -> dict:
    return {k: item[k] for k in ("target", "green", "amber", "dashboards")}


def put_kpi(api, code: str, **changes):
    return api.put(f"/api/config/kpis/{code}", json={**editable(kpi_config(api, code)), **changes})


def summary_kpi(api, code: str, **params) -> dict:
    body = api.get("/api/metrics/summary", params={**PERIOD, **params}).json()
    return next(k for k in body["kpis"] if k["code"] == code)


# --- KPIs y objetivos ---

def test_every_kpi_has_a_config_with_its_direction_and_dashboards(api):
    body = api.get("/api/config").json()
    assert [k["code"] for k in body["kpis"]] == [k.code for k in KPI_DEFS]
    assert {d["value"] for d in body["options"]["dashboards"]} == DASHBOARDS
    for item in body["kpis"]:
        kpi = next(k for k in KPI_DEFS if k.code == item["code"])
        assert item["higher_is_better"] == kpi.higher_is_better and item["label"] == kpi.label
        assert set(item["dashboards"]) <= DASHBOARDS
    assert kpi_config(api, "compliance_rate")["dashboards"] == ["calidad-y-cumplimiento"]
    assert kpi_config(api, "volume")["green"] is None  # sin umbrales: la tarjeta no se colorea


def test_summary_returns_status_and_target(api):
    item = summary_kpi(api, "aht_s")
    config = kpi_config(api, "aht_s")
    assert item["target"] == config["target"]
    assert item["status"] in {"verde", "ambar", "rojo"}
    assert summary_kpi(api, "volume")["status"] is None


def test_default_thresholds_give_a_mix_of_colours(api):
    body = api.get("/api/metrics/summary", params=PERIOD).json()
    assert {k["status"] for k in body["kpis"]} >= {"verde", "ambar", "rojo"}


@pytest.mark.parametrize("code", ["resolution_rate", "aht_s"])
def test_moving_a_threshold_changes_the_status(api, code):
    value = summary_kpi(api, code)["value"]
    higher = kpi_config(api, code)["higher_is_better"]
    step = 1 if code == "resolution_rate" else 10
    if higher:
        cases = [(value - step, value - 2 * step, "verde"), (value + step, value - step, "ambar"),
                 (value + 2 * step, value + step, "rojo")]
    else:
        cases = [(value + step, value + 2 * step, "verde"), (value - step, value + step, "ambar"),
                 (value - 2 * step, value - step, "rojo")]
    for green, amber, expected in cases:
        response = put_kpi(api, code, green=green, amber=amber)
        assert response.status_code == 200, response.text
        assert summary_kpi(api, code)["status"] == expected, (green, amber)


def test_the_value_on_a_threshold_takes_the_better_colour(api):
    value = summary_kpi(api, "resolution_rate")["value"]
    put_kpi(api, "resolution_rate", green=value, amber=value - 5)
    assert summary_kpi(api, "resolution_rate")["status"] == "verde"


@pytest.mark.parametrize("code,green,amber", [
    ("resolution_rate", 60, 70),   # más es mejor: verde debe ser mayor que ámbar
    ("resolution_rate", 70, 70),
    ("aht_s", 400, 300),           # más es peor: verde debe ser menor que ámbar
])
def test_incoherent_thresholds_are_rejected_per_field(api, code, green, amber):
    errors = field_errors(put_kpi(api, code, green=green, amber=amber))
    assert "amber" in errors
    assert audit(api) == []


@pytest.mark.parametrize("code,changes,field", [
    ("resolution_rate", {"green": 120, "amber": 60}, "green"),
    ("csat_avg", {"green": 4.5, "amber": 0.5}, "amber"),
    ("sentiment_avg", {"target": 2}, "target"),
    ("aht_s", {"green": -1, "amber": 10}, "green"),
    ("resolution_rate", {"green": 70, "amber": None}, "amber"),
    ("resolution_rate", {"dashboards": ["inventado"]}, 0),
    ("resolution_rate", {"dashboards": ["vision-general", "vision-general"]}, "dashboards"),
])
def test_out_of_range_or_incomplete_values_are_rejected(api, code, changes, field):
    assert field in field_errors(put_kpi(api, code, **changes))


def test_unknown_kpi_returns_404(api):
    assert api.put("/api/config/kpis/inventado", json={"target": None, "green": None, "amber": None,
                                                        "dashboards": []}).status_code == 404


def test_a_hidden_kpi_is_not_returned_for_that_dashboard(api):
    params = {"dashboard": "vision-general"}
    shown = [k["code"] for k in api.get("/api/metrics/summary", params={**PERIOD, **params}).json()["kpis"]]
    assert "csat_avg" in shown
    put_kpi(api, "csat_avg", dashboards=["experiencia-de-cliente"])
    shown = [k["code"] for k in api.get("/api/metrics/summary", params={**PERIOD, **params}).json()["kpis"]]
    assert "csat_avg" not in shown
    other = api.get("/api/metrics/summary", params={**PERIOD, "dashboard": "experiencia-de-cliente"}).json()
    assert "csat_avg" in [k["code"] for k in other["kpis"]]
    everything = api.get("/api/metrics/summary", params=PERIOD).json()
    assert len(everything["kpis"]) == len(KPI_DEFS)  # sin dashboard, todos (lo usan el explorador y el drill-down)
    assert api.get("/api/metrics/summary", params={**PERIOD, "dashboard": "otro"}).status_code == 422


def test_kpi_changes_are_audited_and_need_config_edit(api):
    put_kpi(api, "resolution_rate", target=80)
    entry = audit(api, "kpis")[0]
    assert entry["element"] == "Tasa de resolución"
    assert entry["after"]["target"] == 80
    as_role(api, "supervisor")
    assert put_kpi(api, "resolution_rate", target=81).status_code == 403


# --- Zona horaria ---

def late_conversation(hour: int = 21):
    """Una conversación reciente de última hora (hora local del banco), que en Tokio ya es el día siguiente."""
    return next(c for c in reversed(get_dataset())
                if c.started_at.hour >= hour and c.started_at.date().isoformat() < days_ago(2))


def listing_ids(api, day: str) -> set[str]:
    body = api.get("/api/conversations", params={"from": day, "to": day, "page_size": 100}).json()
    return {i["id"] for i in body["items"]}


def test_started_at_carries_the_bank_timezone(api):
    conv = get_dataset()[0]
    assert conv.started_at.tzinfo is not None
    assert conv.started_at.utcoffset() == conv.started_at.astimezone(ZoneInfo("Europe/Madrid")).utcoffset()
    item = api.get(f"/api/conversations/{conv.id}").json()
    assert item["started_at"].endswith(("+01:00", "+02:00"))


def test_days_are_computed_in_the_configured_timezone(api):
    conv = late_conversation()
    local_day = conv.started_at.date().isoformat()
    next_day = (conv.started_at.date() + timedelta(days=1)).isoformat()
    assert conv.id in listing_ids(api, local_day)
    assert api.put("/api/config/general", json={**GENERAL, "timezone": "Asia/Tokyo"}).status_code == 200
    assert conv.id not in listing_ids(api, local_day)
    assert conv.id in listing_ids(api, next_day)


def test_explorer_and_kpis_follow_the_timezone(api):
    conv = late_conversation()
    next_day = (conv.started_at.date() + timedelta(days=1)).isoformat()
    api.put("/api/config/general", json={**GENERAL, "timezone": "Asia/Tokyo"})
    run = api.post("/api/query/run", params={"page_size": 100},
                   json={"from": next_day, "to": next_day, "root": {"op": "and", "conditions": []}}).json()
    assert conv.id in {i["id"] for i in run["items"]}
    volume = next(k for k in api.get("/api/metrics/summary", params={"from": next_day, "to": next_day}).json()["kpis"]
                  if k["code"] == "volume")["value"]
    assert volume == run["total"] == len(listing_ids(api, next_day))


@pytest.mark.parametrize("timezone", ["Europe/Madrid", "UTC", "Asia/Tokyo", "America/Los_Angeles"])
def test_daily_series_and_drilldown_agree_in_any_timezone(api, timezone):
    api.put("/api/config/general", json={**GENERAL, "timezone": timezone})
    params = {"kpi": "volume", "granularity": "day", "from": days_ago(14), "to": days_ago(1)}
    points = api.get("/api/metrics/timeseries", params=params).json()["points"]
    for point in points:
        day = point["period_start"]
        listing = api.get("/api/conversations", params={"from": day, "to": day}).json()
        assert listing["total"] == point["value"], (timezone, day)
    total = api.get("/api/metrics/summary", params={"from": days_ago(14), "to": days_ago(1)}).json()["kpis"][0]
    assert sum(p["value"] for p in points) == total["value"]


def test_changing_the_timezone_does_not_change_the_dataset(api):
    before = [(c.id, c.started_at) for c in get_dataset()]
    api.put("/api/config/general", json={**GENERAL, "timezone": "Pacific/Auckland"})
    assert [(c.id, c.started_at) for c in get_dataset()] == before
