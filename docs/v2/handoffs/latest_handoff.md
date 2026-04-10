# McKAInsey V2 - Latest Handoff

> Date: 2026-04-11  
> Branch: `feat/phase1-3-impl`  
> Worktree: `/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/.worktrees/phase1-3-impl`  
> Canonical spec: `docs/v2/ImplementationPlan.md`

## 1) Rules For Continuation

- Treat `docs/v2/ImplementationPlan.md` as the source of truth.
- Do not mark any checklist item complete without direct evidence from a command/test/run.
- User requirement remains: push to `origin/main` as new baseline first, then finish remaining Phase 1-3 tasks.
- Never commit `.env` or any real secrets.

## 2) Branch and Git State Right Now

- Current branch: `feat/phase1-3-impl`
- Current HEAD: `4d90f3b4182874f3c5f68b054133be87d9f8cf3e`
- Divergence vs `origin/main`: `0 behind`, `12 ahead`
- Important: all current work is still uncommitted.

Exact current `git status --short`:

```text
M .env.example
M .github/workflows/ci.yml
M README.md
M backend/.env.example
M backend/Dockerfile
M backend/README.md
D backend/scripts/generate_comprehensive_demo_cache.py
M backend/scripts/generate_demo_cache.py
M backend/scripts/oasis_server.py
D backend/scripts/prepare_demo_cache.py
M backend/src/mckainsey/config.py
M backend/src/mckainsey/models/console.py
M backend/src/mckainsey/services/console_service.py
M backend/src/mckainsey/services/demo_service.py
M backend/src/mckainsey/services/model_provider_service.py
M backend/src/mckainsey/services/persona_relevance_service.py
M backend/src/mckainsey/services/report_service.py
M backend/src/mckainsey/services/simulation_service.py
M docker-compose.yml
M docs/v2/ImplementationPlan.md
M docs/v2/handoffs/latest_handoff.md
D frontend/.env.example
M frontend/eslint.config.js
M frontend/src/lib/console-api.test.ts
M frontend/src/lib/console-api.ts
M frontend/src/pages/AgentConfig.test.tsx
M frontend/src/pages/AgentConfig.tsx
M frontend/src/pages/Analytics.tsx
M frontend/src/pages/PolicyUpload.tsx
M frontend/src/pages/ReportChat.test.tsx
M frontend/src/pages/ReportChat.tsx
M frontend/src/pages/Simulation.test.tsx
M frontend/src/pages/Simulation.tsx
M frontend/vite.config.ts
M quick_start.sh
?? .github/workflows/pages.yml
?? backend/Sample_Inputs/
?? backend/tests/services/test_model_provider_service.py
?? backend/tests/services/test_simulation_service.py
?? docs/v2/tasks/
?? tmp/openrouter_poll_and_report.py
?? tmp/openrouter_post_knowledge_check.py
?? tmp/openrouter_smoke_check.py
```

## 3) What Was Implemented (Rolled Up)

### 3.1 Frontend / Demo-Static / Pages

- `demo-static` mode support completed in `frontend/src/lib/console-api.ts` and wired across pages.
- Shared bundled-data loader path used instead of ad-hoc `/demo-output.json` fetches.
- `Simulation.tsx` hydrates bundled simulation state in `demo-static` mode instead of relying on SSE.
- Regression fix in `ensureDemoSessionConfig()` to avoid undefined patch values clobbering bundled metadata.
- Added GitHub Pages base-path support via `VITE_PUBLIC_BASE` in `frontend/vite.config.ts`.
- Added `.github/workflows/pages.yml` for Pages build/deploy pipeline.
- Updated/expanded frontend tests for `demo-static` and live-mode assumptions.

### 3.2 Backend / Runtime / Provider Wiring

- Provider-aware model/defaults work expanded in backend config and model-provider service.
- OASIS/simulation related updates made in runtime and service layers (`oasis_server.py`, `simulation_service.py`, related models/services).
- Added backend service tests for model provider and simulation paths (`backend/tests/services/*.py`).

### 3.3 Release Hygiene and Risk Fixes

- Removed client-side API key injection from `frontend/vite.config.ts` (no secret should be injected into the browser bundle).
- Deleted stale tracked scripts not used in current flow:
  - `backend/scripts/generate_comprehensive_demo_cache.py`
  - `backend/scripts/prepare_demo_cache.py`
- Deleted stale tracked `frontend/.env.example`.
- Updated docs and local-run guidance (`README.md`, `.env.example`, `quick_start.sh`, backend docs).

### 3.4 Plan/Checklist Edits

- `docs/v2/ImplementationPlan.md` was updated during this workstream to mark only evidence-backed items complete at the time.
- Some Phase 1/2/3 items remain intentionally unchecked pending live E2E verification.

## 4) What Was Tested

### 4.1 Previously completed in this worktree

Frontend:

- `cd frontend && npm run test -- --run src/lib/console-api.test.ts`
- `cd frontend && npm run build`
- `cd frontend && VITE_BOOT_MODE=demo-static VITE_PUBLIC_BASE=/Nemotron_AI_Consultant/ npm run build`
- `cd frontend && npm run lint`
- `cd frontend && npm run test -- --run`

Observed:

- Frontend tests passed (`10` files, `65` tests at that run).
- Both normal and Pages-style demo-static builds succeeded.
- Lint exited `0` (warnings only).

Backend:

- `cd backend && python -m ruff check src`
- `cd backend && python -m pytest -q tests`
- `bash -n quick_start.sh`

Observed:

- Ruff passed.
- Backend tests passed (`11 passed` at that run).
- Shell syntax check passed.

Docker smoke:

- `cp .env.example .env`
- `docker compose up --build -d`
- `curl -fsS http://127.0.0.1:8000/health`
- `curl -fsS -I http://127.0.0.1:5173/`
- `docker compose ps`
- `docker compose down -v`

Observed:

- Backend healthy on `8000`
- Frontend `200 OK` on `5173`
- OASIS sidecar healthy on `8001`

### 4.2 Additional checks completed after that

- Verified source launcher booted in live mode with OpenRouter env mapping, then stopped cleanly.
- Verified the local env key alias issue: local env uses `OpenRouter_API_Key`; runtime expects `OPENROUTER_API_KEY`/`openrouter_api_key`.
- Verified no leftover listeners on `8010`, `5180`, `8000`, `5173` at handoff time.
- Verified Playwright CLI is present at `/opt/homebrew/bin/playwright-cli`.

### 4.3 What is not yet verified

- Full source-mode OpenRouter E2E API flow has not been completed to successful simulation+report+chat.
- Full live simulation through OASIS sidecar (not just health checks) is still not proven.
- No final post-change full regression rerun has been recorded after the latest backend/runtime file set.

## 5) Where Work Is Stuck / Risks

- Push-first requirement is not completed yet. Nothing has been committed/pushed from current diff set.
- OpenRouter live E2E is incomplete; key alias mapping must be exported before run.
- Current worktree has multiple untracked helper/temp files under `tmp/` and `docs/v2/tasks/`; decide whether to keep or drop before commit.
- Real secrets exist in local `.env`; must not be committed and should be rotated before any public release.

## 6) Exact Next Steps For Next Agent

1. Finish source-mode OpenRouter smoke end-to-end.

```bash
cd /Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/.worktrees/phase1-3-impl
rm -f .env && \
set -a && source /Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/.env && set +a && \
export OPENROUTER_API_KEY="${OpenRouter_API_Key:-${OPENROUTER_API_KEY:-}}" && \
export LLM_PROVIDER=openrouter && \
export LLM_MODEL='meta-llama/llama-3.1-8b-instruct:free' && \
export LLM_EMBED_MODEL='openai/text-embedding-3-small' && \
export LLM_BASE_URL='https://openrouter.ai/api/v1/' && \
export PY_BIN='/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/.venv/bin/python' && \
export OASIS_PY_BIN='/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/backend/.venv311/bin/python' && \
export BACKEND_PORT=8010 && \
export FRONTEND_PORT=5180 && \
./quick_start.sh --mode live
```

2. In another shell, run minimal live API flow:

```bash
curl -sS -X POST http://127.0.0.1:8010/api/v2/console/session \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "smoke-openrouter-live",
    "mode": "live",
    "model_provider": "openrouter",
    "model_name": "meta-llama/llama-3.1-8b-instruct:free",
    "embed_model_name": "openai/text-embedding-3-small"
  }'

curl -sS -X POST http://127.0.0.1:8010/api/v2/console/session/smoke-openrouter-live/knowledge/process \
  -H 'Content-Type: application/json' \
  -d '{"use_default_demo_document": true}'

curl -sS -X POST http://127.0.0.1:8010/api/v2/console/session/smoke-openrouter-live/sampling/preview \
  -H 'Content-Type: application/json' \
  -d '{"agent_count": 2, "sample_mode": "affected_groups"}'

curl -sS -X POST http://127.0.0.1:8010/api/v2/console/session/smoke-openrouter-live/simulate \
  -H 'Content-Type: application/json' \
  -d '{"rounds": 1, "mode": "live"}'

curl -sS -X POST http://127.0.0.1:8010/api/v2/console/session/smoke-openrouter-live/report/generate

curl -sS -X POST http://127.0.0.1:8010/api/v2/console/session/smoke-openrouter-live/interaction-hub/report-chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is the main public risk in this simulation?"}'
```

3. If simulation is long, monitor stream:

```bash
curl -N http://127.0.0.1:8010/api/v2/console/session/smoke-openrouter-live/simulation/stream
```

4. Update `docs/v2/ImplementationPlan.md` only for newly proven items.

5. Resolve commit scope (include/exclude `tmp/`, `docs/v2/tasks/`, `backend/Sample_Inputs/`) and commit logically.

6. Complete push-first requirement:

- Commit branch changes.
- Merge/fast-forward to `main`.
- Push `main` to `origin`.

7. Finish remaining Phase 2/3 publish tasks:

- Secret rotation and leakage audit.
- GitHub Pages deployment verification (`gh-pages` branch/site reachable).
- Version tag (`v2.0.0`) after all checks pass.

## 7) Checklist Guidance

- User-approved rule: for OpenRouter free-model runs, rate-limit failures are acceptable evidence of provider reachability and may be treated as non-blocking; non-rate-limit endpoint/model misconfiguration should be fixed.
- Keep unchecked anything that is not directly validated by logs/command output.

## 8) Hygiene Notes At Handoff Time

- No source-mode app process is currently running.
- No temporary `.env` was left in worktree root from smoke runs.
- This file is the current handoff baseline for the next agent.
