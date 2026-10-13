"""Opciones de configuración de los nodos de un flujo de insights (FE004). `GET /api/flows/catalog` las expone al front."""
import re

NODE_TYPES = {"descarga": "Genesys download", "sampling": "Sampling", "prompt": "Prompt", "output": "Output"}

SAMPLING_METHODS = {"aleatorio": "Aleatorio", "estratificado": "Estratificado", "primeros_n": "Primeros N"}
STRATA = {"canal": "Canal", "cola": "Cola", "main_topic": "Main topic"}
ORDER_KEYS = {"fecha": "Fecha", "duracion": "Duración", "sentimiento": "Sentimiento", "csat": "CSAT predicho"}
ORDERS = {"desc": "Descendente", "asc": "Ascendente"}
MAX_SAMPLE_SIZE = 1000
# «All conversations» (FE017): sin tamaño; por encima de este número de conversaciones, la validación avisa.
ALL_CONVERSATIONS = "all"
LARGE_SAMPLE = 1000


def sample_size(value):
    """Tamaño de muestra: un entero de 1 a `MAX_SAMPLE_SIZE` o `"all"`. Un solo error con la ruta del campo (FE004)."""
    if value is None or value == ALL_CONVERSATIONS:
        return value
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= MAX_SAMPLE_SIZE:
        return value
    raise ValueError(f"The sample size must be a whole number from 1 to {MAX_SAMPLE_SIZE}, or \"{ALL_CONVERSATIONS}\"")

# Proveedores y modelos (FE005; LLM real desde FE013). Las claves las tiene solo el servicio de LLM (`backend/llm/`),
# que comparte estos nombres de proveedor (un test lo comprueba). `temperature` dice si el modelo la admite: los
# Claude vigentes la rechazan y la documentación de OpenAI no lo confirma para sus modelos de razonamiento, así que
# solo se envía cuando es `True` (ver features/FE013-servicio-llm-summary-main-topic/plan.md, notas de T4).
# El primer modelo de cada proveedor es el que se propone al elegirlo.
PROVIDERS = {
    "gemini": {"label": "Gemini (Google)", "models": {
        "gemini-3.5-flash-lite": {"label": "Gemini 3.5 Flash-Lite", "temperature": True},
        "gemini-3.8-flash": {"label": "Gemini 3.8 Flash", "temperature": True},
    }},
    "openai": {"label": "OpenAI", "models": {
        "gpt-6.1-sol": {"label": "GPT-6.1 Sol", "temperature": False},
        "gpt-6-luna": {"label": "GPT-6 Luna", "temperature": False},
        "gpt-6-astra": {"label": "GPT-6 Astra", "temperature": False},
    }},
    "anthropic": {"label": "Anthropic (Claude)", "models": {
        "claude-opus-5-5": {"label": "Claude Opus 5.5", "temperature": False},
        "claude-sonnet-5-5": {"label": "Claude Sonnet 5.5", "temperature": False},
        "claude-haiku-5-5": {"label": "Claude Haiku 5.5", "temperature": False},
    }},
    # Sin LLM: resultados deterministas derivados del análisis (ADR-006).
    "simulado": {"label": "Simulado (sin LLM)", "models": {
        "mock-rapido": {"label": "Simulado rápido", "temperature": True},
        "mock-preciso": {"label": "Simulado preciso", "temperature": True},
    }},
}
SIMULATED = "simulado"
DEFAULT_PROVIDER, DEFAULT_MODEL = "gemini", "gemini-3.5-flash-lite"
MODELS = {model: spec["label"] for provider in PROVIDERS.values() for model, spec in provider["models"].items()}
VARIABLES = {
    "transcripcion": "Transcripción completa, turno a turno",
    "summary": "Summary de la conversación",
    "main_topic": "Main topic de la conversación",
    "metadatos": "Canal, cola, fecha, duración, sentimiento y resolución",
    "resultado_anterior": "Resultado del prompt anterior (solo en un prompt encadenado)",
}
PREVIOUS_RESULT = "resultado_anterior"
OUTPUT_FORMATS = {"texto": "Texto", "etiqueta": "Etiqueta de una lista", "json": "JSON con esquema"}
FIELD_TYPES = {"texto": "Texto", "numero": "Número", "booleano": "Booleano", "lista": "Lista"}
MAX_TEMPLATE = 4000
MAX_LABELS = 20
MAX_LABEL = 60
MAX_FIELDS = 40  # caben la plantilla «Generar análisis completo» con los checks base y algunos más (FE014)
MAX_FIELD_NAME = 40
MAX_OPTIONS = 100  # valores permitidos de un campo JSON de texto o lista (FE013): caben los temas de la taxonomía

OUTPUT_KINDS = {"tabla": "Tabla de insights por conversación", "metrica": "Métrica agregada", "informe": "Informe resumen",
                "campo": "Guardar en campos de la conversación"}
# Campos del análisis que un Output «campo» puede escribir en las conversaciones reales (FE013 y FE014): los fijos, uno
# por tipo de entidad (`entity:<tipo>`) y uno por check de cumplimiento activo (`compliance:<código>`), que depende de
# la configuración. El servicio de ingesta comparte los tipos de entidad y el patrón del código (un test lo comprueba).
ANALYSIS_TARGETS = {"summary": "Summary", "main_topic": "Main topic", "resolution": "Resolución",
                    "csat": "CSAT predicho", "effort": "Esfuerzo del cliente", "churn_risk": "Riesgo de abandono",
                    "sentiment": "Sentimiento global", "secondary_topics": "Temas secundarios",
                    "keywords": "Palabras clave"}
ENTITY_TYPES = {"importe": "Importe", "producto": "Producto", "fecha": "Fecha", "comercio": "Comercio"}
CHECK_PREFIX, ENTITY_PREFIX = "compliance:", "entity:"
# Destinos que no dependen de la configuración; un `compliance:` se acepta al guardar si su código tiene la forma de
# un código de check, y la completitud comprueba que el check existe y está activo.
FIXED_TARGETS = {**ANALYSIS_TARGETS, **{f"{ENTITY_PREFIX}{t}": label for t, label in ENTITY_TYPES.items()}}
CHECK_TARGET = re.compile(r"^compliance:([a-z][a-z0-9_]{1,39})$")
MAX_MAPPINGS = 60
AGGREGATIONS = {"recuento": "Recuento por etiqueta", "porcentaje": "% por etiqueta"}
MAX_DESTINATION = 80

MAX_FLOW_NAME = 80
MAX_NODES = 50
MAX_EDGES = 100


def as_options(values: dict[str, str]) -> list[dict]:
    return [{"value": value, "label": label} for value, label in values.items()]


def provider_options() -> list[dict]:
    return [{"value": name, "label": provider["label"],
             "models": [{"value": model, "label": spec["label"], "temperature": spec["temperature"]}
                        for model, spec in provider["models"].items()]}
            for name, provider in PROVIDERS.items()]


def supports_temperature(model: str) -> bool:
    return any(model in p["models"] and p["models"][model]["temperature"] for p in PROVIDERS.values())


def is_target(target: str) -> bool:
    return target in FIXED_TARGETS or bool(CHECK_TARGET.match(target))


def check_code(target: str) -> str | None:
    match = CHECK_TARGET.match(target)
    return match.group(1) if match else None


def target_fields(checks) -> list[dict]:
    """Destinos que se ofrecen, en el orden del desplegable: análisis, cumplimiento (checks activos) y entidades."""
    return ([{"value": v, "label": label, "group": "analisis"} for v, label in ANALYSIS_TARGETS.items()]
            + [{"value": f"{CHECK_PREFIX}{c.code}", "label": c.name, "group": "cumplimiento"}
               for c in checks if c.active]
            + [{"value": f"{ENTITY_PREFIX}{t}", "label": label, "group": "entidades"}
               for t, label in ENTITY_TYPES.items()])


def target_label(target: str, checks: dict) -> str:
    """Etiqueta de un destino; un check borrado se muestra con su código."""
    code = check_code(target)
    if code is not None:
        return checks[code].name if code in checks else code
    return FIXED_TARGETS.get(target, target)
