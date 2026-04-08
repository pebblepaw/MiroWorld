# McKAInsey V2 — Documentation Index

Read this file first, then open only the documents relevant to the task at hand.

## Recommended Reading Order

1. [BRD_V2.md](BRD_V2.md)
2. The screen or backend spec you are actively changing
3. [architecture.md](architecture.md) if you need cross-cutting context
4. [handoffs/latest_handoff.md](handoffs/latest_handoff.md) for the most recent implementation status

## Fast Handoff Path for Graphiti/Memory Work

If your task touches Screen 4 chat, live memory, or backend runtime failures, read in this order:

1. [infrastructure/graphiti.md](infrastructure/graphiti.md)
2. [backend/context-caching.md](backend/context-caching.md)
3. [backend/config-system.md](backend/config-system.md)
4. [BRD_V2.md](BRD_V2.md) sections 3 and 4.5

## Core Documents

### Master References

- [BRD_V2.md](BRD_V2.md): current V2 product and runtime contract
- [architecture.md](architecture.md): system layout, data flow, and state ownership
- [handoffs/latest_handoff.md](handoffs/latest_handoff.md): current implementation snapshot

### Frontend Specs

- [frontend/screen-0-onboarding.md](frontend/screen-0-onboarding.md)
- [frontend/screen-1-knowledge-graph.md](frontend/screen-1-knowledge-graph.md)
- [frontend/screen-2-population-sampling.md](frontend/screen-2-population-sampling.md)
- [frontend/screen-3-simulation.md](frontend/screen-3-simulation.md)
- [frontend/screen-4-report-chat.md](frontend/screen-4-report-chat.md)
- [frontend/screen-5-analytics.md](frontend/screen-5-analytics.md)
- [frontend/frontend-final-check-2026-04-06.md](frontend/frontend-final-check-2026-04-06.md)

### Backend Specs

- [backend/config-system.md](backend/config-system.md): canonical ids, session config persistence, and model/runtime resolution used by memory backends
- [backend/context-caching.md](backend/context-caching.md): token cache behavior plus Graphiti ingestion/retrieval/fallback policy
- [backend/controversy-boost.md](backend/controversy-boost.md): OASIS feed ranking control and runtime contract
- [backend/metrics-heuristics.md](backend/metrics-heuristics.md): quantitative metric generation and analytics derivation rules

### Infrastructure Specs

- [infrastructure/docker.md](infrastructure/docker.md)
- [infrastructure/graphiti.md](infrastructure/graphiti.md): Graphiti dependencies, activation triggers, ingestion loop, retrieval path, and failure behavior

## Current V2 Artboard Map

The Paper MCP references still correspond to the original visual design exploration, but the runtime behavior has converged on the current screen model below:

| Runtime Screen | Artboard ID | Notes |
|:---------------|:------------|:------|
| Screen 0 — Onboarding | `8A-0` | canonical onboarding modal |
| Screen 1 — Knowledge Graph | `F6-0` | upload + analysis question workflow |
| Screen 2 — Population Sampling | `H9-0` | cohort sampling |
| Screen 3 — Simulation | `9U-0` | live OASIS feed |
| Screen 4 — Report + Chat | `NW-0`, `CZ-0`, `PN-0` | all three references now map to the same routed page with view modes |
| Screen 5 — Analytics | `K5-0` | analytics visual language |

Important:

- There is no separate routed Screen 6 in the current implementation.
- “Chat Only” is a Screen 4 view mode.

## Archived Temporary Planning Docs

Temporary implementation notes from the V2 completion pass are archived under `archive/` and are no longer the active documentation surface.

## V1 History

Older Singapore-only/V1 documents remain under `archive/v1/`.
