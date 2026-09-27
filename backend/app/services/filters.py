from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from fastapi import HTTPException, Query, status

from app.data.store import reference_date
from app.models import Conversation

DEFAULT_PERIOD_DAYS = 30


@dataclass
class ConversationFilters:
    date_from: date
    date_to: date
    channel: str | None = None
    queues: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    main_topics: list[str] = field(default_factory=list)

    def matches(self, conv: Conversation, date_from: date | None = None, date_to: date | None = None) -> bool:
        day = conv.started_at.date()
        return (
            (date_from or self.date_from) <= day <= (date_to or self.date_to)
            and (self.channel is None or conv.channel == self.channel)
            and (not self.queues or conv.queue in self.queues)
            and (not self.agents or conv.agent in self.agents)
            and (not self.main_topics or conv.analysis.main_topic in self.main_topics)
        )

    def apply(self, convs, date_from: date | None = None, date_to: date | None = None) -> list[Conversation]:
        return [c for c in convs if self.matches(c, date_from, date_to)]

    def previous_period(self) -> tuple[date, date]:
        length = self.date_to - self.date_from
        prev_to = self.date_from - timedelta(days=1)
        return prev_to - length, prev_to


def conversation_filters(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    channel: Literal["voz", "chat"] | None = None,
    queue: list[str] = Query(default_factory=list),
    agent: list[str] = Query(default_factory=list),
    main_topic: list[str] = Query(default_factory=list),
) -> ConversationFilters:
    date_to = date_to or reference_date() - timedelta(days=1)
    date_from = date_from or date_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    if date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="'from' debe ser anterior o igual a 'to'")
    return ConversationFilters(date_from, date_to, channel, queue, agent, main_topic)
