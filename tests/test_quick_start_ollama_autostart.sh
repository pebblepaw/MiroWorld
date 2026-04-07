#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FAKE_BIN="$TMP_DIR/bin"
mkdir -p "$FAKE_BIN" "$ROOT_DIR/frontend/node_modules" "$ROOT_DIR/backend/log"

cat >"$FAKE_BIN/ollama" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="${TMP_DIR:?}"

if [[ "${1:-}" == "serve" ]]; then
  touch "$TMP_DIR/ollama_serve_called"
  echo "$$" >"$TMP_DIR/ollama.pid"
  touch "$TMP_DIR/ollama_ready"
  while true; do
    sleep 1
  done
fi

exit 0
EOF

cat >"$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="${TMP_DIR:?}"
url="${*: -1}"

if [[ "$url" == *":8000/health" ]]; then
  [[ -f "$TMP_DIR/backend_ready" ]]
  exit $?
fi

if [[ "$url" == *":11434"* ]]; then
  [[ -f "$TMP_DIR/ollama_ready" ]]
  exit $?
fi

exit 1
EOF

cat >"$FAKE_BIN/lsof" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF

cat >"$FAKE_BIN/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "install" ]]; then
  exit 0
fi

exit 0
EOF

cat >"$TMP_DIR/fake-python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="${TMP_DIR:?}"

if [[ "${1:-}" == "-m" && "${2:-}" == "uvicorn" ]]; then
  touch "$TMP_DIR/backend_ready"
  while true; do
    sleep 1
  done
fi

if [[ "${1:-}" == "-u" && "${2:-}" == "scripts/check_oasis_runtime.py" ]]; then
  exit 0
fi

exit 0
EOF

chmod +x "$FAKE_BIN/ollama" "$FAKE_BIN/curl" "$FAKE_BIN/lsof" "$FAKE_BIN/npm" "$TMP_DIR/fake-python"

TMP_DIR="$TMP_DIR" \
PATH="$FAKE_BIN:$PATH" \
PY_BIN="$TMP_DIR/fake-python" \
OASIS_PY_BIN="$TMP_DIR/fake-python" \
LLM_PROVIDER=ollama \
bash "$ROOT_DIR/quick_start.sh" --mode live >/dev/null 2>&1 &
launcher_pid=$!
sleep 6
kill "$launcher_pid" >/dev/null 2>&1 || true
wait "$launcher_pid" >/dev/null 2>&1 || true

if [[ ! -f "$TMP_DIR/ollama_serve_called" ]]; then
  echo "[FAIL] quick_start.sh did not start ollama serve when the server was unreachable" >&2
  exit 1
fi

echo "[PASS] quick_start.sh started ollama serve opportunistically"
