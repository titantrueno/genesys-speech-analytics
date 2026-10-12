#!/usr/bin/env bash
# Levanta todo el proyecto en local (PostgreSQL en Docker/Colima, servicios de ingesta y de LLM, API y web) y lo para
# entero con Ctrl+C: no deja ningún proceso ni contenedor en marcha. Uso y puertos: ver "Entorno local" en README.md.
#
#   ./scripts/dev.sh              # todo
#   ./scripts/dev.sh --no-db      # solo API + web (sin Docker, PostgreSQL ni ingesta)
#   ./scripts/dev.sh --reload     # uvicorn con --reload (para editar código del backend)
#
# Puertos (cámbialos por entorno si los habituales están ocupados): API_PORT=8000 INGESTION_PORT=8001 LLM_PORT=8002
# WEB_PORT=5173. El servicio de LLM solo arranca si hay LLM_TOKEN (en el entorno o en el .env).
set -uo pipefail
set -m # cada proceso lanzado en segundo plano va en su propio grupo: se para entero, con sus hijos
cd "$(dirname "$0")/.."
ROOT=$PWD

API_PORT=${API_PORT:-8000}
INGESTION_PORT=${INGESTION_PORT:-8001}
LLM_PORT=${LLM_PORT:-8002}
WEB_PORT=${WEB_PORT:-5173}
LOG_DIR=$ROOT/.dev-logs

WITH_DB=1
RELOAD=()
for arg in "$@"; do
  case $arg in
    --no-db) WITH_DB=0 ;;
    --reload) RELOAD=(--reload) ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Opción desconocida: $arg" >&2; exit 2 ;;
  esac
done

PIDS=()          # líder de cada grupo de procesos lanzado
COLIMA_STARTED=0 # solo paramos Colima si lo arrancó este script
DB_STARTED=0
CLEANED=0

# Con `set -m` cada comando en primer plano corre en su propio grupo y el SIGINT del Ctrl+C solo lo recibe él, no este
# script (el trap nunca se ejecutaba). Por eso lo que bloquea se lanza en segundo plano y se espera con el builtin
# `wait`, que sí se interrumpe con las señales del propio script.
espera() { "$@" & wait $!; }
nap() { espera sleep "$1"; }

log() { printf '\033[1;36m[dev]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[dev] %s\033[0m\n' "$*" >&2; exit 1; }

port_owner() { lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1" (PID "$2")"}'; }

cleanup() {
  [ "$CLEANED" = 1 ] && return
  CLEANED=1
  trap '' INT TERM # una segunda pulsación de Ctrl+C no interrumpe la limpieza
  echo
  log "Parando…"
  local pid i
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do kill -TERM -- "-$pid" 2>/dev/null; done
  for i in 1 2 3 4 5 6 7 8 9 10; do # hasta 5 s de gracia
    local alive=0
    for pid in ${PIDS[@]+"${PIDS[@]}"}; do kill -0 -- "-$pid" 2>/dev/null && alive=1; done
    [ "$alive" = 0 ] && break
    nap 0.5
  done
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do kill -KILL -- "-$pid" 2>/dev/null; done
  if [ "$WITH_DB" = 1 ] && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    log "Parando PostgreSQL (el volumen pgdata se conserva)"
    espera docker compose stop postgres >/dev/null 2>&1
    espera docker compose rm -f postgres >/dev/null 2>&1
  fi
  if [ "$COLIMA_STARTED" = 1 ]; then
    log "Parando Colima (lo arrancó este script)"
    espera colima stop >/dev/null 2>&1
  fi
  local leftover=""
  for p in $API_PORT $INGESTION_PORT $LLM_PORT $WEB_PORT; do
    [ -n "$(port_owner "$p")" ] && leftover="$leftover $p"
  done
  if [ -n "$leftover" ]; then log "Aviso: siguen ocupados los puertos:$leftover"; else log "Todo parado."; fi
}
trap 'cleanup; exit 130' INT TERM
trap cleanup EXIT

wait_http() { # url, nombre, pid: espera a que el servidor responda a HTTP (cualquier código)
  local i
  for i in $(seq 1 120); do
    espera curl -s -o /dev/null --max-time 2 "$1" && return 0
    kill -0 -- "-$3" 2>/dev/null || { tail -n 20 "$LOG_DIR/$2.log" >&2; die "$2 terminó al arrancar (log: .dev-logs/$2.log)"; }
    nap 0.5
  done
  die "$2 no responde en $1 (log: .dev-logs/$2.log)"
}

start() { # nombre, directorio, comando…: lanza en segundo plano con log propio
  local name=$1 dir=$2
  shift 2
  # Sin stdin del terminal: con `set -m` cada servicio es un grupo en segundo plano y, si lee del tty (Vite lee atajos
  # de teclado), recibe SIGTTIN y queda detenido; un proceso detenido no atiende SIGTERM y el script espera al SIGKILL.
  (cd "$dir" && exec "$@") </dev/null >"$LOG_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
}

# --- Comprobaciones previas: nada se lanza si algo no está en orden -------------------------------------------------
# El servicio de LLM (FE013) necesita su token; sin él, la plataforma funciona con el proveedor simulado.
WITH_LLM=0
{ [ -n "${LLM_TOKEN:-}" ] || grep -qE '^LLM_TOKEN=.+' .env 2>/dev/null; } && WITH_LLM=1
ports="$API_PORT $WEB_PORT"
[ "$WITH_DB" = 1 ] && ports="$ports $INGESTION_PORT"
[ "$WITH_LLM" = 1 ] && ports="$ports $LLM_PORT"
for p in $ports; do
  owner=$(port_owner "$p")
  [ -z "$owner" ] || die "El puerto $p ya está ocupado por $owner. Páralo o usa otro (API_PORT / INGESTION_PORT / LLM_PORT / WEB_PORT)."
done

mkdir -p "$LOG_DIR"
if [ ! -x backend/.venv/bin/uvicorn ]; then
  log "Creando el entorno virtual del backend"
  python3 -m venv backend/.venv && backend/.venv/bin/pip install -q -r backend/requirements.txt || die "No se pudo instalar el backend"
fi
if [ ! -d frontend/node_modules ]; then
  log "Instalando dependencias del frontend"
  (cd frontend && npm install --silent) || die "No se pudo instalar el frontend"
fi

if [ "$WITH_DB" = 1 ]; then
  [ -f .env ] || die "Falta el .env de la raíz (copia .env.example y rellénalo)."
  command -v docker >/dev/null 2>&1 || die "Falta el CLI de Docker."
  if ! docker info >/dev/null 2>&1; then
    command -v colima >/dev/null 2>&1 || die "Docker no responde y no hay Colima instalado."
    log "Arrancando Colima"
    colima start || die "colima start ha fallado"
    COLIMA_STARTED=1
  fi
  if [ -z "$(docker compose ps -q postgres 2>/dev/null)" ]; then
    owner=$(port_owner 5432)
    [ -z "$owner" ] || die "El puerto 5432 ya está ocupado por $owner (¿un túnel ssh u otro PostgreSQL?). Páralo o usa --no-db."
  fi
  log "Arrancando PostgreSQL"
  DB_STARTED=1
  docker compose up -d --wait postgres || die "PostgreSQL no llegó a estar sano"
fi

# --- Servicios -------------------------------------------------------------------------------------------------------
if [ "$WITH_DB" = 1 ]; then
  log "Servicio de ingesta en :$INGESTION_PORT"
  start ingestion "$ROOT/backend" .venv/bin/uvicorn ingestion.main:app --port "$INGESTION_PORT" ${RELOAD[@]+"${RELOAD[@]}"}
  wait_http "http://localhost:$INGESTION_PORT/health" ingestion "${PIDS[${#PIDS[@]}-1]}"
fi

if [ "$WITH_LLM" = 1 ]; then
  log "Servicio de LLM en :$LLM_PORT"
  start llm "$ROOT/backend" .venv/bin/uvicorn llm.main:app --port "$LLM_PORT" ${RELOAD[@]+"${RELOAD[@]}"}
  wait_http "http://localhost:$LLM_PORT/health" llm "${PIDS[${#PIDS[@]}-1]}"
else
  log "Servicio de LLM desactivado: falta LLM_TOKEN en el .env (ver .env.example)"
fi

log "API en :$API_PORT"
INGESTION_URL="http://localhost:$INGESTION_PORT" LLM_URL="http://localhost:$LLM_PORT" CORS_ORIGINS="http://localhost:$WEB_PORT,http://127.0.0.1:$WEB_PORT" \
  start api "$ROOT/backend" .venv/bin/uvicorn app.main:app --port "$API_PORT" ${RELOAD[@]+"${RELOAD[@]}"}
wait_http "http://localhost:$API_PORT/openapi.json" api "${PIDS[${#PIDS[@]}-1]}"

log "Web en :$WEB_PORT"
API_PROXY_TARGET="http://localhost:$API_PORT" \
  start web "$ROOT/frontend" node_modules/.bin/vite --port "$WEB_PORT" --strictPort
wait_http "http://localhost:$WEB_PORT/" web "${PIDS[${#PIDS[@]}-1]}"

cat <<MSG

  Web:        http://localhost:$WEB_PORT   (usuarios demo, contraseña «demo»)
  API:        http://localhost:$API_PORT/docs
  Ingesta:    $([ "$WITH_DB" = 1 ] && echo "http://localhost:$INGESTION_PORT/docs" || echo "desactivada (--no-db)")
  LLM:        $([ "$WITH_LLM" = 1 ] && echo "http://localhost:$LLM_PORT/health" || echo "desactivado (falta LLM_TOKEN)")
  Logs:       .dev-logs/{api,ingestion,llm,web}.log

  Ctrl+C para parar todo.

MSG

# Si cualquiera de los procesos muere, se para el conjunto entero.
while true; do
  for pid in "${PIDS[@]}"; do
    kill -0 -- "-$pid" 2>/dev/null || { log "Un proceso terminó inesperadamente (mira .dev-logs/)."; exit 1; }
  done
  nap 1
done
