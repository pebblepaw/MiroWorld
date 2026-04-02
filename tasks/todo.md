# Task Plan - Phase N Stabilization

## Goal
Complete the remaining Phase N stabilization work by improving runtime reliability and error transparency for Screen 1 across provider-based model execution.

## Constraints
- Keep provider-aware architecture and session model config behavior intact.
- Do not reintroduce deterministic placeholder fallbacks.
- Prefer minimal-impact edits focused on Stage 1 ingestion and error surfacing.

## Assumptions
- Existing provider/model session routes are already functional.
- Remaining issues are operational: limited OpenAI quota and Ollama local throughput.

## Checklist
- [x] Add backend provider-aware error detail propagation for Screen 1 ingestion failures.
- [x] Add Ollama-oriented lightweight ingestion profile for Stage 1 extraction.
- [x] Update frontend Screen 1 error rendering to display backend detail messages.
- [x] Run targeted backend tests covering console/lightrag flows.
- [x] Build frontend and verify no TypeScript/build regressions.
- [x] Update progress docs with stabilization status and verification evidence.

## Verification Plan
- Backend:
  - `pytest -q backend/tests/test_console_routes.py backend/tests/test_lightrag_service.py`
- Frontend:
  - `npm run build` in `frontend`
- Manual:
  - Trigger Screen 1 failure path and confirm UI shows provider-specific error message text from backend response.

## Verification Results
- Backend:
  - `pytest -q tests/test_console_routes.py tests/test_lightrag_service.py`
  - Result: `16 passed`
- Frontend:
  - `npm run build`
  - Result: successful production build.
- Manual:
  - Screen 1 now reports backend `detail` messages directly when available.
  - Generic network failure text is replaced with provider/model-aware runtime guidance.

## Extended Verification (Autonomous Pass)
- Full backend suite:
  - `cd backend && pytest -q`
  - Result: `48 passed`
- Full frontend suite:
  - `cd frontend && npm run test -- --run`
  - Result: `5 files passed, 10 tests passed`
- Frontend production build:
  - `cd frontend && npm run build`
  - Result: successful build (chunk-size warning only)
- Playwright provider matrix on Screen 1:
  - Ollama default verified in settings (`qwen3:4b-instruct-2507-q4_K_M`) and extraction returned HTTP `200`.
  - Gemini (Google provider, `gemini-2.5-flash-lite`) configured via settings with API key from `.env`; extraction returned HTTP `200`.
  - OpenAI (`gpt-5-mini`) configured via settings with API key from `.env`; extraction returned HTTP `502` with `RateLimitError` (expected quota behavior).
  - Screenshots and artifacts captured under `output/playwright/`.
- Audit step:
  - Requested `gemini/skills/audit/skill.md` / `.gemini/skills/audit/SKILL.md` paths were not present in this workspace.
  - Performed manual screenshot audit over provider settings + extraction outcomes before finalization.