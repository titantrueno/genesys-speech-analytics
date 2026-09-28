"""API de flujos de insights (FE004). Lecturas con `flows:view`; escrituras y ejecuciones con `flows:edit`."""
import copy
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.auth import User, require_permission
from app.data.store import get_dataset
from app.flows import catalog
from app.flows.model import Graph, GraphError, parse_graph
from app.flows.rules import validate
from app.flows.store import Flow, get_flow_store
from app.query.engine import run_query
from app.query.model import QueryError, parse_query

router = APIRouter(prefix="/api/flows", tags=["flows"])

VIEW = require_permission("flows:view")
EDIT = require_permission("flows:edit")


class FlowName(BaseModel):
    name: str = Field(min_length=1, max_length=catalog.MAX_FLOW_NAME)


class EstimateIn(BaseModel):
    query: dict[str, Any]
    size: int | None = Field(None, ge=1, le=catalog.MAX_SAMPLE_SIZE)


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="El nombre no puede estar vacío")
    return cleaned


def _flow(flow_id: str) -> Flow:
    flow = get_flow_store().get(flow_id)
    if flow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Flujo no encontrado")
    return flow


def parsed_graph(payload: Any = Body(...)) -> Graph:
    try:
        return parse_graph(payload)
    except GraphError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors) from None


def _summary(flow: Flow) -> dict:
    return {**flow.summary(), "last_run": None}


@router.get("", dependencies=[Depends(VIEW)])
def list_flows() -> dict:
    return {"items": [_summary(flow) for flow in get_flow_store().list()]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_flow(body: FlowName, user: User = Depends(EDIT)) -> dict:
    return get_flow_store().create(user, _clean_name(body.name)).to_dict()


@router.get("/catalog", dependencies=[Depends(VIEW)])
def flow_catalog() -> dict:
    return {
        "node_types": catalog.as_options(catalog.NODE_TYPES),
        "sampling_methods": catalog.as_options(catalog.SAMPLING_METHODS),
        "strata": catalog.as_options(catalog.STRATA),
        "order_keys": catalog.as_options(catalog.ORDER_KEYS),
        "orders": catalog.as_options(catalog.ORDERS),
        "models": catalog.as_options(catalog.MODELS),
        "variables": catalog.as_options(catalog.VARIABLES),
        "output_formats": catalog.as_options(catalog.OUTPUT_FORMATS),
        "field_types": catalog.as_options(catalog.FIELD_TYPES),
        "output_kinds": catalog.as_options(catalog.OUTPUT_KINDS),
        "aggregations": catalog.as_options(catalog.AGGREGATIONS),
        "limits": {
            "max_sample_size": catalog.MAX_SAMPLE_SIZE, "max_template": catalog.MAX_TEMPLATE,
            "max_labels": catalog.MAX_LABELS, "max_label": catalog.MAX_LABEL, "max_fields": catalog.MAX_FIELDS,
            "max_field_name": catalog.MAX_FIELD_NAME, "max_destination": catalog.MAX_DESTINATION,
            "max_flow_name": catalog.MAX_FLOW_NAME, "max_nodes": catalog.MAX_NODES, "max_edges": catalog.MAX_EDGES,
        },
    }


@router.post("/validate", dependencies=[Depends(VIEW)])
def validate_graph(graph: Graph = Depends(parsed_graph)) -> dict:
    issues = validate(graph)
    return {"valid": not issues, "issues": [issue.to_dict() for issue in issues]}


@router.post("/sampling/estimate", dependencies=[Depends(VIEW)])
def estimate(body: EstimateIn) -> dict:
    try:
        query = parse_query(copy.deepcopy(body.query))
    except QueryError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors) from None
    available = len(run_query(query, get_dataset()))
    return {
        "available": available,
        "sample_size": None if body.size is None else min(body.size, available),
        "period": {"from": query.date_from.isoformat(), "to": query.date_to.isoformat()},
    }


@router.get("/{flow_id}", dependencies=[Depends(VIEW)])
def get_flow(flow_id: str) -> dict:
    return _flow(flow_id).to_dict()


@router.patch("/{flow_id}", dependencies=[Depends(EDIT)])
def rename_flow(flow_id: str, body: FlowName) -> dict:
    flow = _flow(flow_id)
    return get_flow_store().rename(flow, _clean_name(body.name)).to_dict()


@router.put("/{flow_id}/graph", dependencies=[Depends(EDIT)])
def save_graph(flow_id: str, graph: Graph = Depends(parsed_graph)) -> dict:
    flow = _flow(flow_id)
    id_map = get_flow_store().save_graph(flow, graph)
    return {**flow.to_dict(), "id_map": id_map}


@router.post("/{flow_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_flow(flow_id: str, user: User = Depends(EDIT)) -> dict:
    return get_flow_store().duplicate(_flow(flow_id), user).to_dict()


@router.delete("/{flow_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(EDIT)])
def delete_flow(flow_id: str) -> Response:
    get_flow_store().delete(_flow(flow_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
