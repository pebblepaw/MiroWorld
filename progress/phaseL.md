# Phase L — Demo Mode with Full Cache Support

**Date:** 2026-03-24

## Summary

Phase L documents the demo-mode implementation that provides a fully cached, end-to-end experience of the McKAInsey console without making external Gemini or Zep calls. Demo mode covers all 7 screens (knowledge ingestion → sampling → simulation → analysis → interaction hub) using pre-generated JSON cache files so operators and evaluators can run the full product workflow locally and deterministically.

## What Demo Mode Provides
- Full cached data for all screens via `backend/data/demo-output.json` and `frontend/public/demo-output.json`.
- A `DemoService` that serves cached responses to console API endpoints when a session is marked `mode: demo`.
- Demo-friendly endpoints include: `/session`, `/knowledge/*`, `/sampling/*`, `/simulation/*`, `/report/*`, `/interaction-hub/*`.
- Demo chat behavior: report and agent chat responses are served from the cache (no outbound LLM calls).

## Architecture & Data Flow

User Request → routes_console.py → (is session demo?) → DemoService → cached JSON

Key components:
- `DemoService` (`backend/src/mckainsey/services/demo_service.py`) — loads and serves the cached payload.
- Console routes (`routes_console.py`) — check session mode and route to `DemoService` when appropriate.
- Demo cache files — produced by helper scripts and copied into both backend and frontend public paths.

## Demo Cache Contents (high-level)
- Screen 1: Knowledge Graph from `Sample_Inputs/fy2026_budget_statement.md` (75 entities)
- Screen 2: Population sampling — 250 Nemotron personas
- Screen 3: Simulation — 6 rounds, ~1496 interactions (posts/comments/reactions)
- Screen 4: Structured Analysis report (executive summary, insights, themes, recommendations, risks)
- Screen 5: Interaction hub & agent chat

## How To Run

Start demo mode (local, no API keys required):

```bash
./quick_start.sh --mode demo
```

Or the shorthand (default):

```bash
./quick_start.sh
```

To regenerate the demo cache from an existing snapshot:

```bash
# From an existing snapshot
python backend/scripts/prepare_demo_cache.py

# Or generate a new comprehensive cache (requires API keys)
python backend/scripts/generate_comprehensive_demo_cache.py --force
```

## Demo Scripts
- `backend/scripts/prepare_demo_cache.py` — prepares a demo `demo-output.json` from a snapshot and copies it into `frontend/public/`.
- `backend/scripts/generate_comprehensive_demo_cache.py` — (optional) full regeneration pipeline that may call Gemini when API keys are available.

## Runbook

1. Start demo: `./quick_start.sh --mode demo`
2. Confirm cached state via HTTP:

```bash
curl http://localhost:8000/api/v2/console/session/demo-session-fy2026-budget/simulation/state
```

3. If cache missing, regenerate: `python backend/scripts/prepare_demo_cache.py`

## Verification
- All console endpoints listed below respond with cached payloads when session mode is `demo`:
  - `POST /session`
  - `POST /knowledge/upload`
  - `POST /sampling/preview`
  - `POST /simulation/start`
  - `GET /simulation/state`
  - `GET /report/full`
  - `POST /report/generate`
  - `POST /interaction-hub/report-chat`
  - `POST /interaction-hub/agent-chat`

## Future Enhancements
- Multiple demo scenarios (policy variations)
- Configurable agent counts (50/100/250/500)
- Demo mode UI indicator
- More sophisticated demo chat behaviors

## Files
- Backend cache: `backend/data/demo-output.json`
- Frontend cache: `frontend/public/demo-output.json`
- Demo service: `backend/src/mckainsey/services/demo_service.py`
- Demo scripts: `backend/scripts/prepare_demo_cache.py`, `backend/scripts/generate_comprehensive_demo_cache.py`
