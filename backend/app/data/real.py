"""Repositorio de las conversaciones reales (FE012): lectura de solo lectura de la PostgreSQL de FE011.

La API no importa `ingestion` (test estructural de FE011): lee las tablas con su propio SQL. La instantánea completa
(conversaciones con turnos, tramos y temas) se guarda junto a un testigo `(recuento, última actualización)` que se
consulta en cada petición: si una descarga de FE011 ha insertado, actualizado o borrado algo, el testigo cambia y se
recarga. Así los datos nuevos aparecen en la petición siguiente sin un canal de avisos entre los dos procesos.
"""
import itertools
import threading
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from app.data.repository import REAL, DataUnavailable, followup_map
from app.envfile import API_DATABASE_KEYS, read_env
from app.models import Analysis, Conversation, GenesysInfo, Turn

CONNECT_TIMEOUT_S = 2
# El testigo de la base se consulta una vez por petición HTTP, no una vez por llamada a un servicio: `begin_request()`
# marca el comienzo de cada petición y la comprobación se recuerda hasta la siguiente. El límite de tiempo cubre las
# llamadas fuera de una petición (tests, tareas en segundo plano).
CHECK_VALIDITY_S = 1.0
_requests = itertools.count(1)
_current_request = 0
_TOKEN_SQL = ("SELECT (SELECT count(*) FROM conversation) AS n, (SELECT max(updated_at) FROM conversation) AS c, "
              "(SELECT max(updated_at) FROM analysis) AS a")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def begin_request() -> None:
    """Lo llama el middleware al empezar cada petición: obliga a comprobar el testigo al menos una vez por petición."""
    global _current_request
    _current_request = next(_requests)


@dataclass(frozen=True)
class Snapshot:
    """Instantánea inmutable de las conversaciones reales: la identidad del objeto sirve de clave de los cachés."""
    token: tuple
    conversations: list[Conversation]
    index: dict[str, Conversation]
    followups: dict[str, bool]


def _rows(cur, sql: str, params=()) -> list[dict]:
    return cur.execute(sql, params).fetchall()


def _grouped(rows: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for row in rows:
        groups[row["conversation_id"]].append(row)
    return groups


def _segment(s: dict) -> dict:
    return {
        "seq": s["seq"], "kind": s["kind"], "name": s["name"], "started_at": _iso(s["started_at"]),
        "ended_at": _iso(s["ended_at"]), "disconnect_type": s["disconnect_type"], "exit_reason": s["exit_reason"],
        "transfer_target": s["transfer_target"],
        "queue": {"id": s["queue_id"], "genesys_id": s["q_gid"], "name": s["q_name"]} if s["queue_id"] else None,
        "agent": {"id": s["agent_id"], "genesys_id": s["a_gid"], "name": s["a_name"]} if s["agent_id"] else None,
        "flow": {"id": s["flow_genesys_id"], "name": s["f_name"], "type": s["f_type"]}
        if s["flow_genesys_id"] else None,
        "wrapup": {"id": s["wrapup_genesys_id"], "name": s["w_name"]} if s["wrapup_genesys_id"] else None,
    }


def _topic(t: dict) -> dict:
    return {"seq": t["seq"], "topic_id": t["genesys_topic_id"], "name": t["name"], "phrase": t["phrase"],
            "speaker": t["speaker"], "turn_seq": t["turn_seq"], "offset_s": t["offset_s"],
            "confidence": t["confidence"]}


def _analysis(row: dict, analysis: dict | None, turns: list[Turn]) -> Analysis:
    timeline = [t.sentiment for t in turns if t.speaker == "cliente" and t.sentiment is not None]
    done = analysis is not None and analysis["status"] == "completo"
    data = analysis if done else {}
    return Analysis(
        summary=data.get("summary") or "", main_topic=data.get("main_topic"),
        secondary_topics=data.get("secondary_topics") or [], sentiment=row["customer_sentiment"],
        sentiment_timeline=timeline, resolution=data.get("resolution"), csat=data.get("csat"),
        effort=data.get("effort"), churn_risk=data.get("churn_risk"), compliance=data.get("compliance") or {},
        entities=data.get("entities") or [], keywords=data.get("keywords") or [], pending=not done)


def _conversation(row: dict, turns: list[dict], segments: list[dict], topics: list[dict], analysis: dict | None,
                  divisions: dict[str, str]) -> Conversation:
    parsed = [Turn(speaker=t["speaker"], text=t["text"], offset_s=round(t["offset_s"]), sentiment=t["sentiment"],
                   delivered=t["delivered"]) for t in turns]
    by_kind = defaultdict(list)
    for s in segments:
        by_kind[s["kind"]].append(s)
    # Cola y agente de la conversación: la última cola por la que pasó y el primer agente que la atendió.
    queue = next((s for s in reversed(by_kind["cola"]) if s["queue_id"]), None)
    agent = next((s for s in by_kind["agente"] if s["agent_id"]), None)
    genesys = GenesysInfo(
        genesys_id=row["genesys_id"], direction=row["direction"], ani=row["ani"], dnis=row["dnis"],
        external_tag=row["external_tag"], transcript_quality=row["transcript_quality"],
        disconnect_type=row["disconnect_type"], transferred=row["transferred"], reconnected=row["reconnected"],
        contained_in_bot=row["contained_in_bot"], derived_to_agent=row["derived_to_agent"],
        abandoned_in_queue=row["abandoned_in_queue"], undelivered_messages=row["undelivered_messages"],
        customer_sentiment=row["customer_sentiment"], mos=row["mos"], metrics=row["metrics"],
        segments=[_segment(s) for s in segments], topics=[_topic(t) for t in topics],
        divisions=[{"id": d, "name": divisions.get(d, d)} for d in row["division_ids"]])
    return Conversation(
        id=row["id"], channel=row["channel"], started_at=row["started_at"], duration_s=row["duration_s"],
        queue_id=queue["queue_id"] if queue else None, queue=queue["q_name"] if queue else None,
        agent_id=agent["agent_id"] if agent else None, agent=agent["a_name"] if agent else None,
        customer_id=row["customer_id"], turns=parsed, analysis=_analysis(row, analysis, parsed), genesys=genesys)


def load_snapshot(conn: psycopg.Connection, token: tuple) -> Snapshot:
    cur = conn.cursor(row_factory=dict_row)
    rows = _rows(cur, "SELECT * FROM conversation ORDER BY started_at, id")
    turns = _grouped(_rows(cur, "SELECT conversation_id, speaker, text, offset_s, sentiment, delivered FROM turn "
                                "ORDER BY conversation_id, seq"))
    segments = _grouped(_rows(
        cur, "SELECT s.*, q.genesys_id AS q_gid, q.name AS q_name, a.genesys_id AS a_gid, a.name AS a_name, "
             "f.name AS f_name, f.type AS f_type, w.name AS w_name FROM segment s "
             "LEFT JOIN queue q ON q.id = s.queue_id LEFT JOIN agent a ON a.id = s.agent_id "
             "LEFT JOIN flow f ON f.genesys_id = s.flow_genesys_id "
             "LEFT JOIN wrapup w ON w.genesys_id = s.wrapup_genesys_id ORDER BY s.conversation_id, s.seq"))
    topics = _grouped(_rows(cur, "SELECT * FROM topic_hit ORDER BY conversation_id, seq"))
    analyses = {a["conversation_id"]: a for a in _rows(cur, "SELECT * FROM analysis")}
    divisions = {d["genesys_id"]: d["name"] for d in _rows(cur, "SELECT genesys_id, name FROM division")}
    conversations = [_conversation(r, turns[r["id"]], segments[r["id"]], topics[r["id"]], analyses.get(r["id"]),
                                   divisions) for r in rows]
    return Snapshot(token, conversations, {c.id: c for c in conversations}, followup_map(conversations))


class RealRepository:
    origin = REAL

    def __init__(self, database_url: Callable[[], str | None]):
        self._database_url = database_url
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._checked: tuple[int, float] | None = None  # (petición, instante) de la última comprobación del testigo

    def _connect(self) -> psycopg.Connection:
        url = self._database_url()
        if not url:
            raise DataUnavailable("Falta DATABASE_URL")
        try:
            return psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT_S, autocommit=True,
                                   options="-c default_transaction_read_only=on")
        except psycopg.Error as exc:
            raise DataUnavailable(type(exc).__name__) from None

    def snapshot(self) -> Snapshot:
        """Instantánea vigente; si el testigo de la base ha cambiado (o cambió la URL), se recarga."""
        current = self._snapshot
        if (current is not None and self._checked is not None and self._checked[0] == _current_request
                and time.monotonic() - self._checked[1] < CHECK_VALIDITY_S
                and current.token[0] == self._database_url()):
            return current
        try:
            with self._connect() as conn:
                row = conn.execute(_TOKEN_SQL).fetchone()
                token = (self._database_url(), *row)
                with self._lock:
                    current = self._snapshot
                    self._checked = (_current_request, time.monotonic())
                    if current is not None and current.token == token:
                        return current
                    # La carga completa corre bajo el cerrojo: dos peticiones simultáneas no la duplican.
                    self._snapshot = load_snapshot(conn, token)
                    return self._snapshot
        except psycopg.Error as exc:
            raise DataUnavailable(type(exc).__name__) from None

    def version(self) -> object:
        return self.snapshot().token

    def conversations(self) -> list[Conversation]:
        return self.snapshot().conversations

    def index(self) -> dict[str, Conversation]:
        return self.snapshot().index

    def followups(self) -> dict[str, bool]:
        return self.snapshot().followups

    def main_topic_usage_in_db(self) -> Counter | None:
        """Conversaciones reales por main topic, leídas de la base aunque el origen activo sea el sintético (FE013).

        `None` sin `DATABASE_URL` (no hay datos reales que proteger); `DataUnavailable` si la base no responde.
        """
        if not self._database_url():
            return None
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT main_topic, count(*) FROM analysis WHERE main_topic IS NOT NULL "
                                    "GROUP BY main_topic").fetchall()
        except psycopg.Error as exc:
            raise DataUnavailable(type(exc).__name__) from None
        return Counter(dict(rows))

    def queues(self) -> list[tuple[str, str]]:
        found = {c.queue_id: c.queue for c in self.conversations() if c.queue_id}
        return sorted(found.items(), key=lambda item: item[1])

    def agents(self) -> list[tuple[str, str, str | None, str | None]]:
        found = {c.agent_id: (c.agent, c.queue_id, c.queue) for c in self.conversations() if c.agent_id}
        return sorted(((aid, name, qid, queue) for aid, (name, qid, queue) in found.items()), key=lambda a: a[1])


def _configured_url() -> str | None:
    return read_env(API_DATABASE_KEYS).get("DATABASE_URL")


_repository = RealRepository(_configured_url)


def real_repository() -> RealRepository:
    return _repository
