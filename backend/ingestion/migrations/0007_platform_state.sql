-- FE015 · Estado de la plataforma que antes vivía en la memoria de la API y se perdía al reiniciarla.
-- La API sigue sin escribir en la base: lo guarda a través del servicio de ingesta (ADR-008).

-- Flujos de insights (FE004): el grafo va entero en `graph`, tal como lo valida y lo serializa la API.
CREATE TABLE insight_flow (
    id          text PRIMARY KEY,
    name        text NOT NULL,
    author_id   text NOT NULL,
    author_name text NOT NULL,
    graph       jsonb NOT NULL,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL
);

-- Secciones de la configuración global (FE005): una fila por sección, con su valor serializado.
CREATE TABLE platform_setting (
    key        text PRIMARY KEY,
    value      jsonb NOT NULL,
    updated_at timestamptz NOT NULL
);
