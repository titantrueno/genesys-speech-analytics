-- FE013 · Corrección de la 0003 (hallazgo de /test). Las ejecuciones creadas antes de existir «Sobrescribir» no omitían
-- las conversaciones existentes, las actualizaban: un `false` heredado de la 0003 decía lo contrario en el historial.
-- Su modo queda desconocido (NULL); las ejecuciones nuevas siempre copian el valor del flujo.
ALTER TABLE download_run ALTER COLUMN overwrite DROP NOT NULL;
ALTER TABLE download_run ALTER COLUMN overwrite DROP DEFAULT;
UPDATE download_run SET overwrite = NULL
WHERE created_at < (SELECT applied_at FROM schema_migrations WHERE version = '0003_overwrite');
