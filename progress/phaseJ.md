# Phase J — Screen 3 Live Simulation & Screen 4A Reports

## Goal
Implement Screen 3 on the Frontend V2 shell as a real live Reddit-mode OASIS simulation with streaming feed updates, all-agent baseline/final opinion checkpoints, graph-aware context routing, and a real Screen 4A `Reports & Insights` view backed by structured Gemini output.

## Current Status
Implemented locally and validated end to end in live mode. Screen 3 and Screen 4A are live on the Frontend V2 shell and ready for operator review. Screen 4B and Screen 4C remain navigable mock tabs in this phase.

## Product Shape Implemented

### Screen 3
- Platform locked to `Reddit` for this phase.
- Round controls now use:
  - quick picks `3 / 4 / 5`
  - default `4`
  - advanced slider `1-8`
- Live feed behavior now includes:
  - append-only stacked thread cards
  - live comments nested beneath posts
  - live reaction counters
  - auto-scroll to newest visible feed content
  - round progress bar
  - completion CTA into Screen 4A
- Live summary tiles now include:
  - visible event count
  - elapsed time
  - ETA
  - hottest thread
  - checkpoint status
  - discussion momentum

### Screen 4A
- `Reports & Insights` is now the real Screen 4 implementation in this phase.
- Fixed structured sections:
  - executive summary
  - key actionable insights
  - strongest supporting views
  - strongest dissenting views
  - approval / dissent breakdown by demographic segment
  - influential posts / influential agents
  - recommendations
  - risks / minority-view watchouts
- Screen 4A is async:
  - `POST /report/generate` starts work
  - `GET /report/full` is polled until completion
- No heuristic free-form fallback is used for live Screen 4A generation:
  - invalid Gemini JSON causes explicit failure state

## Screen 3 Runtime Architecture

### Event Stream
- Screen 3 now consumes the persisted `/api/v2/console/session/{id}/simulation/stream` SSE feed.
- Live events now include:
  - `run_started`
  - `checkpoint_started`
  - `checkpoint_completed`
  - `round_started`
  - `post_created`
  - `comment_created`
  - `reaction_added`
  - `metrics_updated`
  - `round_completed`
  - `run_completed`
  - `run_failed`
- Event payloads now carry feed-ready metadata:
  - `post_id`
  - `comment_id`
  - `actor_agent_id`
  - `actor_name`
  - `actor_subtitle`
  - `title`
  - `content`
  - `reaction`
  - live counters / top threads / momentum snapshots

### Incremental Persistence
- The OASIS runner now writes NDJSON incrementally.
- `SimulationStreamService` ingests new bytes incrementally and rebuilds persisted state snapshots instead of waiting for the entire run to finish.
- Screen 3 state now reflects real progress during the run, not only terminal snapshots.

### Completion Semantics
- The run is no longer marked `completed` at the end of the public-discourse rounds alone.
- Completion now happens only after:
  1. baseline checkpoint completed
  2. OASIS Reddit rounds completed
  3. final checkpoint completed
- This prevents Screen 3 from showing a false “done” state while the final all-agent stance measurement is still running.

## Knowledge Graph To Agent Context Routing

### Context Bundle
- Before OASIS starts, each sampled persona receives a `SimulationContextBundle` built from:
  - matched Screen 1 facet nodes
  - matched Screen 1 document-native nodes
  - adjacent graph nodes
  - LightRAG provenance metadata
  - the persona profile itself
- The bundle carries:
  - `brief`
  - `matched_context_nodes`
  - `graph_node_ids`
  - provenance:
    - `source_ids`
    - `file_paths`

### How Context Is Used
- Baseline checkpoint prompt
- OASIS profile/briefing prompt
- Final checkpoint prompt

### Participation Policy
- All sampled agents remain in the simulation and can read/react.
- Relevance-matched agents are given stronger early issue salience in their OASIS profile text.
- The runner sorts personas by `mckainsey_relevance_score` before profile generation so the early seeded discussion starts with the most relevant agents.
- Less directly affected agents can still join through replies and trending discussion instead of being excluded from the run entirely.

## Full-Cohort Opinion Measurement

### Checkpoints
- Every sampled agent now receives:
  - one `baseline` checkpoint before round 1
  - one `final` checkpoint after the last round
- Checkpoint output fields:
  - `stance_score`
  - `stance_class`
  - `confidence`
  - `primary_driver`
  - `matched_context_nodes`

### Why This Matters
- Screen 3 public feed reflects visible discourse.
- Approval / dissent metrics come from all-agent checkpoint measurements, not only from agents who posted publicly.
- This makes demographic breakdowns and final Screen 4A reporting more defensible.

## ETA Logic
- Initial ETA is seeded from:
  - measured / estimated checkpoint cost
  - round count
  - cohort size
- During live OASIS rounds, `metrics_updated` events refresh:
  - `elapsed_seconds`
  - `estimated_total_seconds`
  - `estimated_remaining_seconds`
- ETA now remains meaningful while baseline/final checkpoints are part of the overall run budget.

## Screen 4A Structured Report Contract
- Response shape now includes:
  - `status`
  - `generated_at`
  - `executive_summary`
  - `insight_cards`
  - `support_themes`
  - `dissent_themes`
  - `demographic_breakdown`
  - `influential_content`
  - `recommendations`
  - `risks`
  - optional `error`
- Report inputs include:
  - Screen 1 knowledge artifact
  - Screen 2 cohort artifact
  - Screen 3 event log
  - baseline checkpoint records
  - final checkpoint records
  - stored interactions
- Gemini must return valid JSON for this schema; otherwise Screen 4A surfaces a failure state.

## OASIS Runtime Hardening
- Added `backend/scripts/check_oasis_runtime.py` to validate the native OASIS Python 3.11 sidecar.
- Added `backend/requirements-oasis-runtime.txt` to pin the dedicated OASIS runtime dependency set.
- `quick_start.sh --mode live --real-oasis` now validates the sidecar and installs the pinned runtime requirements if the import contract is broken.
- Validated import contract after pinning:
  - `numpy`
  - `pyarrow`
  - `sklearn`
  - `transformers`
  - `camel`
  - `oasis`

## Verification

### Automated
- Backend targeted suite:
  - `tests/test_simulation_stream_service.py`
  - `tests/test_simulation_service.py`
  - `tests/test_report_service.py`
  - `tests/test_console_routes.py`
- Frontend:
  - `src/pages/Simulation.test.tsx`
  - `src/pages/Analysis.test.tsx`
  - full `npm test`
  - `tsc --noEmit -p tsconfig.app.json`
  - `npm run build`

### Live
- Verified via `./quick_start.sh --mode live --real-oasis`
- Real end-to-end validation flow completed:
  1. create live session
  2. upload real `CNA SHrinking Birth Rate.docx`
  3. generate live Stage 2 cohort (`sample_count = 4`)
  4. run native OASIS for `3` rounds
  5. observe `34` persisted live events
  6. confirm final checkpoint completion
  7. generate Screen 4A structured report asynchronously
  8. receive completed report with `3` insight cards

## Residual Notes
- Screen 4B and Screen 4C remain mock tabs in this phase by design.
- The OASIS runtime validation script still surfaces a `RequestsDependencyWarning` from the sidecar environment, but the required module import contract now passes and the live OASIS run succeeded after pinning `pyarrow`.
- The Frontend V2 production bundle is large enough for Vite to warn about chunk size; this is a performance optimization task, not a functional blocker for Screen 3 or Screen 4A.

## Tasks
- [x] J1 Replace Screen 3 mock UI with live SSE-driven Reddit feed
- [x] J2 Persist and stream richer OASIS round events incrementally
- [x] J3 Build graph-aware simulation context bundles from Screen 1 + Screen 2
- [x] J4 Add all-agent baseline and final opinion checkpoints
- [x] J5 Make Screen 3 completion wait for final checkpoint completion
- [x] J6 Implement Screen 4A async report generation with fixed structured schema
- [x] J7 Keep Screen 4B / 4C navigable on mock data without blocking Screen 4A
- [x] J8 Add Frontend V2 Screen 3 / 4A tests
- [x] J9 Harden the native OASIS sidecar runtime with validation + pinned requirements
- [x] J10 Verify live Screen 1 → Screen 2 → Screen 3 → Screen 4A end to end
