"""Plantillas de flujo para generar summary y main topic (FE013, criterio 23).

Cada una crea `Sampling → Prompt → Output (campo)` ya configurado con la taxonomía activa y el proveedor y modelo por
defecto de Configuración › Modelos de IA. El Sampling toma las conversaciones con el campo vacío (o alguno de los dos)
sin fechas, así que siempre es relativo al periodo por defecto, y el Output no sobrescribe valores existentes.
"""
from app.config.store import get_config
from app.flows import catalog
from app.flows.model import Graph, parse_graph

TEMPLATES = {"summary": "Generar summary", "main_topic": "Generar main topic",
             "summary_main_topic": "Generar summary y main topic"}
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


def build(template: str) -> Graph:
    config = get_config()
    topics = [t.name for t in config.main_topics.values() if t.active]
    if template == "summary":
        conditions, output, mappings = [_empty("summary")], {"type": "texto"}, [{"target": "summary"}]
        prompt = f"{CONTEXT}{SUMMARY_TASK} Responde solo con el resumen."
    elif template == "main_topic":
        if len(topics) > catalog.MAX_LABELS:
            raise TemplateError(f"Hay más de {catalog.MAX_LABELS} main topics activos: usa «Generar summary y main topic»")
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
    return parse_graph({"version": 1, "nodes": nodes, "edges": edges})
