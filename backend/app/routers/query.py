from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.auth import require_permission
from app.data.store import followup_index, get_dataset, reference_date
from app.query.engine import run_query
from app.query.fields import FIELDS
from app.query.model import Query, QueryError, default_period, parse_query
from app.services.kpis import KPI_DEFS, compute_kpis
from app.services.listing import PageParams, paginate

router = APIRouter(prefix="/api/query", tags=["query"], dependencies=[Depends(require_permission("explorer:use"))])


@router.get("/schema")
def schema() -> dict:
    date_from, date_to = default_period()
    return {
        "fields": [f.schema() for f in FIELDS.values()],
        "reference_date": reference_date().isoformat(),
        "default_period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
    }


def parsed_query(payload: dict = Body(...)) -> Query:
    try:
        return parse_query(payload)
    except QueryError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors) from None


@router.post("/run")
def run(query: Query = Depends(parsed_query), page: PageParams = Depends()) -> dict:
    matched = run_query(query, get_dataset())
    values = compute_kpis(matched, followup_index())
    return {
        "period": {"from": query.date_from.isoformat(), "to": query.date_to.isoformat()},
        "kpis": [{"code": k.code, "label": k.label, "unit": k.unit, "higher_is_better": k.higher_is_better,
                  "value": values[k.code]} for k in KPI_DEFS],
        **paginate(matched, page),
    }
