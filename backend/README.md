# McKAInsey Backend

Phase A backend for persona sampling (Mode 1: HuggingFace streaming + DuckDB on HF parquet), LightRAG ingestion/query, and Zep event logging.

## Quick Start

1. Create and activate a Python virtual environment.
2. Install dependencies:
   - `pip install -e .[dev]`
3. Configure environment variables:
   - Copy `.env.example` to `.env` and set values.
4. Run API:
   - `uvicorn mckainsey.main:app --reload --port 8000`
5. Run tests:
   - `pytest -q`

## API Endpoints

- `GET /health`
- `POST /api/v1/phase-a/personas/sample`
- `POST /api/v1/phase-a/knowledge/process`
- `POST /api/v1/phase-b/simulations/run`
- `GET /api/v1/phase-b/simulations/{simulation_id}`
- `POST /api/v1/phase-c/memory/sync`
- `GET /api/v1/phase-c/memory/{simulation_id}/{agent_id}`
- `POST /api/v1/phase-c/chat/agent`
- `GET /api/v1/phase-d/report/{simulation_id}`
- `POST /api/v1/phase-d/report/chat`
- `GET /api/v1/phase-e/dashboard/{simulation_id}`
- `GET /api/v1/phase-e/geo/planning-areas`

## Real OASIS Runtime (Python 3.11 Sidecar)

The backend default venv may run on Python 3.14, while `camel-oasis` requires Python 3.11.

Setup:

1. `cd backend`
2. `python3.11 -m venv .venv311`
3. `.venv311/bin/pip install -U pip camel-oasis`

Enable native OASIS for simulation runs:

- Set `ENABLE_REAL_OASIS=true`
- Ensure `GEMINI_API_KEY` or `GEMINI_API` is set (used as OpenAI-compatible key)

The service will execute `backend/scripts/oasis_reddit_runner.py` via `.venv311/bin/python` and ingest OASIS outputs into the project simulation store.

## Demo Default Document

The route `POST /api/v1/phase-a/knowledge/process` supports a default demo document.

Example body:

```json
{
   "simulation_id": "demo-budget-2026",
   "use_default_demo_document": true,
   "demographic_focus": "low-income households and seniors in Woodlands"
}
```

The default markdown file path is configured via `DEMO_DEFAULT_POLICY_MARKDOWN`.

## Validation Scripts

- End-to-end flow: `python scripts/run_e2e.py`
- Benchmarks: `python scripts/benchmark.py`

## Unified Local Launcher

From repo root, use `./quick_start.sh` to start backend + frontend together.

Examples:

- `./quick_start.sh --mode auto` (default): live dashboard first, then static demo fallback.
- `./quick_start.sh --mode demo`: static demo-first boot behavior.
- `./quick_start.sh --mode live`: live backend-first boot behavior.
- `./quick_start.sh --refresh-demo --real-oasis --mode demo`: regenerate cached demo artifacts with native OASIS and boot demo-first.
