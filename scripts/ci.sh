#!/usr/bin/env bash
# Gate local equivalente a .github/workflows/ci.yml: cualquier fallo devuelve código distinto de 0.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Vault"
python3 scripts/audit_vault.py

echo "== Backend: tests"
(cd backend && .venv/bin/pytest -q -m "not pg")

# Segunda pasada con otra semilla y otra fecha de referencia (cruza el cambio de hora de octubre): un test que dependa
# del dataset por defecto falla aquí (FE009).
echo "== Backend: tests con otro dataset (semilla 7, referencia 2026-11-10)"
(cd backend && DATA_SEED=7 DATA_REFERENCE_DATE=2026-11-10 .venv/bin/pytest -q -m "not pg")

# Tests con PostgreSQL (FE011): docker compose levanta la base y se crea `speech_analytics_test`. Con REQUIRE_PG=1 un
# test `pg` que se salte falla, así que esta pasada nunca queda en verde sin haberlos ejecutado.
echo "== Backend: tests con PostgreSQL"
if ! docker info >/dev/null 2>&1; then
  echo "Docker no responde. Arranca el daemon (en local, 'colima start') y vuelve a ejecutar el gate." >&2
  exit 1
fi
docker compose up -d --wait postgres >/dev/null
docker compose exec -T postgres sh -c \
  'psql -U speech -d speech_analytics -tAc "SELECT 1 FROM pg_database WHERE datname = '"'"'speech_analytics_test'"'"'" | grep -q 1 || createdb -U speech speech_analytics_test'
if [ -z "${TEST_DATABASE_URL:-}" ]; then
  database_url=$(sed -n 's/^DATABASE_URL=//p' .env | tail -1)
  if [ -z "$database_url" ]; then
    echo "Falta DATABASE_URL en el .env de la raíz (ver .env.example)." >&2
    exit 1
  fi
  TEST_DATABASE_URL="${database_url%/*}/speech_analytics_test"
  unset database_url
fi
(cd backend && TEST_DATABASE_URL="$TEST_DATABASE_URL" REQUIRE_PG=1 .venv/bin/pytest -q -m pg)

echo "== OpenAPI: al día y válido"
backend/.venv/bin/python scripts/export_openapi.py --check
uvx --from openapi-spec-validator openapi-spec-validator backend/openapi.yaml

echo "== Frontend: tests, lint y build"
(cd frontend && npm test --silent && npm run lint --silent && npm run build --silent)

echo "== Seguridad: dependencias"
(cd frontend && npm audit --audit-level=high)
backend/.venv/bin/pip freeze > "${TMPDIR:-/tmp}/ci-requirements.txt"
uvx pip-audit -r "${TMPDIR:-/tmp}/ci-requirements.txt" --no-deps --disable-pip --progress-spinner off

echo "CI local: OK"
