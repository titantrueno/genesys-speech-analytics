from math import ceil
from typing import Literal

from fastapi import Query as QueryParam

from app.data.catalog import MAIN_TOPICS
from app.models import Conversation

SortKey = Literal["date", "duration", "sentiment"]
SortOrder = Literal["asc", "desc"]

SORT_KEYS = {
    "date": lambda c: c.started_at,
    "duration": lambda c: c.duration_s,
    "sentiment": lambda c: c.analysis.sentiment,
}


def list_item(conv: Conversation) -> dict:
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


class PageParams:
    def __init__(
        self,
        page: int = QueryParam(1, ge=1),
        page_size: int = QueryParam(25, ge=1, le=100),
        sort: SortKey = "date",
        order: SortOrder = "desc",
    ):
        self.page, self.page_size, self.sort, self.order = page, page_size, sort, order


def paginate(convs: list[Conversation], params: PageParams) -> dict:
    key = SORT_KEYS[params.sort]
    ordered = sorted(convs, key=lambda c: (key(c), c.id), reverse=params.order == "desc")
    start = (params.page - 1) * params.page_size
    return {
        "total": len(ordered),
        "page": params.page,
        "page_size": params.page_size,
        "pages": ceil(len(ordered) / params.page_size),
        "items": [list_item(c) for c in ordered[start:start + params.page_size]],
    }
