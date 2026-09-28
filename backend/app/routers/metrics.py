from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends

from app.auth import require_permission
from app.config.kpis import DASHBOARDS
from app.config.store import current_zone, get_config, local_day, topic_name
from app.data.store import followup_index, get_dataset
from app.services.filters import ConversationFilters, conversation_filters
from app.services.kpis import KPI_DEFS, compliance_by_check, compute_kpi, compute_kpis, delta, delta_pct, round_value

router = APIRouter(prefix="/api/metrics", tags=["metrics"],
                   dependencies=[Depends(require_permission("dashboards:view"))])

KpiCode = Literal[
    "volume", "aht_s", "sentiment_avg", "negative_pct", "resolution_rate", "escalation_rate", "fcr_rate",
    "csat_avg", "effort_avg", "compliance_rate", "churn_high_pct", "first_response_s", "avg_turns",
]
DIMENSIONS = {
    "main_topic": lambda c: c.analysis.main_topic,
    "channel": lambda c: c.channel,
    "queue": lambda c: c.queue_id,
    "agent": lambda c: c.agent_id,
}
LABELS = {
    "main_topic": lambda c: topic_name(c.analysis.main_topic),
    "channel": lambda c: c.channel,
    "queue": lambda c: c.queue,
    "agent": lambda c: c.agent,
}


def _period(date_from: date, date_to: date) -> dict:
    return {"from": date_from.isoformat(), "to": date_to.isoformat()}


@router.get("/summary")
def summary(
    filters: ConversationFilters = Depends(conversation_filters),
    dashboard: Literal[tuple(DASHBOARDS)] | None = None,  # type: ignore[valid-type]
) -> dict:
    """KPIs del periodo y del anterior, con su estado según los umbrales. Con `dashboard`, solo los que se muestran en él."""
    targets = get_config().kpis
    dataset, followups = get_dataset(), followup_index()
    prev_from, prev_to = filters.previous_period()
    current_convs = filters.apply(dataset)
    current = compute_kpis(current_convs, followups, rounded=False)
    previous = compute_kpis(filters.apply(dataset, prev_from, prev_to), followups, rounded=False)
    return {
        "period": _period(filters.date_from, filters.date_to),
        "previous_period": _period(prev_from, prev_to),
        "kpis": [
            {"code": k.code, "label": k.label, "unit": k.unit, "higher_is_better": k.higher_is_better,
             "value": round_value(current[k.code]), "previous": round_value(previous[k.code]),
             "delta": delta(current[k.code], previous[k.code]),
             "delta_pct": delta_pct(current[k.code], previous[k.code], k.unit),
             "target": targets[k.code].target,
             "status": targets[k.code].status(round_value(current[k.code]), k.higher_is_better)}
            for k in KPI_DEFS if dashboard is None or dashboard in targets[k.code].dashboards
        ],
        "compliance_by_check": compliance_by_check(current_convs),
    }


def _buckets(date_from: date, date_to: date, granularity: str):
    start = date_from
    while start <= date_to:
        end = start if granularity == "day" else min(start + timedelta(days=6 - start.weekday()), date_to)
        yield start, end
        start = end + timedelta(days=1)


@router.get("/timeseries")
def timeseries(
    kpi: KpiCode,
    granularity: Literal["day", "week"] = "day",
    filters: ConversationFilters = Depends(conversation_filters),
) -> dict:
    convs, followups = filters.apply(get_dataset()), followup_index()
    zone = current_zone()
    by_day = defaultdict(list)
    for c in convs:
        by_day[local_day(c.started_at, zone)].append(c)
    points = []
    for start, end in _buckets(filters.date_from, filters.date_to, granularity):
        bucket = [c for offset in range((end - start).days + 1) for c in by_day[start + timedelta(days=offset)]]
        points.append({"period_start": start.isoformat(), "period_end": end.isoformat(),
                       "value": compute_kpi(kpi, bucket, followups)})
    return {"kpi": kpi, "granularity": granularity, "period": _period(filters.date_from, filters.date_to),
            "points": points}


@router.get("/breakdown")
def breakdown(
    dimension: Literal["main_topic", "channel", "queue", "agent"],
    filters: ConversationFilters = Depends(conversation_filters),
) -> dict:
    convs, followups = filters.apply(get_dataset()), followup_index()
    groups = defaultdict(list)
    for c in convs:
        groups[DIMENSIONS[dimension](c)].append(c)
    items = [
        {"key": key, "label": LABELS[dimension](group[0]), "kpis": compute_kpis(group, followups)}
        for key, group in groups.items()
    ]
    items.sort(key=lambda i: (-i["kpis"]["volume"], i["label"]))
    return {"dimension": dimension, "period": _period(filters.date_from, filters.date_to), "items": items}
