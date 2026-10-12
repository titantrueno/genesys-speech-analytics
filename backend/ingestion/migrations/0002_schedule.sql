-- FE011 · Programación de los flujos de descarga (T5).
-- `next_run_at`: próxima ejecución programada (vacía si el flujo no está programado o está inactivo).
-- `missed_runs`: ejecuciones programadas omitidas porque había otra en curso; la siguiente ejecución las anota en su
-- log (`download_run.notes`) y se vacían.
ALTER TABLE download_flow ADD COLUMN next_run_at timestamptz;
ALTER TABLE download_flow ADD COLUMN missed_runs jsonb NOT NULL DEFAULT '[]';
ALTER TABLE download_run ADD COLUMN notes jsonb NOT NULL DEFAULT '[]';
CREATE INDEX download_flow_next_run ON download_flow (next_run_at) WHERE next_run_at IS NOT NULL;
