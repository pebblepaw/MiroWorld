# Latest Handoff

**Date:** 2026-03-20
**Session:** McKAInsey console rebuild completion + real Stage 1 upload flow + real Stage 5 Gemini/Zep chat + native OASIS live verification

## What Changed
- Replaced the inherited dashboard with the new McKAInsey console shell and 7 priority screens.
- Added the new console backend surface under `/api/v2/console/...`.
- Implemented real Stage 1 uploaded file parsing:
  - PDF via `pypdf`
  - DOCX via `python-docx`
  - text-like files via direct decoding and normalization
- Implemented real Stage 2 document-aware Nemotron sampling:
  - local parquet-backed retrieval
  - relevance scoring against the uploaded document artifact
  - balanced hybrid sampling across planning area, income bracket, and age bucket
- Implemented Stage 3 native OASIS event streaming persistence and SSE delivery.
- Split Stage 4 into distinct report, opinions, and friction-map payloads.
- Implemented Stage 5 real report chat and agent chat backed by Gemini and Zep Cloud.
- Updated `quick_start.sh` to keep demo and live boot as the primary operator flows.
- Added Playwright coverage for demo boot and live boot smoke validation.

## What Is Stable
- `./quick_start.sh --mode demo` remains the primary demo launch path.
- `./quick_start.sh --mode live --real-oasis` boots the live console path when the OASIS sidecar is installed.
- Stage 1 file upload is fully wired UI -> API -> persisted knowledge artifact.
- Stage 2 returns real sampled personas, representativeness diagnostics, and agent selection reasons.
- Stage 3 supports native OASIS runs and live stream/state retrieval.
- Stage 5 report chat and agent chat both make real API calls to Gemini and Zep Cloud.
- Backend tests, frontend build, and Playwright smoke tests all pass.

## What Was Verified
- Backend tests: `19 passed`
- Frontend build: passed
- Playwright:
  - demo console smoke passed
  - live boot smoke passed
- Real live end-to-end session:
  - session id: `oasis-v2-docx-1773994001`
  - uploaded DOCX parsed successfully
  - population preview returned a real selected cohort
  - native OASIS completed a 2-round run
  - persisted event count reached `36`
  - report chat returned `200` with Gemini + Zep context
  - agent chat returned `200` with Gemini + Zep context
- Real PDF upload path was also verified using:
  - `Sample_Inputs/fy2026_budget_statement.pdf`

## Operator Runbook
1. Demo mode
   - `./quick_start.sh --mode demo`
   - open `http://127.0.0.1:5173`
2. Live mode
   - ensure `.env` contains valid Gemini and Zep credentials
   - ensure `backend/.venv311/bin/python` exists with native OASIS dependencies
   - run `./quick_start.sh --mode live --real-oasis`
   - create a session, upload a document, run sampling, then start simulation
3. Optional demo refresh
   - `./quick_start.sh --refresh-demo --mode demo`

## Remaining Risks
- Live mode still depends on external service health for Gemini and Zep Cloud.
- Native OASIS still requires the Python 3.11 sidecar runtime.
- Frontend bundle size remains large because graphing/mapping modules are not yet split into lazy chunks.

## Recommended Next Work
1. Add frontend code-splitting for graph and map bundles.
2. Add CI automation for backend tests, frontend build, and Playwright smoke coverage.
3. Add a longer live Playwright scenario that exercises a full multi-step simulation run once provider quotas allow.

## File Links
- [BRD.md](../../BRD.md)
- [Progress.md](../../Progress.md)
- [progress/index.md](../../progress/index.md)
- [progress/phaseG.md](../../progress/phaseG.md)
- [quick_start.sh](../../quick_start.sh)
