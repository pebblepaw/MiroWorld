# Phase C - Agent Memory (Zep Cloud Integration)

## Goal
Wire agent interactions and temporal memory into Zep Cloud and expose memory query APIs.

## Current Status
Completed

## Tasks
- [x] C1 Zep SDK setup
- [x] C2 Episode ingestion pipeline
- [x] C3 Temporal fact validation
- [x] C4 Memory query API
- [x] C5 Memory-informed chat endpoint

## Completed Work
- Added memory APIs:
	- `POST /api/v1/phase-c/memory/sync`
	- `GET /api/v1/phase-c/memory/{simulation_id}/{agent_id}`
	- `POST /api/v1/phase-c/chat/agent`
- Implemented `MemoryService` for:
	- simulation interaction -> episode conversion,
	- Zep `graph.add_batch` ingestion,
	- resilient fallback on remote Zep API failures,
	- memory-grounded agent chat prompting.

## Open Issues
- Zep Cloud may return `404 not found` for some graph operations depending on account/project state; fallback keeps local flow operational.

## Decisions Made
- Treat Zep sync as best-effort and never fail critical simulation/report paths on external API errors.

## Next Actions
1. Continue with Phase D reporting pipeline.

## Evidence
- Phase C tests added: `tests/test_phase_c_memory.py`.
- `pytest -q` passes including sync and memory retrieval paths.
