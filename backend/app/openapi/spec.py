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
from app.config.model import AiConfig, GeneralConfig, PrivacyConfig
from app.config.taxonomy import MainTopicIn, SecondaryTopicIn
from app.flows.model import Graph
from app.openapi import schemas as s
from app.query.model import Query
from app.routers.users import NewRoleIn, RoleIn, UserIn

API_VERSION = "0.6.0"
AUTH_VERSION_HEADER = "X-Auth-Version"

DESCRIPTION = """
API de la plataforma de Speech & Text Analytics de Banco Horizonte (datos mock). La consume el front React.

**Autenticación.** `POST /api/auth/login` devuelve un token que se envía como `Authorization: Bearer <token>`. El
usuario y los permisos de su rol se releen en cada petición. Sin token o con un token no válido: `401`. Sin el
permiso de la operación: `403`. Cada operación indica su permiso en la descripción.

**`X-Auth-Version`.** Toda respuesta a una petición con sesión lleva esta cabecera: un entero que sube con cada cambio
de usuarios o roles. Si cambia, el front vuelve a pedir `/api/auth/me`.

**Identificadores.** `PREFIJO-UUID` en mayúsculas (`1CO` conversación, `1QU` cola, `1AG` agente, `1US` usuario,
`1RO` rol, `1FL` flujo, `1ND` nodo, `1RN` ejecución, `1QY` consulta guardada, `1TP`/`1TS` temas, `1CK` check, `1CN`
conector, `1AU` auditoría). En las rutas se aceptan en minúsculas.

**Fechas.** Instantes en ISO 8601 con desfase. `from` y `to` son días (`YYYY-MM-DD`, incluidos) en la zona horaria
configurada; por defecto, los 30 días que acaban el día anterior a la fecha de referencia del dataset.

**Errores.** Siempre con `detail`, en seis formas según la operación: texto (`ErrorText`), validación nativa de FastAPI
(`HTTPValidationError`, en inglés), errores por campo (`FieldErrors`), errores de consulta (`QueryErrors`), errores de
grafo (`GraphErrors`) e incidencias de flujo (`FlowIssues`).

**Persistencia.** Todo lo que se escribe vive en memoria y se pierde al reiniciar la API.

Referencia ampliada: `vault/arquitectura/contrato-api-front-back.md`.
""".strip()

TAGS = [
    {"name": "health", "description": "Sonda de salud."},
    {"name": "auth", "description": "Inicio de sesión y usuario actual."},
    {"name": "metrics", "description": "KPIs de los dashboards (FE001, FE005)."},
    {"name": "conversations", "description": "Listado, detalle y catálogo de filtros (FE001)."},
    {"name": "query", "description": "Explorador de consultas asistidas y consultas guardadas (FE002)."},
    {"name": "search", "description": "Búsqueda semántica y conversaciones similares (FE003)."},
    {"name": "flows", "description": "Flujos de insights y sus ejecuciones simuladas (FE004)."},
    {"name": "config", "description": "Configuración global de la plataforma (FE005)."},
    {"name": "users", "description": "Usuarios, roles y matriz de permisos (FE006)."},
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


NOT_FOUND = "No existe (o el identificador es de otro tipo)."


def _e422(description: str, models: Models) -> dict[int, tuple[str, Models]]:
    return {422: (description, models)}


FILTERS_422 = _e422("`from` posterior a `to` o identificador de cola o agente mal formado.", s.ErrorText)
PROTECTION_409 = ("Protección de administración: quitarse a uno mismo `users:admin`, dejar sin ningún `admin` activo "
                  "o quitar `users:admin` al rol `admin`.")


OPERATIONS: dict[tuple[str, str], Op] = {
    # --- Salud y sesión ---
    ("GET", "/api/health"): Op("Sonda de salud", s.Health, public=True,
                               description="Responde cuando la API ha terminado de arrancar (índice de búsqueda construido)."),
    ("POST", "/api/auth/login"): Op(
        "Iniciar sesión", None, public=True,
        description="Devuelve el token Bearer (caduca a las 8 h) y el usuario con sus permisos. Anota el último acceso. "
                    "El email no distingue mayúsculas.",
        errors={401: ("Credenciales incorrectas, usuario inexistente o desactivado (misma respuesta).", s.ErrorText)}),
    ("GET", "/api/auth/me"): Op("Usuario actual", None,
                                description="Usuario de la sesión, nombre de su rol y permisos vigentes."),

    # --- Métricas ---
    ("GET", "/api/metrics/summary"): Op(
        "Resumen de KPIs", s.Summary, "dashboards:view",
        "Los 13 KPIs del periodo con el periodo anterior (misma longitud), variación, objetivo y estado según los "
        "umbrales de Configuración. Con `dashboard`, solo los KPIs configurados para ese dashboard. Incluye el "
        "cumplimiento por check activo.",
        errors=FILTERS_422),
    ("GET", "/api/metrics/timeseries"): Op(
        "Serie temporal de un KPI", s.Timeseries, "dashboards:view",
        "Un punto por día o por semana (lunes a domingo, recortada al periodo), en la zona horaria configurada.",
        errors=FILTERS_422),
    ("GET", "/api/metrics/breakdown"): Op(
        "KPIs por dimensión", s.Breakdown, "dashboards:view",
        "Los 13 KPIs por main topic, canal, cola o agente, ordenados por volumen.",
        errors=FILTERS_422),
    ("GET", "/api/catalog"): Op(
        "Catálogo de filtros", s.Catalog, ("dashboards:view", "conversations:view"),
        "Canales, colas, agentes, main topics (también desactivados), checks activos, resoluciones, riesgos y fecha "
        "de referencia."),

    # --- Conversaciones ---
    ("GET", "/api/conversations"): Op(
        "Listado de conversaciones", s.ConversationPage, "conversations:view",
        "Listado filtrado, paginado y ordenado. Los filtros `resolution`, `churn_risk`, `sentiment_lt`, `compliant` y "
        "`repeat_contact` son los del drill-down: seleccionan el numerador de cada KPI.",
        errors=FILTERS_422),
    ("GET", "/api/conversations/{conversation_id}"): Op(
        "Detalle de una conversación", s.ConversationDetail, "conversations:view",
        "Turnos y análisis completo. Texto enmascarado si el enmascarado de PII está activado.",
        errors={404: (NOT_FOUND, s.ErrorText)}),

    # --- Explorador ---
    ("GET", "/api/query/schema"): Op(
        "Campos del explorador", s.QuerySchema, ("explorer:use", "flows:view"),
        "Campos con su tipo, operadores, valores y rangos, más la fecha de referencia y el periodo por defecto."),
    ("POST", "/api/query/run"): Op(
        "Ejecutar una consulta", s.QueryResult, "explorer:use",
        "Ejecuta una consulta (`Query`) y devuelve el total, los 13 KPIs del resultado y una página del listado. "
        "Máximo 50 condiciones, 2 niveles de grupos y 200 valores por lista.",
        body=Query, errors=_e422("Consulta no válida (por condición) o parámetros fuera de rango.", s.QueryErrors)),
    ("GET", "/api/query/suggest"): Op(
        "Valores de un campo", s.Suggestions, ("explorer:use", "flows:view"),
        "Valores de un campo categórico en el intervalo, con su recuento.",
        errors=_e422("Campo no categórico o `from` posterior a `to`.", s.ErrorText)),
    ("POST", "/api/query/interpret"): Op(
        "Interpretar una frase", s.Interpretation, "explorer:use",
        "Convierte una frase en español (1–500 caracteres) en una consulta editable. No la ejecuta.",
        errors=_e422("Frase vacía o demasiado larga.", s.ErrorText)),
    ("GET", "/api/query/saved"): Op("Consultas guardadas", s.SavedQueries, "explorer:use",
                                    "Consultas privadas del usuario, de la más reciente a la más antigua."),
    ("POST", "/api/query/saved"): Op(
        "Guardar una consulta", s.SavedQuery, "explorer:use",
        "Guarda la consulta en forma canónica. Sin `from`/`to`, sigue siendo relativa al periodo por defecto.",
        status=201, errors=_e422("Nombre vacío o consulta no válida.", (s.ErrorText, s.QueryErrors))),
    ("GET", "/api/query/saved/{query_id}"): Op("Consulta guardada", s.SavedQuery, "explorer:use",
                                               errors={404: ("No existe o es de otro usuario.", s.ErrorText)}),
    ("PATCH", "/api/query/saved/{query_id}"): Op(
        "Renombrar o cambiar una consulta guardada", s.SavedQuery, "explorer:use",
        errors={404: ("No existe o es de otro usuario.", s.ErrorText),
                422: ("Nombre vacío o consulta no válida.", (s.ErrorText, s.QueryErrors))}),
    ("DELETE", "/api/query/saved/{query_id}"): Op("Borrar una consulta guardada", None, "explorer:use", status=204,
                                                  errors={404: ("No existe o es de otro usuario.", s.ErrorText)}),

    # --- Búsqueda ---
    ("GET", "/api/search/semantic"): Op(
        "Búsqueda semántica", s.SemanticSearch, "search:use",
        "Busca fragmentos de 3 turnos por significado (TF-IDF con sinónimos, ADR-005). Con `group=conversation`, el "
        "mejor fragmento por conversación.",
        errors=_e422("Consulta vacía o parámetros fuera de rango.", s.ErrorText)),
    ("GET", "/api/search/similar/{conversation_id}"): Op(
        "Conversaciones similares", s.SimilarConversations, "search:use", "Las 10 conversaciones más parecidas.",
        errors={404: (NOT_FOUND, s.ErrorText)}),

    # --- Flujos ---
    ("GET", "/api/flows"): Op("Flujos", s.FlowList, "flows:view",
                              "Flujos con su estado y su última ejecución, del modificado más recientemente al más antiguo."),
    ("POST", "/api/flows"): Op("Crear un flujo", s.Flow, "flows:edit", "Crea un flujo con el grafo vacío.", status=201,
                               errors=_e422("Nombre vacío.", s.ErrorText)),
    ("GET", "/api/flows/catalog"): Op("Opciones de los nodos", s.FlowCatalog, "flows:view",
                                      "Opciones de configuración de cada tipo de nodo, modelo por defecto y límites."),
    ("POST", "/api/flows/validate"): Op(
        "Validar un grafo", s.Validation, "flows:view",
        "Comprueba la completitud de un grafo sin guardarlo. Un grafo sin integridad responde `422`.",
        body=Graph, errors=_e422("Grafo sin integridad.", s.GraphErrors)),
    ("POST", "/api/flows/sampling/estimate"): Op(
        "Estimar una muestra", s.SampleEstimate, "flows:view",
        "Cuántas conversaciones cumplen los filtros de un Sampling y cuántas tendría la muestra.",
        errors=_e422("Consulta no válida.", s.QueryErrors)),
    ("GET", "/api/flows/{flow_id}"): Op("Flujo", s.Flow, "flows:view", errors={404: (NOT_FOUND, s.ErrorText)}),
    ("PATCH", "/api/flows/{flow_id}"): Op("Renombrar un flujo", s.Flow, "flows:edit",
                                          errors={404: (NOT_FOUND, s.ErrorText), 422: ("Nombre vacío.", s.ErrorText)}),
    ("DELETE", "/api/flows/{flow_id}"): Op("Borrar un flujo", None, "flows:edit", "Borra también sus ejecuciones.",
                                           status=204, errors={404: (NOT_FOUND, s.ErrorText)}),
    ("PUT", "/api/flows/{flow_id}/graph"): Op(
        "Guardar el grafo", s.SavedFlow, "flows:edit",
        "Reemplaza el grafo. Asigna un identificador `1ND` a cada nodo temporal (`tmp-…`) y devuelve la "
        "correspondencia en `id_map`. Exige integridad, no completitud.",
        body=Graph, errors={404: (NOT_FOUND, s.ErrorText), 422: ("Grafo sin integridad.", s.GraphErrors)}),
    ("POST", "/api/flows/{flow_id}/duplicate"): Op("Duplicar un flujo", s.Flow, "flows:edit",
                                                   "Crea «Copia de …» con nodos nuevos.", status=201,
                                                   errors={404: (NOT_FOUND, s.ErrorText)}),
    ("POST", "/api/flows/{flow_id}/runs"): Op(
        "Ejecutar un flujo", s.Run, "flows:edit",
        "Acepta la ejecución y la procesa en segundo plano. El progreso se consulta con "
        "`GET /api/flows/{flow_id}/runs/{run_id}` (el front lo hace cada 500 ms mientras está activa).",
        status=202, ok_description="Ejecución aceptada (`status: pendiente`).",
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("Ya hay una ejecución en curso de este flujo.", s.ErrorText),
                422: ("El flujo no es válido.", s.FlowIssues)}),
    ("GET", "/api/flows/{flow_id}/runs"): Op("Ejecuciones de un flujo", s.RunList, "flows:view",
                                             "Las 50 últimas, de la más reciente a la más antigua.",
                                             errors={404: (NOT_FOUND, s.ErrorText)}),
    ("GET", "/api/flows/{flow_id}/runs/{run_id}"): Op(
        "Ejecución", s.Run, "flows:view", "Instantánea con el estado de cada nodo y los resultados de cada Output.",
        errors={404: (NOT_FOUND, s.ErrorText)}),

    # --- Configuración ---
    ("GET", "/api/config/public"): Op("Configuración pública", s.PublicConfig, public=True,
                                      description="Nombre, zona horaria e idioma: los necesitan el login y todos los roles."),
    ("GET", "/api/config"): Op("Configuración", s.PlatformConfig, "config:view",
                               "Configuración completa, versión y opciones de los selectores."),
    ("PUT", "/api/config/general"): Op("Guardar General", s.PlatformConfig, "config:edit", body=GeneralConfig,
                                       errors=_e422("Errores por campo.", s.FieldErrors)),
    ("PUT", "/api/config/privacy"): Op("Guardar Privacidad", s.PlatformConfig, "config:edit", body=PrivacyConfig,
                                       errors=_e422("Errores por campo.", s.FieldErrors)),
    ("PUT", "/api/config/ai"): Op("Guardar Modelos de IA", s.PlatformConfig, "config:edit", body=AiConfig,
                                  errors=_e422("Proveedor o modelo desconocidos.", s.FieldErrors)),
    ("GET", "/api/config/connectors"): Op("Conectores", s.Connectors, "config:view",
                                          "Conectores mock de Genesys con su volumen de conversaciones."),
    ("POST", "/api/config/connectors/{connector_id}/sync"): Op(
        "Sincronizar un conector", s.Connector, "config:edit",
        "Simulado: actualiza la fecha de sincronización y no cambia el dataset.", errors={404: (NOT_FOUND, s.ErrorText)}),
    ("GET", "/api/config/audit"): Op("Registro de cambios de la configuración", s.AuditLog, "config:view",
                                     "Entradas de las secciones de configuración, de la más reciente a la más antigua."),
    ("GET", "/api/config/taxonomy"): Op("Taxonomía", s.Taxonomy, "config:view",
                                        "Main topics y temas secundarios con su número de conversaciones."),
    ("POST", "/api/config/taxonomy/{kind_name}"): Op(
        "Crear un tema", s.TaxonomyTopic, "config:edit",
        "`MainTopicIn` para `main-topics`; `SecondaryTopicIn` para `secondary-topics`.", status=201,
        body=(MainTopicIn, SecondaryTopicIn), errors=_e422("Errores por campo (incluido código o nombre duplicado).",
                                                           s.FieldErrors)),
    ("PUT", "/api/config/taxonomy/{kind_name}/{topic_id}"): Op(
        "Editar un tema", s.TaxonomyTopic, "config:edit", "El código no se puede cambiar.",
        body=(MainTopicIn, SecondaryTopicIn),
        errors={404: (NOT_FOUND, s.ErrorText), 422: ("Errores por campo.", s.FieldErrors)}),
    ("DELETE", "/api/config/taxonomy/{kind_name}/{topic_id}"): Op(
        "Borrar un tema", None, "config:edit", status=204,
        errors={404: (NOT_FOUND, s.ErrorText),
                409: ("Está asignado a conversaciones: no se puede borrar, solo desactivar.", s.ErrorText)}),
    ("GET", "/api/config/compliance-checks"): Op("Checks de cumplimiento", s.ComplianceChecks, "config:view"),
    ("POST", "/api/config/compliance-checks"): Op(
        "Crear un check", s.ComplianceCheck, "config:edit", "Se evalúa por frases dichas por el agente.", status=201,
        body=CheckIn, errors=_e422("Errores por campo (incluido código o nombre duplicado).", s.FieldErrors)),
    ("PUT", "/api/config/compliance-checks/{check_id}"): Op(
        "Editar un check", s.ComplianceCheck, "config:edit", "El código no se puede cambiar.", body=CheckIn,
        errors={404: (NOT_FOUND, s.ErrorText), 422: ("Errores por campo.", s.FieldErrors)}),
    ("DELETE", "/api/config/compliance-checks/{check_id}"): Op(
        "Borrar un check", None, "config:edit", status=204,
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("Es un check del análisis: solo se puede desactivar.", s.ErrorText)}),
    ("PUT", "/api/config/kpis/{code}"): Op(
        "Objetivo y umbrales de un KPI", s.PlatformConfig, "config:edit",
        "Umbrales verde y ámbar (los dos o ninguno), coherentes con el sentido del KPI y dentro del rango de su unidad.",
        body=KpiTargetIn, errors={404: ("KPI desconocido.", s.ErrorText), 422: ("Errores por campo.", s.FieldErrors)}),

    # --- Usuarios y roles ---
    ("GET", "/api/users"): Op("Usuarios", s.ManagedUsers, "users:admin",
                              "Búsqueda por nombre o email (sin tildes ni mayúsculas) y filtros por rol y estado."),
    ("POST", "/api/users"): Op(
        "Crear un usuario", s.ManagedUser, "users:admin",
        "Email normalizado (sin espacios, en minúsculas) y único. El usuario entra con la contraseña demo.", status=201,
        body=UserIn, errors={409: ("Email duplicado (en el campo `email`).", s.FieldErrors),
                             422: ("Errores por campo (rol desconocido incluido).", s.FieldErrors)}),
    ("PUT", "/api/users/{user_id}"): Op(
        "Editar, desactivar o reactivar un usuario", s.ManagedUser, "users:admin",
        "Cuerpo completo; `active: false` desactiva al usuario e invalida su sesión en la siguiente petición.",
        body=UserIn,
        errors={404: (NOT_FOUND, s.ErrorText),
                409: ("Email duplicado (`FieldErrors`) o protección de administración (`ErrorText`): quitarse a uno "
                      "mismo `users:admin` o dejar sin ningún `admin` activo.", (s.FieldErrors, s.ErrorText)),
                422: ("Errores por campo.", s.FieldErrors)}),
    ("GET", "/api/users/audit"): Op("Registro de cambios de usuarios y roles", s.AuditLog, "users:admin"),
    ("GET", "/api/roles"): Op("Roles y catálogo de permisos", s.Roles, "users:admin",
                              "Roles con su número de usuarios y el catálogo de permisos para la matriz."),
    ("POST", "/api/roles"): Op(
        "Crear un rol personalizado", s.RoleItem, "users:admin", status=201, body=NewRoleIn,
        errors={409: ("Código o nombre duplicados (por campo).", s.FieldErrors),
                422: ("Errores por campo (permiso desconocido incluido).", s.FieldErrors)}),
    ("PUT", "/api/roles/{role_id}"): Op(
        "Cambiar nombre y permisos de un rol", s.RoleItem, "users:admin",
        "Lista completa de permisos. Los roles base no se renombran.", body=RoleIn,
        errors={404: (NOT_FOUND, s.ErrorText), 409: (PROTECTION_409, s.ErrorText),
                422: ("Errores por campo.", s.FieldErrors)}),
    ("DELETE", "/api/roles/{role_id}"): Op(
        "Borrar un rol personalizado", None, "users:admin", status=204,
        errors={404: (NOT_FOUND, s.ErrorText), 409: ("Rol base o con usuarios asignados.", s.ErrorText)}),
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
            raise ValueError(f"Esquema OpenAPI duplicado con distinto contenido: {name}")
        schemas[name] = schema

    def ref(model: type[BaseModel], mode: str = "serialization") -> dict:
        return keys[(model, mode)]

    spec["components"]["securitySchemes"] = {"bearerAuth": {
        "type": "http", "scheme": "bearer",
        "description": "Token de `POST /api/auth/login`. Caduca a las 8 h (`AUTH_TOKEN_TTL_SECONDS`)."}}
    spec["components"]["headers"] = {"XAuthVersion": {
        "description": "Versión de usuarios y roles; si cambia, hay que volver a pedir `/api/auth/me` (FE006).",
        "schema": {"type": "integer", "minimum": 0}}}
    spec["security"] = [{"bearerAuth": []}]
    spec["info"]["x-permissions"] = [{"value": p, "label": PERMISSION_LABELS[p]} for p in ALL_PERMISSIONS]

    documented = set()
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            key = (method.upper(), path)
            if key not in OPERATIONS:
                raise ValueError(f"Operación sin documentar en app/openapi/spec.py: {method.upper()} {path}")
            documented.add(key)
            _document(operation, OPERATIONS[key], key, ref)
    missing = set(OPERATIONS) - documented
    if missing:
        raise ValueError(f"Operaciones documentadas que no existen: {sorted(missing)}")
    return spec


def _permissions(op: Op) -> str:
    permissions = op.permission if isinstance(op.permission, tuple) else (op.permission,)
    return " o ".join(f"`{p}`" for p in permissions)


def _document(operation: dict, op: Op, key: tuple[str, str], ref) -> None:
    operation["summary"] = op.summary
    access = ("Público." if op.public else "Requiere sesión." if op.permission is None else
              f"Permiso: {_permissions(op)}.")
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
        responses["204"] = {"description": "Hecho, sin cuerpo."}
    elif op.ok is None:  # usa el `response_model` que declara la ruta (login y me)
        responses[str(op.status)] = {**ok, "description": op.ok_description or "Correcto."}
    else:
        responses[str(op.status)] = {"description": op.ok_description or "Correcto.", "content": _content([ref(op.ok)])}

    errors = dict(op.errors)
    if not op.public:
        errors.setdefault(401, ("Sin sesión válida: falta el token, está manipulado o caducado, o el usuario está "
                                "desactivado.", s.ErrorText))
        if op.permission is not None:
            errors.setdefault(403, (f"Falta el permiso {_permissions(op)}.", s.ErrorText))
    validation = "422" in generated  # FastAPI valida parámetros o un cuerpo declarado: error nativo (en inglés)
    for status_code in sorted(set(errors) | ({422} if validation else set())):
        description, models = errors.get(status_code, ("Parámetros no válidos.", ()))
        refs = [ref(model) for model in _as_tuple(models)]
        if status_code == 422 and validation:
            refs.append({"$ref": "#/components/schemas/HTTPValidationError"})
            if len(refs) > 1:
                description += " Los parámetros fuera de rango o de tipo devuelven el error nativo de FastAPI."
        responses[str(status_code)] = {"description": description, "content": _content(refs)}

    if not op.public:
        for response in responses.values():
            response["headers"] = {AUTH_VERSION_HEADER: {"$ref": "#/components/headers/XAuthVersion"}}
    operation["responses"] = responses
