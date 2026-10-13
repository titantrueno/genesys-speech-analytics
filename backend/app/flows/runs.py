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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from app import ids
from app.auth import User
from app.flows import catalog
from app.flows.analysis_writer import BATCH_SIZE, FIELD_STATES, AnalysisWriter, WriterUnavailable
from app.flows.download_config import resolve_interval
from app.flows.downloader import Downloader, DownloaderUnavailable, DownloadRejected
from app.flows.fields import NO_VALUE, ValueRejected, coerce
from app.flows.model import DownloadNode, Graph, OutputNode, PromptNode, SamplingNode
from app.flows.outputs import build_metric, build_report, build_table
from app.services.listing import list_item
from app.flows.prompting import PromptFailed, PromptRejected, PromptRunner, PromptUnavailable
from app.flows.sampling import candidates, draw_sample
from app.clock import now
from app.config.store import get_config
from app.data.real import begin_request
from app.ingestion_client import UNAVAILABLE
from app.flows.store import Flow
from app.models import Conversation
from app.privacy.masking import masked

PENDING, RUNNING, OK, ERROR = "pendiente", "en_curso", "ok", "error"
# Nodo que no se ejecuta porque la descarga de la caja no trajo conversaciones (FE017, criterio 6).
SKIPPED = "omitido"
NO_CONVERSATIONS = "The download returned no conversations"
ACTIVE = {PENDING, RUNNING}
DOWNLOAD_ACTIVE = {"pendiente", "en_curso"}
# Cada cuánto se consulta el estado de la descarga de la caja (los tests lo ponen a 0).
DOWNLOAD_POLL_S = 2.0
DEFAULT_STEP_DELAY_MS = 15
# Las ejecuciones viven en memoria y una tabla de 1.000 filas ocupa ~1 MB: se conservan las últimas por flujo.
MAX_RUNS_PER_FLOW = 50
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
    # Solo en los Prompt con un LLM real (FE013): respuestas fuera de formato y conversaciones sin respuesta.
    rejected: int = 0
    failed: int = 0


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
    origin: str = "manual"
    # Descarga de la caja «Genesys download» (FE017): su `1RN` en la ingesta, su estado y sus contadores.
    download: dict | None = None
    nodes: dict[str, NodeState] = field(default_factory=dict)
    outputs: dict[str, dict] = field(default_factory=dict)
    # Por nodo Prompt, las conversaciones excluidas de los outputs y el motivo (FE013).
    failures: dict[str, list[dict]] = field(default_factory=dict)
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
                "failures": self.failures,
                "download": self.download,
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
        runs = self._by_flow[flow.id]
        runs.insert(0, run)
        finished = [r for r in runs if r.summary()["status"] not in ACTIVE]
        for old in finished[MAX_RUNS_PER_FLOW - 1:]:  # la nueva también acabará terminada
            runs.remove(old)
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
    def __init__(self, runner: PromptRunner, delay_s: float, on_step: Callable[[Run], None] | None = None,
                 writer: AnalysisWriter | None = None, downloader: Downloader | None = None,
                 poll_s: float | None = None):
        self.runner = runner
        self.delay_s = delay_s
        self.on_step = on_step
        self.writer = writer  # solo lo usan los Output «campo» (FE013)
        self.downloader = downloader  # solo lo usa la caja «Genesys download» (FE017)
        self.poll_s = DOWNLOAD_POLL_S if poll_s is None else poll_s

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
        reached: dict[str, list[Conversation]] = {}  # por Prompt, las conversaciones que le llegaron
        results: dict[str, dict[str, Any]] = {}
        subsets: dict[str, set[str]] = {}  # por caja de descarga, las conversaciones que descargó (FE017)
        skipped: set[str] = set()
        failed = False
        for node_id in topological_order(graph):
            node = graph.node(node_id)
            inputs = graph.inputs(node_id)
            if node_id in skipped or any(source not in sampled for source in inputs):
                continue  # su entrada ha fallado, no se ha ejecutado o no trajo nada: queda pendiente u omitido
            run.update_node(node_id, status=RUNNING)
            self._step(run)
            try:
                if isinstance(node, DownloadNode):
                    subsets[node_id] = self._download(run, node)
                    sampled[node_id] = []
                    if not subsets[node_id]:
                        skipped |= self._skip_after(run, graph, node_id)
                elif isinstance(node, SamplingNode):
                    subset = subsets.get(inputs[0]) if inputs else None
                    sampled[node_id] = self._sampling(run, node, subset)
                elif isinstance(node, PromptNode):
                    reached[node_id] = sampled[inputs[0]]
                    results[node_id] = self._prompt(run, node, sampled[inputs[0]], results.get(inputs[0]))
                    # Solo siguen las conversaciones con un resultado válido (FE013, criterio 13).
                    sampled[node_id] = [c for c in sampled[inputs[0]] if c.id in results[node_id]]
                elif node.config.kind == "campo":
                    self._fields(run, node, graph.node(inputs[0]), reached[inputs[0]], results[inputs[0]])
                    sampled[node_id] = sampled[inputs[0]]
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

    def _download(self, run: Run, node: DownloadNode) -> set[str]:
        """Lanza la descarga en el servicio de ingesta, sigue sus contadores hasta que termina y devuelve su subconjunto
        (FE017, criterios 4, 5 y 6). El intervalo se resuelve ahora, en la zona horaria de la plataforma."""
        if self.downloader is None:
            raise NodeFailure(UNAVAILABLE)
        cfg, tz = node.config, get_config().general.timezone
        start, end = resolve_interval(cfg.interval, tz, now())
        try:
            state = self.downloader.start(
                insight_flow_id=run.flow_id, interval_from=start, interval_to=end, channels=list(cfg.channels),
                overwrite=bool(cfg.overwrite), origin=run.origin, timezone=tz,
                user={"id": run.user_id, "name": run.user_name})
            self._follow(run, node, state)
            while state["status"] in DOWNLOAD_ACTIVE:
                if self.poll_s:
                    time.sleep(self.poll_s)
                state = self.downloader.status(state["id"])
                self._follow(run, node, state)
            if state["status"] == "error":
                raise NodeFailure(f"The download failed: {state.get('error') or 'unknown error'}")
            subset = set(self.downloader.subset(state["id"]))
        except DownloadRejected as exc:
            raise NodeFailure(str(exc)) from exc
        except DownloaderUnavailable as exc:
            raise NodeFailure(UNAVAILABLE) from exc
        begin_request()  # la instantánea de los datos reales se recarga: el Sampling ve lo recién descargado
        return subset

    def _follow(self, run: Run, node: DownloadNode, state: dict) -> None:
        counters = state.get("counters") or {}
        done = sum(counters.get(k, 0) for k in ("inserted", "updated", "skipped", "skipped_existing", "errors"))
        run.update(download={"node_id": node.id, "run_id": state["id"], "status": state["status"],
                             "counters": counters, "error": state.get("error")})
        run.update_node(node.id, processed=done, total=counters.get("found"))
        self._step(run)

    def _skip_after(self, run: Run, graph: Graph, node_id: str) -> set[str]:
        """Marca como `omitido` todo lo que depende de una caja cuya descarga no trajo conversaciones."""
        pending, skipped = list(graph.outputs(node_id)), set()
        while pending:
            current = pending.pop()
            if current not in skipped:
                skipped.add(current)
                run.update_node(current, status=SKIPPED, message=NO_CONVERSATIONS)
                pending += graph.outputs(current)
        self._step(run)
        return skipped

    def _sampling(self, run: Run, node: SamplingNode, subset: set[str] | None = None) -> list[Conversation]:
        available = candidates(node.config, subset)
        sample = draw_sample(available, node.config, run.seed)
        with run.lock:
            run.sample_size = (run.sample_size or 0) + len(sample)
        run.update_node(node.id, total=len(sample), processed=len(sample))
        if not sample:
            raise NodeFailure("The sample is empty: no conversation matches the filters.")
        # Los prompts y los outputs trabajan siempre con texto enmascarado, esté o no activado el interruptor (FE005).
        return [masked(conv) for conv in sample]

    def _prompt(self, run: Run, node: PromptNode, conversations: list[Conversation],
                previous: dict[str, Any] | None) -> dict[str, Any]:
        run.update_node(node.id, total=len(conversations))
        results: dict[str, Any] = {}
        failures: list[dict] = []

        def one(conv: Conversation) -> None:
            try:
                value = self.runner.run(node.config, conv, previous.get(conv.id) if previous else None)
            except (PromptRejected, PromptFailed) as exc:
                status = "rechazado" if isinstance(exc, PromptRejected) else "error"
                with run.lock:
                    failures.append({"conversation_id": conv.id, "status": status, "reason": str(exc)})
            except PromptUnavailable as exc:
                raise NodeFailure(f"Error running the prompt: {exc}") from exc
            except Exception as exc:  # un proveedor real puede fallar por muchas causas; se informa en el nodo
                raise NodeFailure(f"Error running the prompt: {exc}") from exc
            else:
                with run.lock:
                    results[conv.id] = value

        parallelism = getattr(self.runner, "parallelism_for", lambda _: 1)(node.config)
        if parallelism <= 1:
            for i, conv in enumerate(conversations, start=1):
                one(conv)
                self._progress(run, node.id, i, failures)
        else:
            with ThreadPoolExecutor(max_workers=parallelism, thread_name_prefix="prompt") as pool:
                pending = {pool.submit(one, conv) for conv in conversations}
                done_count = 0
                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        if future.exception() is not None:
                            for other in pending:
                                other.cancel()
                            raise future.exception()
                        done_count += 1
                        self._progress(run, node.id, done_count, failures)
        if conversations and not results:
            raise NodeFailure("No conversation got a valid result: check the template and the format.")
        # En el orden de la muestra, como el resto de nodos.
        order = {conv.id: i for i, conv in enumerate(conversations)}
        with run.lock:
            run.failures[node.id] = sorted(failures, key=lambda f: order[f["conversation_id"]])
        return {conv.id: results[conv.id] for conv in conversations if conv.id in results}

    def _progress(self, run: Run, node_id: str, processed: int, failures: list[dict]) -> None:
        with run.lock:
            rejected = sum(f["status"] == "rechazado" for f in failures)
            failed = len(failures) - rejected
        run.update_node(node_id, processed=processed, rejected=rejected, failed=failed)
        self._step(run)

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


    def _fields(self, run: Run, node: OutputNode, prompt: PromptNode, conversations: list[Conversation],
                results: dict[str, Any]) -> None:
        """Output «Guardar en campos» (FE013, criterios 19 y 22): escribe por lotes y da el estado de cada campo."""
        cfg = node.config
        if self.writer is None:
            raise NodeFailure("There is nowhere to save the fields: the ingestion service is missing.")
        targets = [m.target for m in cfg.mappings]
        failures = {f["conversation_id"]: f for f in run.failures.get(prompt.id, [])}
        run.update_node(node.id, total=len(conversations))
        rows, items = [], []
        for conv in conversations:
            # `reason`: por qué falló la conversación entera; `reasons`: por qué no se guardó un campo (FE014).
            row = {"conversation": list_item(conv), "values": {}, "states": {}, "reason": None, "reasons": {}}
            if conv.id not in results:  # el Prompt la rechazó o no obtuvo respuesta
                failure = failures.get(conv.id, {"status": "error", "reason": "No Prompt result"})
                row["states"] = {t: failure["status"] for t in targets}
                row["reason"] = failure["reason"]
            else:
                for mapping in cfg.mappings:
                    answer = results[conv.id] if mapping.source is None else results[conv.id][mapping.source]
                    try:  # un valor no válido solo deja en «rechazado» su campo (criterio 4)
                        value = coerce(mapping.target, answer)
                    except ValueRejected as exc:
                        row["states"][mapping.target] = "rechazado"
                        row["reasons"][mapping.target] = str(exc)
                        continue
                    if value is NO_VALUE:
                        row["states"][mapping.target] = "sin_valor"
                        continue
                    row["values"][mapping.target] = value
                if row["values"]:
                    items.append({"conversation_id": conv.id, "values": row["values"]})
            rows.append(row)
        by_id = {row["conversation"]["id"]: row for row in rows}
        written = 0
        for start in range(0, len(items), BATCH_SIZE):
            batch = items[start:start + BATCH_SIZE]
            try:
                outcomes = self.writer.write(run.id, prompt.config.provider or catalog.SIMULATED, prompt.config.model,
                                             bool(cfg.overwrite), batch)
            except WriterUnavailable as exc:
                raise NodeFailure(f"{exc}: {written} of {len(items)} conversations were saved.") from exc
            for conversation_id, written_fields in outcomes.items():
                row = by_id[conversation_id]
                for target, outcome in written_fields["outcomes"].items():
                    row["states"][target] = "error" if outcome == "no_encontrada" else outcome
                    if outcome == "no_encontrada":
                        row["reason"] = "The conversation is not in the database"
                row["reasons"].update(written_fields.get("reasons", {}))
            written += len(batch)
            run.update_node(node.id, processed=min(len(conversations), written))
            self._step(run)
        counts = {t: {state: sum(row["states"].get(t) == state for row in rows) for state in FIELD_STATES}
                  for t in targets}
        with run.lock:
            run.outputs[node.id] = {"node_id": node.id, "kind": "campo", "destination": _fields_destination(targets),
                                    "result": {"targets": targets, "rows": rows, "counts": counts}}
        run.update_node(node.id, processed=len(conversations))


def _fields_destination(targets: list[str]) -> str:
    """Nombre de la pestaña de un Output «campo»: los destinos, o los dos primeros y cuántos más (FE014)."""
    labels = [catalog.target_label(t, get_config().checks) for t in targets]
    if len(labels) <= 3:
        return " + ".join(labels)
    return f"{' + '.join(labels[:2])} and {len(labels) - 2} more fields"


_store = RunStore()


def get_run_store() -> RunStore:
    return _store


def reset_run_store() -> None:
    global _store
    _store = RunStore()
