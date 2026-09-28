"""Ejecuciones simuladas de flujos (FE004, criterios 5, 6 y 7).

Una ejecución guarda una copia del grafo, así que editar el flujo después no cambia lo que muestra. El ejecutor
corre en segundo plano (`BackgroundTasks`) y las peticiones leen el estado a la vez, así que todo acceso al estado
de una ejecución pasa por su cerrojo y las lecturas devuelven copias.
"""
import copy
import os
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from app import ids
from app.auth import User
from app.flows.model import Graph, OutputNode, PromptNode, SamplingNode
from app.flows.outputs import build_metric, build_report, build_table
from app.flows.prompting import PromptRunner
from app.flows.sampling import candidates, draw_sample
from app.flows.store import Flow, now
from app.models import Conversation

PENDING, RUNNING, OK, ERROR = "pendiente", "en_curso", "ok", "error"
ACTIVE = {PENDING, RUNNING}
DEFAULT_STEP_DELAY_MS = 15
_rng = random.SystemRandom()


def step_delay_seconds() -> float:
    """Retardo por elemento procesado (`FLOW_RUN_STEP_DELAY_MS`), para que el progreso sea visible en la demo."""
    try:
        value = int(os.environ.get("FLOW_RUN_STEP_DELAY_MS", DEFAULT_STEP_DELAY_MS))
    except ValueError:
        value = DEFAULT_STEP_DELAY_MS
    return max(value, 0) / 1000


class NodeFailure(Exception):
    """Fallo esperado de un nodo, con un mensaje para la persona usuaria."""


@dataclass
class NodeState:
    status: str = PENDING
    processed: int = 0
    total: int | None = None
    message: str | None = None


@dataclass
class Run:
    id: str
    flow_id: str
    user_id: str
    user_name: str
    graph: Graph
    seed: int
    created_at: datetime = field(default_factory=now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: str = PENDING
    sample_size: int | None = None
    nodes: dict[str, NodeState] = field(default_factory=dict)
    outputs: dict[str, dict] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        self.nodes = self.nodes or {n.id: NodeState() for n in self.graph.nodes}

    def _summary(self) -> dict:
        duration = (self.finished_at - self.started_at) if self.finished_at and self.started_at else None
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": round(duration.total_seconds() * 1000) if duration is not None else None,
            "status": self.status,
            "sample_size": self.sample_size,
            "user": {"id": self.user_id, "name": self.user_name},
        }

    def summary(self) -> dict:
        with self.lock:
            return self._summary()

    def snapshot(self) -> dict:
        with self.lock:
            return copy.deepcopy({
                **self._summary(),
                "flow_id": self.flow_id,
                "seed": self.seed,
                "graph": self.graph.dump(),
                "nodes": {node_id: vars(state) for node_id, state in self.nodes.items()},
                "outputs": self.outputs,
            })

    def update(self, **changes: Any) -> None:
        with self.lock:
            for key, value in changes.items():
                setattr(self, key, value)

    def update_node(self, node_id: str, **changes: Any) -> None:
        with self.lock:
            for key, value in changes.items():
                setattr(self.nodes[node_id], key, value)


class RunStore:
    def __init__(self):
        self._by_flow: dict[str, list[Run]] = defaultdict(list)
        self._lock = threading.Lock()

    def _add(self, flow: Flow, user: User, seed: int | None) -> Run:
        run = Run(ids.new_id(ids.RUN, _rng), flow.id, user.id, user.name, flow.graph.model_copy(deep=True),
                  _rng.randrange(2**31) if seed is None else seed)
        self._by_flow[flow.id].insert(0, run)
        return run

    def create(self, flow: Flow, user: User, seed: int | None = None) -> Run:
        with self._lock:
            return self._add(flow, user, seed)

    def start(self, flow: Flow, user: User) -> Run | None:
        """Crea una ejecución si no hay otra en curso del mismo flujo; la comprobación y el alta son atómicas."""
        with self._lock:
            return None if self.active(flow.id) else self._add(flow, user, None)

    def list(self, flow_id: str) -> list[Run]:
        return list(self._by_flow.get(flow_id, []))

    def get(self, flow_id: str, run_id: str) -> Run | None:
        run_id = ids.normalize(run_id)
        return next((r for r in self._by_flow.get(flow_id, []) if r.id == run_id), None)

    def active(self, flow_id: str) -> Run | None:
        return next((r for r in self._by_flow.get(flow_id, []) if r.summary()["status"] in ACTIVE), None)

    def delete_flow(self, flow_id: str) -> None:
        self._by_flow.pop(flow_id, None)


def topological_order(graph: Graph) -> list[str]:
    """Orden de ejecución: cada nodo después de su entrada; a igualdad, en el orden del grafo."""
    position = {n.id: i for i, n in enumerate(graph.nodes)}
    indegree = {n.id: len(graph.inputs(n.id)) for n in graph.nodes}
    ready = sorted((n for n, d in indegree.items() if d == 0), key=position.get)
    order = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for child in graph.outputs(current):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort(key=position.get)
    return order


class FlowExecutor:
    def __init__(self, runner: PromptRunner, delay_s: float, on_step: Callable[[Run], None] | None = None):
        self.runner = runner
        self.delay_s = delay_s
        self.on_step = on_step

    def _step(self, run: Run) -> None:
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.on_step:
            self.on_step(run)

    def execute(self, run: Run) -> None:
        run.update(status=RUNNING, started_at=now())
        self._step(run)
        graph = run.graph
        sampled: dict[str, list[Conversation]] = {}
        results: dict[str, dict[str, Any]] = {}
        failed = False
        for node_id in topological_order(graph):
            node = graph.node(node_id)
            inputs = graph.inputs(node_id)
            if any(source not in sampled for source in inputs):
                continue  # su entrada ha fallado o no se ha ejecutado: queda pendiente
            run.update_node(node_id, status=RUNNING)
            self._step(run)
            try:
                if isinstance(node, SamplingNode):
                    sampled[node_id] = self._sampling(run, node)
                elif isinstance(node, PromptNode):
                    sampled[node_id] = sampled[inputs[0]]
                    results[node_id] = self._prompt(run, node, sampled[node_id], results.get(inputs[0]))
                else:
                    self._output(run, node, graph.node(inputs[0]), sampled[inputs[0]], results[inputs[0]])
                    sampled[node_id] = sampled[inputs[0]]
            except Exception as exc:  # noqa: BLE001 — ningún fallo puede dejar la ejecución «en curso»
                failed = True
                sampled.pop(node_id, None)
                message = str(exc) if isinstance(exc, NodeFailure) else f"Error inesperado: {exc}"
                run.update_node(node_id, status=ERROR, message=message)
                self._step(run)
                continue
            run.update_node(node_id, status=OK)
            self._step(run)
        run.update(status=ERROR if failed else OK, finished_at=now())

    def _sampling(self, run: Run, node: SamplingNode) -> list[Conversation]:
        available = candidates(node.config)
        sample = draw_sample(available, node.config, run.seed)
        with run.lock:
            run.sample_size = (run.sample_size or 0) + len(sample)
        run.update_node(node.id, total=len(sample), processed=len(sample))
        if not sample:
            raise NodeFailure("La muestra está vacía: ninguna conversación cumple los filtros.")
        return sample

    def _prompt(self, run: Run, node: PromptNode, conversations: list[Conversation],
                previous: dict[str, Any] | None) -> dict[str, Any]:
        run.update_node(node.id, total=len(conversations))
        results = {}
        for i, conv in enumerate(conversations, start=1):
            try:
                results[conv.id] = self.runner.run(node.config, conv, previous.get(conv.id) if previous else None)
            except Exception as exc:  # un proveedor real puede fallar por muchas causas; se informa en el nodo
                raise NodeFailure(f"Error al ejecutar el prompt: {exc}") from exc
            run.update_node(node.id, processed=i)
            self._step(run)
        return results

    def _output(self, run: Run, node: OutputNode, prompt: PromptNode, conversations: list[Conversation],
                results: dict[str, Any]) -> None:
        cfg = node.config
        run.update_node(node.id, total=len(conversations))
        if cfg.kind == "tabla":
            result = build_table(conversations, results)
        elif cfg.kind == "metrica":
            result = build_metric(prompt.config.output.labels, conversations, results, cfg)
        else:
            result = build_report(conversations, results, cfg)
        with run.lock:
            run.outputs[node.id] = {"node_id": node.id, "kind": cfg.kind, "destination": cfg.destination.strip(),
                                    "result": result}
        run.update_node(node.id, processed=len(conversations))


_store = RunStore()


def get_run_store() -> RunStore:
    return _store


def reset_run_store() -> None:
    global _store
    _store = RunStore()
