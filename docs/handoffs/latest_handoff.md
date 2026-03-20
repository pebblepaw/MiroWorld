# Latest Handoff

**Date:** 2026-03-21
**Session:** Screen 1 Frontend V2 hardening complete + Screen 2 sampling plan locked

## What Changed
- Completed Screen 1 on the Frontend V2 codebase and documented it as [progress/phaseH.md](../../progress/phaseH.md).
- Hardened the Stage 1 LightRAG graph adapter in [backend/src/mckainsey/services/lightrag_service.py](../../backend/src/mckainsey/services/lightrag_service.py):
  - controlled facet inference
  - named-person / photo-credit suppression
  - explicit `display_bucket`
  - `support_count`, `degree_count`, `importance_score`
  - `generic_placeholder`, `low_value_orphan`, `ui_default_hidden`
- Hardened the Screen 1 UI in [frontend/src/pages/PolicyUpload.tsx](../../frontend/src/pages/PolicyUpload.tsx):
  - segmented control: `All`, `Nemotron Entities`, `Other Entities`
  - separate bucket filter row
  - hidden-node filtering for default graph and `Top 3`
  - edge-label toggle now hides only text labels, not the lines
- Added Screen 1 regression coverage in:
  - [backend/tests/test_lightrag_service.py](../../backend/tests/test_lightrag_service.py)
  - [frontend/src/pages/PolicyUpload.test.tsx](../../frontend/src/pages/PolicyUpload.test.tsx)
- Added Screen 2 planning and next-phase design doc in [progress/phaseI.md](../../progress/phaseI.md), including:
  - two explicit sampling modes
  - local Singapore parquet as the source-of-truth
  - exact → BM25 → semantic rerank retrieval order
  - `Sampling Instructions` parsing
  - repeatable re-sampling
  - Screen 1-style agent graph design

## What Is Stable
- `./quick_start.sh --mode demo` remains the primary demo launch path.
- `./quick_start.sh --mode live --real-oasis` boots the live console path when the OASIS sidecar is installed.
- Stage 1 file upload is fully wired UI -> API -> persisted knowledge artifact on the Frontend V2 shell.
- Screen 1 now has stable filter semantics:
  - family filter via `facet_kind`
  - bucket filter via `display_bucket`
  - zero-count buckets hidden
  - hidden-node policy driven by `ui_default_hidden`
- Generic placeholders like `Concept` stay in the artifact but do not appear in the default graph or `Top 3`.
- Isolated facet nodes remain visible, so `Nemotron Entities` no longer collapses to an empty state for valid facet matches.
- Stage 2/3/4/5 code from the earlier console rebuild remains intact and working.
- The Screen 2 planning target now assumes the local Singapore parquet in `backend/data/nemotron/data/*.parquet`, not a generic fallback dataset shape.

## What Was Verified
- Backend tests: `14 passed`
- Frontend tests: `5 passed`
- Frontend build: passed
- Live Screen 1 verification on `Sample_Inputs/CNA SHrinking Birth Rate.docx`:
  - `75` entities
  - `50` relationships
  - `8` paragraphs
  - `Concept` preserved with `generic_placeholder=true` and `ui_default_hidden=true`
  - `Nemotron Entities` populated by a live visible facet node:
    - `Elderly People` → `age_cohort:senior`
- Browser spot-check:
  - Screen 1 completed extraction in live mode
  - clicking `Nemotron Entities` produced the `Age Group` filtered view instead of an empty graph

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
- Screen 1 facet extraction is intentionally conservative now. It is less noisy, but some documents may still yield only a small number of Nemotron-aligned facet nodes.
- Hidden nodes are artifact-preserved but currently have no explicit “show hidden nodes” control in the UI.
- Stage 2 has not yet been reworked for the Frontend V2 shell; that is the next active phase.

## Recommended Next Work
1. Implement Screen 2 using the plan in [progress/phaseI.md](../../progress/phaseI.md).
2. Ship two explicit sampling modes:
   - `Affected Groups`
   - `Population Baseline`
3. Keep `Affected Groups` as the default first-generation mode.
4. Add the `Sampling Instructions` text box and parse it into structured boosts/filters.
5. Implement repeatable re-sampling with a visible seed.
6. Reuse the Screen 1 graph visual language for the Stage 2 agent graph.

## File Links
- [BRD.md](../../BRD.md)
- [Progress.md](../../Progress.md)
- [progress/index.md](../../progress/index.md)
- [progress/phaseG.md](../../progress/phaseG.md)
- [progress/phaseH.md](../../progress/phaseH.md)
- [progress/phaseI.md](../../progress/phaseI.md)
- [quick_start.sh](../../quick_start.sh)
