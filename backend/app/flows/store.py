"""Flujos de insights en memoria (FE004). Se pierden al reiniciar la API, como el resto de escrituras (ADR-002)."""
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app import ids
from app.auth import User
from app.flows import catalog
from app.flows.model import Graph
from app.flows.rules import validate

_rng = random.SystemRandom()
_clock_lock = threading.Lock()
_last_time = datetime.min.replace(tzinfo=timezone.utc)


def now() -> datetime:
    """Hora actual estrictamente creciente, para que el orden por modificación sea estable."""
    global _last_time
    with _clock_lock:
        _last_time = max(datetime.now(timezone.utc), _last_time + timedelta(microseconds=1))
        return _last_time


@dataclass
class Flow:
    id: str
    name: str
    author_id: str
    author_name: str
    graph: Graph = field(default_factory=Graph)
    created_at: datetime = field(default_factory=now)
    updated_at: datetime | None = None

    def __post_init__(self):
        self.updated_at = self.updated_at or self.created_at

    def status(self) -> str:
        return "con_errores" if validate(self.graph) else "valido"

    def summary(self) -> dict:
        return {"id": self.id, "name": self.name, "author": {"id": self.author_id, "name": self.author_name},
                "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat(),
                "status": self.status()}

    def to_dict(self) -> dict:
        return {**self.summary(), "graph": self.graph.dump()}


def assign_node_ids(graph: Graph, renew_all: bool = False) -> tuple[Graph, dict[str, str]]:
    """Asigna un identificador `1ND` a cada clave temporal (o a todos los nodos) y reescribe las conexiones."""
    mapping = {n.id: ids.new_id(ids.NODE, _rng) for n in graph.nodes if renew_all or not ids.is_valid(n.id, ids.NODE)}
    if not mapping:
        return graph, {}
    rename = lambda node_id: mapping.get(node_id, node_id)  # noqa: E731
    nodes = [n.model_copy(update={"id": rename(n.id)}, deep=True) for n in graph.nodes]
    edges = [e.model_copy(update={"source": rename(e.source), "target": rename(e.target)}) for e in graph.edges]
    return Graph(version=graph.version, nodes=nodes, edges=edges), mapping


class FlowStore:
    def __init__(self):
        self._items: dict[str, Flow] = {}

    def list(self) -> list[Flow]:
        return sorted(self._items.values(), key=lambda f: f.updated_at, reverse=True)

    def get(self, flow_id: str) -> Flow | None:
        return self._items.get(ids.normalize(flow_id))

    def create(self, user: User, name: str, graph: Graph | None = None) -> Flow:
        flow = Flow(ids.new_id(ids.FLOW, _rng), name, user.id, user.name, graph or Graph())
        self._items[flow.id] = flow
        return flow

    def duplicate(self, flow: Flow, user: User) -> Flow:
        graph, _ = assign_node_ids(flow.graph, renew_all=True)
        return self.create(user, f"Copia de {flow.name}"[:catalog.MAX_FLOW_NAME], graph)

    def rename(self, flow: Flow, name: str) -> Flow:
        flow.name = name
        flow.updated_at = now()
        return flow

    def save_graph(self, flow: Flow, graph: Graph) -> dict[str, str]:
        flow.graph, mapping = assign_node_ids(graph)
        flow.updated_at = now()
        return mapping

    def delete(self, flow: Flow) -> None:
        del self._items[flow.id]


_store = FlowStore()


def get_flow_store() -> FlowStore:
    return _store


def reset_flow_store() -> None:
    global _store
    _store = FlowStore()
