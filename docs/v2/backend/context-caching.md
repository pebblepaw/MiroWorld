# Backend — Context Caching and Memory Retrieval

## Scope

This document covers two similarly named but different backend concerns:

1. Provider token/context caching (cost optimization)
2. SQLite temporal memory retrieval (chat grounding)
3. LightRAG session workspaces and internal response caches during knowledge extraction

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

## B. SQLite Memory Retrieval (Chat Grounding Layer)

### Purpose

Retrieve session-scoped discourse memory to ground live chat responses.

### Where memory retrieval is triggered

Chat grounding runs through:

- `POST /api/v2/console/session/{id}/chat/group`
- `POST /api/v2/console/session/{id}/chat/agent/{agent_id}`
- `POST /api/v2/console/session/{id}/interaction-hub/report-chat`

These routes ultimately query `MemoryService` against persisted interactions, transcripts, and checkpoint records in SQLite.

### Retrieval model

`MemoryService` builds an FTS query from the user prompt, then ranks:

1. matching `interactions`
2. matching `interaction_transcripts`
3. recent checkpoint evidence

Session isolation comes from filtering everything by `session_id`.

## Current Runtime Caveats

- the response payload still includes the legacy field `graphiti_context_used`, but it remains `false`
- `memory_backend` is now `"sqlite"` for live local retrieval and `"demo"` for demo-mode responses
- cache hits in `MemoryService._simulation_context_cache` return with `synced_events=0` by design

## Validation Checklist

1. token-usage endpoints still return correct estimates for active provider/model.
2. live group chat returns `memory_backend=sqlite`.
3. live 1:1 chat returns grounded memory results from the current session.
4. report chat remains grounded without any external memory service.
5. non-live/demo mode still degrades gracefully to demo responses when applicable.

## C. LightRAG Session Caching (Knowledge Extraction Layer)

### Purpose

Keep knowledge extraction session-scoped while still allowing LightRAG to reuse its own internal artifacts within a single session workspace.

### Working-directory contract

`ConsoleService` builds a session-specific LightRAG workspace under:

- `backend/data/lightrag/sessions/{session_id}/{provider}_{embed_model}`

The backend clears that workspace when knowledge is reset for the same session.

### Why this matters

This layer is separate from:

- provider token caching
- SQLite chat-memory retrieval

If Screen 1 shows entities that do not belong to the current document, the correct place to investigate is the LightRAG/session-workdir path and its internal caches, not `MemoryService`.

### Current investigation note

During 2026-04-12 verification, a pasted-text live run produced a clean session-scoped knowledge artifact, but a separate Ollama/default-document run still showed signs of stale LightRAG cache contamination in backend logs. Treat this as a known diagnostic area, not as expected product behavior.
