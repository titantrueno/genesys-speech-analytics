from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_permission
from app import ids
from app.data.catalog import AGENT_IDS, AGENTS_BY_QUEUE, COMPLIANCE_CHECKS, MAIN_TOPICS, QUEUE_IDS, QUEUES
from app.data.store import conversation_index, get_dataset, reference_date
from app.privacy.masking import shown
from app.services.filters import ConversationFilters, conversation_list_filters
from app.services.listing import PageParams, paginate

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations", dependencies=[Depends(require_permission("conversations:view"))])
def list_conversations(
    filters: ConversationFilters = Depends(conversation_list_filters),
    page: PageParams = Depends(),
) -> dict:
    return paginate(filters.apply(get_dataset()), page)


@router.get("/conversations/{conversation_id}", dependencies=[Depends(require_permission("conversations:view"))])
def get_conversation(conversation_id: str) -> dict:
    conv = conversation_index().get(ids.normalize(conversation_id))
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")
    return {**shown(conv).model_dump(), "main_topic_label": MAIN_TOPICS[conv.analysis.main_topic].name}


@router.get("/catalog", dependencies=[Depends(require_permission("dashboards:view", "conversations:view"))])
def catalog() -> dict:
    return {
        "reference_date": reference_date().isoformat(),
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
