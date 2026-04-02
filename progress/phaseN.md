# Phase N — Provider-Aware Model Selector & Runtime Routing — Incomplete

**Date:** 2026-03-31

## Summary

Phase N introduces a production-grade provider/model selection flow across frontend and backend so each console session can run on Google, OpenAI, OpenRouter, or Ollama. The phase is currently marked INCOMPLETE because provider-specific runtime constraints were discovered during live validation:

- Ollama (qwen3:4b-instruct-2507-q4_K_M) is available and selectable, but local LightRAG extraction can stall or exceed practical latency on this machine.
- OpenAI provider wiring is functional, but the configured key currently returns `insufficient_quota` (HTTP 429) during live extraction.

Google provider completed end-to-end Screen 1 extraction successfully with live output.

## Implemented Changes

- Frontend settings UX
  - Added bottom-left `Settings` action in the sidebar.
  - Added centered settings modal with:
    - Provider selector (`Google`, `OpenRouter`, `OpenAI`, `Ollama`)
    - Model selector (provider-scoped model list)
    - API key input
  - Added save flow for both:
    - pre-session defaults
    - in-session model updates

- Frontend API client (`frontend/src/lib/console-api.ts`)
  - Added provider/model/session-model APIs:
    - `GET /api/v2/console/model/providers`
    - `GET /api/v2/console/model/providers/{provider}/models`
    - `GET /api/v2/console/session/{id}/model`
    - `PUT /api/v2/console/session/{id}/model`
  - Extended session creation to accept provider/model/api-key/base-url.

- Frontend app state
  - Added shared model config state in `AppContext`:
    - provider, model, embed model, api key, base URL.
  - Screen 1 session creation now passes selected model config to backend.

- Backend provider routing
  - Added provider-aware model resolver/service (`model_provider_service.py`).
  - Added session-persisted model config fields in storage schema and migrations.
  - Added provider/model/session-model contracts and routes.
  - Updated core services to resolve runtime settings per session.

- Runtime strictness (no placeholder response paths)
  - Removed deterministic fallback text branches in LLM-facing report/memory/persona flows.
  - Enforced model-backed responses for key chat/recommendation paths.

- Quick start defaults
  - `./quick_start.sh --mode live` now defaults to Ollama provider/model:
    - chat model: `qwen3:4b-instruct-2507-q4_K_M`
    - embed model: `nomic-embed-text`
  - Added Ollama preflight/pull checks on live start.

- LightRAG robustness fixes
  - Isolated LightRAG storage by session/provider/embed-model to avoid embedding-dimension collisions.
  - Added Ollama model-name normalization (`name` vs `name:latest`) in availability checks.
  - Added embedding payload truncation before embedding API calls.
  - Added lightweight Ollama ingestion profile for Screen 1:
    - document truncation for ingestion and fallback extraction paths
    - compact fallback graph-extraction prompt guidance
    - reduced summary/demographic query modes for local runtime stability.

- Screen 1 error transparency
  - Added provider/model-aware backend error wrapping for knowledge extraction failures.
  - Frontend Screen 1 now preserves backend `detail` messages and replaces generic network failures with actionable runtime guidance.

## Validation Performed

- Backend regression tests:
  - `tests/test_console_routes.py`
  - `tests/test_llm_client.py`
  - `tests/test_memory_service.py`
  - `tests/test_lightrag_service.py`
  - Result: all passing.

- Frontend build:
  - `npm run build`
  - Result: successful build.

- Live browser validation (Screen 1):
  - Google provider: successful extraction and graph output.
  - OpenAI provider: settings update works; extraction fails with `insufficient_quota` (429).
  - Ollama provider: settings update works; extraction path is currently latency-constrained on local runtime.

## Pending Work

1. Re-run full three-provider Screen 1 live extraction once:
   - OpenAI quota is available,
   - Ollama local throughput is acceptable.

Status: INCOMPLETE — core architecture is implemented, with provider runtime constraints still to be resolved for full three-provider live success on this machine.

---

## Phase N Addendum — Screen 3 OASIS Runtime Stabilization

**Date:** 2026-04-02

### Scope Implemented

Implemented the requested Screen 3 stabilization set (Options 2, 1, 3, 4), explicitly excluding checkpoint-progress UX, plus the Screen 2 low-agent slider behavior.

- Option 2: provider-aware round filtering semantics (activity-aware thread visibility in Screen 3 feed).
- Option 1: provider-aware OASIS runtime controls (timeout/semaphore tuning with stronger Ollama headroom).
- Option 3: checkpoint prompt and batch optimizations (compact context bundle, shared digest, provider-aware batch sizing).
- Option 4: provider-aware runtime estimate recalibration in backend and frontend.
- Screen 2 UX/runtime behavior:
  - slider now starts at `0` with step `2`.
  - request payload clamps runtime minimum to `2` agents.

### Key File Updates

- Backend:
  - `backend/src/mckainsey/config.py`
  - `backend/src/mckainsey/services/simulation_service.py`
  - `backend/src/mckainsey/services/console_service.py`
  - `backend/scripts/oasis_reddit_runner.py`
  - `backend/tests/test_simulation_service.py`
- Frontend:
  - `frontend/src/pages/Simulation.tsx`
  - `frontend/src/pages/AgentConfig.tsx`
  - `frontend/src/pages/AgentConfig.test.tsx`
  - `frontend/src/contexts/AppContext.tsx`

### Validation Results

- Backend targeted tests:
  - `cd backend && /Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/.venv/bin/python -m pytest -q tests/test_simulation_service.py tests/test_console_routes.py`
  - Result: `18 passed`

- Frontend targeted tests:
  - `cd frontend && npm run test -- src/pages/AgentConfig.test.tsx src/pages/Simulation.test.tsx`
  - Result: `2 files passed, 4 tests passed`

- Real Ollama Screen 3 live run (10 agents, 2 rounds, no heuristic fallback path):
  - Session: `session-ollama-proof-1775126659`
  - Result: `completed`
  - `last_round=2`, `planned_rounds=2`
  - `simulation_runtime=oasis`
  - `run_completed_count=1`, `run_failed_count=0`
  - OASIS log: `backend/data/oasis/logs/session-ollama-proof-1775126659-20260402T104541Z.log`
  - Log evidence: contains `completed round 2/2` and `process_exit_code=0`
  - Heuristic/fallback check: state payload did not contain heuristic marker

### Runtime Environment Note

During the first live attempt, the process failed because `OASIS_PYTHON_BIN` resolved to an interpreter missing CAMEL/OASIS dependencies (`ModuleNotFoundError: No module named 'camel'`).

Successful rerun used:

- `OASIS_PYTHON_BIN=/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/backend/.venv311/bin/python`

This should be the default for repeatable local live Screen 3 validation on this machine.
