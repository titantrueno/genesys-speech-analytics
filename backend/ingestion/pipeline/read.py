"""Lectura de una conversación guardada (FE011, criterio 2): `GET /conversations/{id}` del servicio de ingesta.

Acepta el `1CO` o el identificador de Genesys y devuelve la conversación normalizada con los nombres de sus catálogos.
La usan los tests y la prueba real, y la usará FE012.
"""
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from app import ids

_ANALYSIS = ["status", "source", "summary", "main_topic", "secondary_topics", "resolution", "csat", "effort",
             "churn_risk", "compliance", "entities", "keywords"]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def read_conversation(conn: psycopg.Connection, key: str) -> dict | None:
    cur = conn.cursor(row_factory=dict_row)
    column = "id" if ids.is_valid(ids.normalize(key), ids.CONVERSATION) else "genesys_id"
    value = ids.normalize(key) if column == "id" else key
    row = cur.execute(f"SELECT * FROM conversation WHERE {column} = %s", (value,)).fetchone()
    if row is None:
        return None
    cid = row["id"]
    divisions = {r["genesys_id"]: r["name"] for r in cur.execute(
        "SELECT genesys_id, name FROM division WHERE genesys_id = ANY(%s)", (row["division_ids"],)).fetchall()}
    segments = cur.execute(
        "SELECT s.*, q.genesys_id AS q_gid, q.name AS q_name, a.genesys_id AS a_gid, a.name AS a_name, "
        "f.name AS f_name, f.type AS f_type, w.name AS w_name FROM segment s "
        "LEFT JOIN queue q ON q.id = s.queue_id LEFT JOIN agent a ON a.id = s.agent_id "
        "LEFT JOIN flow f ON f.genesys_id = s.flow_genesys_id LEFT JOIN wrapup w ON w.genesys_id = s.wrapup_genesys_id "
        "WHERE s.conversation_id = %s ORDER BY s.seq", (cid,)).fetchall()
    turns = cur.execute("SELECT t.*, a.name AS a_name FROM turn t LEFT JOIN agent a ON a.id = t.agent_id "
                        "WHERE t.conversation_id = %s ORDER BY t.seq", (cid,)).fetchall()
    topics = cur.execute("SELECT * FROM topic_hit WHERE conversation_id = %s ORDER BY seq", (cid,)).fetchall()
    analysis = cur.execute("SELECT * FROM analysis WHERE conversation_id = %s", (cid,)).fetchone()
    return {
        "id": cid, "genesys_id": row["genesys_id"], "channel": row["channel"],
        "started_at": _iso(row["started_at"]), "ended_at": _iso(row["ended_at"]), "duration_s": row["duration_s"],
        "direction": row["direction"], "external_tag": row["external_tag"], "ani": row["ani"], "dnis": row["dnis"],
        "customer_id": row["customer_id"],
        "divisions": [{"id": d, "name": divisions.get(d, d)} for d in row["division_ids"]],
        "transcript_quality": row["transcript_quality"], "disconnect_type": row["disconnect_type"],
        "transferred": row["transferred"], "reconnected": row["reconnected"],
        "contained_in_bot": row["contained_in_bot"], "derived_to_agent": row["derived_to_agent"],
        "abandoned_in_queue": row["abandoned_in_queue"], "undelivered_messages": row["undelivered_messages"],
        "customer_sentiment": row["customer_sentiment"], "mos": row["mos"], "metrics": row["metrics"],
        "segments": [{
            "seq": s["seq"], "kind": s["kind"], "name": s["name"],
            "started_at": _iso(s["started_at"]), "ended_at": _iso(s["ended_at"]),
            "disconnect_type": s["disconnect_type"], "exit_reason": s["exit_reason"],
            "transfer_target": s["transfer_target"],
            "queue": {"id": s["queue_id"], "genesys_id": s["q_gid"], "name": s["q_name"]} if s["queue_id"] else None,
            "agent": {"id": s["agent_id"], "genesys_id": s["a_gid"], "name": s["a_name"]} if s["agent_id"] else None,
            "flow": {"id": s["flow_genesys_id"], "name": s["f_name"], "type": s["f_type"]}
            if s["flow_genesys_id"] else None,
            "wrapup": {"id": s["wrapup_genesys_id"], "name": s["w_name"]} if s["wrapup_genesys_id"] else None,
        } for s in segments],
        "turns": [{
            "seq": t["seq"], "speaker": t["speaker"], "text": t["text"], "offset_s": t["offset_s"],
            "sentiment": t["sentiment"], "delivered": t["delivered"], "message_id": t["message_id"],
            "confidence": t["confidence"],
            "agent": {"id": t["agent_id"], "name": t["a_name"]} if t["agent_id"] else None,
        } for t in turns],
        "topics": [{"seq": t["seq"], "topic_id": t["genesys_topic_id"], "name": t["name"], "phrase": t["phrase"],
                    "speaker": t["speaker"], "turn_seq": t["turn_seq"], "offset_s": t["offset_s"],
                    "confidence": t["confidence"]} for t in topics],
        "analysis": {name: analysis[name] for name in _ANALYSIS} if analysis else None,
        "ingested_at": _iso(row["ingested_at"]), "updated_at": _iso(row["updated_at"]),
    }
