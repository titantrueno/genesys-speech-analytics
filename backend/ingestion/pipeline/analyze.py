"""Etapa `analizar` del pipeline (FE011, criterio 11).

El análisis de la plataforma (summary, main topic de la taxonomía, CSAT, resolución…) no lo da Genesys. En esta fase
queda `pendiente`; la siguiente fase sustituirá `PendingAnalyzer` por un analizador con LLM sin cambiar el esquema ni
la lectura, igual que `PromptRunner` en ADR-006.
"""
from dataclasses import dataclass
from typing import Any, Protocol

from ingestion.pipeline.normalize import NormalizedConversation


@dataclass
class Analysis:
    status: str  # pendiente | completo | error
    source: str  # genesys | llm
    summary: str | None = None
    main_topic: str | None = None
    secondary_topics: list[str] | None = None
    resolution: str | None = None
    csat: float | None = None
    effort: float | None = None
    churn_risk: str | None = None
    compliance: dict[str, Any] | None = None
    entities: list[dict] | None = None
    keywords: list[str] | None = None
    error: str | None = None


class Analyzer(Protocol):
    def analyze(self, conversation: NormalizedConversation) -> Analysis: ...


class PendingAnalyzer:
    def analyze(self, conversation: NormalizedConversation) -> Analysis:
        return Analysis(status="pendiente", source="genesys")
