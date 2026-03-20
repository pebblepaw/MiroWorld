# Latest Handoff

**Date:** 2026-03-21
**Session:** Screen 2 Frontend V2 implementation complete, verified locally, awaiting operator review

## What Changed
- Implemented Screen 2 live cohort generation on the Frontend V2 shell.
- Wired [frontend/src/pages/AgentConfig.tsx](../../frontend/src/pages/AgentConfig.tsx) to the live backend route:
  - `POST /api/v2/console/session/{id}/sampling/preview`
- Extended the Screen 2 state in [frontend/src/contexts/AppContext.tsx](../../frontend/src/contexts/AppContext.tsx):
  - `sampleMode`
  - `samplingInstructions`
  - `sampleSeed`
  - `populationArtifact`
  - `populationLoading`
  - `populationError`
- Added the Stage 2 API contract in [frontend/src/lib/console-api.ts](../../frontend/src/lib/console-api.ts).
- Extended the backend Screen 2 request/response models in [backend/src/mckainsey/models/console.py](../../backend/src/mckainsey/models/console.py).
- Implemented live candidate retrieval and preview flow in [backend/src/mckainsey/services/console_service.py](../../backend/src/mckainsey/services/console_service.py).
- Expanded [backend/src/mckainsey/services/persona_sampler.py](../../backend/src/mckainsey/services/persona_sampler.py) so Screen 2 uses the local Singapore parquet through deterministic structured candidate retrieval.
- Expanded [backend/src/mckainsey/services/persona_relevance_service.py](../../backend/src/mckainsey/services/persona_relevance_service.py):
  - issue-profile building from Screen 1 graph artifacts
  - BM25 shortlist
  - bounded semantic rerank
  - two sampling modes
  - parsed-instruction handling
  - agent graph payload generation
  - parser fallback when Gemini returns notes-only / non-actionable output
  - filtering of hidden Screen 1 nodes from Stage 2 issue-profile matching
  - active use of `soft_penalties`, `exclusions`, and `distribution_targets`
  - correct hobby/skill matching against Nemotron list fields
- Added/updated Stage 2 tests:
  - [backend/tests/test_persona_relevance_service.py](../../backend/tests/test_persona_relevance_service.py)
  - [backend/tests/test_console_routes.py](../../backend/tests/test_console_routes.py)
  - [backend/tests/test_llm_client.py](../../backend/tests/test_llm_client.py)
  - [frontend/src/pages/AgentConfig.test.tsx](../../frontend/src/pages/AgentConfig.test.tsx)

## Screen 2 Product Shape Now Implemented

### Modes
- `Affected Groups`
- `Population Baseline`

### Controls
- live agent-count selector
- live sampling-mode toggle
- live `Sampling Instructions` textbox
- live `Generate Agents`
- live `Re-sample`
- visible `Sample Seed`

### Retrieval Stack
- structured candidate filtering first
- BM25 shortlist second
- semantic rerank third

### Parsed Instructions
- UI now renders a read-only parsed summary for:
  - `Hard Filters`
  - `Soft Boosts`
  - `Exclusions`
  - `Distribution Targets`
- Backend parser behavior:
  - Gemini first
  - deterministic fallback when Gemini is unavailable, errors, or returns notes-only output

### Agent Graph
- Screen 2 graph now matches the Screen 1 visual language:
  - small nodes
  - external labels
  - always-visible edges
  - optional relationship-label toggle
  - legend derived from live graph categories

## What Is Stable
- The local Singapore parquet is the Screen 2 source of truth.
- Screen 2 no longer relies on mock agent generation.
- The Screen 2 slider no longer advertises unsupported sizes above the backend contract.
- `Generate Agents` and `Re-sample` both use the live backend and return real seeds.
- The Screen 2 cohort response is explainable:
  - parsed instructions
  - selection rationale
  - cohort diagnostics
  - agent graph
- Screen 2 preview requests now reject unknown extra fields instead of silently accepting them.

## What Was Verified
- Backend targeted suite:
  - `16 passed`
- Frontend test suite:
  - `8 passed`
- Frontend app typecheck:
  - passed
- Frontend build:
  - passed
- Live launcher:
  - `./quick_start.sh --mode live --real-oasis`
  - backend health passed
  - frontend served on `http://127.0.0.1:5173`
- Live browser flow:
  1. upload real `CNA SHrinking Birth Rate.docx`
  2. complete Screen 1 extraction
  3. proceed to Screen 2
  4. generate a live 500-agent cohort
- Live Screen 2 browser verification confirmed:
  - `Candidate Pool`
  - `Sample Size`
  - `Sample Seed`
  - parsed instruction summary rendered in the page
  - live selection-rationale cards
  - live agent graph

## Current Known Limits
- Screen 2 is now functional and operator-reviewable, but some documents can still leak broad document-native entities into rationale text if those entities survive Screen 1 as visible non-facet nodes.
- The deterministic Stage 2 parser intentionally stays conservative; it does not attempt broad free-form demographic inference.
- Stage 3, Stage 4, and Stage 5 remain as previously implemented; this session only changed Screen 2 and its supporting backend logic.

## Recommended Next Work
1. Operator review of Screen 2 in live mode.
2. If approved, start Screen 3 using the same Frontend V2 shell.
3. Reuse Screen 2 cohort/state contract as the input surface for Screen 3 live simulation startup.

## Runbook
1. Live mode
   - ensure `.env` contains valid Gemini and Zep credentials
   - ensure `backend/.venv311/bin/python` exists with native OASIS dependencies
   - run `./quick_start.sh --mode live --real-oasis`
   - upload a document in Screen 1
   - proceed to Screen 2
   - generate agents and re-sample as needed
2. Demo mode
   - `./quick_start.sh --mode demo`

## File Links
- [Progress.md](../../Progress.md)
- [progress/index.md](../../progress/index.md)
- [progress/phaseH.md](../../progress/phaseH.md)
- [progress/phaseI.md](../../progress/phaseI.md)
- [frontend/src/pages/AgentConfig.tsx](../../frontend/src/pages/AgentConfig.tsx)
- [backend/src/mckainsey/services/persona_relevance_service.py](../../backend/src/mckainsey/services/persona_relevance_service.py)
- [quick_start.sh](../../quick_start.sh)
