"""Ejecuciones de descarga: alta, estado, log y ejecutor (FE011, criterios 6, 15, 17 y 18).

El ejecutor recorre el pipeline `extraer → normalizar → analizar → cargar` y guarda los contadores después de cada
conversación, así que quien consulta la ejecución ve el progreso. Cada conversación va en su propia transacción: un fallo
en una no deshace las anteriores y la ejecución sigue. Solo un error de autenticación (o de la búsqueda) la detiene.
El log guarda identificadores, recuentos y motivos, nunca el texto de los turnos ni secretos.
"""
import random
from collections.abc import Callable
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app import ids
from app.clock import now
from ingestion.genesys.client import GenesysAuthError, GenesysClient, GenesysError
from ingestion.pipeline.analyze import Analyzer, PendingAnalyzer
from ingestion.pipeline.extract import IN_PROGRESS, GenesysNames, fetch, search
from ingestion.pipeline.load import INSERTED, load
from ingestion.pipeline.normalize import normalize

_rng = random.SystemRandom()
ACTIVE = ("pendiente", "en_curso")
LEVELS = ("info", "aviso", "error")


class RunAlreadyActive(Exception):
    pass


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def new_counters() -> dict:
    return {"found": 0, "downloaded": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": 0,
            "skipped_in_progress": 0, "skipped_other_channel": 0, "by_channel": {"voz": 0, "chat": 0},
            "by_quality": {"completa": 0, "parcial": 0, "sin_transcripcion": 0}, "undelivered_messages": 0}


def create_run(database_url: str, flow_id: str, origin: str, start: datetime, end: datetime, channels: list[str],
               user: tuple[str, str] | None = None) -> str:
    run_id = ids.new_id(ids.RUN, _rng)
    user_id, user_name = user or (None, None)
    try:
        with psycopg.connect(database_url) as conn:
            conn.execute(
                "INSERT INTO download_run (id, flow_id, origin, status, interval_from, interval_to, channels, counters, "
                "started_by_id, started_by_name, created_at) VALUES (%s, %s, %s, 'pendiente', %s, %s, %s, %s, %s, %s, %s)",
                (run_id, flow_id, origin, start, end, list(channels), Jsonb(new_counters()), user_id, user_name, now()))
    except psycopg.errors.UniqueViolation:
        raise RunAlreadyActive(flow_id) from None
    return run_id


def run_to_dict(row: dict) -> dict:
    finished, started = row["finished_at"], row["started_at"]
    return {
        "id": row["id"], "flow_id": row["flow_id"], "origin": row["origin"], "status": row["status"],
        "interval": {"from": _iso(row["interval_from"]), "to": _iso(row["interval_to"])},
        "channels": row["channels"], "counters": row["counters"], "error": row["error"],
        "started_by": {"id": row["started_by_id"], "name": row["started_by_name"]} if row["started_by_id"] else None,
        "created_at": _iso(row["created_at"]), "started_at": _iso(started), "finished_at": _iso(finished),
        "duration_s": round((finished - started).total_seconds(), 3) if finished and started else None,
    }


def get_run(database_url: str, run_id: str) -> dict | None:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        row = conn.execute("SELECT * FROM download_run WHERE id = %s", (ids.normalize(run_id),)).fetchone()
    return run_to_dict(row) if row else None


def list_log(database_url: str, run_id: str, after: int = 0, level: str | None = None) -> list[dict]:
    query = "SELECT id, at, level, stage, message, genesys_id FROM run_log WHERE run_id = %s AND id > %s"
    params: list = [ids.normalize(run_id), after]
    if level:
        query += " AND level = %s"
        params.append(level)
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute(query + " ORDER BY id", params).fetchall()
    return [{**row, "at": _iso(row["at"])} for row in rows]


class RunExecutor:
    def __init__(self, database_url: str, client_factory: Callable[[], GenesysClient],
                 analyzer: Analyzer | None = None, on_step: Callable[[str], None] | None = None):
        self.database_url = database_url
        self.client_factory = client_factory
        self.analyzer = analyzer or PendingAnalyzer()
        self.on_step = on_step or (lambda stage: None)

    def execute(self, run_id: str) -> None:
        with psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row) as conn:
            _Execution(self, conn, run_id).run()


class _Execution:
    def __init__(self, executor: RunExecutor, conn: psycopg.Connection, run_id: str):
        self.x, self.conn, self.run_id = executor, conn, run_id
        self.row = conn.execute("SELECT * FROM download_run WHERE id = %s", (run_id,)).fetchone()
        self.counters = new_counters()
        self.warnings = 0
        self.client: GenesysClient | None = None

    # Log y estado ------------------------------------------------------------------------------------------------------

    def log(self, level: str, stage: str, message: str, genesys_id: str | None = None) -> None:
        if self.client:
            message = self.client.redact(message)
        self.warnings += level != "info"
        self.conn.execute("INSERT INTO run_log (run_id, at, level, stage, message, genesys_id) "
                          "VALUES (%s, %s, %s, %s, %s, %s)", (self.run_id, now(), level, stage, message, genesys_id))

    def save(self) -> None:
        self.conn.execute("UPDATE download_run SET counters = %s WHERE id = %s", (Jsonb(self.counters), self.run_id))

    def step(self, stage: str) -> None:
        self.save()
        self.x.on_step(stage)

    def finish(self, status: str, error: str | None = None) -> None:
        self.conn.execute("UPDATE download_run SET status = %s, error = %s, counters = %s, finished_at = %s "
                          "WHERE id = %s", (status, error, Jsonb(self.counters), now(), self.run_id))

    # Ejecución ---------------------------------------------------------------------------------------------------------

    def run(self) -> None:
        start, end, channels = self.row["interval_from"], self.row["interval_to"], self.row["channels"]
        self.conn.execute("UPDATE download_run SET status = 'en_curso', started_at = %s WHERE id = %s",
                          (now(), self.run_id))
        self.log("info", "inicio", f"Ejecución {self.row['origin']} de {_iso(start)} a {_iso(end)} "
                                   f"({', '.join(channels)})")
        try:
            self.client = self.x.client_factory()
            self.client.ensure_token()
            self.log("info", "autenticación", "Conectado con Genesys Cloud")
            self.step("autenticación")
            self.extract_and_load(start, end, channels)
        except GenesysAuthError as exc:
            self.log("error", "autenticación", str(exc))
            self.finish("error", str(exc))
            return
        except Exception as exc:  # la búsqueda no se puede completar: la ejecución no tiene qué descargar
            message = self.client.redact(f"{exc}") if self.client else type(exc).__name__
            self.log("error", "búsqueda", message)
            self.finish("error", message)
            return
        self.finish("completada_con_avisos" if self.warnings else "completada")

    def extract_and_load(self, start: datetime, end: datetime, channels: list[str]) -> None:
        c = self.counters

        def on_chunk(number, total, chunk_start, chunk_end, found):
            self.log("info", "búsqueda", f"Tramo {number}/{total} ({_iso(chunk_start)} – {_iso(chunk_end)}): "
                                         f"{found} conversaciones")

        result = search(self.client, start, end, set(channels), on_chunk=on_chunk)
        c["found"] = len(result.found) + len(result.skipped)
        for genesys_id, reason in result.skipped:
            c["skipped"] += 1
            c["skipped_in_progress" if reason == IN_PROGRESS else "skipped_other_channel"] += 1
            self.log("aviso", "búsqueda", f"Omitida: {reason}", genesys_id)
        self.log("info", "búsqueda", f"{c['found']} encontradas, {len(result.found)} por descargar, "
                                     f"{c['skipped']} omitidas")
        self.step("búsqueda")

        names = GenesysNames(self.client)
        analyzed = 0
        for details in result.found:
            genesys_id = details["conversationId"]
            stage = "descarga"
            try:
                raw = fetch(self.client, details)
                c["downloaded"] += 1
                self.step("descarga")
                stage = "normalización"
                normalized = normalize(raw, names)
                for warning in normalized.warnings:
                    self.log("aviso", "normalización", warning, genesys_id)
                self.x.on_step("normalización")
                stage = "análisis"
                analysis = self.x.analyzer.analyze(normalized)
                analyzed += analysis.status == "completo"
                self.x.on_step("análisis")
                stage = "carga"
                outcome = load(self.conn, normalized, analysis)
            except GenesysAuthError:
                raise
            except Exception as exc:  # noqa: BLE001 - una conversación que falla no detiene la ejecución
                c["errors"] += 1
                detail = str(exc) if isinstance(exc, GenesysError) else f"{type(exc).__name__}: {exc}"
                self.log("error", stage, f"No se pudo procesar: {detail}", genesys_id)
                self.save()
                continue
            c["inserted" if outcome == INSERTED else "updated"] += 1
            c["by_channel"][normalized.channel] += 1
            c["by_quality"][normalized.transcript_quality] += 1
            c["undelivered_messages"] += normalized.undelivered_messages
            self.step("carga")

        self.log("info", "descarga", f"{c['downloaded']} descargadas, {c['errors']} con error")
        self.log("info", "normalización", f"Calidad: {c['by_quality']['completa']} completas, "
                                          f"{c['by_quality']['parcial']} parciales, "
                                          f"{c['by_quality']['sin_transcripcion']} sin transcripción; "
                                          f"{c['undelivered_messages']} mensajes no entregados")
        self.log("info", "análisis", f"{analyzed} analizadas, {c['downloaded'] - analyzed - c['errors']} pendientes")
        self.log("info", "carga", f"{c['inserted']} insertadas, {c['updated']} actualizadas")
