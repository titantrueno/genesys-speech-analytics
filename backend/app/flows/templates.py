"""Plantillas de flujo para generar el análisis con un LLM (FE013, criterio 23; FE014, criterio 13).

Cada una crea `Sampling → Prompt → Output (campo)` ya configurado con la taxonomía activa y el proveedor y modelo por
defecto de Configuración › Modelos de IA. El Sampling toma las conversaciones con alguno de sus campos vacío, sin
fechas, así que siempre es relativo al periodo por defecto, y el Output no sobrescribe valores existentes.

«Generar análisis completo» pide todo el análisis en **una llamada** por conversación: un campo JSON por destino del
catálogo (con un check por cada check activo) y una línea de instrucciones por campo en el prompt.
"""
from app.config.store import get_config
from app.flows import catalog
from app.flows.model import Graph, GraphError, parse_graph

TEMPLATES = {"summary": "Generar summary", "main_topic": "Generar main topic",
             "summary_main_topic": "Generar summary y main topic", "analisis_completo": "Generar análisis completo"}
SAMPLE_SIZE = 100
CONTEXT = "Esta es la transcripción de una conversación de atención al cliente de un banco.\n\n{{transcripcion}}\n\n"
SUMMARY_TASK = "Resume la conversación en 2 a 4 frases: motivo del contacto, gestión realizada y resultado."
TOPIC_TASK = "Indica su main topic: el motivo principal del contacto."


class TemplateError(ValueError):
    pass


def _empty(field: str) -> dict:
    return {"field": field, "operator": "is_empty"}


def _node(node_id: str, node_type: str, config: dict, x: int) -> dict:
    return {"id": node_id, "type": node_type, "position": {"x": x, "y": 120}, "config": config}


# Análisis completo: campo JSON, tipo, valores permitidos e instrucción de cada destino fijo.
FULL_FIELDS = [
    ("summary", "summary", "texto", None, SUMMARY_TASK),
    ("main_topic", "main_topic", "texto", "main_topics", "El motivo principal del contacto."),
    ("resolution", "resolution", "texto", ["resuelta", "no_resuelta", "escalada"],
     "resuelta si el problema queda solucionado en la conversación, no_resuelta si no, escalada si se deriva a otra "
     "área o se abre una gestión posterior."),
    ("csat", "csat", "numero", None, "Satisfacción predicha del cliente, de 1 (muy insatisfecho) a 5 (muy satisfecho)."),
    ("effort", "effort", "numero", None, "Esfuerzo que tuvo que hacer el cliente, de 1 (ninguno) a 5 (máximo)."),
    ("churn_risk", "churn_risk", "texto", ["bajo", "medio", "alto"], "Riesgo de que el cliente deje el banco."),
    ("sentiment", "sentiment", "numero", None, "Sentimiento global del cliente, de -1 (muy negativo) a 1 (muy positivo)."),
]
LIST_FIELDS = [
    ("secondary_topics", "secondary_topics", "lista", "secondary_topics",
     "Otros temas tratados, además del principal; una lista vacía si no hay."),
    ("keywords", "keywords", "lista", None, "De 3 a 10 palabras clave de la conversación."),
]
CHECK_ANSWERS = ["cumple", "no_cumple", "no_aplica"]
ENTITY_TASKS = {"importe": "El importe principal mencionado", "producto": "El producto del banco del que se habla",
                "fecha": "La fecha relevante mencionada", "comercio": "El comercio mencionado"}
# Lo común a varios campos va una vez, para que quepan más checks en `MAX_TEMPLATE` (hallazgo de /test).
FULL_TASK = ("Analiza la conversación y responde con estos campos. Usa solo la información de la transcripción. En "
             "cada check_…, cumple, no_cumple o no_aplica si no corresponde en esta conversación; en las entidades, "
             "un texto vacío si no aparecen.")
# Condiciones del Sampling: los campos escalares; las listas y entidades vacías pueden ser la respuesta correcta.
FULL_EMPTY = ("summary", "main_topic", "resolution", "csat", "effort", "churn_risk")


def _full(config) -> tuple[list[dict], dict, list[dict], str]:
    checks = [c for c in config.checks.values() if c.active]
    fixed = len(FULL_FIELDS) + len(LIST_FIELDS) + len(catalog.ENTITY_TYPES)
    if fixed + len(checks) > catalog.MAX_FIELDS:
        raise TemplateError(f"There are {len(checks)} active checks and one call supports {catalog.MAX_FIELDS - fixed}: "
                            "deactivate some checks or create the flow by hand with several Prompts.")
    options = {"main_topics": [t.name for t in config.main_topics.values() if t.active],
               "secondary_topics": [t.name for t in config.secondary_topics.values() if t.active]}
    # En el orden del catálogo de destinos: análisis, cumplimiento y entidades.
    rows = [(target, name, ftype, options[opts] if isinstance(opts, str) else opts, task)
            for target, name, ftype, opts, task in FULL_FIELDS + LIST_FIELDS]
    for i, check in enumerate(checks):
        name = f"check_{check.code}" if len(check.code) <= catalog.MAX_FIELD_NAME - 6 else f"check_{i}"
        rows.append((f"{catalog.CHECK_PREFIX}{check.code}", name, "texto", CHECK_ANSWERS,
                     f"¿{check.name}? {check.description}".strip()))
    rows += [(f"{catalog.ENTITY_PREFIX}{etype}", f"entidad_{etype}", "texto", None, f"{task}.")
             for etype, task in ENTITY_TASKS.items()]
    fields = [{"name": name, "type": ftype, **({"options": opts} if opts else {})} for _, name, ftype, opts, _ in rows]
    mappings = [{"target": target, "source": name} for target, name, *_ in rows]
    lines = "\n".join(f"- {name}: {task}" for _, name, _, _, task in rows)
    conditions = [_empty(f) for f in FULL_EMPTY] + [_empty(f"check:{c.code}") for c in checks]
    prompt = f"{CONTEXT}{FULL_TASK}\n{lines}"
    if len(prompt) > catalog.MAX_TEMPLATE:
        raise TemplateError("The instructions of the active checks do not fit in a prompt: shorten their descriptions.")
    return conditions, {"type": "json", "fields": fields}, mappings, prompt


def build(template: str) -> Graph:
    config = get_config()
    topics = [t.name for t in config.main_topics.values() if t.active]
    if template == "analisis_completo":
        conditions, output, mappings, prompt = _full(config)
    elif template == "summary":
        conditions, output, mappings = [_empty("summary")], {"type": "texto"}, [{"target": "summary"}]
        prompt = f"{CONTEXT}{SUMMARY_TASK} Responde solo con el resumen."
    elif template == "main_topic":
        if len(topics) > catalog.MAX_LABELS:
            raise TemplateError(f"There are more than {catalog.MAX_LABELS} active main topics: use “Generate summary and main topic”")
        conditions, output, mappings = [_empty("main_topic")], {"type": "etiqueta", "labels": topics}, [{"target": "main_topic"}]
        prompt = f"{CONTEXT}{TOPIC_TASK}"
    else:
        conditions = [_empty("summary"), _empty("main_topic")]
        output = {"type": "json", "fields": [{"name": "summary", "type": "texto"},
                                             {"name": "main_topic", "type": "texto", "options": topics}]}
        mappings = [{"target": "summary", "source": "summary"}, {"target": "main_topic", "source": "main_topic"}]
        prompt = f"{CONTEXT}{SUMMARY_TASK} {TOPIC_TASK}"
    sampling = {"query": {"root": {"op": "or" if len(conditions) > 1 else "and", "conditions": conditions}},
                "method": "aleatorio", "size": SAMPLE_SIZE}
    nodes = [
        _node("tmp-sampling", "sampling", sampling, 0),
        _node("tmp-prompt", "prompt", {"template": prompt, "provider": config.ai.provider, "model": config.ai.model,
                                       "temperature": 0.2, "output": output}, 320),
        _node("tmp-output", "output", {"kind": "campo", "overwrite": False, "mappings": mappings}, 640),
    ]
    edges = [{"source": "tmp-sampling", "target": "tmp-prompt"}, {"source": "tmp-prompt", "target": "tmp-output"}]
    try:
        return parse_graph({"version": 1, "nodes": nodes, "edges": edges})
    except GraphError:  # p. ej., más temas activos que valores permitidos (hallazgo de /review de FE014)
        raise TemplateError(f"The active taxonomy does not fit in the template: a field allows at most "
                            f"{catalog.MAX_OPTIONS} allowed values and there are more active topics.") from None
