# Infrastructure — Graphiti Memory Runtime

## Why This Exists

This document is the operational handoff for Graphiti in V2. It explains exactly what must be present, when Graphiti is used, how data is ingested, how retrieval happens, and what errors are expected when dependencies are missing.

## Runtime Dependency Contract

### Python packages

- `graphiti-core` (required for Graphiti search and ingest)
- `openai` (used by Graphiti embedder and reranker clients)
- `zep-cloud` (compatibility backend only; not required for live Graphiti flow)

### Services

- FalkorDB reachable at `FALKORDB_HOST:FALKORDB_PORT` (default `localhost:6379`)

### Provider/session requirements

Graphiti uses the session's resolved provider/model credentials:

- provider from `console_sessions.model_provider`
- model from `console_sessions.model_name`
- embed model from `console_sessions.embed_model_name`
- API key from session override or provider defaults
- base URL from session override or provider defaults

## Activation Model

### 1. Session mode

Graphiti strict mode activates when `console_sessions.mode == live`.

### 2. Endpoint trigger

Graphiti retrieval is invoked during live chat endpoints:

- `POST /api/v2/console/session/{session_id}/chat/group`
- `POST /api/v2/console/session/{session_id}/chat/agent/{agent_id}`

Both routes call `MemoryService.agent_chat_realtime(..., live_mode=True)` for live sessions.

### 3. Startup path

`./quick_start.sh --mode live` enforces Falkor readiness before boot:

- checks reachability at `FALKORDB_HOST:FALKORDB_PORT`
- if local host and unavailable, starts Docker Compose service `falkordb`
- fails startup if Falkor is still unreachable

## Ingestion Pipeline (Current)

Graphiti ingest is on-demand and incremental, not a one-shot preload.

For each live memory search:

1. Initialize `GraphitiService`
2. Sync a bounded batch from SQLite into Graphiti
3. Run Graphiti search
4. Close Graphiti client

### What gets ingested

- Memory-worthy interaction rows from `interactions` (post/comment style actions with non-empty content)
- Checkpoint rows from `simulation_checkpoints`

### Sync cursor state

Progress is persisted in `memory_sync_state`:

- `last_interaction_id`
- `last_checkpoint_id`
- `synced_events`

### Batch controls

- `GRAPHITI_SYNC_BATCH_SIZE` (default `2`)
- `GRAPHITI_SYNC_SCAN_LIMIT` (default `max(120, batch_size*6)`)

Implication: large backlogs are ingested across multiple queries.

## Retrieval Pipeline (Current)

### Group isolation

All episodes are written/read in Graphiti group:

- `group_id = session_{session_id}`

### Query path

- `MemoryService.search_simulation_context` calls `_search_graphiti_context`
- Graphiti search runs with `group_ids=[session_{session_id}]`
- Results normalize to:
	- `content`
	- `timestamp`
	- `confidence`

### Prompt usage

Live chat prompts include:

- Graphiti memory search results
- additional local timeline evidence (recent interactions and checkpoints)

This dual evidence improves stability when Graphiti recall is sparse.

## Live vs Non-Live Behavior

### Live mode (`live_mode=True`)

- Graphiti required
- no fallback to Zep/local
- dependency failures raise runtime errors (surfaced as HTTP 503)

### Non-live mode (`live_mode=False`)

- tries Graphiti first
- optional Zep path when `MEMORY_BACKEND=zep`
- local lexical fallback when neither graph backend can serve

## Known Quirks and Patches

### Falkor group-id escaping

`GraphitiService` patches Falkor full-text query construction to safely escape group IDs. Hyphens are intentionally preserved because over-escaping breaks session-id filters.

### Timeout guard

Graphiti search is wrapped by:

- `GRAPHITI_SEARCH_TIMEOUT_SECONDS` (default `90`, minimum `20`)

Timeouts in live mode raise explicit runtime errors recommending Falkor/provider checks.

## Environment Variables You Actually Need

- `FALKORDB_HOST` (default `localhost`)
- `FALKORDB_PORT` (default `6379`)
- `GRAPHITI_SEARCH_TIMEOUT_SECONDS` (default `90`)
- `GRAPHITI_SYNC_BATCH_SIZE` (default `2`)
- `GRAPHITI_SYNC_SCAN_LIMIT` (default derived value)
- `MEMORY_BACKEND` (default `graphiti`; only relevant for non-live fallback policy)

Compatibility only:

- `ZEP_API_KEY` / `ZEP_CLOUD`

## Validation Checklist for Next Agent

1. Confirm `graphiti-core` import path is available in backend runtime.
2. Confirm FalkorDB is reachable before live chat tests.
3. Run one live group chat call; verify `memory_backend == graphiti`.
4. Run one live agent chat call; verify `graphiti_context_used` toggles with retrieved episodes.
5. Check `memory_sync_state` advances after chat queries.
6. Verify runtime failures are explicit when Falkor/Graphiti is unavailable.
