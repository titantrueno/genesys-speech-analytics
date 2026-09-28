"""Opciones de configuración de los nodos de un flujo de insights (FE004). `GET /api/flows/catalog` las expone al front."""

NODE_TYPES = {"sampling": "Sampling", "prompt": "Prompt", "output": "Output"}

SAMPLING_METHODS = {"aleatorio": "Aleatorio", "estratificado": "Estratificado", "primeros_n": "Primeros N"}
STRATA = {"canal": "Canal", "cola": "Cola", "main_topic": "Main topic"}
ORDER_KEYS = {"fecha": "Fecha", "duracion": "Duración", "sentimiento": "Sentimiento", "csat": "CSAT predicho"}
ORDERS = {"desc": "Descendente", "asc": "Ascendente"}
MAX_SAMPLE_SIZE = 1000

# Modelos simulados: ninguno llama a un LLM (ver vault/decisiones/adr-006-ejecucion-de-prompts-simulada.md).
MODELS = {"mock-rapido": "Simulado rápido", "mock-preciso": "Simulado preciso"}
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

MAX_NODES = 50
MAX_EDGES = 100


def as_options(values: dict[str, str]) -> list[dict]:
    return [{"value": value, "label": label} for value, label in values.items()]
