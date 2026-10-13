"""Ejecuciones de descarga: alta, estado, log y ejecutor (FE011, criterios 6, 15, 17 y 18).

El ejecutor recorre el pipeline `extraer → normalizar → analizar → cargar` y guarda los contadores después de cada
conversación, así que quien consulta la ejecución ve el progreso. Cada conversación va en su propia transacción: un fallo
en una no deshace las anteriores y la ejecución sigue. Solo un error de autenticación (o de la búsqueda) la detiene.
El log guarda identificadores, recuentos y motivos, nunca el texto de los turnos ni secretos.
"""
import logging
import random
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app import ids
from app.clock import now
from ingestion.genesys.client import GenesysAuthError, GenesysClient, GenesysError
from ingestion.pipeline.analyze import Analyzer, PendingAnalyzer
from ingestion.pipeline.extract import IN_PROGRESS, GenesysNames, fetch, search
from ingestion.pipeline.load import INSERTED, OMITTED, load
from ingestion.pipeline.normalize import normalize

_rng = random.SystemRandom()
logger = logging.getLogger("ingestion")
ACTIVE = ("pendiente", "en_curso")
LEVELS = ("info", "aviso", "error")


class RunAlreadyActive(Exception):
    pass


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def new_counters() -> dict:
    return {"found": 0, "downloaded": 0, "inserted": 0, "updated": 0, "skipped": 0, "skipped_existing": 0, "errors": 0,
            "skipped_in_progress": 0, "skipped_other_channel": 0, "by_channel": {"voz": 0, "chat": 0},
            "by_quality": {"completa": 0, "parcial": 0, "sin_transcripcion": 0}, "undelivered_messages": 0}


MAX_RUNS_PER_FLOW = 200


def create_run(database_url: str, flow_id: str, origin: str, start: datetime, end: datetime, channels: list[str],
               user: tuple[str, str] | None = None, notes: list[str] | None = None) -> str:
    """Crea una ejecución `pendiente` (como mucho una activa por flujo) y conserva las 200 más recientes del flujo.

    Copia la casilla «Sobrescribir» del flujo: editar el flujo con la ejecución ya creada no la cambia.
    """
    return _insert_run(database_url, "flow_id", flow_id, origin, start, end, channels, user, notes,
                       overwrite_sql="(SELECT overwrite FROM download_flow WHERE id = %s)", overwrite=flow_id)


def create_insight_run(database_url: str, insight_flow_id: str, origin: str, start: datetime, end: datetime,
                       channels: list[str], overwrite: bool, timezone: str, user: tuple[str, str] | None = None,
                       notes: list[str] | None = None) -> str:
    """Crea la descarga de la caja «Genesys download» de un flujo de insights (FE017), con la configuración de la caja."""
    return _insert_run(database_url, "insight_flow_id", insight_flow_id, origin, start, end, channels, user, notes,
                       overwrite_sql="%s", overwrite=overwrite, timezone=timezone)


def _insert_run(database_url: str, owner: str, owner_id: str, origin: str, start: datetime, end: datetime,
                channels: list[str], user: tuple[str, str] | None, notes: list[str] | None, *, overwrite_sql: str,
                overwrite, timezone: str | None = None) -> str:
    run_id = ids.new_id(ids.RUN, _rng)
    user_id, user_name = user or (None, None)
    try:
        with psycopg.connect(database_url) as conn:
            conn.execute(
                f"INSERT INTO download_run (id, {owner}, origin, status, interval_from, interval_to, channels, "
                "counters, started_by_id, started_by_name, created_at, notes, timezone, overwrite) "
                f"VALUES (%s, %s, %s, 'pendiente', %s, %s, %s, %s, %s, %s, %s, %s, %s, {overwrite_sql})",
                (run_id, owner_id, origin, start, end, list(channels), Jsonb(new_counters()), user_id, user_name,
                 now(), Jsonb(notes or []), timezone, overwrite))
            conn.execute(
                f"DELETE FROM download_run WHERE {owner} = %s AND status <> ALL(%s) AND id NOT IN ("
                f"SELECT id FROM download_run WHERE {owner} = %s ORDER BY created_at DESC LIMIT %s)",
                (owner_id, list(ACTIVE), owner_id, MAX_RUNS_PER_FLOW))
    except psycopg.errors.UniqueViolation:
        raise RunAlreadyActive(owner_id) from None
    return run_id


def list_subset(database_url: str, run_id: str) -> list[str]:
    """Conversaciones (`1CO`) que la ejecución insertó o actualizó, en orden de identificador (FE017)."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute("SELECT conversation_id FROM download_run_conversation WHERE run_id = %s "
                            "ORDER BY conversation_id", (ids.normalize(run_id),)).fetchall()
    return [row[0] for row in rows]


def list_runs(database_url: str, flow_id: str) -> list[dict]:
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute("SELECT * FROM download_run WHERE flow_id = %s ORDER BY created_at DESC",
                            (flow_id,)).fetchall()
    return [run_to_dict(row) for row in rows]


def run_to_dict(row: dict) -> dict:
    finished, started = row["finished_at"], row["started_at"]
    return {
        "id": row["id"], "flow_id": row["flow_id"], "origin": row["origin"], "status": row["status"],
        "interval": {"from": _iso(row["interval_from"]), "to": _iso(row["interval_to"])},
        "channels": row["channels"], "overwrite": row["overwrite"],
        # Las ejecuciones anteriores a FE013 no tienen `skipped_existing`.
        "counters": {**new_counters(), **row["counters"]}, "error": row["error"],
        "started_by": {"id": row["started_by_id"], "name": row["started_by_name"]} if row["started_by_id"] else None,
        "created_at": _iso(row["created_at"]), "started_at": _iso(started), "finished_at": _iso(finished),
        "duration_s": round((finished - started).total_seconds(), 3) if finished and started else None,
        # Solo en las descargas de una caja (FE017): las de los flujos de descarga mantienen su contrato de FE011.
        **({"insight_flow_id": row["insight_flow_id"]} if row.get("insight_flow_id") else {}),
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
        try:
            with psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row) as conn:
                _Execution(self, conn, run_id).run()
        except Exception:  # noqa: BLE001 - una ejecución activa para siempre bloquearía su flujo (409)
            logger.exception("Ejecución %s: fallo inesperado", run_id)
            try:
                with psycopg.connect(self.database_url) as conn:
                    conn.execute("UPDATE download_run SET status = 'error', error = %s, finished_at = %s "
                                 "WHERE id = %s AND status = ANY(%s)",
                                 ("Fallo inesperado del servicio de ingesta", now(), run_id, list(ACTIVE)))
            except psycopg.Error:
                logger.exception("Ejecución %s: no se pudo marcar como fallida", run_id)


def describe_error(exc: Exception) -> str:
    """Motivo de un fallo para el log, sin datos de la conversación.

    Un error de PostgreSQL puede traer la fila entera en su `DETAIL` («Failing row contains …», con el texto de un
    turno): solo se usa su mensaje principal.
    """
    if isinstance(exc, psycopg.Error):
        return f"{type(exc).__name__}: {exc.diag.message_primary or 'database error'}"
    return str(exc) if isinstance(exc, GenesysError) else f"{type(exc).__name__}: {exc}"


class _Execution:
    def __init__(self, executor: RunExecutor, conn: psycopg.Connection, run_id: str):
        self.x, self.conn, self.run_id = executor, conn, run_id
        self.row = conn.execute("SELECT * FROM download_run WHERE id = %s", (run_id,)).fetchone()
        flow = conn.execute("SELECT timezone FROM download_flow WHERE id = %s", (self.row["flow_id"],)).fetchone()
        # La descarga de una caja (FE017) trae su zona horaria; la de un flujo de descarga, la del flujo.
        self.timezone = self.row.get("timezone") or (flow["timezone"] if flow else "UTC")
        self.counters = new_counters()
        self.warnings = 0
        self.client: GenesysClient | None = None

    def span(self, start: datetime, end: datetime) -> str:
        """Intervalo legible en la zona horaria del flujo: «12/10/2026 00:00 – 12/10/2026 15:51 (Europe/Madrid)»."""
        zone = ZoneInfo(self.timezone)
        return f"{start.astimezone(zone):%d/%m/%Y %H:%M} – {end.astimezone(zone):%d/%m/%Y %H:%M} ({self.timezone})"

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

    def exists(self, genesys_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM conversation WHERE genesys_id = %s", (genesys_id,)).fetchone() is not None

    def skip_existing(self, genesys_id: str) -> None:
        self.counters["skipped_existing"] += 1
        self.log("info", "download", "Already exists: not downloaded", genesys_id)
        self.save()

    # Ejecución ---------------------------------------------------------------------------------------------------------

    def run(self) -> None:
        start, end, channels = self.row["interval_from"], self.row["interval_to"], self.row["channels"]
        self.conn.execute("UPDATE download_run SET status = 'en_curso', started_at = %s WHERE id = %s",
                          (now(), self.run_id))
        mode = "overwrites the existing ones" if self.row["overwrite"] else "skips the existing ones"  # nulo: anterior a FE013
        self.log("info", "start", f"Run {self.row['origin']}: {self.span(start, end)}, {', '.join(channels)}; "
                                   f"{mode}")
        for note in self.row.get("notes") or []:
            self.log("aviso", "scheduling", note)
        try:
            self.client = self.x.client_factory()
            self.client.ensure_token()
            self.log("info", "authentication", "Connected to Genesys Cloud")
            self.step("authentication")
            self.extract_and_load(start, end, channels)
        except GenesysAuthError as exc:
            self.log("error", "authentication", str(exc))
            self.finish("error", str(exc))
            return
        except Exception as exc:  # la búsqueda no se puede completar: la ejecución no tiene qué descargar
            message = self.client.redact(describe_error(exc)) if self.client else type(exc).__name__
            self.log("error", "search", message)
            self.finish("error", message)
            return
        self.finish("completada_con_avisos" if self.warnings else "completada")

    def extract_and_load(self, start: datetime, end: datetime, channels: list[str]) -> None:
        c = self.counters

        def on_chunk(number, total, chunk_start, chunk_end, found):
            self.log("info", "search", f"Chunk {number}/{total} ({self.span(chunk_start, chunk_end)}): "
                                         f"{found} conversations")

        result = search(self.client, start, end, set(channels), on_chunk=on_chunk)
        c["found"] = len(result.found) + len(result.skipped)
        for genesys_id, reason in result.skipped:
            c["skipped"] += 1
            c["skipped_in_progress" if reason == IN_PROGRESS else "skipped_other_channel"] += 1
            self.log("aviso", "search", f"Skipped: {reason}", genesys_id)
        self.log("info", "search", f"{c['found']} found, {len(result.found)} to download, "
                                     f"{c['skipped']} skipped")
        self.step("search")

        names = GenesysNames(self.client)
        analyzed = 0
        overwrite = bool(self.row["overwrite"])
        for details in result.found:
            genesys_id = details["conversationId"]
            stage = "download"
            try:
                # Sin «Sobrescribir», lo que ya está en la base no se descarga (FE013, criterio 26).
                if not overwrite and self.exists(genesys_id):
                    self.skip_existing(genesys_id)
                    continue
                raw = fetch(self.client, details)
                c["downloaded"] += 1
                self.step("download")
                stage = "normalization"
                normalized = normalize(raw, names)
                for warning in normalized.warnings:
                    self.log("aviso", "normalization", warning, genesys_id)
                self.x.on_step("normalization")
                stage = "analysis"
                analysis = self.x.analyzer.analyze(normalized)
                analyzed += analysis.status == "completo"
                self.x.on_step("analysis")
                stage = "load"
                with self.conn.transaction():  # la conversación y su entrada en el subconjunto, juntas (FE017)
                    outcome = load(self.conn, normalized, analysis, overwrite)
                    if outcome != OMITTED:
                        self.conn.execute("INSERT INTO download_run_conversation (run_id, conversation_id) "
                                          "VALUES (%s, %s) ON CONFLICT DO NOTHING", (self.run_id, normalized.id))
            except GenesysAuthError:
                raise
            except Exception as exc:  # noqa: BLE001 - una conversación que falla no detiene la ejecución
                c["errors"] += 1
                self.log("error", stage, f"Could not be processed: {describe_error(exc)}", genesys_id)
                self.save()
                continue
            if outcome == OMITTED:  # otra ejecución la cargó mientras se descargaba
                self.skip_existing(genesys_id)
                continue
            c["inserted" if outcome == INSERTED else "updated"] += 1
            c["by_channel"][normalized.channel] += 1
            c["by_quality"][normalized.transcript_quality] += 1
            c["undelivered_messages"] += normalized.undelivered_messages
            self.step("load")

        self.log("info", "download", f"{c['downloaded']} downloaded, {c['errors']} with errors")
        self.log("info", "normalization", f"Quality: {c['by_quality']['completa']} complete, "
                                          f"{c['by_quality']['parcial']} partial, "
                                          f"{c['by_quality']['sin_transcripcion']} without transcript; "
                                          f"{c['undelivered_messages']} undelivered messages")
        self.log("info", "analysis", f"{analyzed} analyzed, {c['downloaded'] - analyzed - c['errors']} pending")
        self.log("info", "load", f"{c['inserted']} inserted, {c['updated']} updated, "
                                  f"{c['skipped_existing']} already existing")
