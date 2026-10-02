#!/usr/bin/env bash
# Gate local equivalente a .github/workflows/ci.yml: cualquier fallo devuelve código distinto de 0.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== Vault"
python3 scripts/audit_vault.py

echo "== Backend: tests"
(cd backend && .venv/bin/pytest -q)

# Segunda pasada con otra semilla y otra fecha de referencia (cruza el cambio de hora de octubre): un test que dependa
# del dataset por defecto falla aquí (FE009).
echo "== Backend: tests con otro dataset (semilla 7, referencia 2026-11-10)"
(cd backend && DATA_SEED=7 DATA_REFERENCE_DATE=2026-11-10 .venv/bin/pytest -q)

echo "== Frontend: tests, lint y build"
(cd frontend && npm test --silent && npm run lint --silent && npm run build --silent)

echo "== Seguridad: dependencias"
(cd frontend && npm audit --audit-level=high)
backend/.venv/bin/pip freeze > "${TMPDIR:-/tmp}/ci-requirements.txt"
uvx pip-audit -r "${TMPDIR:-/tmp}/ci-requirements.txt" --no-deps --disable-pip --progress-spinner off

echo "CI local: OK"
