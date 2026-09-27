from collections import Counter
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query as QueryParam, Response, status

from pydantic import BaseModel, Field

from app.auth import User, require_permission
from app.data.store import followup_index, get_dataset, reference_date
from app.query.engine import run_query
from app.query.saved import SavedQuery, get_saved_store
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


@router.get("/suggest")
def suggest(
    field: str,
    date_from: date | None = QueryParam(None, alias="from"),
    date_to: date | None = QueryParam(None, alias="to"),
) -> dict:
    fdef = FIELDS.get(field)
    if fdef is None or fdef.type != "categorical":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"'{field}' no es un campo categórico")
    default_from, default_to = default_period()
    date_from, date_to = date_from or default_from, date_to or default_to
    if date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="'from' debe ser anterior o igual a 'to'")
    counts: Counter[str] = Counter()
    for conv in get_dataset():
        if date_from <= conv.started_at.date() <= date_to:
            value = fdef.extract(conv)
            counts.update(set(value) if fdef.multi_valued else [value])
    labels = dict(fdef.values)
    values = [{"value": v, "label": labels.get(v, v), "count": n} for v, n in counts.items()]
    values.sort(key=lambda item: (-item["count"], item["label"]))
    return {"field": field, "period": {"from": date_from.isoformat(), "to": date_to.isoformat()}, "values": values}


EXPLORER = require_permission("explorer:use")


class SavedQueryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    query: dict


class SavedQueryPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    query: dict | None = None


def _canonical(payload: dict) -> dict:
    try:
        parsed = parse_query(payload)
    except QueryError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors) from None
    canonical = parsed.model_dump(mode="json", by_alias=True)
    for key in ("from", "to"):
        if key not in payload:
            canonical.pop(key, None)
    return canonical


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El nombre no puede estar vacío")
    return cleaned


def _owned(query_id: str, user: User) -> SavedQuery:
    item = get_saved_store().get(user.id, query_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Consulta guardada no encontrada")
    return item


@router.get("/saved")
def list_saved(user: User = Depends(EXPLORER)) -> dict:
    return {"items": [q.to_dict() for q in get_saved_store().list_for(user.id)]}


@router.post("/saved", status_code=status.HTTP_201_CREATED)
def create_saved(body: SavedQueryIn, user: User = Depends(EXPLORER)) -> dict:
    return get_saved_store().create(user.id, _clean_name(body.name), _canonical(body.query)).to_dict()


@router.get("/saved/{query_id}")
def get_saved(query_id: str, user: User = Depends(EXPLORER)) -> dict:
    return _owned(query_id, user).to_dict()


@router.patch("/saved/{query_id}")
def update_saved(query_id: str, body: SavedQueryPatch, user: User = Depends(EXPLORER)) -> dict:
    item = _owned(query_id, user)
    name = _clean_name(body.name) if body.name is not None else None
    query = _canonical(body.query) if body.query is not None else None
    return get_saved_store().update(item, name, query).to_dict()


@router.delete("/saved/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved(query_id: str, user: User = Depends(EXPLORER)) -> Response:
    get_saved_store().delete(_owned(query_id, user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
