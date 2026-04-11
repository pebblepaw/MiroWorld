# MiroWorld Backend

FastAPI backend for the MiroWorld V2 workflow: knowledge extraction, population sampling, live OASIS simulation, SQLite-backed memory retrieval, reporting, and analytics.

## Quick Start

1. Create and activate a Python virtual environment.
2. Install dependencies:
   - `pip install -e .[dev]`
3. Configure environment variables:
   - Prefer the canonical repo-root `../.env.example`
4. Run API:
   - `uvicorn miroworld.main:app --reload --port 8000`
5. Run tests:
   - `pytest -q`

## Canonical Runtime Endpoints

- `GET /health`
- `POST /api/v2/session/create`
- `PATCH /api/v2/session/{session_id}/config`
- `POST /api/v2/console/session/{session_id}/scrape`
- `POST /api/v2/console/session/{session_id}/knowledge/process`
- `GET /api/v2/console/session/{session_id}/knowledge/stream`
- `POST /api/v2/console/session/{session_id}/sampling/preview`
- `POST /api/v2/console/session/{session_id}/simulation/start`
- `POST /api/v2/console/session/{session_id}/simulate`
- `GET /api/v2/console/session/{session_id}/simulation/state`
- `GET /api/v2/console/session/{session_id}/simulation/stream`
- `GET /api/v2/console/session/{session_id}/report`
- `POST /api/v2/console/session/{session_id}/report/generate`
- `POST /api/v2/console/session/{session_id}/chat/group`
- `POST /api/v2/console/session/{session_id}/chat/agent/{agent_id}`
- `POST /api/v2/console/session/{session_id}/interaction-hub/report-chat`
- `GET /api/v2/console/session/{session_id}/analytics/polarization`
- `GET /api/v2/console/session/{session_id}/analytics/opinion-flow`
- `GET /api/v2/console/session/{session_id}/analytics/influence`
- `GET /api/v2/console/session/{session_id}/analytics/cascades`

Legacy `/api/v1/phase-*` routes still exist for compatibility and demo-cache generation, but V2 console endpoints are the active contract.

## Runtime Notes

- Live chat memory is grounded from local SQLite FTS5 retrieval over interactions, transcripts, and checkpoints.
- Graphiti, FalkorDB, and Zep are no longer part of the active runtime.
- `quick_start.sh --mode live` launches the FastAPI app plus the Python 3.11 OASIS sidecar flow without Docker dependencies in source mode.

## Real OASIS Runtime (Python 3.11 Sidecar)

The main backend virtualenv can run on Python 3.11 or 3.12, but the native OASIS runtime still needs Python 3.11.

Setup:

1. `cd backend`
2. `python3.11 -m venv .venv311`
3. `.venv311/bin/pip install -U pip`
4. `.venv311/bin/pip install -r requirements-oasis-runtime.txt`

Enable native OASIS for simulation runs:

- Run the repo launcher in live mode: `./quick_start.sh --mode live`
- Configure a provider in the repo-root `.env` (`google`, `openai`, `openrouter`, or `ollama`)

The service executes `backend/scripts/oasis_reddit_runner.py` via the configured Python 3.11 sidecar and stores outputs in the shared SQLite/local-file data directory.

If `.venv311` or OASIS imports are missing, `quick_start.sh --mode live` auto-creates the sidecar and installs pinned runtime dependencies before boot.

## Demo Default Document

The route `POST /api/v1/phase-a/knowledge/process` supports a default demo document.

Example body:

```json
{
  "simulation_id": "demo-ai-strategy-2025",
  "use_default_demo_document": true,
  "demographic_focus": "low-income households and seniors in Woodlands"
}
```

The default markdown file path is configured via `DEMO_DEFAULT_POLICY_MARKDOWN`.

## Validation Scripts

- End-to-end flow: `python scripts/run_e2e.py`
- Benchmarks: `python scripts/benchmark.py`

## Unified Local Launcher

From repo root, use `./quick_start.sh` to start backend and frontend together.

Examples:

- `./quick_start.sh --mode demo`: demo-first boot behavior
- `./quick_start.sh --mode live`: live backend boot with native OASIS
- `./quick_start.sh --refresh-demo --mode demo`: regenerate cached demo artifacts before demo-first boot
