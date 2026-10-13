"""Flujos de insights (FE004) en memoria, guardados en PostgreSQL para que sobrevivan a un reinicio (FE015).

Se cargan la primera vez que se piden y cada cambio se guarda antes de aplicarse en memoria: si no se puede guardar,
la petición falla (`503`) y el flujo queda como estaba. Sin servicio de ingesta configurado viven solo en memoria.
"""
import logging
import random
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime

from app import ids
from app.auth import User
from app.clock import now
from app.flows import catalog
from app.flows.model import Graph
from app.flows.rules import validate
from app.state_backend import StateBackend, default_backend

logger = logging.getLogger(__name__)
_rng = random.SystemRandom()


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

    def record(self) -> dict:
        """Lo que se guarda: el flujo sin su estado de validación, que se recalcula al leerlo."""
        return {"id": self.id, "name": self.name, "author": {"id": self.author_id, "name": self.author_name},
                "graph": self.graph.dump(), "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat()}

    @classmethod
    def from_record(cls, record: dict) -> "Flow":
        return cls(record["id"], record["name"], record["author"]["id"], record["author"]["name"],
                   Graph.model_validate(record["graph"]), datetime.fromisoformat(record["created_at"]),
                   datetime.fromisoformat(record["updated_at"]))


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
    def __init__(self, backend: StateBackend | None = None):
        self._backend = backend
        self._items: dict[str, Flow] = {}
        self._loaded = backend is None
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            for record in self._backend.load_flows():
                try:
                    flow = Flow.from_record(record)
                except (KeyError, TypeError, ValueError):
                    # Un flujo guardado que ya no encaja en el modelo no impide usar los demás.
                    logger.warning("Flujo de insights guardado no válido, se omite: %s", record.get("id"))
                    continue
                self._items[flow.id] = flow
            self._loaded = True

    def _save(self, flow: Flow) -> None:
        if self._backend:
            self._backend.save_flow(flow.record())

    def list(self) -> list[Flow]:
        self._ensure_loaded()
        return sorted(self._items.values(), key=lambda f: f.updated_at, reverse=True)

    def get(self, flow_id: str) -> Flow | None:
        self._ensure_loaded()
        return self._items.get(ids.normalize(flow_id))

    def create(self, user: User, name: str, graph: Graph | None = None) -> Flow:
        self._ensure_loaded()
        flow = Flow(ids.new_id(ids.FLOW, _rng), name, user.id, user.name, graph or Graph())
        self._save(flow)
        self._items[flow.id] = flow
        return flow

    def duplicate(self, flow: Flow, user: User) -> Flow:
        graph, _ = assign_node_ids(flow.graph, renew_all=True)
        return self.create(user, f"Copia de {flow.name}"[:catalog.MAX_FLOW_NAME], graph)

    def _update(self, flow: Flow, **changes) -> Flow:
        """Guarda la versión cambiada y, solo si se ha guardado, la aplica sobre el mismo objeto."""
        changed = replace(flow, **changes, updated_at=now())
        self._save(changed)
        flow.__dict__.update(changed.__dict__)
        return flow

    def rename(self, flow: Flow, name: str) -> Flow:
        return self._update(flow, name=name)

    def save_graph(self, flow: Flow, graph: Graph) -> dict[str, str]:
        graph, mapping = assign_node_ids(graph)
        self._update(flow, graph=graph)
        return mapping

    def delete(self, flow: Flow) -> None:
        if self._backend:
            self._backend.delete_flow(flow.id)
        del self._items[flow.id]


_store = FlowStore(default_backend())


def get_flow_store() -> FlowStore:
    return _store


def reset_flow_store(backend: StateBackend | None = None) -> None:
    global _store
    _store = FlowStore(backend)
