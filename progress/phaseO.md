# Phase O — OASIS Engine Performance + Streaming + UX Hardening — Completed

**Date:** 2026-04-03

## Scope

This phase implemented the MiroFish-inspired runtime and streaming behavior for Screen 3, plus feed UX fixes and persona-display improvements requested for Screen 2 and Screen 3.

## Requirement Coverage

1. **Time-based activation (MiroFish-style subset stepping) — Completed**
    - Implemented per-agent activity profiles and hour-aware participation windows.
    - Added `_build_activity_profile`, `_simulated_hour_for_round`, and `_get_active_agents_for_round` in `backend/scripts/oasis_reddit_runner.py`.
    - Round loop now steps selected active subsets instead of all agents every round.

2. **More frequent streaming via smaller `env.step` batches — Completed**
    - Round execution is split into incremental batches (10% of active agents, min 1, max 25).
    - `_emit_incremental_db_events(...)` is called after each batch flush.
    - Added `round_batch_flushed` event emission for frontend progress visibility.

3. **"View more replies" + no post cap in feed — Completed**
    - Added per-thread expand/collapse state for replies in `frontend/src/pages/Simulation.tsx`.
    - Button now toggles full reply list (`View N more replies` / `Show fewer replies`).
    - Feed rendering uses full `feedThreads` without hard cap, preserving scroll-through of all posts.

4. **Policy kick-off seed posts reduced from 5 to 1 — Completed**
    - Seed injection now uses `min(1, len(profiles))` in `backend/scripts/oasis_reddit_runner.py`.

5. **Agent names data pipeline from persona text — Completed**
    - Added regex-based display-name extraction in backend persona sampling and runner paths:
      - `backend/src/mckainsey/services/persona_relevance_service.py`
      - `backend/scripts/oasis_reddit_runner.py`
    - Added `display_name` plumbing into sampled persona type and Screen 2 mapping:
      - `frontend/src/lib/console-api.ts`
      - `frontend/src/pages/AgentConfig.tsx`
    - Agent tooltip and list labels now prioritize extracted display names.

6. **Proper post headers/titles instead of first-line fallback — Completed**
    - Added `_extract_title(...)` and emit `title` in `post_created` events from runner.
    - Screen 3 cards render title field directly.

7. **Progress UX in right panel with clear stages — Completed**
    - Added Process Timeline card in `frontend/src/pages/Simulation.tsx`.
    - Stages shown with status badges (`pending`, `running`, `completed`) in scrollable list.
    - Includes runtime init, baseline checkpoint, round execution, batch streaming, final checkpoint, artifact finalization.

8. **Round 1 empty feed behavior (2 agents, 10 rounds) — Addressed**
    - Seed post events are tagged `round_no=1` and incremental flush occurs immediately after seed step.
    - Round 1 active-agent selection enforces a stronger minimum to avoid empty first-round participation.
    - Post/comment matching in frontend uses robust post-id comparison to avoid missed attachment by type mismatch.
    - Expected behavior now: Round 1 should show content (at minimum the seed thread), even with very small populations.

## Additional Fix Applied During Validation

- Corrected double-escaped regex patterns in `backend/scripts/oasis_reddit_runner.py` so fallback name extraction and title parsing behave correctly when direct name fields are missing.

## Verification Evidence

### Automated tests

- Backend/root pytest run (excluding non-test script collectors):
  - Command: `/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/.venv/bin/python -m pytest -q --ignore=test_sim.py --ignore=test_sim2.py`
  - Result: **62 passed**

- Frontend unit/integration tests:
  - Command: `cd frontend && npm test`
  - Result: **5 files passed, 10 tests passed**

- Frontend production build:
  - Command: `cd frontend && npm run build`
  - Result: **build succeeded**

### Runtime sanity checks

- Round-1 activation sanity: validated selected active agents for a 2-agent scenario.
- Name extraction sanity: validated regex fallback extracts persona name from text (example: `Laura Tan`).
- Title generation sanity: validated policy content is condensed into a meaningful header string.

### Screenshot evidence (Screen 3)

- `output/playwright/screen3-phaseO-feed-card-clean.png`
- `output/playwright/screen3-phaseO-process-timeline-clean.png`
- `output/playwright/screen3-phaseO-overview-clean.png`

All three captures were validated as clean, readable, and correctly framed.

## Phase Status

Completed
