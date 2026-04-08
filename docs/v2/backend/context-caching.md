# Backend — Context Caching and Memory Retrieval

## Scope

This document covers two similarly named but different backend concerns:

1. Provider token/context caching (cost optimization)
2. Graphiti temporal memory retrieval (chat grounding)

Both are active in V2 and should be debugged separately.

## A. Provider Context Caching (Token Cost Layer)

### Purpose

Reduce repeated token spend for shared simulation context (especially Gemini workflows).

### Current provider behavior

- Gemini: native cached-token semantics supported
- OpenAI: no provider-native cache path in this layer
- Ollama: no provider cache path; treated as local runtime

### Source of truth

- implementation: `token_tracker.py`
- persisted runtime totals: `session_token_usage`

### Endpoints

- `GET /api/v2/token-usage/{session_id}`
- `GET /api/v2/token-usage/{session_id}/estimate?agents={n}&rounds={r}`

## B. Graphiti Memory Retrieval (Chat Grounding Layer)

### Purpose

Retrieve session-scoped discourse memory to ground live chat responses.

### Where Graphiti is triggered

For live sessions, Graphiti-backed search runs through:

- `POST /api/v2/console/session/{id}/chat/group`
- `POST /api/v2/console/session/{id}/chat/agent/{agent_id}`

These routes call `MemoryService.agent_chat_realtime(..., live_mode=True)`.

### Ingestion model

Graphiti ingest is incremental and on-demand per query.

Per search call:

1. initialize Graphiti
2. sync bounded unsynced interactions/checkpoints from SQLite
3. execute Graphiti search
4. close client

Synced cursor state is stored in `memory_sync_state`.

### Sync controls

- `GRAPHITI_SYNC_BATCH_SIZE` (default `2`)
- `GRAPHITI_SYNC_SCAN_LIMIT` (default derived from batch size)
- `GRAPHITI_SEARCH_TIMEOUT_SECONDS` (default `90`, minimum `20`)

### Grouping and isolation

Graphiti episodes are grouped under:

- `group_id = session_{session_id}`

Search is filtered to that same group.

### Live-mode policy

Live memory is Graphiti-strict:

- if Graphiti/Falkor is unavailable, live chat raises runtime errors
- no local fallback in live mode

### Non-live compatibility policy

Non-live memory search order:

1. Graphiti (if available)
2. Zep when `MEMORY_BACKEND=zep`
3. local lexical fallback

## Current Runtime Caveats

- report chat still uses `search_simulation_context(..., live_mode=False)` path today, so strict live Graphiti enforcement is strongest on group and agent chat endpoints
- cache hits in `MemoryService._simulation_context_cache` return with `synced_events=0` by design
- Graphiti sync is intentionally small-batch; backlogs need multiple requests to fully ingest

## Validation Checklist

1. token-usage endpoints still return correct estimates for active provider/model.
2. live group chat returns `memory_backend=graphiti` when dependencies are healthy.
3. live 1:1 chat returns explicit failure when Graphiti/Falkor is unavailable.
4. `memory_sync_state` advances after repeated chat calls.
5. non-live mode still degrades gracefully when Graphiti is missing.
