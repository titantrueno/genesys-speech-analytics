"""Reglas de conexión entre nodos (FE004, criterio 2).

Las mismas reglas existen en `frontend/src/flows/rules.ts`; los casos de `frontend/src/flows/rules.cases.json`
se ejecutan en los dos lados para que no diverjan.
"""
from collections import defaultdict
from dataclasses import dataclass

from app.flows.catalog import NODE_TYPES

ALLOWED = {("sampling", "prompt"), ("prompt", "prompt"), ("prompt", "output")}
SINGLE_INPUT = {"prompt", "output"}


@dataclass(frozen=True)
class Rejection:
    code: str
    message: str


def _pair_message(source_type: str, target_type: str) -> str:
    if source_type == "output":
        return "An Output is the end of the flow: it has no outputs."
    if target_type == "sampling":
        return "A Sampling is the start of the flow: it accepts no inputs."
    if source_type == "sampling":
        return "A Sampling can only be connected to a Prompt."
    return f"A {NODE_TYPES[source_type]} cannot be connected to a {NODE_TYPES[target_type]}."


def _reaches(edges: list[tuple[str, str]], start: str, goal: str) -> bool:
    children = defaultdict(list)
    for source, target in edges:
        children[source].append(target)
    pending, seen = [start], {start}
    while pending:
        current = pending.pop()
        if current == goal:
            return True
        for child in children[current]:
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return False


def connection_rejection(types: dict[str, str], edges: list[tuple[str, str]], source: str, target: str) -> Rejection | None:
    """Motivo por el que no se admite la conexión `source → target` en un grafo con esos nodos y conexiones."""
    if source not in types or target not in types:
        return Rejection("unknown_node", "The connection points to a node that does not exist.")
    if source == target:
        return Rejection("self_loop", "A node cannot be connected to itself.")
    if (types[source], types[target]) not in ALLOWED:
        return Rejection("invalid_pair", _pair_message(types[source], types[target]))
    if (source, target) in edges:
        return Rejection("duplicate", "These nodes are already connected.")
    if types[target] in SINGLE_INPUT and any(t == target for _, t in edges):
        return Rejection("input_taken", f"The {NODE_TYPES[types[target]]} already has an input; disconnect it first.")
    if _reaches(edges, target, source):
        return Rejection("cycle", "The connection would create a cycle.")
    return None
