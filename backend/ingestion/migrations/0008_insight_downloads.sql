-- FE017 · Descargas lanzadas por la caja «Genesys download» de un flujo de insights.
-- Una ejecución de descarga cuelga de un flujo de descarga (FE011) o de un flujo de insights (FE015), nunca de los dos.
ALTER TABLE download_run ALTER COLUMN flow_id DROP NOT NULL;
ALTER TABLE download_run ADD COLUMN insight_flow_id text REFERENCES insight_flow (id) ON DELETE CASCADE;
ALTER TABLE download_run ADD CONSTRAINT download_run_one_owner CHECK ((flow_id IS NULL) <> (insight_flow_id IS NULL));
-- La caja no guarda zona horaria: la envía la API al lanzarla, y el log la usa para escribir el intervalo.
ALTER TABLE download_run ADD COLUMN timezone text;
-- Como mucho una descarga activa por caja, como por flujo de descarga (`download_run_one_active`).
CREATE UNIQUE INDEX download_run_one_active_insight ON download_run (insight_flow_id)
    WHERE insight_flow_id IS NOT NULL AND status IN ('pendiente', 'en_curso');
CREATE INDEX download_run_insight_created ON download_run (insight_flow_id, created_at DESC);

-- Subconjunto de una descarga: las conversaciones que insertó o actualizó. Es lo que recibe el Sampling de la caja.
CREATE TABLE download_run_conversation (
    run_id           text NOT NULL REFERENCES download_run (id) ON DELETE CASCADE,
    conversation_id  text NOT NULL REFERENCES conversation (id) ON DELETE CASCADE,
    PRIMARY KEY (run_id, conversation_id)
);
