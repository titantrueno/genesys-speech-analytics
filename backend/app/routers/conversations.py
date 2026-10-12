from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_permission
from app import ids
from app.config.store import get_config, topic_name
from app.config.compliance import active_checks, effective_compliance
from app.data.repository import active_repository
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
    body = shown(conv).model_dump()
    # Sin analizar no hay cumplimiento que mostrar (un «no aplica» engañaría); la UI dice «Análisis pendiente».
    body["analysis"]["compliance"] = {} if conv.analysis.pending else effective_compliance(conv)
    return {**body, "main_topic_label": topic_name(conv.analysis.main_topic)}


@router.get("/catalog", dependencies=[Depends(require_permission("dashboards:view", "conversations:view"))])
def catalog() -> dict:
    repository = active_repository()
    return {
        "reference_date": reference_date().isoformat(),
        # El front adapta listado y filtros al origen (FE012); lo leen todos los roles con acceso a datos.
        "origin": repository.origin,
        "channels": [{"code": "voz", "label": "Voz"}, {"code": "chat", "label": "Chat"}],
        "queues": [{"id": qid, "name": name} for qid, name in repository.queues()],
        "agents": [{"id": aid, "name": name, "queue_id": qid, "queue": queue}
                   for aid, name, qid, queue in repository.agents()],
        # Incluye los desactivados, para poner nombre a sus filtros; el front solo ofrece los activos (FE005).
        "main_topics": [{"code": t.code, "name": t.name, "active": t.active} for t in get_config().main_topics.values()],
        "compliance_checks": [{"code": c.code, "label": c.name} for c in active_checks()],
        "resolutions": [{"code": "resuelta", "label": "Resuelta"}, {"code": "no_resuelta", "label": "No resuelta"},
                        {"code": "escalada", "label": "Escalada"}],
        "churn_risks": [{"code": "bajo", "label": "Bajo"}, {"code": "medio", "label": "Medio"},
                        {"code": "alto", "label": "Alto"}],
    }
