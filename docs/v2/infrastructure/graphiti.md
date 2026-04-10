# Infrastructure — Graphiti Memory Runtime

## Status

Graphiti has been removed from the active V2 runtime. This file remains only as a historical note so older handoffs and archived docs still have a landing point.

## Current Runtime Replacement

Screen 4 chat grounding now uses:

- SQLite FTS5 over persisted `interactions` and `interaction_transcripts`
- checkpoint evidence from `simulation_checkpoints`
- provider-aware LLM settings resolved from `console_sessions`

No FalkorDB, Graphiti client, or Zep dependency is required for current local or Docker flows.

## What To Read Instead

- `docs/v2/backend/context-caching.md`
- `docs/v2/backend/config-system.md`
- `docs/v2/architecture.md`

## Historical Note

Older planning documents may still mention Graphiti because the original V2 design evaluated it as a potential live-memory backend. The implementation plan later removed it in favor of SQLite FTS5 locally and PostgreSQL FTS for future cloud deployment.
