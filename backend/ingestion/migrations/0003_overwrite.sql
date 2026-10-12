-- FE013 · Casilla «Sobrescribir» de los flujos de descarga (T1).
-- `download_flow.overwrite`: sin marcar, una conversación que ya está en la base no se descarga ni se toca; marcada, se
-- sustituye entera y su análisis vuelve a `pendiente` (se borran el summary y el main topic del LLM).
-- `download_run.overwrite`: el valor del flujo al crear la ejecución; editar el flujo después no la cambia.
ALTER TABLE download_flow ADD COLUMN overwrite boolean NOT NULL DEFAULT false;
ALTER TABLE download_run ADD COLUMN overwrite boolean NOT NULL DEFAULT false;
