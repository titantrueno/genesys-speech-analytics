"""Programador de los flujos de insights con caja «Genesys download» (FE017, criterio 9).

Las ejecuciones de insights viven en la memoria de la API (FE004, FE015), así que es la API quien las lanza. Un hilo
llama a `tick()` cada 30 s; los tests lo llaman con un reloj simulado, sin hilos. Recuerda en memoria la última vez que
miró cada flujo y la inicializa con la primera vez que lo ve: tras un reinicio (o al programar un flujo) la primera
ejecución es la siguiente hora programada, y las perdidas no se recuperan.
"""
import logging
import os
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.clock import now as real_now
from app.config.store import get_config
from app.flows.download_config import NoSchedule, next_occurrence
from app.flows.model import DownloadNode, Graph
from app.flows.rules import IngestionUp, LlmKeys, blocking, validate
from app.flows.runs import ERROR, FlowExecutor, get_run_store
from app.flows.store import Flow, get_flow_store

TICK_SECONDS = 30
logger = logging.getLogger(__name__)
Job = Callable[[], None]


@dataclass(frozen=True)
class Actor:
    """Quien lanza una ejecución programada: no es una persona usuaria."""
    id: str = "system"
    name: str = "Scheduler"


SCHEDULER = Actor()


def scheduled_box(graph: Graph) -> DownloadNode | None:
    """La caja del flujo si está programada y activa."""
    box = next((n for n in graph.nodes if isinstance(n, DownloadNode)), None)
    if box is None or box.config.schedule is None or isinstance(box.config.schedule.root, NoSchedule):
        return None
    return box if box.config.active is not False else None


class FlowScheduler:
    def __init__(self, clock: Callable[[], datetime] = real_now,
                 executor_factory: Callable[[], FlowExecutor] | None = None,
                 run_in_background: Callable[[Job], None] | None = None,
                 llm_keys: LlmKeys | None = None, ingestion_up: IngestionUp | None = None):
        self.clock = clock
        self.executor_factory = executor_factory
        self.run_in_background = run_in_background or (lambda job: threading.Thread(target=job, daemon=True).start())
        self.llm_keys = llm_keys
        self.ingestion_up = ingestion_up
        self._last: dict[str, datetime] = {}
        self._missed: dict[str, list[datetime]] = defaultdict(list)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def next_run(self, flow: Flow) -> datetime | None:
        box = scheduled_box(flow.graph)
        if box is None:
            return None
        with self._lock:
            after = self._last.get(flow.id) or self.clock()
        return next_occurrence(box.config.schedule, get_config().general.timezone, after)

    def tick(self) -> list[str]:
        """Lanza las ejecuciones debidas (como mucho una por flujo y tic) y devuelve sus identificadores."""
        now = self.clock()
        tz = get_config().general.timezone
        launched = []
        flows = get_flow_store().list()
        with self._lock:
            for gone in set(self._last) - {f.id for f in flows}:
                self._last.pop(gone, None)
        for flow in flows:
            box = scheduled_box(flow.graph)
            with self._lock:
                if box is None:
                    self._last.pop(flow.id, None)
                    continue
                last = self._last.setdefault(flow.id, now)
                due = next_occurrence(box.config.schedule, tz, last)
                if due is None or due > now:
                    continue
                self._last[flow.id] = now
            run_id = self._launch(flow, due, tz)
            if run_id:
                launched.append(run_id)
        return launched

    def _launch(self, flow: Flow, due: datetime, tz: str) -> str | None:
        store = get_run_store()
        issues = blocking(validate(flow.graph, self.llm_keys, self.ingestion_up))
        if issues:
            run = store.create(flow, SCHEDULER, origin="programada")
            moment = self.clock()
            run.update(status=ERROR, started_at=moment, finished_at=moment,
                       notes=[f"{issue.code}: {issue.message}" for issue in issues])
            return run.id
        run = store.start(flow, SCHEDULER, origin="programada")
        if run is None:
            self._missed[flow.id].append(due)
            return None
        missed = self._missed.pop(flow.id, [])
        zone = ZoneInfo(tz)
        run.update(notes=[f"Scheduled run at {moment.astimezone(zone):%H:%M} skipped: another run was in progress"
                          for moment in missed])
        executor = self.executor_factory()
        self.run_in_background(lambda: executor.execute(run))
        return run.id

    def safe_tick(self) -> list[str]:
        try:
            return self.tick()
        except Exception:  # noqa: BLE001 - un fallo (por ejemplo, la ingesta caída) no deja caer el hilo
            logger.exception("Fallo en un tic del programador de flujos de insights")
            return []

    def start(self) -> None:
        def loop():
            while not self._stop.wait(TICK_SECONDS):
                self.safe_tick()

        self._thread = threading.Thread(target=loop, name="programador-de-flujos", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def _default_scheduler() -> FlowScheduler:
    """El de la API: el motor de prompts, la escritura de campos y las descargas con los clientes por defecto."""
    from app.flows.analysis_writer import IngestionAnalysisWriter
    from app.flows.downloader import IngestionDownloader
    from app.flows.llm_runner import build_runner
    from app.flows.runs import step_delay_seconds
    from app.ingestion_client import get_ingestion_client
    from app.llm_client import get_llm_client
    from app.routers.flows import llm_keys

    def executor() -> FlowExecutor:
        client = get_ingestion_client()
        return FlowExecutor(build_runner(get_llm_client()), step_delay_seconds(),
                            writer=IngestionAnalysisWriter(client), downloader=IngestionDownloader(client))

    return FlowScheduler(executor_factory=executor, llm_keys=llm_keys(get_llm_client()),
                         ingestion_up=lambda: IngestionDownloader(get_ingestion_client()).available())


_scheduler: FlowScheduler | None = None


def get_scheduler() -> FlowScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = _default_scheduler()
    return _scheduler


def scheduler_enabled() -> bool:
    """`FLOW_SCHEDULER=0` lo apaga (los tests no arrancan el hilo)."""
    return os.environ.get("FLOW_SCHEDULER", "1") != "0"
