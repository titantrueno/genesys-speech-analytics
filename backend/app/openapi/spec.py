"""OpenAPI completo de la API: parte del que genera FastAPI y le añade respuestas, errores, seguridad y descripciones.

Cada operación está en `OPERATIONS`; si se añade una ruta sin documentarla aquí, construir el esquema falla (y con él
`/openapi.json`, `/docs` y la suite). Los modelos de respuesta son solo documentación (`app/openapi/schemas.py`).
"""
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from app.auth import ALL_PERMISSIONS, PERMISSION_LABELS
from app.config.checks import CheckIn
from app.config.kpis import KpiTargetIn
from app.config.model import AiConfig, GeneralConfig, PrivacyConfig, SourcesConfig
from app.config.taxonomy import MainTopicIn, SecondaryTopicIn
from app.flows.model import Graph
from app.openapi import schemas as s
from app.query.model import Query
from app.routers.users import NewRoleIn, RoleIn, UserIn

API_VERSION = "0.12.0"
AUTH_VERSION_HEADER = "X-Auth-Version"

DESCRIPTION = """
API of the Banco Horizonte Speech & Text Analytics platform (mock data). It is consumed by the React front end.

**Authentication.** `POST /api/auth/login` returns a token that is sent as `Authorization: Bearer <token>`. The
user and the permissions of their role are re-read on every request. Without a token or with an invalid token: `401`.
Without the operation's permission: `403`. Each operation states its permission in the description.

**`X-Auth-Version`.** Every response to a request with a session carries this header: an integer that increases with
each change to users or roles. If it changes, the front end requests `/api/auth/me` again.

**Identifiers.** `PREFIX-UUID` in uppercase (`1CO` conversation, `1QU` queue, `1AG` agent, `1US` user,
`1RO` role, `1FL` flow, `1ND` node, `1RN` run, `1QY` saved query, `1TP`/`1TS` topics, `1CK` check, `1CN`
connector, `1AU` audit). In paths they are accepted in lowercase.

**Dates.** Instants in ISO 8601 with offset. `from` and `to` are days (`YYYY-MM-DD`, inclusive) in the configured
time zone; by default, the 30 days ending the day before the dataset's reference date.

**Errors.** Always with `detail`, in six shapes depending on the operation: text (`ErrorText`), native FastAPI
validation (`HTTPValidationError`), per-field errors (`FieldErrors`), query errors (`QueryErrors`), graph errors
(`GraphErrors`) and flow issues (`FlowIssues`). All messages are in English, whatever the language configured for the interface.

**Persistence.** The ingestion service stores in PostgreSQL the download flows (FE011), the insight flows and the General, Data origin, Privacy and AI models sections of the settings (FE015), which survive a restart. If that service is not available, its routes respond `503` and the change is not applied. The rest (insight flow runs, taxonomy, checks, KPIs, users, saved queries and audit log) lives in memory and is lost when the API restarts.

Extended reference: `vault/arquitectura/contrato-api-front-back.md`.
""".strip()

TAGS = [
    {"name": "health", "description": "Health probe."},
    {"name": "auth", "description": "Sign-in and current user."},
    {"name": "metrics", "description": "Dashboard KPIs (FE001, FE005)."},
    {"name": "conversations", "description": "List, detail and filter catalog (FE001)."},
    {"name": "query", "description": "Assisted query explorer and saved queries (FE002)."},
    {"name": "search", "description": "Semantic search and similar conversations (FE003)."},
    {"name": "flows", "description": "Insight flows and their simulated runs (FE004)."},
    {"name": "config", "description": "Global platform settings (FE005)."},
    {"name": "downloads", "description": "Genesys Cloud conversation download flows (FE011)."},
    {"name": "users", "description": "Users, roles and permission matrix (FE006)."},
]

Models = type[BaseModel] | tuple[type[BaseModel], ...]


@dataclass(frozen=True)
class Op:
    summary: str
    ok: type[BaseModel] | None
    permission: str | tuple[str, ...] | None = None  # None con `public=False` → solo autenticada
    description: str = ""
    status: int = 200
    public: bool = False
    body: Models | None = None
    errors: dict[int, tuple[str, Models]] = field(default_factory=dict)
    ok_description: str = ""


NOT_FOUND = "It does not exist (or the identifier is of another type)."
UNAVAILABLE_503 = "The ingestion service is not available."
LLM_503 = "The LLM service is not available."
STATE_503 = "The insight flows cannot be read or saved: the ingestion service is not available (FE015)."
CONFIG_503 = "The section cannot be saved: the ingestion service is not available (FE015). It is not applied."
DOWNLOAD_422 = ("A field is not valid: name, interval (ranges, order, 90 days, not in the future), channels or schedule (only with a relative interval).")


def _e422(description: str, models: Models) -> dict[int, tuple[str, Models]]:
    return {422: (description, models)}


FILTERS_422 = _e422("`from` after `to`, or a malformed queue or agent identifier.", s.ErrorText)
PROTECTION_409 = ("Administration protection: removing `users:admin` from oneself, leaving no active `admin`, or removing `users:admin` from the `admin` role.")


OPERATIONS: dict[tuple[str, str], Op] = {
    # --- Salud y sesión ---
    ("GET", "/api/health"): Op("Health probe", s.Health, public=True,
                               description="Responds when the API has finished starting (search index built)."),
    ("POST", "/api/auth/login"): Op(
        "Sign in", None, public=True,
        description="Returns the Bearer token (expires after 8 h) and the user with their permissions. Records the last sign-in. The email is case-insensitive.",
        errors={401: ("Wrong credentials, non-existent or deactivated user (same response).", s.ErrorText)}),
    ("GET", "/api/auth/me"): Op("Usuario actual", None,
                                description="Session user, name of their role and current permissions."),

    # --- Métricas ---
    ("GET", "/api/metrics/summary"): Op(
        "KPI summary", s.Summary, "dashboards:view",
        "The 13 KPIs of the period with the previous period (same length), variation, target and status according to the thresholds in Settings. With `dashboard`, only the KPIs configured for that dashboard. Includes compliance by active check.",
        errors=FILTERS_422),
    ("GET", "/api/metrics/timeseries"): Op(
        "KPI time series", s.Timeseries, "dashboards:view",
        "One point per day or per week (Monday to Sunday, trimmed to the period), in the configured time zone.",
        errors=FILTERS_422),
    ("GET", "/api/metrics/breakdown"): Op(
        "KPIs by dimension", s.Breakdown, "dashboards:view",
        "The 13 KPIs by main topic, channel, queue or agent, sorted by volume.",
        errors=FILTERS_422),
    ("GET", "/api/catalog"): Op(
        "Filter catalog", s.Catalog, ("dashboards:view", "conversations:view"),
        "Channels, queues, agents, main topics (including deactivated ones), active checks, resolutions, risks and the reference date."),

    # --- Conversaciones ---
    ("GET", "/api/conversations"): Op(
        "Conversation list", s.ConversationPage, "conversations:view",
        "Filtered, paginated and sorted list. The `resolution`, `churn_risk`, `sentiment_lt`, `compliant` and `repeat_contact` filters are the drill-down ones: they select the numerator of each KPI. `phone` (ANI, with or without +34) and `external_tag` search exactly in the real conversations (FE012).",
        errors=FILTERS_422),
    ("GET", "/api/conversations/{conversation_id}"): Op(
        "Conversation detail", s.ConversationDetail, "conversations:view",
        "Turns and full analysis. Masked text if PII masking is enabled.",
        errors={404: (NOT_FOUND, s.ErrorText)}),

    # --- Explorador ---
    ("GET", "/api/query/schema"): Op(
        "Explorer fields", s.QuerySchema, ("explorer:use", "flows:view"),
        "Fields with their type, operators, values and ranges, plus the reference date and the default period."),
    ("POST", "/api/query/run"): Op(
        "Run a query", s.QueryResult, "explorer:use",
        "Runs a query (`Query`) and returns the total, the 13 KPIs of the result and a page of the list. Maximum 50 conditions, 2 group levels and 200 values per list.",
        body=Query, errors=_e422("Invalid query (per condition) or out-of-range parameters.", s.QueryErrors)),
    ("GET", "/api/query/suggest"): Op(
        "Field values", s.Suggestions, ("explorer:use", "flows:view"),
        "Values of a categorical field in the interval, with their count.",
        errors=_e422("Non-categorical field or `from` after `to`.", s.ErrorText)),
    ("POST", "/api/query/interpret"): Op(
        "Interpret a sentence", s.Interpretation, "explorer:use",
        "Converts a sentence in Spanish (1–500 characters) into an editable query. It does not run it.",
        errors=_e422("Empty or too long sentence.", s.ErrorText)),
    ("GET", "/api/query/saved"): Op("Consultas guardadas", s.SavedQueries, "explorer:use",
                                    "The user's private queries, from the most recent to the oldest."),
    ("POST", "/api/query/saved"): Op(
        "Save a query", s.SavedQuery, "explorer:use",
        "Saves the query in canonical form. Without `from`/`to`, it remains relative to the default period.",
        status=201, errors=_e422("Empty name or invalid query.", (s.ErrorText, s.QueryErrors))),
    ("GET", "/api/query/saved/{query_id}"): Op("Consulta guardada", s.SavedQuery, "explorer:use",
                                               errors={404: ("It does not exist or belongs to another user.", s.ErrorText)}),
    ("PATCH", "/api/query/saved/{query_id}"): Op(
        "Rename or change a saved query", s.SavedQuery, "explorer:use",
        errors={404: ("It does not exist or belongs to another user.", s.ErrorText),
                422: ("Empty name or invalid query.", (s.ErrorText, s.QueryErrors))}),
    ("DELETE", "/api/query/saved/{query_id}"): Op("Delete a saved query", None, "explorer:use", status=204,
                                                  errors={404: ("It does not exist or belongs to another user.", s.ErrorText)}),

    # --- Búsqueda ---
    ("GET", "/api/search/semantic"): Op(
        "Semantic search", s.SemanticSearch, "search:use",
        "Searches 3-turn fragments by meaning (TF-IDF with synonyms, ADR-005). With `group=conversation`, the best fragment per conversation.",
        errors=_e422("Empty query or out-of-range parameters.", s.ErrorText)),
    ("GET", "/api/search/similar/{conversation_id}"): Op(
        "Conversaciones similares", s.SimilarConversations, "search:use", "The 10 most similar conversations.",
        errors={404: (NOT_FOUND, s.ErrorText)}),

    # --- Flujos ---
    ("GET", "/api/flows"): Op("Flujos", s.FlowList, "flows:view",
                              "Flows with their status and last run, from the most recently modified to the oldest.",
                              errors={503: (STATE_503, s.ErrorText)}),
    ("POST", "/api/flows"): Op("Create a flow", s.Flow, "flows:edit",
                               "Creates a flow with an empty graph or, with `template`, already configured to generate summary, main topic or both in one call (FE013).", status=201,
                               errors={**_e422("Empty name, unknown template or too many active main topics for the main topic template.", s.ErrorText),
                                       503: (STATE_503, s.ErrorText)}),
    ("GET", "/api/flows/catalog"): Op("Node options", s.FlowCatalog, "flows:view",
                                      "Configuration options of each node type, default model and limits."),
    ("POST", "/api/flows/validate"): Op(
        "Validate a graph", s.Validation, "flows:view",
        "Checks the completeness of a graph without saving it. A graph without integrity responds `422`.",
        body=Graph, errors=_e422("Graph without integrity.", s.GraphErrors)),
    ("POST", "/api/flows/sampling/estimate"): Op(
        "Estimate a sample", s.SampleEstimate, "flows:view",
        "How many conversations match the filters of a Sampling and how many the sample would have. `size` admits "
        "`\"all\"` (All conversations); with `after_download: true` the filters are optional and the count depends on "
        "the download.",
        errors=_e422("Invalid query.", s.QueryErrors)),
    ("GET", "/api/flows/{flow_id}"): Op("Flujo", s.Flow, "flows:view",
                                        errors={404: (NOT_FOUND, s.ErrorText), 503: (STATE_503, s.ErrorText)}),
    ("PATCH", "/api/flows/{flow_id}"): Op("Rename a flow", s.Flow, "flows:edit",
                                          errors={404: (NOT_FOUND, s.ErrorText), 422: ("Empty name.", s.ErrorText),
                                                  503: (STATE_503, s.ErrorText)}),
    ("DELETE", "/api/flows/{flow_id}"): Op("Delete a flow", None, "flows:edit", "It also deletes its runs.",
                                           status=204,
                                           errors={404: (NOT_FOUND, s.ErrorText), 503: (STATE_503, s.ErrorText)}),
    ("PUT", "/api/flows/{flow_id}/graph"): Op(
        "Save the graph", s.SavedFlow, "flows:edit",
        "Replaces the graph. Assigns a `1ND` identifier to each temporary node (`tmp-…`) and returns the mapping in `id_map`. Requires integrity, not completeness.",
        body=Graph, errors={404: (NOT_FOUND, s.ErrorText), 422: ("Graph without integrity.", s.GraphErrors),
                            503: (STATE_503, s.ErrorText)}),
    ("POST", "/api/flows/{flow_id}/duplicate"): Op("Duplicate a flow", s.Flow, "flows:edit",
                                                   "Creates “Copia de …” with new nodes.", status=201,
                                                   errors={404: (NOT_FOUND, s.ErrorText), 503: (STATE_503, s.ErrorText)}),
    ("POST", "/api/flows/{flow_id}/runs"): Op(
        "Run a flow", s.Run, "flows:edit",
        "Accepts the run and processes it in the background. Progress is queried with `GET /api/flows/{flow_id}/runs/{run_id}` (the front end does it every 500 ms while it is active).",
        status=202, ok_description="Run accepted (`status: pendiente`).",
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("This flow is already running.", s.ErrorText),
                422: ("The flow is not valid.", s.FlowIssues), 503: (STATE_503, s.ErrorText)}),
    ("GET", "/api/flows/{flow_id}/runs"): Op("Runs of a flow", s.RunList, "flows:view",
                                             "The last 50, from the most recent to the oldest.",
                                             errors={404: (NOT_FOUND, s.ErrorText), 503: (STATE_503, s.ErrorText)}),
    ("GET", "/api/flows/{flow_id}/runs/{run_id}"): Op(
        "Run", s.Run, "flows:view", "Snapshot with the status of each node and the results of each Output.",
        errors={404: (NOT_FOUND, s.ErrorText), 503: (STATE_503, s.ErrorText)}),
    ("GET", "/api/flows/{flow_id}/runs/{run_id}/download"): Op(
        "Download of the run", s.DownloadRun, "flows:view",
        "Status and counters of the download of the Genesys download box of the run (FE017). `404` if the run has "
        "no box.", errors={404: (NOT_FOUND, s.ErrorText), 503: (UNAVAILABLE_503, s.ErrorText)}),
    ("GET", "/api/flows/{flow_id}/runs/{run_id}/download/log"): Op(
        "Download log of the run", s.DownloadLog, "flows:view",
        "Log of the download of the Genesys download box, with the same `after`, `level` and `format` as a "
        "download flow log. It never contains the text of the turns or secrets.",
        errors={404: (NOT_FOUND, s.ErrorText), 503: (UNAVAILABLE_503, s.ErrorText)}),

    # --- Flujos de descarga (FE011) ---
    ("GET", "/api/download-flows"): Op(
        "Download flows", s.DownloadFlowList, "flows:view",
        "Genesys download flows with their last run and the next scheduled one, from the most recent to the oldest.",
        errors={503: (UNAVAILABLE_503, s.ErrorText)}),
    ("POST", "/api/download-flows"): Op(
        "Create a download flow", s.DownloadFlow, "flows:edit",
        "The author is the caller and the time zone is the platform's: “hoy”, “ayer” and the schedule are calculated in it.", status=201, body=s.DownloadFlowIn,
        errors={422: (DOWNLOAD_422, s.FieldErrors), 503: (UNAVAILABLE_503, s.ErrorText)}),
    ("GET", "/api/download-flows/{flow_id}"): Op(
        "Download flow", s.DownloadFlow, "flows:view",
        errors={404: (NOT_FOUND, s.ErrorText), 503: (UNAVAILABLE_503, s.ErrorText)}),
    ("PUT", "/api/download-flows/{flow_id}"): Op(
        "Save a download flow", s.DownloadFlow, "flows:edit",
        "Replaces the configuration and recalculates the next run; the author does not change and the time zone becomes the current one.", body=s.DownloadFlowIn,
        errors={404: (NOT_FOUND, s.ErrorText), 422: (DOWNLOAD_422, s.FieldErrors), 503: (UNAVAILABLE_503, s.ErrorText)}),
    ("DELETE", "/api/download-flows/{flow_id}"): Op(
        "Delete a download flow", None, "flows:edit", "It also deletes its runs and its logs.", status=204,
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("It has a run in progress.", s.ErrorText),
                503: (UNAVAILABLE_503, s.ErrorText)}),
    ("POST", "/api/download-flows/{flow_id}/runs"): Op(
        "Descargar ahora", s.DownloadRun, "flows:edit",
        "Resolves the interval at this moment, creates the `pendiente` run and starts it in the background. Progress is queried with `GET /api/download-flows/{flow_id}/runs/{run_id}`.", status=202,
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("This flow is already running.", s.ErrorText),
                503: (UNAVAILABLE_503, s.ErrorText)}),
    ("GET", "/api/download-flows/{flow_id}/runs"): Op(
        "Download history", s.DownloadRunList, "flows:view",
        "Runs of the flow, from the most recent to the oldest (the last 200 are kept).",
        errors={404: (NOT_FOUND, s.ErrorText), 503: (UNAVAILABLE_503, s.ErrorText)}),
    ("GET", "/api/download-flows/{flow_id}/runs/{run_id}"): Op(
        "Descarga", s.DownloadRun, "flows:view", "Status and counters, updated after each conversation.",
        errors={404: (NOT_FOUND, s.ErrorText), 503: (UNAVAILABLE_503, s.ErrorText)}),
    ("GET", "/api/download-flows/{flow_id}/runs/{run_id}/log"): Op(
        "Download log", s.DownloadLog, "flows:view",
        "Entries from `after` (`id` cursor), filterable by `level`. With `format=text`, the full log as a `text/plain` attachment. It never contains the text of the turns or secrets.",
        errors={404: (NOT_FOUND, s.ErrorText), 503: (UNAVAILABLE_503, s.ErrorText)}),

    # --- Configuración ---
    ("GET", "/api/config/public"): Op("Public settings", s.PublicConfig, public=True,
                                      description="Name, time zone and language: the login and all roles need them."),
    ("GET", "/api/config"): Op("Settings", s.PlatformConfig, "config:view",
                               "Full settings, version and options of the selectors."),
    ("PUT", "/api/config/general"): Op("Guardar General", s.PlatformConfig, "config:edit", body=GeneralConfig,
                                       errors={**_e422("Per-field errors.", s.FieldErrors),
                                               503: (CONFIG_503, s.ErrorText)}),
    ("PUT", "/api/config/sources"): Op("Save Data origin", s.PlatformConfig, "config:edit", body=SourcesConfig,
                                       description="Changes the data origin of the whole platform (FE012).",
                                       errors={**_e422("Origen desconocido.", s.FieldErrors),
                                               503: (CONFIG_503, s.ErrorText)}),
    ("PUT", "/api/config/privacy"): Op("Guardar Privacidad", s.PlatformConfig, "config:edit", body=PrivacyConfig,
                                       errors={**_e422("Per-field errors.", s.FieldErrors),
                                               503: (CONFIG_503, s.ErrorText)}),
    ("PUT", "/api/config/ai"): Op("Save AI models", s.PlatformConfig, "config:edit", body=AiConfig,
                                  errors={**_e422("Unknown provider or model.", s.FieldErrors),
                                          503: (CONFIG_503, s.ErrorText)}),
    ("GET", "/api/config/ai/status"): Op(
        "LLM service status", s.AiStatus, "config:view",
        "Which providers have a key in the LLM service (yes or no, never the key).",
        errors={503: (LLM_503, s.ErrorText)}),
    ("POST", "/api/config/ai/test/{provider}"): Op(
        "Test an LLM provider", s.AiTestResult, "config:edit",
        "Makes a minimal request with the given model. A provider error (no key, rejected key…) responds `200` with `ok: false` and its message.", body=s.AiTestIn,
        errors={422: ("Unknown provider or model of another provider.", s.FieldErrors),
                503: (LLM_503, s.ErrorText)}),
    ("GET", "/api/config/connectors"): Op("Conectores", s.Connectors, "config:view",
                                          "Mock Genesys connectors with their conversation volume."),
    ("POST", "/api/config/connectors/{connector_id}/sync"): Op(
        "Sync a connector", s.Connector, "config:edit",
        "Simulated: updates the sync date and does not change the dataset.", errors={404: (NOT_FOUND, s.ErrorText)}),
    ("GET", "/api/config/connectors/genesys"): Op(
        "Genesys Cloud connector", s.GenesysConnector, "config:view",
        "Status of the ingestion service (FE011): region, configured credentials, last test and last download, and stored conversations by channel and by transcript quality. If the service does not respond, `200` with `service: no_disponible`."),
    ("POST", "/api/config/connectors/genesys/test"): Op(
        "Test the connection with Genesys Cloud", s.GenesysTest, "config:edit",
        "The ingestion service requests a token with the `.env` credentials and reads the organization. A credentials failure is `200` with `ok: false`.", errors={503: (UNAVAILABLE_503, s.ErrorText)}),
    ("GET", "/api/config/audit"): Op("Settings change log", s.AuditLog, "config:view",
                                     "Entries of the settings sections, from the most recent to the oldest."),
    ("GET", "/api/config/taxonomy"): Op("Taxonomy", s.Taxonomy, "config:view",
                                        "Main topics and secondary topics with their number of conversations."),
    ("POST", "/api/config/taxonomy/{kind_name}"): Op(
        "Create a topic", s.TaxonomyTopic, "config:edit",
        "`MainTopicIn` for `main-topics`; `SecondaryTopicIn` for `secondary-topics`.", status=201,
        body=(MainTopicIn, SecondaryTopicIn), errors=_e422("Per-field errors (including duplicate code or name).",
                                                           s.FieldErrors)),
    ("PUT", "/api/config/taxonomy/{kind_name}/{topic_id}"): Op(
        "Edit a topic", s.TaxonomyTopic, "config:edit", "The code cannot be changed.",
        body=(MainTopicIn, SecondaryTopicIn),
        errors={404: (NOT_FOUND, s.ErrorText), 422: ("Per-field errors.", s.FieldErrors)}),
    ("DELETE", "/api/config/taxonomy/{kind_name}/{topic_id}"): Op(
        "Delete a topic", None, "config:edit",
        "A main topic is checked in the synthetic dataset and in the real PostgreSQL conversations, whichever origin is active.", status=204,
        errors={404: (NOT_FOUND, s.ErrorText),
                409: ("It is assigned to conversations (the message gives the count of each origin): it cannot be deleted, only deactivated.", s.ErrorText),
                503: ("Usage in the real data cannot be checked (PostgreSQL does not respond).", s.ErrorText)}),
    ("GET", "/api/config/compliance-checks"): Op("Compliance checks", s.ComplianceChecks, "config:view"),
    ("POST", "/api/config/compliance-checks"): Op(
        "Create a check", s.ComplianceCheck, "config:edit", "It is evaluated by phrases said by the agent.", status=201,
        body=CheckIn, errors=_e422("Per-field errors (including duplicate code or name).", s.FieldErrors)),
    ("PUT", "/api/config/compliance-checks/{check_id}"): Op(
        "Edit a check", s.ComplianceCheck, "config:edit", "The code cannot be changed.", body=CheckIn,
        errors={404: (NOT_FOUND, s.ErrorText), 422: ("Per-field errors.", s.FieldErrors)}),
    ("DELETE", "/api/config/compliance-checks/{check_id}"): Op(
        "Delete a check", None, "config:edit", status=204,
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("It is an analysis check: it can only be deactivated.", s.ErrorText)}),
    ("PUT", "/api/config/kpis/{code}"): Op(
        "Target and thresholds of a KPI", s.PlatformConfig, "config:edit",
        "Green and amber thresholds (both or neither), consistent with the direction of the KPI and within the range of its unit.",
        body=KpiTargetIn, errors={404: ("KPI desconocido.", s.ErrorText), 422: ("Per-field errors.", s.FieldErrors)}),

    # --- Usuarios y roles ---
    ("GET", "/api/users"): Op("Usuarios", s.ManagedUsers, "users:admin",
                              "Search by name or email (accent- and case-insensitive) and filters by role and status."),
    ("POST", "/api/users"): Op(
        "Create a user", s.ManagedUser, "users:admin",
        "Normalized email (no spaces, lowercase) and unique. The user signs in with the demo password.", status=201,
        body=UserIn, errors={409: ("Duplicate email (in the `email` field).", s.FieldErrors),
                             422: ("Per-field errors (including unknown role).", s.FieldErrors)}),
    ("PUT", "/api/users/{user_id}"): Op(
        "Edit, deactivate or reactivate a user", s.ManagedUser, "users:admin",
        "Full body; `active: false` deactivates the user and invalidates their session on the next request.",
        body=UserIn,
        errors={404: (NOT_FOUND, s.ErrorText),
                409: ("Duplicate email (`FieldErrors`) or administration protection (`ErrorText`): removing `users:admin` from oneself or leaving no active `admin`.", (s.FieldErrors, s.ErrorText)),
                422: ("Per-field errors.", s.FieldErrors)}),
    ("GET", "/api/users/audit"): Op("Users and roles change log", s.AuditLog, "users:admin"),
    ("GET", "/api/roles"): Op("Roles and permission catalog", s.Roles, "users:admin",
                              "Roles with their number of users and the permission catalog for the matrix."),
    ("POST", "/api/roles"): Op(
        "Create a custom role", s.RoleItem, "users:admin", status=201, body=NewRoleIn,
        errors={409: ("Duplicate code or name (per field).", s.FieldErrors),
                422: ("Per-field errors (including unknown permission).", s.FieldErrors)}),
    ("PUT", "/api/roles/{role_id}"): Op(
        "Change the name and permissions of a role", s.RoleItem, "users:admin",
        "Full list of permissions. Built-in roles cannot be renamed.", body=RoleIn,
        errors={404: (NOT_FOUND, s.ErrorText), 409: (PROTECTION_409, s.ErrorText),
                422: ("Per-field errors.", s.FieldErrors)}),
    ("DELETE", "/api/roles/{role_id}"): Op(
        "Delete a custom role", None, "users:admin", status=204,
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("Built-in role or with assigned users.", s.ErrorText)}),
}

EXAMPLES: dict[tuple[str, str], dict[str, Any]] = {
    ("POST", "/api/auth/login"): {"email": "analista@bancohorizonte.demo", "password": "demo"},
    ("POST", "/api/query/run"): {"from": "2026-08-28", "to": "2026-09-26", "root": {"op": "and", "conditions": [
        {"field": "channel", "operator": "is", "value": "chat"},
        {"field": "sentiment", "operator": "lt", "value": -0.3},
        {"op": "or", "conditions": [{"field": "check:saludo", "operator": "fails"},
                                    {"field": "transcript", "operator": "contains", "value": "PIN", "speaker": "agente"}]}]}},
    ("PUT", "/api/flows/{flow_id}/graph"): {"version": 1, "nodes": [
        {"id": "tmp-s", "type": "sampling", "position": {"x": 0, "y": 0},
         "config": {"query": {"root": {"op": "and", "conditions": []}}, "method": "aleatorio", "size": 20}},
        {"id": "tmp-p", "type": "prompt", "position": {"x": 300, "y": 0},
         "config": {"template": "Clasifica el motivo: {{transcripcion}}", "model": "mock-rapido", "temperature": 0.2,
                    "output": {"type": "etiqueta", "labels": ["queja", "consulta"]}}},
        {"id": "tmp-o", "type": "output", "position": {"x": 600, "y": 0},
         "config": {"kind": "metrica", "aggregation": "porcentaje", "destination": "Motivos"}}],
        "edges": [{"source": "tmp-s", "target": "tmp-p"}, {"source": "tmp-p", "target": "tmp-o"}]},
    ("POST", "/api/users"): {"name": "Lucía Pérez", "email": "lucia.perez@bancohorizonte.demo", "role": "analista"},
    ("POST", "/api/download-flows"): {"name": "Descarga diaria", "interval": {"type": "relativo", "unit": "ayer"},
                                     "channels": ["voz", "chat"], "schedule": {"type": "diaria", "time": "07:30"},
                                     "active": True},
    ("POST", "/api/roles"): {"code": "lector_flujos", "name": "Lector de flujos", "permissions": ["flows:view"]},
    ("PUT", "/api/config/kpis/{code}"): {"target": 4, "green": 4, "amber": 3.5, "dashboards": ["vision-general"]},
}


def _as_tuple(models: Models | None) -> tuple[type[BaseModel], ...]:
    if models is None:
        return ()
    return models if isinstance(models, tuple) else (models,)


def _collect_models() -> list[tuple[type[BaseModel], str]]:
    pairs: dict[tuple[type[BaseModel], str], None] = {}
    for op in OPERATIONS.values():
        if op.ok is not None:
            pairs[(op.ok, "serialization")] = None
        for model in _as_tuple(op.body):
            pairs[(model, "validation")] = None
        for _, models in op.errors.values():
            for model in _as_tuple(models):
                pairs[(model, "serialization")] = None
    pairs[(s.ErrorText, "serialization")] = None
    return list(pairs)


def _content(refs: list[dict]) -> dict:
    schema = refs[0] if len(refs) == 1 else {"oneOf": refs}
    return {"application/json": {"schema": schema}}


def build_openapi(app: FastAPI) -> dict:
    spec = get_openapi(title=app.title, version=API_VERSION, description=DESCRIPTION, routes=app.routes, tags=TAGS)
    keys, definitions = models_json_schema(_collect_models(), ref_template="#/components/schemas/{model}")
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    for name, schema in definitions.get("$defs", {}).items():
        if name in schemas and schemas[name] != schema:
            raise ValueError(f"Duplicate OpenAPI schema with different content: {name}")
        schemas[name] = schema

    def ref(model: type[BaseModel], mode: str = "serialization") -> dict:
        return keys[(model, mode)]

    spec["components"]["securitySchemes"] = {"bearerAuth": {
        "type": "http", "scheme": "bearer",
        "description": "Token from `POST /api/auth/login`. Expires after 8 h (`AUTH_TOKEN_TTL_SECONDS`)."}}
    spec["components"]["headers"] = {"XAuthVersion": {
        "description": "Users and roles version; if it changes, `/api/auth/me` must be requested again (FE006).",
        "schema": {"type": "integer", "minimum": 0}}}
    spec["security"] = [{"bearerAuth": []}]
    spec["info"]["x-permissions"] = [{"value": p, "label": PERMISSION_LABELS[p]} for p in ALL_PERMISSIONS]

    documented = set()
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            key = (method.upper(), path)
            if key not in OPERATIONS:
                raise ValueError(f"Operation not documented in app/openapi/spec.py: {method.upper()} {path}")
            documented.add(key)
            _document(operation, OPERATIONS[key], key, ref)
    missing = set(OPERATIONS) - documented
    if missing:
        raise ValueError(f"Documented operations that do not exist: {sorted(missing)}")
    return spec


def _permissions(op: Op) -> str:
    permissions = op.permission if isinstance(op.permission, tuple) else (op.permission,)
    return " o ".join(f"`{p}`" for p in permissions)


def _document(operation: dict, op: Op, key: tuple[str, str], ref) -> None:
    operation["summary"] = op.summary
    access = ("Public." if op.public else "Requires a session." if op.permission is None else
              f"Permission: {_permissions(op)}.")
    operation["description"] = f"{access} {op.description}".strip()
    # FastAPI declara su propio esquema `HTTPBearer` en las rutas con la dependencia de auth; todas heredan el global.
    operation.pop("security", None)
    if op.public:
        operation["security"] = []
    if op.body is not None:
        body_refs = [ref(model, "validation") for model in _as_tuple(op.body)]
        operation["requestBody"] = {"required": True, "content": _content(body_refs)}
    if key in EXAMPLES:
        operation["requestBody"]["content"]["application/json"]["example"] = EXAMPLES[key]

    generated = operation.get("responses", {})
    responses: dict[str, dict] = {}
    ok = generated.get(str(op.status), {})
    if op.status == 204:
        responses["204"] = {"description": "Done, no body."}
    elif op.ok is None:  # usa el `response_model` que declara la ruta (login y me)
        responses[str(op.status)] = {**ok, "description": op.ok_description or "Correcto."}
    else:
        responses[str(op.status)] = {"description": op.ok_description or "Correcto.", "content": _content([ref(op.ok)])}

    errors = dict(op.errors)
    if not op.public:
        errors.setdefault(401, ("No valid session: the token is missing, tampered with or expired, or the user is deactivated.", s.ErrorText))
        if op.permission is not None:
            errors.setdefault(403, (f"Missing permission {_permissions(op)}.", s.ErrorText))
    validation = "422" in generated  # FastAPI valida parámetros o un cuerpo declarado: error nativo (en inglés)
    for status_code in sorted(set(errors) | ({422} if validation else set())):
        description, models = errors.get(status_code, ("Invalid parameters.", ()))
        refs = [ref(model) for model in _as_tuple(models)]
        if status_code == 422 and validation:
            refs.append({"$ref": "#/components/schemas/HTTPValidationError"})
            if len(refs) > 1:
                description += " Out-of-range or wrongly typed parameters return the native FastAPI error."
        responses[str(status_code)] = {"description": description, "content": _content(refs)}

    if not op.public:
        for response in responses.values():
            response["headers"] = {AUTH_VERSION_HEADER: {"$ref": "#/components/headers/XAuthVersion"}}
    operation["responses"] = responses
