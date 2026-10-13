from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Channel = Literal["voz", "chat"]
Speaker = Literal["cliente", "agente", "bot", "sistema"]
Resolution = Literal["resuelta", "no_resuelta", "escalada"]
ChurnRisk = Literal["bajo", "medio", "alto"]


class Turn(BaseModel):
    speaker: Speaker
    text: str
    offset_s: int
    sentiment: float | None
    delivered: bool = True  # un mensaje de chat no entregado conserva su texto (FE011)


class Entity(BaseModel):
    type: Literal["importe", "producto", "fecha", "comercio"]
    value: str


class Analysis(BaseModel):
    """Análisis de la plataforma. Con `pending`, los campos que aún no existen son `None` (FE012): quien los lee los
    trata como vacíos, nunca como 0."""
    summary: str
    main_topic: str | None
    secondary_topics: list[str]
    sentiment: float | None
    sentiment_timeline: list[float]
    resolution: Resolution | None
    csat: float | None
    effort: float | None
    churn_risk: ChurnRisk | None
    compliance: dict[str, bool | None]
    entities: list[Entity]
    keywords: list[str]
    pending: bool = False


class GenesysInfo(BaseModel):
    """Analytics that Genesys gives for a real conversation (FE011): it only exists in the `real` origin."""
    genesys_id: str
    direction: str | None = None
    ani: str | None = None
    dnis: str | None = None
    external_tag: str | None = None
    transcript_quality: str
    disconnect_type: str | None = None
    transferred: bool = False
    reconnected: bool = False
    contained_in_bot: bool = False
    derived_to_agent: bool = False
    abandoned_in_queue: bool = False
    undelivered_messages: int = 0
    customer_sentiment: float | None = None
    mos: float | None = None
    metrics: dict[str, Any] = {}
    segments: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    divisions: list[dict[str, Any]] = []


class Conversation(BaseModel):
    id: str
    channel: Channel
    started_at: datetime
    duration_s: int
    queue_id: str | None
    queue: str | None
    agent_id: str | None
    agent: str | None
    customer_id: str | None
    turns: list[Turn]
    analysis: Analysis
    genesys: GenesysInfo | None = None
