-- FE011 · Esquema inicial del servicio de ingesta.
-- Identificadores de la plataforma: `PREFIJO-UUID` generados con `app/ids.py` (v5 derivados del identificador de
-- Genesys para las conversaciones reales, de modo que la carga sea idempotente). Los catálogos sin entidad propia en la
-- plataforma (flujos, wrap-ups, divisiones) usan el identificador de Genesys como clave.

-- Catálogos ------------------------------------------------------------------------------------------------------------

CREATE TABLE queue (
    id          text PRIMARY KEY CHECK (id LIKE '1QU-%'),
    genesys_id  text NOT NULL UNIQUE,
    name        text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agent (
    id          text PRIMARY KEY CHECK (id LIKE '1AG-%'),
    genesys_id  text NOT NULL UNIQUE,
    name        text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE flow (
    genesys_id  text PRIMARY KEY,
    name        text NOT NULL,
    type        text,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE wrapup (
    genesys_id  text PRIMARY KEY,
    name        text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE division (
    genesys_id  text PRIMARY KEY,
    name        text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Conversaciones -------------------------------------------------------------------------------------------------------

-- Las columnas escalares son las que se filtran (FE012); el resto de la analítica (tiempos, métricas de chat,
-- reparto del tiempo de STA, acústica, confianza por hablante) va en `metrics`, con las métricas ausentes sin clave.
CREATE TABLE conversation (
    id                    text PRIMARY KEY CHECK (id LIKE '1CO-%'),
    genesys_id            text NOT NULL UNIQUE,
    channel               text NOT NULL CHECK (channel IN ('voz', 'chat')),
    started_at            timestamptz NOT NULL,
    ended_at              timestamptz NOT NULL,
    duration_s            integer NOT NULL CHECK (duration_s >= 0),
    direction             text,
    external_tag          text,
    ani                   text,
    dnis                  text,
    customer_id           text CHECK (customer_id LIKE '1CU-%'),
    division_ids          text[] NOT NULL DEFAULT '{}',
    transcript_quality    text NOT NULL CHECK (transcript_quality IN ('completa', 'parcial', 'sin_transcripcion')),
    disconnect_type       text,
    transferred           boolean NOT NULL DEFAULT false,
    reconnected           boolean NOT NULL DEFAULT false,
    contained_in_bot      boolean NOT NULL DEFAULT false,
    derived_to_agent      boolean NOT NULL DEFAULT false,
    abandoned_in_queue    boolean NOT NULL DEFAULT false,
    undelivered_messages  integer NOT NULL DEFAULT 0,
    customer_sentiment    real,
    mos                   real,
    metrics               jsonb NOT NULL DEFAULT '{}',
    ingested_at           timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX conversation_started_at ON conversation (started_at);
CREATE INDEX conversation_ani ON conversation (ani);
CREATE INDEX conversation_external_tag ON conversation (external_tag);

-- Tramos: cada paso por un participante (cliente, flujo de entrada, IVR o bot, cola, agente, externo), en orden.
CREATE TABLE segment (
    conversation_id      text NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    seq                  integer NOT NULL,
    kind                 text NOT NULL CHECK (kind IN ('cliente', 'flujo_entrada', 'ivr', 'cola', 'agente', 'externo')),
    name                 text,
    genesys_participant_id text,
    queue_id             text REFERENCES queue (id),
    agent_id             text REFERENCES agent (id),
    flow_genesys_id      text REFERENCES flow (genesys_id),
    wrapup_genesys_id    text REFERENCES wrapup (genesys_id),
    disconnect_type      text,
    exit_reason          text,
    transfer_target      text,
    started_at           timestamptz NOT NULL,
    ended_at             timestamptz,
    PRIMARY KEY (conversation_id, seq)
);

CREATE TABLE turn (
    conversation_id  text NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    seq              integer NOT NULL,
    speaker          text NOT NULL CHECK (speaker IN ('cliente', 'agente', 'bot', 'sistema')),
    text             text NOT NULL,
    offset_s         real NOT NULL CHECK (offset_s >= 0),
    sentiment        real CHECK (sentiment BETWEEN -1 AND 1),
    delivered        boolean NOT NULL DEFAULT true,
    agent_id         text REFERENCES agent (id),
    message_id       text,
    confidence       real,
    PRIMARY KEY (conversation_id, seq)
);

CREATE TABLE topic_hit (
    conversation_id   text NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    seq               integer NOT NULL,
    genesys_topic_id  text NOT NULL,
    name              text NOT NULL,
    phrase            text,
    speaker           text CHECK (speaker IN ('cliente', 'agente', 'bot', 'sistema')),
    turn_seq          integer,
    offset_s          real,
    confidence        real,
    PRIMARY KEY (conversation_id, seq)
);

-- Análisis de la plataforma (summary, main topic, CSAT…): vacío y `pendiente` hasta la fase con LLM.
CREATE TABLE analysis (
    conversation_id   text PRIMARY KEY REFERENCES conversation (id) ON DELETE CASCADE,
    status            text NOT NULL CHECK (status IN ('pendiente', 'completo', 'error')),
    source            text NOT NULL CHECK (source IN ('genesys', 'llm')),
    summary           text,
    main_topic        text,
    secondary_topics  jsonb,
    resolution        text,
    csat              real,
    effort            real,
    churn_risk        text,
    compliance        jsonb,
    entities          jsonb,
    keywords          jsonb,
    error             text,
    updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Respuestas originales de Genesys (detalle de analítica, STA, transcripciones, mensajes) para poder reanalizar.
CREATE TABLE raw_payload (
    conversation_id  text NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    kind             text NOT NULL,
    payload          jsonb NOT NULL,
    fetched_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (conversation_id, kind)
);

-- Flujos de descarga, ejecuciones y log ---------------------------------------------------------------------------------

CREATE TABLE download_flow (
    id           text PRIMARY KEY CHECK (id LIKE '1FL-%'),
    name         text NOT NULL,
    interval     jsonb NOT NULL,
    channels     text[] NOT NULL,
    schedule     jsonb NOT NULL,
    active       boolean NOT NULL DEFAULT true,
    timezone     text NOT NULL,
    author_id    text NOT NULL,
    author_name  text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE download_run (
    id               text PRIMARY KEY CHECK (id LIKE '1RN-%'),
    flow_id          text NOT NULL REFERENCES download_flow (id) ON DELETE CASCADE,
    origin           text NOT NULL CHECK (origin IN ('manual', 'programada')),
    status           text NOT NULL CHECK (status IN ('pendiente', 'en_curso', 'completada', 'completada_con_avisos', 'error')),
    interval_from    timestamptz NOT NULL,
    interval_to      timestamptz NOT NULL,
    channels         text[] NOT NULL,
    counters         jsonb NOT NULL DEFAULT '{}',
    error            text,
    started_by_id    text,
    started_by_name  text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    started_at       timestamptz,
    finished_at      timestamptz
);
CREATE INDEX download_run_flow_created ON download_run (flow_id, created_at DESC);
-- Como mucho una ejecución activa por flujo: el arranque concurrente choca aquí y la API responde `409`.
CREATE UNIQUE INDEX download_run_one_active ON download_run (flow_id) WHERE status IN ('pendiente', 'en_curso');

CREATE TABLE run_log (
    id          bigserial PRIMARY KEY,
    run_id      text NOT NULL REFERENCES download_run (id) ON DELETE CASCADE,
    at          timestamptz NOT NULL DEFAULT now(),
    level       text NOT NULL CHECK (level IN ('info', 'aviso', 'error')),
    stage       text NOT NULL,
    message     text NOT NULL,
    genesys_id  text
);
CREATE INDEX run_log_run ON run_log (run_id, id);
