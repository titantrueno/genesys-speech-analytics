"""Opciones de configuración de los nodos de un flujo de insights (FE004). `GET /api/flows/catalog` las expone al front."""

NODE_TYPES = {"sampling": "Sampling", "prompt": "Prompt", "output": "Output"}

SAMPLING_METHODS = {"aleatorio": "Aleatorio", "estratificado": "Estratificado", "primeros_n": "Primeros N"}
STRATA = {"canal": "Canal", "cola": "Cola", "main_topic": "Main topic"}
ORDER_KEYS = {"fecha": "Fecha", "duracion": "Duración", "sentimiento": "Sentimiento", "csat": "CSAT predicho"}
ORDERS = {"desc": "Descendente", "asc": "Ascendente"}
MAX_SAMPLE_SIZE = 1000

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
FIELD_TYPES = {"texto": "Texto", "numero": "Número", "booleano": "Booleano"}
MAX_TEMPLATE = 4000
MAX_LABELS = 20
MAX_LABEL = 60
MAX_FIELDS = 20
MAX_FIELD_NAME = 40

OUTPUT_KINDS = {"tabla": "Tabla de insights por conversación", "metrica": "Métrica agregada", "informe": "Informe resumen"}
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
