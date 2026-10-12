"""Acceso a PostgreSQL y migraciones SQL numeradas (FE011, criterios 1 y 2).

Cada fichero de `migrations/` se aplica una sola vez, en su propia transacción, y queda en `schema_migrations`. Un
cerrojo consultivo evita que dos procesos migren a la vez.
"""
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent / "migrations"
_MIGRATION_LOCK = 711_011  # identificador arbitrario y fijo del cerrojo consultivo


def connect(database_url: str, **kwargs) -> psycopg.Connection:
    return psycopg.connect(database_url, **kwargs)


def migrate(conn: psycopg.Connection) -> list[str]:
    """Aplica las migraciones pendientes y devuelve sus nombres, en orden."""
    applied = []
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                     "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.stem in done:
                continue
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
            applied.append(path.stem)
    return applied


def ping(database_url: str) -> bool:
    try:
        with connect(database_url, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False
