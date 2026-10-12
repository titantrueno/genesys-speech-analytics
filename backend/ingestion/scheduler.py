"""Lanzamiento de ejecuciones y programador de los flujos de descarga (FE011, criterios 15 y 16).

`launch` lo comparten la ejecución manual y la programada: resuelve el intervalo con la zona horaria del flujo, crea la
ejecución (`RunAlreadyActive` si ya hay una activa) y la ejecuta en segundo plano. El programador es un hilo que cada
30 s lanza las ejecuciones debidas; los tests llaman a `tick()` con un reloj simulado, sin hilos.
"""
import logging
import threading
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.clock import now as real_now
from ingestion.flows import Interval, Schedule, next_occurrence, resolve_interval
from ingestion.genesys.client import GenesysClient
from ingestion.pipeline.analyze import Analyzer
from ingestion.runs import RunAlreadyActive, RunExecutor, create_run

TICK_SECONDS = 30
logger = logging.getLogger("ingestion")
Job = Callable[[], None]


def launch(database_url: str, flow_id: str, origin: str, user: tuple[str, str] | None, now: datetime,
           client_factory: Callable[[], GenesysClient], run_in_background: Callable[[Job], None],
           analyzer: Analyzer | None = None) -> str:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        flow = conn.execute("SELECT interval, timezone, channels, missed_runs FROM download_flow WHERE id = %s",
                            (flow_id,)).fetchone()
    start, end = resolve_interval(Interval.model_validate(flow["interval"]), flow["timezone"], now)
    zone = ZoneInfo(flow["timezone"])
    notes = [f"Ejecución programada de las {datetime.fromisoformat(missed).astimezone(zone):%H:%M} omitida: "
             f"había otra ejecución en curso" for missed in flow["missed_runs"]]
    run_id = create_run(database_url, flow_id, origin, start, end, flow["channels"], user, notes)
    if notes:
        with psycopg.connect(database_url) as conn:
            conn.execute("UPDATE download_flow SET missed_runs = '[]' WHERE id = %s", (flow_id,))
    executor = RunExecutor(database_url, client_factory, analyzer)
    run_in_background(lambda: executor.execute(run_id))
    return run_id


class Scheduler:
    def __init__(self, database_url: str, client_factory: Callable[[], GenesysClient],
                 clock: Callable[[], datetime] = real_now, run_in_background: Callable[[Job], None] | None = None,
                 analyzer: Analyzer | None = None):
        self.database_url = database_url
        self.client_factory = client_factory
        self.clock = clock
        self.run_in_background = run_in_background or (lambda job: threading.Thread(target=job, daemon=True).start())
        self.analyzer = analyzer
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> list[str]:
        """Lanza las ejecuciones programadas debidas y fija la siguiente de cada flujo. Devuelve las lanzadas."""
        now = self.clock()
        launched = []
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            due = conn.execute("SELECT id, schedule, timezone, next_run_at FROM download_flow "
                               "WHERE active AND next_run_at IS NOT NULL AND next_run_at <= %s", (now,)).fetchall()
        for flow in due:
            following = next_occurrence(Schedule.model_validate(flow["schedule"]), flow["timezone"], now)
            try:
                launched.append(launch(self.database_url, flow["id"], "programada", None, now, self.client_factory,
                                       self.run_in_background, self.analyzer))
                missed = []
            except RunAlreadyActive:
                missed = [flow["next_run_at"].isoformat()]
            with psycopg.connect(self.database_url) as conn:
                conn.execute("UPDATE download_flow SET next_run_at = %s, missed_runs = missed_runs || %s WHERE id = %s",
                             (following, Jsonb(missed), flow["id"]))
        return launched

    def safe_tick(self) -> list[str]:
        """`tick` sin dejar caer el hilo: un fallo (por ejemplo, PostgreSQL caído) se registra y se reintenta en el
        siguiente tic."""
        try:
            return self.tick()
        except Exception:  # noqa: BLE001
            logger.exception("Fallo en un tic del programador de descargas")
            return []

    def start(self) -> None:
        def loop():
            while not self._stop.wait(TICK_SECONDS):
                self.safe_tick()

        self._thread = threading.Thread(target=loop, name="programador-de-descargas", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
