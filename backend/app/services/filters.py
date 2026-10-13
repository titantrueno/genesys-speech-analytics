from dataclasses import dataclass, field
from datetime import date, timedelta, tzinfo
from typing import Literal

from fastapi import Depends, HTTPException, Query, status

from app import ids
from app.config.compliance import has_compliance, is_compliant
from app.config.store import current_zone, local_day
from app.data.store import default_period_end, followup_index
from app.models import Conversation

DEFAULT_PERIOD_DAYS = 30


def phone_digits(value: str | None) -> str:
    """Número sin espacios, guiones ni prefijo de España (`+34`, `0034`): «+34 675 075 376» y «675075376» coinciden."""
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    for prefix in ("0034", "34"):
        if digits.startswith(prefix) and len(digits) == len(prefix) + 9:
            return digits[len(prefix):]
    return digits


def same_phone(ani: str | None, wanted: str) -> bool:
    return bool(ani) and phone_digits(ani) == phone_digits(wanted) != ""


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
    phone: str | None = None  # ANI exacto, con o sin prefijo +34 (FE012)
    external_tag: str | None = None  # `externalTag` exacto (FE012)

    def matches(self, conv: Conversation, date_from: date | None = None, date_to: date | None = None,
                zone: tzinfo | None = None) -> bool:
        day = local_day(conv.started_at, zone)
        return (
            (date_from or self.date_from) <= day <= (date_to or self.date_to)
            and (self.channel is None or conv.channel == self.channel)
            and (not self.queues or conv.queue_id in self.queues)
            and (not self.agents or conv.agent_id in self.agents)
            and (not self.main_topics or conv.analysis.main_topic in self.main_topics)
            and (not self.resolutions or conv.analysis.resolution in self.resolutions)
            and (not self.churn_risks or conv.analysis.churn_risk in self.churn_risks)
            and (self.sentiment_lt is None
                 or (conv.analysis.sentiment is not None and conv.analysis.sentiment < self.sentiment_lt))
            # Un campo sin analizar no cumple ninguna condición (FE012, criterio 10), campo a campo (FE014).
            and (self.compliant is None or (has_compliance(conv) and is_compliant(conv) == self.compliant))
            and (self.repeat_contact is None
                 or (conv.analysis.resolution is not None and followup_index()[conv.id] == self.repeat_contact))
            and (self.phone is None or (conv.genesys is not None and same_phone(conv.genesys.ani, self.phone)))
            and (self.external_tag is None
                 or (conv.genesys is not None and (conv.genesys.external_tag or "").casefold()
                     == self.external_tag.strip().casefold()))
        )

    def apply(self, convs, date_from: date | None = None, date_to: date | None = None) -> list[Conversation]:
        zone = current_zone()
        return [c for c in convs if self.matches(c, date_from, date_to, zone)]

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
    date_to = date_to or default_period_end()
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
    phone: str | None = Query(None, max_length=30),
    external_tag: str | None = Query(None, max_length=200),
) -> ConversationFilters:
    base.resolutions = list(resolution)
    base.churn_risks = list(churn_risk)
    base.sentiment_lt = sentiment_lt
    base.compliant = compliant
    base.repeat_contact = repeat_contact
    base.phone = phone.strip() if phone and phone.strip() else None
    base.external_tag = external_tag if external_tag and external_tag.strip() else None
    return base
