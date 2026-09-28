"""Grafos de ejemplo para los tests de flujos de insights (FE004)."""
import copy

SAMPLING = {
    "query": {"from": "2026-09-01", "to": "2026-09-26", "root": {"op": "and", "conditions": []}},
    "method": "aleatorio",
    "size": 40,
}
PROMPT_LABEL = {
    "template": "Clasifica el motivo de la conversación: {{summary}}",
    "model": "mock-rapido",
    "temperature": 0.2,
    "output": {"type": "etiqueta", "labels": ["Positivo", "Neutro", "Negativo"]},
}
PROMPT_TEXT = {
    "template": "Resume en una frase lo que pide el cliente: {{transcripcion}}",
    "model": "mock-preciso",
    "temperature": 0.5,
    "output": {"type": "texto"},
}
OUTPUT_METRIC = {"kind": "metrica", "aggregation": "recuento", "destination": "sentimiento_por_etiqueta"}
OUTPUT_TABLE = {"kind": "tabla", "destination": "insights_por_conversacion"}
OUTPUT_REPORT = {"kind": "informe", "destination": "informe_resumen"}


def node(node_id: str, node_type: str, config: dict | None = None, x: float = 0, y: float = 0) -> dict:
    return {"id": node_id, "type": node_type, "position": {"x": x, "y": y}, "config": copy.deepcopy(config or {})}


def edge(source: str, target: str) -> dict:
    return {"source": source, "target": target}


def graph(nodes: list[dict], edges: list[dict]) -> dict:
    return {"version": 1, "nodes": nodes, "edges": edges}


def complete_graph() -> dict:
    """Sampling → Prompt (etiqueta) → Output (métrica): el flujo válido más pequeño."""
    return graph(
        [node("tmp-s", "sampling", SAMPLING), node("tmp-p", "prompt", PROMPT_LABEL, x=300),
         node("tmp-o", "output", OUTPUT_METRIC, x=600)],
        [edge("tmp-s", "tmp-p"), edge("tmp-p", "tmp-o")],
    )


def chained_graph() -> dict:
    """Sampling → Prompt (etiqueta) → Prompt (texto) con tres outputs: métrica, tabla e informe."""
    chained = {**PROMPT_TEXT, "template": "Explica por qué la etiqueta es {{resultado_anterior}}: {{summary}}"}
    return graph(
        [node("tmp-s", "sampling", SAMPLING), node("tmp-p1", "prompt", PROMPT_LABEL, x=300),
         node("tmp-p2", "prompt", chained, x=600), node("tmp-o1", "output", OUTPUT_METRIC, x=600, y=200),
         node("tmp-o2", "output", OUTPUT_TABLE, x=900), node("tmp-o3", "output", OUTPUT_REPORT, x=900, y=200)],
        [edge("tmp-s", "tmp-p1"), edge("tmp-p1", "tmp-p2"), edge("tmp-p1", "tmp-o1"),
         edge("tmp-p2", "tmp-o2"), edge("tmp-p2", "tmp-o3")],
    )
