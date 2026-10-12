"""Carga idempotente de una conversación normalizada en PostgreSQL (FE011, criterio 10).

Una transacción por conversación: catálogos, `upsert` de la conversación por su identificador de Genesys y reemplazo de
sus tramos, turnos, temas y respuestas originales.

Casilla «Sobrescribir» del flujo (FE013): sin ella, una conversación que ya existe no se toca (`OMITTED`); el ejecutor
ya lo comprueba antes de descargar, y esto cubre otra ejecución que la cargue mientras tanto. Con ella, la conversación
se sustituye entera y su análisis también, aunque estuviera `completo`: se borran el summary y el main topic del LLM.
"""
from dataclasses import asdict

import psycopg
from psycopg.rows import tuple_row
from psycopg.types.json import Jsonb

from ingestion.pipeline.analyze import Analysis
from ingestion.pipeline.normalize import NormalizedConversation

INSERTED, UPDATED, OMITTED = "insertada", "actualizada", "omitida"

_CONVERSATION_COLUMNS = [
    "id", "genesys_id", "channel", "started_at", "ended_at", "duration_s", "direction", "external_tag", "ani", "dnis",
    "customer_id", "division_ids", "transcript_quality", "disconnect_type", "transferred", "reconnected",
    "contained_in_bot", "derived_to_agent", "abandoned_in_queue", "undelivered_messages", "customer_sentiment", "mos",
    "metrics",
]
_ANALYSIS_FIELDS = ["status", "source", "summary", "main_topic", "secondary_topics", "resolution", "csat", "effort",
                    "churn_risk", "compliance", "entities", "keywords", "error"]
_JSON_ANALYSIS = {"secondary_topics", "compliance", "entities", "keywords"}


def _conversation_values(c: NormalizedConversation) -> list:
    values = {name: getattr(c, name) for name in _CONVERSATION_COLUMNS}
    values["metrics"] = Jsonb(c.metrics)
    return [values[name] for name in _CONVERSATION_COLUMNS]


def load(conn: psycopg.Connection, c: NormalizedConversation, analysis: Analysis, overwrite: bool) -> str:
    with conn.transaction():
        for queue_id, (genesys_id, name) in c.queues.items():
            conn.execute("INSERT INTO queue (id, genesys_id, name) VALUES (%s, %s, %s) ON CONFLICT (id) "
                         "DO UPDATE SET name = EXCLUDED.name, updated_at = now()", (queue_id, genesys_id, name))
        for agent_id, (genesys_id, name) in c.agents.items():
            conn.execute("INSERT INTO agent (id, genesys_id, name) VALUES (%s, %s, %s) ON CONFLICT (id) "
                         "DO UPDATE SET name = EXCLUDED.name, updated_at = now()", (agent_id, genesys_id, name))
        for genesys_id, (name, flow_type) in c.flows.items():
            conn.execute("INSERT INTO flow (genesys_id, name, type) VALUES (%s, %s, %s) ON CONFLICT (genesys_id) "
                         "DO UPDATE SET name = EXCLUDED.name, type = EXCLUDED.type, updated_at = now()",
                         (genesys_id, name, flow_type))
        for table, items in (("wrapup", c.wrapups), ("division", c.divisions)):
            for genesys_id, name in items.items():
                conn.execute(f"INSERT INTO {table} (genesys_id, name) VALUES (%s, %s) ON CONFLICT (genesys_id) "
                             "DO UPDATE SET name = EXCLUDED.name, updated_at = now()", (genesys_id, name))

        columns = ", ".join(_CONVERSATION_COLUMNS)
        values = _conversation_values(c)
        # Insertada o actualizada con semántica documentada: `ON CONFLICT DO NOTHING` solo devuelve (`RETURNING`) las
        # filas que inserta; si no devuelve ninguna, ya existía y se actualiza. Cursor de tuplas: la conexión puede venir
        # configurada con otra fábrica de filas (el ejecutor usa `dict_row`).
        inserted = conn.cursor(row_factory=tuple_row).execute(
            f"INSERT INTO conversation ({columns}) VALUES ({', '.join(['%s'] * len(_CONVERSATION_COLUMNS))}) "
            "ON CONFLICT (genesys_id) DO NOTHING RETURNING id", values).fetchone() is not None
        if not inserted and not overwrite:
            return OMITTED
        if not inserted:
            editable = [name for name in _CONVERSATION_COLUMNS if name != "genesys_id"]
            conn.execute(f"UPDATE conversation SET {', '.join(f'{name} = %s' for name in editable)}, updated_at = now() "
                         "WHERE genesys_id = %s",
                         [v for name, v in zip(_CONVERSATION_COLUMNS, values) if name != "genesys_id"] + [c.genesys_id])

        for table in ("segment", "turn", "topic_hit", "raw_payload"):
            conn.execute(f"DELETE FROM {table} WHERE conversation_id = %s", (c.id,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO segment (conversation_id, seq, kind, name, genesys_participant_id, queue_id, agent_id, "
                "flow_genesys_id, wrapup_genesys_id, disconnect_type, exit_reason, transfer_target, started_at, "
                "ended_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [(c.id, s.seq, s.kind, s.name, s.genesys_participant_id, s.queue_id, s.agent_id, s.flow_genesys_id,
                  s.wrapup_genesys_id, s.disconnect_type, s.exit_reason, s.transfer_target, s.started_at, s.ended_at)
                 for s in c.segments])
            cur.executemany(
                "INSERT INTO turn (conversation_id, seq, speaker, text, offset_s, sentiment, delivered, agent_id, "
                "message_id, confidence) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [(c.id, t.seq, t.speaker, t.text, t.offset_s, t.sentiment, t.delivered, t.agent_id, t.message_id,
                  t.confidence) for t in c.turns])
            cur.executemany(
                "INSERT INTO topic_hit (conversation_id, seq, genesys_topic_id, name, phrase, speaker, turn_seq, "
                "offset_s, confidence) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [(c.id, t.seq, t.genesys_topic_id, t.name, t.phrase, t.speaker, t.turn_seq, t.offset_s, t.confidence)
                 for t in c.topics])
            cur.executemany(
                "INSERT INTO raw_payload (conversation_id, kind, payload) VALUES (%s, %s, %s)",
                [(c.id, kind, Jsonb(payload)) for kind, payload in c.raw.payloads().items()])

        values = asdict(analysis)
        params = [Jsonb(values[f]) if f in _JSON_ANALYSIS and values[f] is not None else values[f]
                  for f in _ANALYSIS_FIELDS]
        assignments = ", ".join(f"{f} = EXCLUDED.{f}" for f in _ANALYSIS_FIELDS)
        conn.execute(
            f"INSERT INTO analysis (conversation_id, {', '.join(_ANALYSIS_FIELDS)}) "
            f"VALUES (%s, {', '.join(['%s'] * len(_ANALYSIS_FIELDS))}) "
            # Con «Sobrescribir» también se borra la trazabilidad de lo que escribió un LLM (FE013).
            f"ON CONFLICT (conversation_id) DO UPDATE SET {assignments}, llm_meta = '{{}}', updated_at = now()",
            [c.id, *params])
    return INSERTED if inserted else UPDATED
