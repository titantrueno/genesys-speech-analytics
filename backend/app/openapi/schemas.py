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
    """E1: motivo en texto (401, 403, 404, 409 y reglas de negocio sueltas en 422)."""
    detail: str = Field(examples=["Conversación no encontrada"])


class FieldIssue(Doc):
    loc: list[str | int] = Field(description="Ruta del campo; empieza por `body`.", examples=[["body", "email"]])
    msg: str = Field(description="Mensaje en español para mostrar junto al campo.")
    type: str


class FieldErrors(Doc):
    """E3: errores por campo de los cuerpos de configuración (422) y de usuarios y roles (422 y 409 por duplicado)."""
    detail: list[FieldIssue]


class QueryIssue(Doc):
    path: str = Field(description="Ruta del nodo de la consulta.", examples=["root.conditions[0]"])
    message: str


class QueryErrors(Doc):
    """E4: errores de una consulta del explorador."""
    detail: list[QueryIssue]


class GraphIssue(Doc):
    path: str = Field(examples=["nodes[0].config.size"])
    node_id: str | None
    message: str


class GraphErrors(Doc):
    """E5: errores de integridad de un grafo de flujo."""
    detail: list[GraphIssue]


IssueCode = Literal[
    "missing_sampling", "missing_output", "node_unconfigured", "invalid_config", "disconnected_node",
    "prompt_without_variables", "unknown_variable", "previous_result_without_chain", "metric_requires_labels",
    "duplicate_destination", "analysis_pending",
]


class FlowIssue(Doc):
    code: IssueCode
    message: str
    node_id: str | None = None
    severity: Literal["error", "warning"] = Field(
        "error", description="`warning` avisa sin impedir la ejecución (FE012); `error` la impide.")


class FlowIssues(Doc):
    """E6: incidencias de completitud que impiden ejecutar un flujo."""
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
    active: bool = Field(description="Los desactivados se incluyen para poner nombre a filtros antiguos.")


class Catalog(Doc):
    reference_date: date = Field(description="Fecha de referencia del dataset; el periodo por defecto acaba el día anterior.")
    origin: Literal["sintetico", "real"] = Field(description="Origen de datos activo (FE012).")
    channels: list[CodeLabel]
    queues: list[CatalogQueue]
    agents: list[CatalogAgent]
    main_topics: list[CatalogTopic]
    compliance_checks: list[CodeLabel] = Field(description="Solo checks activos.")
    resolutions: list[CodeLabel]
    churn_risks: list[CodeLabel]


class SummaryKpi(Doc):
    code: KpiCode
    label: str
    unit: KpiUnit
    higher_is_better: bool
    value: Number = Field(description="`null` si no hay conversaciones aplicables.")
    previous: Number
    delta: float | None
    delta_pct: float | None = Field(description="`null` si el anterior es 0 o nulo, o si la unidad es `índice`.")
    target: float | None
    status: Literal["verde", "ambar", "rojo"] | None = Field(description="Según los umbrales; `null` sin umbrales.")
    pending: bool = Field(description="`true` si depende del análisis de la plataforma y las conversaciones reales aún "
                                      "no lo tienen: la UI muestra «Sin datos · pendiente de análisis».")
    based_on: int | None = Field(description="Conversaciones sobre las que se calcula, en los KPIs que pueden usar solo "
                                             "una parte (AHT, sentimiento, primera respuesta); `null` en el resto.")


class CheckRate(Doc):
    code: str
    label: str
    value: float | None = Field(description="% de conversaciones aplicables que cumplen.")
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
    pending: bool = Field(description="`true` si el KPI depende del análisis y aún está pendiente (puntos `null`).")
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
    key: str = Field(description="Código o identificador del grupo.")
    label: str
    kpis: KpiValues


class Breakdown(Doc):
    dimension: Literal["main_topic", "channel", "queue", "agent"]
    period: Period
    pending: bool = Field(description="`true` si hay conversaciones sin analizar: sus KPIs de análisis son `null` y el "
                                      "desglose por main topic no tiene grupos.")
    items: list[BreakdownItem]


# --- Conversaciones ------------------------------------------------------------------------------------------------

class ConversationItem(Doc):
    """Elemento de listado, compartido por conversaciones, explorador, búsqueda y outputs de flujos."""
    id: str
    started_at: datetime
    channel: Literal["voz", "chat"]
    queue_id: str | None
    queue: str | None
    agent_id: str | None
    agent: str | None
    main_topic: str | None
    main_topic_label: str | None
    summary: str = Field(description="Enmascarado si `privacy.pii_masking` está activado; vacío si el análisis está "
                                     "pendiente.")
    sentiment: float | None
    resolution: Literal["resuelta", "no_resuelta", "escalada"] | None
    csat: float | None
    duration_s: int
    analysis_pending: bool = Field(description="Conversación real cuyo análisis de la plataforma aún no existe (FE012).")
    ani: str | None = Field(description="Teléfono de origen; solo en conversaciones reales con teléfono.")
    external_tag: str | None
    contained_in_bot: bool | None = Field(description="Solo en conversaciones reales.")
    transcript_quality: Literal["completa", "parcial", "sin_transcripcion"] | None = Field(
        description="Solo en conversaciones reales.")


class ConversationPage(Doc):
    total: int
    page: int
    page_size: int
    pages: int
    items: list[ConversationItem]


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
    analysis: Analysis = Field(description="`compliance` es el cumplimiento efectivo con los checks activos "
                                           "(`true`, `false` o `null` si no aplica).")
    main_topic_label: str | None
    genesys: GenesysInfo | None = Field(None, description="Analítica de Genesys; solo con el origen `real` (FE012).")


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
    query: dict[str, Any] = Field(description="Consulta editable (formato `Query`), sin ejecutar.")
    unrecognized: list[str] = Field(description="Palabras que el intérprete no ha entendido.")


class SavedQuery(Doc):
    id: str = Field(description="Identificador `1QY-…`.")
    name: str
    query: dict[str, Any] = Field(description="Consulta canónica (formato `Query`).")
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
    score: float = Field(ge=0, le=1, description="Similitud coseno con 4 decimales; no es una probabilidad.")
    turns: list[SearchTurn]
    highlights: list[str]
    conversation: ConversationItem


class SemanticSearch(Doc):
    query: str
    expansions: list[str]
    period: Period
    total: int = Field(description="Resultados tras el umbral y la agrupación, antes de `limit`.")
    max_score: float | None = Field(description="Mejor puntuación antes del umbral.")
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
    models: list[ValueLabel]
    default_model: str = Field(description="Modelo que toma un nodo Prompt nuevo (Configuración › Modelos de IA).")
    variables: list[ValueLabel]
    output_formats: list[ValueLabel]
    field_types: list[ValueLabel]
    output_kinds: list[ValueLabel]
    aggregations: list[ValueLabel]
    limits: FlowLimits


class Validation(Doc):
    valid: bool
    issues: list[FlowIssue]


class SampleEstimate(Doc):
    available: int
    sample_size: int | None
    period: Period


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


class NodeState(Doc):
    status: RunStatus
    processed: int
    total: int | None
    message: str | None


class TableRow(Doc):
    conversation: ConversationItem
    result: Any = Field(description="Texto, etiqueta u objeto JSON según el formato del prompt.")


class TableResult(Doc):
    rows: list[TableRow]


class MetricItem(Doc):
    label: str
    count: int
    percent: float = Field(description="Un decimal; los porcentajes suman exactamente 100.")


class MetricResult(Doc):
    aggregation: Literal["recuento", "porcentaje"]
    total: int
    items: list[MetricItem]


class ReportResult(Doc):
    text: str


class RunOutput(Doc):
    node_id: str
    kind: Literal["tabla", "metrica", "informe"]
    destination: str
    result: TableResult | MetricResult | ReportResult


class Run(RunSummary):
    flow_id: str
    seed: int
    graph: Graph = Field(description="Copia del grafo ejecutado.")
    nodes: dict[str, NodeState] = Field(description="Estado por identificador de nodo.")
    outputs: dict[str, RunOutput] = Field(description="Resultado por identificador de nodo Output.")


# --- Configuración -------------------------------------------------------------------------------------------------

class PublicConfig(Doc):
    platform_name: str
    timezone: str = Field(examples=["Europe/Madrid"])
    language: str = Field(examples=["es-ES"])


class Privacy(Doc):
    pii_masking: bool


class Sources(Doc):
    origin: Literal["sintetico", "real"] = Field(
        description="`sintetico` (dataset generado) o `real` (conversaciones de Genesys guardadas por la ingesta).")


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


class ProviderOption(ValueLabel):
    models: list[ValueLabel]


class ConfigOptions(Doc):
    languages: list[ValueLabel]
    timezones: list[str]
    providers: list[ProviderOption]
    sections: list[ValueLabel]
    dashboards: list[ValueLabel]


class PlatformConfig(Doc):
    version: int = Field(description="Sube con cada cambio aceptado.")
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
    section: str = Field(description="Sección de configuración o `usuarios`.")
    element: str
    before: Any = Field(description="`null` en altas.")
    after: Any = Field(description="`null` en bajas.")


class AuditLog(Doc):
    items: list[AuditEntry]


class TaxonomyTopic(Doc):
    id: str = Field(description="Identificador `1TP-…` (main topic) o `1TS-…` (tema secundario).")
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
    role: str = Field(description="Código del rol.")
    role_name: str
    active: bool
    last_login: datetime | None


class ManagedUsers(Doc):
    items: list[ManagedUser]


class RoleItem(Doc):
    id: str = Field(description="Identificador `1RO-…`, derivado del código.")
    code: str
    name: str
    builtin: bool
    permissions: list[str] = Field(description="En el orden del catálogo de permisos.")
    users: int


class Roles(Doc):
    items: list[RoleItem]
    permissions: list[ValueLabel] = Field(description="Catálogo de los 9 permisos con su etiqueta.")


# --- Flujos de descarga de Genesys Cloud (FE011) -------------------------------------------------------------------

DownloadRunStatus = Literal["pendiente", "en_curso", "completada", "completada_con_avisos", "error"]
DownloadChannel = Literal["voz", "chat"]


class DownloadInterval(Doc):
    """Relativo (`hoy`, `ayer`, últimas N `horas` o `dias`) o específico (`from`–`to` en la zona horaria del flujo)."""
    type: Literal["relativo", "especifico"]
    unit: Literal["hoy", "ayer", "horas", "dias"] | None = Field(None, description="Solo en un intervalo relativo.")
    amount: int | None = Field(None, description="Horas (1–720) o días (1–90); nulo en `hoy` y `ayer`.")
    from_: str | None = Field(None, alias="from", description="Solo en uno específico: fecha y hora local.",
                              examples=["2026-10-01T08:00:00"])
    to: str | None = Field(None, description="Solo en uno específico; como mucho 90 días después de `from`.")


class DownloadSchedule(Doc):
    type: Literal["desactivada", "cada_horas", "diaria"]
    hours: int | None = Field(None, description="Cada cuántas horas (1–24), alineadas con la medianoche local.")
    time: str | None = Field(None, description="Hora local `HH:MM` de la ejecución diaria.", examples=["07:30"])


class DownloadFlowIn(Doc):
    """Cuerpo para crear o guardar un flujo de descarga. La API añade la autoría y la zona horaria vigente."""
    name: str = Field(max_length=80)
    interval: DownloadInterval
    channels: list[DownloadChannel] = Field(min_length=1)
    schedule: DownloadSchedule = Field(description="Una descarga programada necesita un intervalo relativo.")
    active: bool = Field(True, description="Un flujo inactivo no se ejecuta por programación, pero sí a mano.")


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
    timezone: str = Field(description="Zona horaria de la plataforma cuando se guardó el flujo.")
    author: Person
    created_at: datetime
    updated_at: datetime
    next_run_at: datetime | None = Field(description="Próxima ejecución programada; nula si no está programado o activo.")
    last_run: DownloadRunRef | None


class DownloadFlowList(Doc):
    items: list[DownloadFlow]


class DownloadCounters(Doc):
    found: int = Field(description="Encontradas = insertadas + actualizadas + omitidas + con error, al terminar.")
    downloaded: int
    inserted: int
    updated: int
    skipped: int
    errors: int
    skipped_in_progress: int
    skipped_other_channel: int = Field(description="De otro canal o de un medio no soportado.")
    by_channel: dict[str, int]
    by_quality: dict[str, int] = Field(description="`completa`, `parcial` y `sin_transcripcion`.")
    undelivered_messages: int


class DownloadRunInterval(Doc):
    from_: datetime = Field(alias="from")
    to: datetime


class DownloadRun(Doc):
    id: str = Field(description="Identificador `1RN-…`.")
    flow_id: str
    origin: Literal["manual", "programada"]
    status: DownloadRunStatus
    interval: DownloadRunInterval = Field(description="Intervalo resuelto al lanzar la ejecución.")
    channels: list[DownloadChannel]
    counters: DownloadCounters
    error: str | None
    started_by: Person | None = Field(description="Quién la lanzó; nulo en las programadas.")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_s: float | None


class DownloadRunList(Doc):
    items: list[DownloadRun]


class DownloadLogEntry(Doc):
    id: int = Field(description="Creciente; sirve de cursor para `after`.")
    at: datetime
    level: Literal["info", "aviso", "error"]
    stage: str = Field(examples=["normalización"])
    message: str = Field(description="Identificadores, recuentos y motivos; nunca el texto de los turnos.")
    genesys_id: str | None = Field(description="Conversación de Genesys afectada, si la hay.")


class DownloadLog(Doc):
    items: list[DownloadLogEntry]


class GenesysTest(Doc):
    ok: bool
    at: datetime
    organization: str | None = Field(description="Nombre de la organización de Genesys, si la conexión funciona.")
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
    """Estado del conector real. Con el servicio de ingesta caído, `service` es `no_disponible` y el resto, nulo."""
    service: Literal["disponible", "no_disponible"]
    region: str | None
    credentials_configured: bool | None = Field(description="Si el servicio de ingesta tiene `GENESYS_*`.")
    database: str | None
    last_test: GenesysTest | None = Field(description="Última «Probar conexión» desde que arrancó el servicio.")
    last_download: GenesysLastDownload | None
    conversations: GenesysConversations | None
