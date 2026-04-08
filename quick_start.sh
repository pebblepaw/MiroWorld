#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

LLM_PROVIDER_DEFAULT="${LLM_PROVIDER:-ollama}"
LLM_MODEL_DEFAULT="${LLM_MODEL:-qwen3:4b-instruct-2507-q4_K_M}"
LLM_EMBED_MODEL_DEFAULT="${LLM_EMBED_MODEL:-nomic-embed-text}"
LLM_BASE_URL_DEFAULT="${LLM_BASE_URL:-http://127.0.0.1:11434/v1/}"

PY_BIN="${PY_BIN:-$ROOT_DIR/.venv/bin/python}"
OASIS_PY_BIN_DEFAULT="$BACKEND_DIR/.venv311/bin/python"
OLLAMA_LOG="$BACKEND_DIR/log/quick_start_ollama.log"
OLLAMA_PID=""
OLLAMA_REACHABILITY_URL="${LLM_BASE_URL_DEFAULT%/}"
OLLAMA_REACHABILITY_URL="${OLLAMA_REACHABILITY_URL%/v1}"
OLLAMA_REACHABILITY_URL="$OLLAMA_REACHABILITY_URL/api/tags"
FALKORDB_HOST_DEFAULT="${FALKORDB_HOST:-127.0.0.1}"
FALKORDB_PORT_DEFAULT="${FALKORDB_PORT:-6379}"

REFRESH_DEMO=false
LIVE_OASIS=false
BOOT_MODE="demo"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --refresh-demo)
      REFRESH_DEMO=true
      shift
      ;;
    --mode=*)
      BOOT_MODE="${1#*=}"
      shift
      ;;
    --mode)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --mode. Use: --mode demo|live"
        exit 1
      fi
      BOOT_MODE="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: ./quick_start.sh [--refresh-demo] [--mode demo|live]

Options:
  --refresh-demo  Regenerate demo cache before launching servers.
  --mode          Frontend bootstrap mode: demo (default) or live.

Environment overrides:
  PY_BIN, OASIS_PY_BIN, BACKEND_HOST, BACKEND_PORT, FRONTEND_HOST, FRONTEND_PORT
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use --help for usage."
      exit 1
      ;;
  esac
done

case "$BOOT_MODE" in
  demo|live)
    ;;
  *)
    echo "Invalid --mode value: $BOOT_MODE"
    echo "Valid values: demo, live"
    exit 1
    ;;
esac

if [[ "$BOOT_MODE" == "live" ]]; then
  LIVE_OASIS=true
fi

if [[ ! -x "$PY_BIN" ]]; then
  echo "Python executable not found at: $PY_BIN"
  echo "Create the project venv first, e.g. python3 -m venv .venv and install dependencies."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required but not found in PATH."
  exit 1
fi

if lsof -iTCP:"$BACKEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Backend port $BACKEND_PORT is already in use. Stop that process and retry."
  exit 1
fi

if lsof -iTCP:"$FRONTEND_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Frontend port $FRONTEND_PORT is already in use. Stop that process and retry."
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "[setup] Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

ensure_ollama_model() {
  local model_name="$1"
  if ollama list | awk 'NR>1 {print $1}' | grep -Fxq "$model_name"; then
    return 0
  fi
  echo "[ollama] Pulling missing model: $model_name"
  ollama pull "$model_name" >/dev/null
}

ensure_oasis_runtime() {
  OASIS_PY_BIN="${OASIS_PY_BIN:-$OASIS_PY_BIN_DEFAULT}"

  if [[ ! -x "$OASIS_PY_BIN" ]]; then
    if [[ "$OASIS_PY_BIN" != "$OASIS_PY_BIN_DEFAULT" ]]; then
      echo "Configured OASIS_PY_BIN is not executable: $OASIS_PY_BIN"
      echo "Point OASIS_PY_BIN to a Python 3.11 interpreter with camel-oasis installed."
      exit 1
    fi
    if ! command -v python3.11 >/dev/null 2>&1; then
      echo "Live mode needs Python 3.11 for camel-oasis, but python3.11 was not found."
      echo "Install Python 3.11 and re-run: ./quick_start.sh --mode live"
      echo "Or set OASIS_PY_BIN to an existing Python 3.11 interpreter."
      exit 1
    fi
    echo "[oasis] Creating Python 3.11 sidecar venv at $BACKEND_DIR/.venv311 ..."
    python3.11 -m venv "$BACKEND_DIR/.venv311"
  fi

  if ! "$OASIS_PY_BIN" "$BACKEND_DIR/scripts/check_oasis_runtime.py" >/tmp/mckainsey_oasis_runtime_check.log 2>&1; then
    echo "[oasis] Runtime validation failed. Installing pinned OASIS dependencies..."
    "$OASIS_PY_BIN" -m pip install -U pip
    "$OASIS_PY_BIN" -m pip install -r "$BACKEND_DIR/requirements-oasis-runtime.txt"
    "$OASIS_PY_BIN" "$BACKEND_DIR/scripts/check_oasis_runtime.py" >/tmp/mckainsey_oasis_runtime_check.log 2>&1 || {
      echo "OASIS runtime is still invalid after installing pinned dependencies."
      cat /tmp/mckainsey_oasis_runtime_check.log
      exit 1
    }
  fi
}

ollama_server_reachable() {
  curl -sf "$OLLAMA_REACHABILITY_URL" >/dev/null 2>&1
}

start_ollama_server_if_needed() {
  local normalized_provider
  normalized_provider="$(printf '%s' "$LLM_PROVIDER_DEFAULT" | tr '[:upper:]' '[:lower:]')"

  if [[ "$normalized_provider" != "ollama" ]]; then
    return 0
  fi

  if ollama_server_reachable; then
    echo "[ollama] Local server is already reachable."
    return 0
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    echo "[ollama] CLI not found; continuing without local Ollama auto-start."
    return 0
  fi

  echo "[ollama] Starting local server in the background..."
  ollama serve > "$OLLAMA_LOG" 2>&1 &
  OLLAMA_PID=$!

  for _ in {1..30}; do
    if ollama_server_reachable; then
      echo "[ollama] Local server is ready."
      return 0
    fi

    if ! kill -0 "$OLLAMA_PID" >/dev/null 2>&1; then
      echo "[ollama] Server exited before becoming reachable. See log: $OLLAMA_LOG"
      return 0
    fi

    sleep 1
  done

  echo "[ollama] Server is still starting in the background."
}

falkordb_reachable() {
  if command -v nc >/dev/null 2>&1; then
    nc -z "$FALKORDB_HOST_DEFAULT" "$FALKORDB_PORT_DEFAULT" >/dev/null 2>&1
    return $?
  fi

  FALKORDB_HOST_DEFAULT="$FALKORDB_HOST_DEFAULT" FALKORDB_PORT_DEFAULT="$FALKORDB_PORT_DEFAULT" "$PY_BIN" - <<'PY' >/dev/null 2>&1
import os
import socket

host = os.environ.get("FALKORDB_HOST_DEFAULT", "127.0.0.1")
port = int(os.environ.get("FALKORDB_PORT_DEFAULT", "6379"))
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(1.0)
try:
    sock.connect((host, port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
}

ensure_falkordb_runtime() {
  if falkordb_reachable; then
    echo "[graphiti] FalkorDB is reachable at $FALKORDB_HOST_DEFAULT:$FALKORDB_PORT_DEFAULT."
    return 0
  fi

  if [[ "$FALKORDB_HOST_DEFAULT" != "127.0.0.1" && "$FALKORDB_HOST_DEFAULT" != "localhost" ]]; then
    echo "Live mode requires FalkorDB, but $FALKORDB_HOST_DEFAULT:$FALKORDB_PORT_DEFAULT is not reachable."
    echo "Start FalkorDB on that host or update FALKORDB_HOST/FALKORDB_PORT before retrying."
    exit 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "Live mode requires FalkorDB, but Docker is not installed."
    echo "Install Docker and re-run ./quick_start.sh --mode live."
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "Live mode requires FalkorDB, but Docker daemon is not running."
    echo "Start Docker Desktop and re-run ./quick_start.sh --mode live."
    exit 1
  fi

  local compose_cmd=()
  if docker compose version >/dev/null 2>&1; then
    compose_cmd=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    compose_cmd=(docker-compose)
  else
    echo "Live mode requires FalkorDB, but Docker Compose is not available."
    exit 1
  fi

  echo "[graphiti] Starting FalkorDB via Docker Compose..."
  (
    cd "$ROOT_DIR"
    "${compose_cmd[@]}" up -d falkordb
  )

  for _ in {1..30}; do
    if falkordb_reachable; then
      echo "[graphiti] FalkorDB is ready at $FALKORDB_HOST_DEFAULT:$FALKORDB_PORT_DEFAULT."
      return 0
    fi
    sleep 1
  done

  echo "FalkorDB did not become reachable at $FALKORDB_HOST_DEFAULT:$FALKORDB_PORT_DEFAULT."
  echo "Check docker-compose logs for the falkordb service and retry."
  exit 1
}

cleanup() {
  if [[ -n "${OLLAMA_PID:-}" ]] && kill -0 "$OLLAMA_PID" >/dev/null 2>&1; then
    kill "$OLLAMA_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

if [[ "$LIVE_OASIS" == "true" ]]; then
  ensure_oasis_runtime
  ensure_falkordb_runtime
fi

if [[ "$REFRESH_DEMO" == "true" ]]; then
  echo "[demo] Regenerating demo cache..."
  DEMO_ENV=("PYTHONPATH=src")

  if [[ "$LIVE_OASIS" == "true" ]]; then
    DEMO_ENV+=("ENABLE_REAL_OASIS=true")
    DEMO_ENV+=("OASIS_PYTHON_BIN=$OASIS_PY_BIN")
    DEMO_ENV+=("OASIS_RUNNER_SCRIPT=$BACKEND_DIR/scripts/oasis_reddit_runner.py")
    DEMO_ENV+=("OASIS_TIMEOUT_SECONDS=1800")
  fi

  (
    cd "$BACKEND_DIR"
    env "${DEMO_ENV[@]}" "$PY_BIN" -u scripts/generate_demo_cache.py --from-stage simulation --skip-knowledge --agent-count 50 --rounds 10
  )
fi

mkdir -p "$BACKEND_DIR/log"
BACKEND_LOG="$BACKEND_DIR/log/quick_start_backend.log"
FRONTEND_LOG="$BACKEND_DIR/log/quick_start_frontend.log"

if [[ "$LIVE_OASIS" == "true" ]]; then
  start_ollama_server_if_needed
fi

BACKEND_ENV=("PYTHONPATH=src")
BACKEND_ENV+=("LLM_PROVIDER=$LLM_PROVIDER_DEFAULT")
BACKEND_ENV+=("LLM_MODEL=$LLM_MODEL_DEFAULT")
BACKEND_ENV+=("LLM_EMBED_MODEL=$LLM_EMBED_MODEL_DEFAULT")
BACKEND_ENV+=("LLM_BASE_URL=$LLM_BASE_URL_DEFAULT")
if [[ "$LIVE_OASIS" == "true" ]]; then
  BACKEND_ENV+=("ENABLE_REAL_OASIS=true")
  BACKEND_ENV+=("OASIS_PYTHON_BIN=$OASIS_PY_BIN")
  BACKEND_ENV+=("OASIS_RUNNER_SCRIPT=$BACKEND_DIR/scripts/oasis_reddit_runner.py")
  BACKEND_ENV+=("OASIS_TIMEOUT_SECONDS=1800")
fi

echo "[backend] Starting API on http://$BACKEND_HOST:$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  env "${BACKEND_ENV[@]}" "$PY_BIN" -m uvicorn mckainsey.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" > "$BACKEND_LOG" 2>&1
) &
BACKEND_PID=$!

for i in {1..60}; do
  if curl -sf "http://$BACKEND_HOST:$BACKEND_PORT/health" >/dev/null 2>&1; then
    echo "[backend] Health check passed."
    break
  fi
  sleep 1
  if [[ "$i" -eq 60 ]]; then
    echo "Backend failed to become healthy. See logs: $BACKEND_LOG"
    exit 1
  fi
done

echo "[frontend] Starting UI on http://$FRONTEND_HOST:$FRONTEND_PORT ..."
(
  cd "$FRONTEND_DIR"
  VITE_API_BASE="http://$BACKEND_HOST:$BACKEND_PORT" VITE_BOOT_MODE="$BOOT_MODE" npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" > "$FRONTEND_LOG" 2>&1
) &
FRONTEND_PID=$!

sleep 2

echo ""
echo "McKAInsey console is up:"
echo "  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "  Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "  Boot mode: $BOOT_MODE"
echo ""
echo "Logs:"
echo "  $BACKEND_LOG"
echo "  $FRONTEND_LOG"
echo ""
echo "Press Ctrl+C to stop both services."

wait "$FRONTEND_PID"
