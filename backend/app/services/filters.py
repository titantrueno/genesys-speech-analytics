from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from fastapi import Depends, HTTPException, Query, status

from app import ids
from app.data.store import followup_index, reference_date
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
    resolutions: list[str] = field(default_factory=list)
    churn_risks: list[str] = field(default_factory=list)
    sentiment_lt: float | None = None
    compliant: bool | None = None
    repeat_contact: bool | None = None

    def matches(self, conv: Conversation, date_from: date | None = None, date_to: date | None = None) -> bool:
        day = conv.started_at.date()
        return (
            (date_from or self.date_from) <= day <= (date_to or self.date_to)
            and (self.channel is None or conv.channel == self.channel)
            and (not self.queues or conv.queue_id in self.queues)
            and (not self.agents or conv.agent_id in self.agents)
            and (not self.main_topics or conv.analysis.main_topic in self.main_topics)
            and (not self.resolutions or conv.analysis.resolution in self.resolutions)
            and (not self.churn_risks or conv.analysis.churn_risk in self.churn_risks)
            and (self.sentiment_lt is None or conv.analysis.sentiment < self.sentiment_lt)
            and (self.compliant is None or is_compliant(conv) == self.compliant)
            and (self.repeat_contact is None or followup_index()[conv.id] == self.repeat_contact)
        )

    def apply(self, convs, date_from: date | None = None, date_to: date | None = None) -> list[Conversation]:
        return [c for c in convs if self.matches(c, date_from, date_to)]

    def previous_period(self) -> tuple[date, date]:
        length = self.date_to - self.date_from
        prev_to = self.date_from - timedelta(days=1)
        return prev_to - length, prev_to


def is_compliant(conv: Conversation) -> bool:
    return all(v for v in conv.analysis.compliance.values() if v is not None)


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
    return ConversationFilters(date_from, date_to, channel, _entity_ids(queue, ids.QUEUE, "queue"),
                               _entity_ids(agent, ids.AGENT, "agent"), main_topic)


def _entity_ids(values: list[str], prefix: str, param: str) -> list[str]:
    normalized = [ids.normalize(v) for v in values]
    invalid = [v for v in normalized if not ids.is_valid(v, prefix)]
    if invalid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail=f"'{param}' espera identificadores {prefix}-UUID: {', '.join(invalid)}")
    return normalized


def conversation_list_filters(
    base: ConversationFilters = Depends(conversation_filters),
    resolution: list[Literal["resuelta", "no_resuelta", "escalada"]] = Query(default_factory=list),
    churn_risk: list[Literal["bajo", "medio", "alto"]] = Query(default_factory=list),
    sentiment_lt: float | None = Query(None, ge=-1, le=1),
    compliant: bool | None = None,
    repeat_contact: bool | None = None,
) -> ConversationFilters:
    base.resolutions = list(resolution)
    base.churn_risks = list(churn_risk)
    base.sentiment_lt = sentiment_lt
    base.compliant = compliant
    base.repeat_contact = repeat_contact
    return base
