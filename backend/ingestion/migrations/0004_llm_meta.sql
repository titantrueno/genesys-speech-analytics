-- FE013 · Trazabilidad de lo que escribe un flujo de insights con un LLM (T6).
-- `llm_meta`: por campo (`summary`, `main_topic`), proveedor, modelo, ejecución (`1RN`) e instante de la escritura.
-- Una redescarga con «Sobrescribir» la vacía junto con los campos.
ALTER TABLE analysis ADD COLUMN llm_meta jsonb NOT NULL DEFAULT '{}';
