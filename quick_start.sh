#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

PY_BIN="${PY_BIN:-$ROOT_DIR/.venv/bin/python}"
OASIS_PY_BIN_DEFAULT="$BACKEND_DIR/.venv311/bin/python"

REFRESH_DEMO=false
REAL_OASIS=false
BOOT_MODE="demo"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --refresh-demo)
      REFRESH_DEMO=true
      shift
      ;;
    --real-oasis)
      REAL_OASIS=true
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
Usage: ./quick_start.sh [--refresh-demo] [--real-oasis] [--mode demo|live]

Options:
  --refresh-demo  Regenerate demo cache before launching servers.
  --real-oasis    Enable native OASIS runtime for backend simulation runs.
  --mode          Frontend bootstrap mode: demo (default) or live.

Environment overrides:
  PY_BIN, BACKEND_HOST, BACKEND_PORT, FRONTEND_HOST, FRONTEND_PORT
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

if [[ "$REFRESH_DEMO" == "true" ]]; then
  echo "[demo] Regenerating demo cache..."
  DEMO_ENV=("PYTHONPATH=src")

  if [[ "$REAL_OASIS" == "true" ]]; then
    OASIS_PY_BIN="${OASIS_PY_BIN:-$OASIS_PY_BIN_DEFAULT}"
    if [[ ! -x "$OASIS_PY_BIN" ]]; then
      echo "Requested --real-oasis but OASIS_PY_BIN was not found: $OASIS_PY_BIN"
      echo "Create backend/.venv311 and install camel-oasis, or set OASIS_PY_BIN explicitly."
      exit 1
    fi
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

BACKEND_ENV=("PYTHONPATH=src")
if [[ "$REAL_OASIS" == "true" ]]; then
  OASIS_PY_BIN="${OASIS_PY_BIN:-$OASIS_PY_BIN_DEFAULT}"
  if [[ ! -x "$OASIS_PY_BIN" ]]; then
    echo "Requested --real-oasis but OASIS_PY_BIN was not found: $OASIS_PY_BIN"
    exit 1
  fi
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

cleanup() {
  if kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

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
