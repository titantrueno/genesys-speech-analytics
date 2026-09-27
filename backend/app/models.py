from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Channel = Literal["voz", "chat"]
Speaker = Literal["cliente", "agente", "bot", "sistema"]
Resolution = Literal["resuelta", "no_resuelta", "escalada"]
ChurnRisk = Literal["bajo", "medio", "alto"]


class Turn(BaseModel):
    speaker: Speaker
    text: str
    offset_s: int
    sentiment: float


class Entity(BaseModel):
    type: Literal["importe", "producto", "fecha", "comercio"]
    value: str


class Analysis(BaseModel):
    summary: str
    main_topic: str
    secondary_topics: list[str]
    sentiment: float
    sentiment_timeline: list[float]
    resolution: Resolution
    csat: float
    effort: float
    churn_risk: ChurnRisk
    compliance: dict[str, bool | None]
    entities: list[Entity]
    keywords: list[str]


class Conversation(BaseModel):
    id: str
    channel: Channel
    started_at: datetime
    duration_s: int
    queue: str
    agent: str
    customer_id: str
    turns: list[Turn]
    analysis: Analysis
