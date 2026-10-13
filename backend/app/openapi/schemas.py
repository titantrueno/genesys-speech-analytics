"""Esquemas de documentación de la API (OpenAPI).

Solo describen las respuestas y los errores: las rutas siguen devolviendo `dict`, así que estos modelos no cambian
el comportamiento. Todos prohíben campos extra; los tests de contrato (`tests/test_openapi.py`) validan respuestas
reales contra ellos, de modo que un campo añadido, quitado o renombrado en una ruta rompe la suite.
"""
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.flows.model import Graph
from app.models import Analysis, GenesysInfo, Turn


class Doc(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- Errores -------------------------------------------------------------------------------------------------------

class ErrorText(Doc):
    """E1: reason as text (401, 403, 404, 409 and stray business rules in 422)."""
    detail: str = Field(examples=["Conversation not found"])


class FieldIssue(Doc):
    loc: list[str | int] = Field(description="Path of the field; starts with `body`.", examples=[["body", "email"]])
    msg: str = Field(description="Message in English to show next to the field.")
    type: str


class FieldErrors(Doc):
    """E3: per-field errors of the settings bodies (422) and of users and roles (422, and 409 for duplicates)."""
    detail: list[FieldIssue]


class QueryIssue(Doc):
    path: str = Field(description="Path of the query node.", examples=["root.conditions[0]"])
    message: str


class QueryErrors(Doc):
    """E4: errors of an explorer query."""
    detail: list[QueryIssue]


class GraphIssue(Doc):
    path: str = Field(examples=["nodes[0].config.size"])
    node_id: str | None
    message: str


class GraphErrors(Doc):
    """E5: integrity errors of a flow graph."""
    detail: list[GraphIssue]


IssueCode = Literal[
    "missing_sampling", "missing_output", "node_unconfigured", "invalid_config", "disconnected_node",
    "prompt_without_variables", "unknown_variable", "previous_result_without_chain", "metric_requires_labels",
    "duplicate_destination", "analysis_pending",
    # FE013: proveedores de LLM y «Guardar en campos».
    "llm_unavailable", "provider_without_key", "model_not_in_provider", "field_output_requires_real_data",
    "simulated_values_to_real_data", "duplicate_target", "invalid_mapping", "summary_requires_text",
    "main_topic_requires_taxonomy",
    # FE014: un check asignado que ya no existe o está desactivado.
    "unknown_check",
    # FE017: la caja «Genesys download» solo trabaja con datos reales; «All conversations» con muchas conversaciones.
    "download_needs_real_origin", "large_sample", "ingestion_unavailable",
]


class FlowIssue(Doc):
    code: IssueCode
    message: str
    node_id: str | None = None
    severity: Literal["error", "warning"] = Field(
        "error", description="`warning` warns without preventing the run (FE012); `error` prevents it.")


class FlowIssues(Doc):
    """E6: completeness issues that prevent running a flow."""
    detail: list[FlowIssue]


# --- Comunes -------------------------------------------------------------------------------------------------------

class Period(Doc):
    date_from: date = Field(alias="from")
    date_to: date = Field(alias="to")


class Person(Doc):
    id: str
    name: str


class CodeLabel(Doc):
    code: str
    label: str


class ValueLabel(Doc):
    value: str
    label: str


class TargetField(ValueLabel):
    group: Literal["analisis", "cumplimiento", "entidades"] = Field(description="Dropdown group (FE014).")


class Health(Doc):
    status: Literal["ok"]


# --- Catálogo y métricas -------------------------------------------------------------------------------------------

KpiCode = Literal["volume", "aht_s", "sentiment_avg", "negative_pct", "resolution_rate", "escalation_rate",
                  "fcr_rate", "csat_avg", "effort_avg", "compliance_rate", "churn_high_pct", "first_response_s",
                  "avg_turns"]
KpiUnit = Literal["conversaciones", "s", "índice", "%", "1-5", "turnos"]
Number = float | int | None


class CatalogQueue(Doc):
    id: str = Field(description="Identificador `1QU-…`.")
    name: str


class CatalogAgent(Doc):
    id: str = Field(description="Identificador `1AG-…`.")
    name: str
    queue_id: str
    queue: str


class CatalogTopic(Doc):
    code: str
    name: str
    active: bool = Field(description="Deactivated ones are included to give a name to old filters.")


class Catalog(Doc):
    reference_date: date = Field(description="Dataset reference date; the default period ends the day before.")
    origin: Literal["sintetico", "real"] = Field(description="Active data origin (FE012).")
    channels: list[CodeLabel]
    queues: list[CatalogQueue]
    agents: list[CatalogAgent]
    main_topics: list[CatalogTopic]
    compliance_checks: list[CodeLabel] = Field(description="Active checks only.")
    resolutions: list[CodeLabel]
    churn_risks: list[CodeLabel]


class SummaryKpi(Doc):
    code: KpiCode
    label: str
    unit: KpiUnit
    higher_is_better: bool
    value: Number = Field(description="`null` if there are no applicable conversations.")
    previous: Number
    delta: float | None
    delta_pct: float | None = Field(description="`null` if the previous one is 0 or null, or if the unit is `índice`.")
    target: float | None
    status: Literal["verde", "ambar", "rojo"] | None = Field(description="According to the thresholds; `null` without thresholds.")
    pending: bool = Field(description="`true` if it depends on the platform analysis and the real conversations do not have it yet: the UI shows “No data · analysis pending”.")
    based_on: int | None = Field(description="Conversations the value is computed on, for KPIs that can use only a part (AHT, sentiment, first response); `null` for the rest.")


class CheckRate(Doc):
    code: str
    label: str
    value: float | None = Field(description="% of applicable conversations that comply.")
    applicable: int


class Summary(Doc):
    period: Period
    previous_period: Period
    kpis: list[SummaryKpi]
    compliance_by_check: list[CheckRate]


class TimePoint(Doc):
    period_start: date
    period_end: date
    value: Number


class Timeseries(Doc):
    kpi: KpiCode
    granularity: Literal["day", "week"]
    period: Period
    pending: bool = Field(description="`true` if the KPI depends on the analysis and is still pending (`null` points).")
    points: list[TimePoint]


class KpiValues(Doc):
    volume: int
    aht_s: Number
    sentiment_avg: Number
    negative_pct: Number
    resolution_rate: Number
    escalation_rate: Number
    fcr_rate: Number
    csat_avg: Number
    effort_avg: Number
    compliance_rate: Number
    churn_high_pct: Number
    first_response_s: Number
    avg_turns: Number


class BreakdownItem(Doc):
    key: str = Field(description="Code or identifier of the group.")
    label: str
    kpis: KpiValues


class Breakdown(Doc):
    dimension: Literal["main_topic", "channel", "queue", "agent"]
    period: Period
    pending: bool = Field(description="`true` if some conversations lack analysis; in the breakdown by main topic, only if none has a main topic yet (FE014).")
    pending_kpis: list[str] = Field(description="Analysis KPIs without the value in any conversation of the period: they are shown as pending (FE014).")
    items: list[BreakdownItem]


# --- Conversaciones ------------------------------------------------------------------------------------------------

class ConversationItem(Doc):
    """List item, shared by conversations, explorer, search and flow outputs."""
    id: str
    started_at: datetime
    channel: Literal["voz", "chat"]
    queue_id: str | None
    queue: str | None
    agent_id: str | None
    agent: str | None
    main_topic: str | None
    main_topic_label: str | None
    summary: str = Field(description="Masked if `privacy.pii_masking` is enabled; empty if the analysis is pending.")
    sentiment: float | None
    resolution: Literal["resuelta", "no_resuelta", "escalada"] | None
    csat: float | None
    duration_s: int
    analysis_pending: bool = Field(description="Real conversation whose platform analysis does not exist yet (FE012).")
    ani: str | None = Field(description="Calling number; only in real conversations with a phone number.")
    external_tag: str | None
    contained_in_bot: bool | None = Field(description="Only in real conversations.")
    transcript_quality: Literal["completa", "parcial", "sin_transcripcion"] | None = Field(
        description="Only in real conversations.")


class ConversationPage(Doc):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[ConversationItem]


class DetailAnalysis(Analysis):
    """Detail analysis: each field is given as soon as it exists (FE014); missing ones are `null` or empty."""
    compliance: dict[str, bool | None] = Field(
        description="Active checks with a result: `true` met, `false` not met, `null` not applicable. A stored result (from a flow with an LLM) takes precedence over the evaluation by phrases (FE014).")
    compliance_pending: list[str] = Field(description="Active checks with no result yet (FE014).")


class ConversationDetail(Doc):
    id: str
    channel: Literal["voz", "chat"]
    started_at: datetime
    duration_s: int
    queue_id: str | None
    queue: str | None
    agent_id: str | None
    agent: str | None
    customer_id: str | None
    turns: list[Turn]
    analysis: "DetailAnalysis"
    main_topic_label: str | None
    genesys: GenesysInfo | None = Field(None, description="Genesys analytics; only with the `real` origin (FE012).")


# --- Explorador ----------------------------------------------------------------------------------------------------

class Operator(Doc):
    key: str
    label: str


class QueryField(Doc):
    key: str = Field(examples=["sentiment", "check:saludo"])
    label: str
    type: Literal["categorical", "numeric", "check", "text", "boolean"]
    operators: list[Operator]
    values: list[ValueLabel] | None = None
    min: float | None = None
    max: float | None = None
    speakers: list[str] | None = None


class QuerySchema(Doc):
    fields: list[QueryField]
    reference_date: date
    default_period: Period


class KpiValue(Doc):
    code: KpiCode
    label: str
    unit: KpiUnit
    higher_is_better: bool
    value: Number


class QueryResult(ConversationPage):
    period: Period
    kpis: list[KpiValue]


class Suggestion(Doc):
    value: str
    label: str
    count: int


class Suggestions(Doc):
    field: str
    period: Period
    values: list[Suggestion]


class Interpretation(Doc):
    query: dict[str, Any] = Field(description="Editable query (`Query` format), not run.")
    unrecognized: list[str] = Field(description="Words the interpreter did not understand.")


class SavedQuery(Doc):
    id: str = Field(description="Identificador `1QY-…`.")
    name: str
    query: dict[str, Any] = Field(description="Canonical query (`Query` format).")
    created_at: datetime
    updated_at: datetime


class SavedQueries(Doc):
    items: list[SavedQuery]


# --- Búsqueda ------------------------------------------------------------------------------------------------------

class SearchTurn(Doc):
    index: int
    speaker: Literal["cliente", "agente", "bot", "sistema"]
    text: str


class SearchResult(Doc):
    conversation_id: str
    start_turn: int
    end_turn: int
    score: float = Field(ge=0, le=1, description="Cosine similarity with 4 decimals; it is not a probability.")
    turns: list[SearchTurn]
    highlights: list[str]
    conversation: ConversationItem


class SemanticSearch(Doc):
    query: str
    expansions: list[str]
    period: Period
    total: int = Field(description="Results after the threshold and the grouping, before `limit`.")
    max_score: float | None = Field(description="Best score before the threshold.")
    results: list[SearchResult]


class SimilarItem(Doc):
    conversation_id: str
    score: float
    conversation: ConversationItem


class SimilarConversations(Doc):
    conversation_id: str
    results: list[SimilarItem]


# --- Flujos --------------------------------------------------------------------------------------------------------

RunStatus = Literal["pendiente", "en_curso", "ok", "error"]


class LastRun(Doc):
    id: str
    created_at: datetime
    status: RunStatus


class FlowListItem(Doc):
    id: str = Field(description="Identificador `1FL-…`.")
    name: str
    author: Person
    created_at: datetime
    updated_at: datetime
    status: Literal["valido", "con_errores"]
    last_run: LastRun | None


class FlowList(Doc):
    items: list[FlowListItem]


class Flow(Doc):
    id: str
    name: str
    author: Person
    created_at: datetime
    updated_at: datetime
    status: Literal["valido", "con_errores"]
    graph: Graph


class SavedFlow(Flow):
    id_map: dict[str, str] = Field(description="Clave temporal (`tmp-…`) → identificador `1ND-…` asignado.")


class FlowLimits(Doc):
    max_sample_size: int
    max_template: int
    max_labels: int
    max_label: int
    max_fields: int
    max_field_name: int
    max_mappings: int = Field(description="Mappings of a “campo” Output (FE014).")
    max_destination: int
    max_flow_name: int
    max_nodes: int
    max_edges: int


class FlowCatalog(Doc):
    node_types: list[ValueLabel]
    sampling_methods: list[ValueLabel]
    strata: list[ValueLabel]
    order_keys: list[ValueLabel]
    orders: list[ValueLabel]
    models: list[ValueLabel] = Field(description="All models, from all providers.")
    providers: list["ProviderOption"] = Field(description="Providers with their models (FE013).")
    default_provider: str = Field(description="Provider taken by a new Prompt node (Settings › AI models).")
    default_model: str = Field(description="Model taken by a new Prompt node (Settings › AI models).")
    variables: list[ValueLabel]
    output_formats: list[ValueLabel]
    field_types: list[ValueLabel]
    output_kinds: list[ValueLabel]
    target_fields: list["TargetField"] = Field(
        description="Target fields of a “campo” Output (FE013): the analysis ones, a `compliance:<code>` per active check and an `entity:<type>` per entity type (FE014).")
    templates: list[ValueLabel] = Field(description="Templates to create an already configured flow (FE013).")
    origin: Literal["sintetico", "real"] = Field(
        description="Active data origin: a “campo” Output can only run with `real` (FE013).")
    aggregations: list[ValueLabel]
    limits: FlowLimits


class Validation(Doc):
    valid: bool
    issues: list[FlowIssue]


class SampleEstimate(Doc):
    available: int | None = Field(description="`null` behind a Genesys download box: it depends on the download.")
    sample_size: int | None = Field(description="With `size: \"all\"` (All conversations), every available one.")
    period: Period | None
    depends_on_download: bool | None = Field(None, description="Only behind a Genesys download box (FE017).")


class RunSummary(Doc):
    id: str = Field(description="Identificador `1RN-…`.")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    status: RunStatus
    sample_size: int | None
    user: Person


class RunList(Doc):
    items: list[RunSummary]


# `omitido` (FE017): el nodo no se ejecuta porque la descarga de la caja no trajo conversaciones.
NodeStatus = Literal["pendiente", "en_curso", "ok", "error", "omitido"]


class NodeState(Doc):
    status: NodeStatus
    processed: int
    total: int | None
    message: str | None
    rejected: int = Field(description="Prompt with an LLM: answers outside the output format (FE013).")
    failed: int = Field(description="Prompt with an LLM: conversations without a response from the provider (FE013).")


class PromptFailure(Doc):
    conversation_id: str
    status: Literal["rechazado", "error"]
    reason: str = Field(description="Reason, without conversation or provider data.")


class TableRow(Doc):
    conversation: ConversationItem
    result: Any = Field(description="Text, label or JSON object depending on the prompt format.")


class TableResult(Doc):
    rows: list[TableRow]


class MetricItem(Doc):
    label: str
    count: int
    percent: float = Field(description="One decimal; the percentages add up to exactly 100.")


class MetricResult(Doc):
    aggregation: Literal["recuento", "porcentaje"]
    total: int
    items: list[MetricItem]


class ReportResult(Doc):
    text: str


FieldState = Literal["escrito", "omitido", "rechazado", "sin_valor", "error"]


class FieldRow(Doc):
    conversation: ConversationItem
    values: dict[str, str | float | bool | list[str] | None] = Field(
        description="Validated value that was sent to be saved, per target field: `main_topic` and secondary topics by their code, checks as `true`, `false` or `null` (not applicable) (FE014).")
    states: dict[str, FieldState] = Field(
        description="Status per target field; `sin_valor`: the answer says there is nothing (FE014).")
    reason: str | None = Field(description="Reason for a `rechazado` or `error` of the whole conversation.")
    reasons: dict[str, str] = Field(
        description="Reason per target field (FE014): rejected value, already had a value, Genesys already gives the sentiment.")


class FieldsResult(Doc):
    targets: list[str] = Field(description="Target fields: the analysis ones, `compliance:<code>` and `entity:<type>` (FE014).")
    rows: list[FieldRow] = Field(description="One row per conversation that reached the Prompt.")
    counts: dict[str, dict[FieldState, int]] = Field(description="Count of each status per target field.")


class RunOutput(Doc):
    node_id: str
    kind: Literal["tabla", "metrica", "informe", "campo"]
    destination: str = Field(description="Destination name or, in `campo`, the target fields (“Summary + Main topic”).")
    result: TableResult | MetricResult | ReportResult | FieldsResult


class Run(RunSummary):
    flow_id: str
    seed: int
    graph: Graph = Field(description="Copy of the executed graph.")
    nodes: dict[str, NodeState] = Field(description="Status per node identifier.")
    outputs: dict[str, RunOutput] = Field(description="Result per Output node identifier.")
    failures: dict[str, list[PromptFailure]] = Field(
        description="Per Prompt node with an LLM, the conversations excluded from the outputs (FE013).")
    download: "RunDownload | None" = Field(
        description="Download of the Genesys download box (FE017); `null` in a flow without a box.")


class RunDownload(Doc):
    node_id: str
    run_id: str = Field(description="`1RN-…` of the download in the ingestion service.")
    status: Literal["pendiente", "en_curso", "completada", "completada_con_avisos", "error"]
    counters: dict[str, Any] = Field(description="Counters of the download (as in a download flow run).")
    error: str | None


# --- Configuración -------------------------------------------------------------------------------------------------

class PublicConfig(Doc):
    platform_name: str
    timezone: str = Field(examples=["Europe/Madrid"])
    language: str = Field(examples=["es-ES", "en-US"])


class Privacy(Doc):
    pii_masking: bool


class Sources(Doc):
    origin: Literal["sintetico", "real"] = Field(
        description="`sintetico` (generated dataset) or `real` (Genesys conversations stored by the ingestion).")


class AiSettings(Doc):
    provider: str
    model: str
    simulated: bool


class KpiSettings(Doc):
    code: KpiCode
    label: str
    unit: KpiUnit
    higher_is_better: bool
    target: float | None
    green: float | None
    amber: float | None
    dashboards: list[str]


class ModelOption(ValueLabel):
    temperature: bool = Field(description="Whether the model supports `temperature`; if not, it is not sent (FE013).")


class ProviderOption(ValueLabel):
    models: list[ModelOption] = Field(description="The first one is proposed when the provider is chosen.")


class AiProviderStatus(ValueLabel):
    key_configured: bool = Field(description="Whether the LLM service has its key; never the key.")


class AiStatus(Doc):
    service: Literal["disponible"]
    providers: list[AiProviderStatus]


class AiTestIn(Doc):
    model: str


class AiTestResult(Doc):
    ok: bool
    provider: str
    model: str
    message: str = Field(description="“The provider responded correctly” or the provider's error.")


class ConfigOptions(Doc):
    languages: list[ValueLabel]
    timezones: list[str]
    providers: list[ProviderOption]
    sections: list[ValueLabel]
    dashboards: list[ValueLabel]


class PlatformConfig(Doc):
    version: int = Field(description="Increases with each accepted change.")
    general: PublicConfig
    sources: Sources
    privacy: Privacy
    ai: AiSettings
    kpis: list[KpiSettings]
    options: ConfigOptions


class Connector(Doc):
    id: str = Field(description="Identificador `1CN-…`.")
    name: str
    channel: Literal["voz", "chat"]
    status: str
    last_sync: datetime
    conversations: int


class Connectors(Doc):
    items: list[Connector]


class AuditEntry(Doc):
    id: str = Field(description="Identificador `1AU-…`.")
    user: Person
    at: datetime
    section: str = Field(description="Settings section or `usuarios`.")
    element: str
    before: Any = Field(description="`null` on creation.")
    after: Any = Field(description="`null` on deletion.")


class AuditLog(Doc):
    items: list[AuditEntry]


class TaxonomyTopic(Doc):
    id: str = Field(description="Identifier `1TP-…` (main topic) or `1TS-…` (secondary topic).")
    code: str
    name: str
    description: str
    keywords: list[str]
    active: bool
    conversations: int


class Taxonomy(Doc):
    main_topics: list[TaxonomyTopic]
    secondary_topics: list[TaxonomyTopic]


class ComplianceCheck(Doc):
    id: str = Field(description="Identificador `1CK-…`.")
    code: str
    name: str
    description: str
    phrases: list[str]
    channel: Literal["voz", "chat", "ambos"]
    active: bool
    evaluation: Literal["analisis", "frases"]
    builtin: bool


class ComplianceChecks(Doc):
    items: list[ComplianceCheck]


# --- Usuarios y roles ----------------------------------------------------------------------------------------------

class ManagedUser(Doc):
    id: str = Field(description="Identificador `1US-…`.")
    name: str
    email: str
    role: str = Field(description="Role code.")
    role_name: str
    active: bool
    last_login: datetime | None


class ManagedUsers(Doc):
    items: list[ManagedUser]


class RoleItem(Doc):
    id: str = Field(description="Identifier `1RO-…`, derived from the code.")
    code: str
    name: str
    builtin: bool
    permissions: list[str] = Field(description="In the order of the permission catalog.")
    users: int


class Roles(Doc):
    items: list[RoleItem]
    permissions: list[ValueLabel] = Field(description="Catalog of the 9 permissions with their label.")


# --- Flujos de descarga de Genesys Cloud (FE011) -------------------------------------------------------------------

DownloadRunStatus = Literal["pendiente", "en_curso", "completada", "completada_con_avisos", "error"]
DownloadChannel = Literal["voz", "chat"]


class DownloadInterval(Doc):
    """Relative (`hoy`, `ayer`, last N `horas` or `dias`) or specific (`from`–`to` in the flow time zone)."""
    type: Literal["relativo", "especifico"]
    unit: Literal["hoy", "ayer", "horas", "dias"] | None = Field(None, description="Only in a relative interval.")
    amount: int | None = Field(None, description="Hours (1–720) or days (1–90); null in `hoy` and `ayer`.")
    from_: str | None = Field(None, alias="from", description="Only in a specific one: local date and time.",
                              examples=["2026-10-01T08:00:00"])
    to: str | None = Field(None, description="Only in a specific one; at most 90 days after `from`.")


class DownloadSchedule(Doc):
    type: Literal["desactivada", "cada_horas", "diaria"]
    hours: int | None = Field(None, description="Every how many hours (1–24), aligned with local midnight.")
    time: str | None = Field(None, description="Local time `HH:MM` of the daily run.", examples=["07:30"])


class DownloadFlowIn(Doc):
    """Body to create or save a download flow. The API adds the author and the current time zone."""
    name: str = Field(max_length=80)
    interval: DownloadInterval
    channels: list[DownloadChannel] = Field(min_length=1)
    schedule: DownloadSchedule = Field(description="A scheduled download needs a relative interval.")
    active: bool = Field(True, description="An inactive flow does not run on schedule, but it does run manually.")
    overwrite: bool = Field(False, description="Overwrite: downloads again the conversations that already exist and deletes their LLM summary and main topic. Unchecked, the existing ones are not downloaded.")


class DownloadRunRef(Doc):
    id: str = Field(description="Identificador `1RN-…`.")
    status: DownloadRunStatus
    created_at: datetime


class DownloadFlow(Doc):
    id: str = Field(description="Identificador `1FL-…`.")
    name: str
    interval: DownloadInterval
    channels: list[DownloadChannel]
    schedule: DownloadSchedule
    active: bool
    overwrite: bool
    timezone: str = Field(description="Platform time zone when the flow was saved.")
    author: Person
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime | None = Field(description="Next scheduled run; null if it is not scheduled or active.")
    last_run: DownloadRunRef | None


class DownloadFlowList(Doc):
    items: list[DownloadFlow]


class DownloadCounters(Doc):
    found: int = Field(description="Found = inserted + updated + skipped + already existing + with errors, when finished.")
    downloaded: int
    inserted: int
    updated: int
    skipped: int
    errors: int
    skipped_in_progress: int
    skipped_existing: int = Field(description="They were already in the database and were not downloaded (flow without “Overwrite”).")
    skipped_other_channel: int = Field(description="From another channel or from an unsupported media.")
    by_channel: dict[str, int]
    by_quality: dict[str, int] = Field(description="`completa`, `parcial` and `sin_transcripcion`.")
    undelivered_messages: int


class DownloadRunInterval(Doc):
    from_: datetime = Field(alias="from")
    to: datetime


class DownloadRun(Doc):
    id: str = Field(description="Identificador `1RN-…`.")
    flow_id: str | None = Field(description="Download flow; `null` in the download of a Genesys download box.")
    insight_flow_id: str | None = Field(None, description="Only in the download of a Genesys download box (FE017).")
    origin: Literal["manual", "programada"]
    status: DownloadRunStatus
    interval: DownloadRunInterval = Field(description="Interval resolved when the run was started.")
    channels: list[DownloadChannel]
    overwrite: bool | None = Field(description="Value of “Overwrite” of the flow when the run was created; null in runs prior to FE013, whose mode is unknown.")
    counters: DownloadCounters
    error: str | None
    started_by: Person | None = Field(description="Who started it; null in scheduled ones.")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_s: float | None


class DownloadRunList(Doc):
    items: list[DownloadRun]


class DownloadLogEntry(Doc):
    id: int = Field(description="Increasing; serves as the cursor for `after`.")
    at: datetime
    level: Literal["info", "aviso", "error"]
    stage: str = Field(examples=["normalization"])
    message: str = Field(description="Identifiers, counts and reasons; never the text of the turns.")
    genesys_id: str | None = Field(description="Affected Genesys conversation, if any.")


class DownloadLog(Doc):
    items: list[DownloadLogEntry]


class GenesysTest(Doc):
    ok: bool
    at: datetime
    organization: str | None = Field(description="Name of the Genesys organization, if the connection works.")
    region: str | None
    message: str


class GenesysLastDownload(Doc):
    run_id: str
    flow_id: str
    status: DownloadRunStatus
    finished_at: datetime | None


class GenesysConversations(Doc):
    total: int
    by_channel: dict[str, int]
    by_quality: dict[str, int]


class GenesysConnector(Doc):
    """Status of the real connector. With the ingestion service down, `service` is `no_disponible` and the rest is null."""
    service: Literal["disponible", "no_disponible"]
    region: str | None
    credentials_configured: bool | None = Field(description="Whether the ingestion service has `GENESYS_*`.")
    database: str | None
    last_test: GenesysTest | None = Field(description="Last “Test connection” since the service started.")
    last_download: GenesysLastDownload | None
    conversations: GenesysConversations | None
