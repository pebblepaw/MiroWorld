#!/usr/bin/env bash
set -euo pipefail

SESSION_ID="${1:-session-281324dc}"
DB_PATH="${2:-backend/data/simulation.db}"
OLLAMA_LOG="${3:-backend/data/oasis/logs/session-281324dc-20260401T170440Z.log}"
GEMINI_LOG="${4:-backend/data/oasis/logs/session-281324dc-20260401T173808Z.log}"
MCP_SCREENSHOT="${5:-output/playwright/mcp-click-settings-proof.png}"

fail() {
  echo "[FAIL] $1" >&2
  exit 1
}

pass() {
  echo "[PASS] $1"
}

[ -f "$DB_PATH" ] || fail "Simulation DB not found: $DB_PATH"
[ -f "$OLLAMA_LOG" ] || fail "Ollama OASIS log not found: $OLLAMA_LOG"
[ -f "$GEMINI_LOG" ] || fail "Gemini OASIS log not found: $GEMINI_LOG"

if [ -f "$MCP_SCREENSHOT" ]; then
  pass "MCP Playwright screenshot exists: $MCP_SCREENSHOT"
else
  echo "[WARN] MCP Playwright screenshot missing: $MCP_SCREENSHOT"
fi

grep -q "provider=ollama" "$OLLAMA_LOG" || fail "Ollama provider header missing in log"
grep -q "completed round 1/1" "$OLLAMA_LOG" || fail "Ollama round completion missing"
grep -q "process_exit_code=0" "$OLLAMA_LOG" || fail "Ollama process did not exit cleanly"
pass "Ollama OASIS run log shows successful 1-round completion"

grep -q "provider=google" "$GEMINI_LOG" || fail "Gemini provider header missing in log"
grep -q "completed round 1/1" "$GEMINI_LOG" || fail "Gemini round completion missing"
grep -q "process_exit_code=0" "$GEMINI_LOG" || fail "Gemini process did not exit cleanly"
pass "Gemini OASIS run log shows successful 1-round completion"

RUN_COMPLETED_COUNT="$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM simulation_events WHERE session_id='$SESSION_ID' AND event_type='run_completed';")"
[ "${RUN_COMPLETED_COUNT:-0}" -ge 1 ] || fail "No run_completed event found for session $SESSION_ID"
pass "Simulation events contain run_completed for $SESSION_ID"

echo "[PASS] Dual-provider OASIS Screen 3 verification checks passed"
