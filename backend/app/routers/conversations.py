from math import ceil
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import require_permission
from app import ids
from app.data.catalog import AGENT_IDS, AGENTS_BY_QUEUE, COMPLIANCE_CHECKS, MAIN_TOPICS, QUEUE_IDS, QUEUES
from app.data.store import conversation_index, get_dataset
from app.services.filters import ConversationFilters, conversation_list_filters

router = APIRouter(prefix="/api", tags=["conversations"])

SORT_KEYS = {
    "date": lambda c: c.started_at,
    "duration": lambda c: c.duration_s,
    "sentiment": lambda c: c.analysis.sentiment,
}


def _list_item(conv) -> dict:
    return {
        "id": conv.id,
        "started_at": conv.started_at,
        "channel": conv.channel,
        "queue_id": conv.queue_id,
        "queue": conv.queue,
        "agent_id": conv.agent_id,
        "agent": conv.agent,
        "main_topic": conv.analysis.main_topic,
        "main_topic_label": MAIN_TOPICS[conv.analysis.main_topic].name,
        "summary": conv.analysis.summary,
        "sentiment": conv.analysis.sentiment,
        "resolution": conv.analysis.resolution,
        "csat": conv.analysis.csat,
        "duration_s": conv.duration_s,
    }


@router.get("/conversations", dependencies=[Depends(require_permission("conversations:view"))])
def list_conversations(
    filters: ConversationFilters = Depends(conversation_list_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: Literal["date", "duration", "sentiment"] = "date",
    order: Literal["asc", "desc"] = "desc",
) -> dict:
    convs = filters.apply(get_dataset())
    key = SORT_KEYS[sort]
    convs.sort(key=lambda c: (key(c), c.id), reverse=order == "desc")
    start = (page - 1) * page_size
    return {
        "total": len(convs),
        "page": page,
        "page_size": page_size,
        "pages": ceil(len(convs) / page_size),
        "items": [_list_item(c) for c in convs[start:start + page_size]],
    }


@router.get("/conversations/{conversation_id}", dependencies=[Depends(require_permission("conversations:view"))])
def get_conversation(conversation_id: str) -> dict:
    conv = conversation_index().get(ids.normalize(conversation_id))
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")
    return {**conv.model_dump(), "main_topic_label": MAIN_TOPICS[conv.analysis.main_topic].name}


@router.get("/catalog", dependencies=[Depends(require_permission("dashboards:view", "conversations:view"))])
def catalog() -> dict:
    return {
        "channels": [{"code": "voz", "label": "Voz"}, {"code": "chat", "label": "Chat"}],
        "queues": [{"id": QUEUE_IDS[name], "name": name} for name in QUEUES],
        "agents": [{"id": AGENT_IDS[name], "name": name, "queue_id": QUEUE_IDS[queue], "queue": queue}
                   for queue, names in AGENTS_BY_QUEUE.items() for name in names],
        "main_topics": [{"code": t.code, "name": t.name} for t in MAIN_TOPICS.values()],
        "compliance_checks": [{"code": code, "label": label} for code, label in COMPLIANCE_CHECKS.items()],
        "resolutions": [{"code": "resuelta", "label": "Resuelta"}, {"code": "no_resuelta", "label": "No resuelta"},
                        {"code": "escalada", "label": "Escalada"}],
        "churn_risks": [{"code": "bajo", "label": "Bajo"}, {"code": "medio", "label": "Medio"},
                        {"code": "alto", "label": "Alto"}],
    }
