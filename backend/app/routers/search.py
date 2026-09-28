from datetime import date
from functools import cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import ids
from app.auth import require_permission
from app.data.store import conversation_index, get_dataset
from app.privacy.masking import masked, shown
from app.search.engine import Hit, SearchEngine, best_per_conversation
from app.search.text import matching_terms, tokenize
from app.search.tfidf import TfidfEngine
from app.services.filters import ConversationFilters, conversation_filters
from app.services.listing import list_item

router = APIRouter(prefix="/api/search", tags=["search"], dependencies=[Depends(require_permission("search:use"))])

MAX_QUERY = 500
SIMILAR_COUNT = 10


@cache
def build_default_engine() -> SearchEngine:
    # El índice nunca contiene datos personales, esté o no activado el enmascarado (FE005).
    return TfidfEngine([masked(conv) for conv in get_dataset()])


def get_search_engine() -> SearchEngine:
    """Punto de sustitución del motor (ver ADR-005): la API solo conoce la interfaz `SearchEngine`."""
    return build_default_engine()


def search_filters(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    channel: Literal["voz", "chat"] | None = None,
    queue: list[str] = Query(default_factory=list),
) -> ConversationFilters:
    return conversation_filters(date_from, date_to, channel, queue, [], [])


def _score(hit: Hit) -> float:
    return round(hit.score, 4)


def _result(hit: Hit, terms: list[str]) -> dict:
    fragment = hit.fragment
    conv = shown(conversation_index()[fragment.conversation_id])
    return {
        "conversation_id": conv.id,
        "start_turn": fragment.start_turn,
        "end_turn": fragment.end_turn,
        "score": _score(hit),
        "turns": [{"index": i, "speaker": conv.turns[i].speaker, "text": conv.turns[i].text} for i in fragment.turns],
        "highlights": matching_terms(fragment.text, terms),
        "conversation": list_item(conv),
    }


@router.get("/semantic")
def semantic(
    q: str = Query(min_length=1, max_length=MAX_QUERY),
    filters: ConversationFilters = Depends(search_filters),
    min_score: float = Query(0, ge=0, le=1, allow_inf_nan=False),
    group: Literal["conversation", "fragment"] = "conversation",
    limit: int = Query(20, ge=1, le=100),
    engine: SearchEngine = Depends(get_search_engine),
) -> dict:
    if not q.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La consulta no puede estar vacía")
    candidates = {conv.id for conv in filters.apply(get_dataset())}
    matched = engine.search(q, candidates)
    hits = [hit for hit in matched if _score(hit) >= min_score]
    if group == "conversation":
        hits = best_per_conversation(hits)
    expansions = engine.expansions(q)
    terms = tokenize(q) + [w for expression in expansions for w in tokenize(expression)]
    return {
        "query": q,
        "expansions": expansions,
        "period": {"from": filters.date_from.isoformat(), "to": filters.date_to.isoformat()},
        "total": len(hits),
        # Mejor puntuación antes del umbral, para situar el control en la UI (criterio 19).
        "max_score": _score(matched[0]) if matched else None,
        "results": [_result(hit, terms) for hit in hits[:limit]],
    }


@router.get("/similar/{conversation_id}")
def similar(conversation_id: str, engine: SearchEngine = Depends(get_search_engine)) -> dict:
    conv = conversation_index().get(ids.normalize(conversation_id))
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversación no encontrada")
    return {
        "conversation_id": conv.id,
        "results": [{"conversation_id": cid, "score": round(score, 4), "conversation": list_item(conversation_index()[cid])}
                    for cid, score in engine.similar(conv.id, SIMILAR_COUNT)],
    }
