# McKAInsey V2 — Documentation Index

> Quick-reference for any agent or developer joining this project.
> Read this file first, then follow the links to only the documents relevant to your task.

## Reading Order for New Agents

1. **This file** → understand the doc layout
2. [BRD_V2.md](BRD_V2.md) → skim §1 (Executive Summary) and §5 (Phases) for scope
3. The sub-document for your assigned phase → implementation detail
4. [handoffs/latest_handoff.md](handoffs/latest_handoff.md) → what happened last, what to do next

Do **not** read all documents. Load only what your current task requires.

---

## Document Map

### Master Document
| File | Purpose |
|:-----|:--------|
| [BRD_V2.md](BRD_V2.md) | Single source of truth: architecture, decisions, phases, API contracts |

### Frontend Specs (one per screen)
| File | Screen | Key Features |
|:-----|:-------|:-------------|
| [frontend/screen-0-onboarding.md](frontend/screen-0-onboarding.md) | Screen 0 | Country, provider, model, use case selection |
| [frontend/screen-1-knowledge-graph.md](frontend/screen-1-knowledge-graph.md) | Screen 1 | Multi-doc upload, URL scraper, draggable graph |
| [frontend/screen-2-population-sampling.md](frontend/screen-2-population-sampling.md) | Screen 2 | Dynamic filters, token cost tracker |
| [frontend/screen-3-simulation.md](frontend/screen-3-simulation.md) | Screen 3 | Controversy slider, dynamic metrics, viewport fix |
| [frontend/screen-4-report-chat.md](frontend/screen-4-report-chat.md) | Screen 4 | 60/40 split, 3-mode toggle, group chat, DOCX export |
| [frontend/screen-5-analytics.md](frontend/screen-5-analytics.md) | Screen 5 | Polarization, Sankey, Influence graph, Cascade tree |

### Backend Specs (one per feature domain)
| File | Domain | Key Deliverables |
|:-----|:-------|:-----------------|
| [backend/config-system.md](backend/config-system.md) | Configuration | YAML schemas, ConfigService, prompt externalization |
| [backend/controversy-boost.md](backend/controversy-boost.md) | OASIS RecSys | `calculate_hot_score` modification |
| [backend/context-caching.md](backend/context-caching.md) | Token Optimization | Gemini caching wrapper, TokenTracker |
| [backend/metrics-heuristics.md](backend/metrics-heuristics.md) | Analytics | Polarization, influence, cascade computation |

### Infrastructure
| File | Domain | Key Deliverables |
|:-----|:-------|:-----------------|
| [infrastructure/docker.md](infrastructure/docker.md) | Deployment | docker-compose, Dockerfiles, graceful degradation |
| [infrastructure/graphiti.md](infrastructure/graphiti.md) | Memory | Graphiti + FalkorDB, Zep migration |

### Operational
| File | Purpose |
|:-----|:--------|
| [handoffs/latest_handoff.md](handoffs/latest_handoff.md) | Last session state, next actions |

---

## Phase → Document Mapping

| Phase | Documents to Read |
|:------|:------------------|
| **Q: Foundation** | BRD §5, [config-system.md](backend/config-system.md), [docker.md](infrastructure/docker.md), [context-caching.md](backend/context-caching.md) |
| **R: Multi-Country** | [screen-0-onboarding.md](frontend/screen-0-onboarding.md), [screen-2-population-sampling.md](frontend/screen-2-population-sampling.md), [config-system.md](backend/config-system.md) |
| **S: Screen 1** | [screen-1-knowledge-graph.md](frontend/screen-1-knowledge-graph.md) |
| **T: Simulation** | [screen-3-simulation.md](frontend/screen-3-simulation.md), [controversy-boost.md](backend/controversy-boost.md), [metrics-heuristics.md](backend/metrics-heuristics.md) |
| **U: Report+Chat** | [screen-4-report-chat.md](frontend/screen-4-report-chat.md), [metrics-heuristics.md](backend/metrics-heuristics.md) |
| **U2: Analytics** | [screen-5-analytics.md](frontend/screen-5-analytics.md), [metrics-heuristics.md](backend/metrics-heuristics.md) |
| **V: Memory** | [graphiti.md](infrastructure/graphiti.md) |
| **W: Polish** | All documents (E2E validation) |

---

## Paper MCP Mockup Reference

All UI designs exist as artboards in the Paper MCP file. Use `get_jsx(artboard_id)` to extract CSS/JSX structure.

| Screen | Artboard ID | Name |
|:-------|:------------|:-----|
| 0 | `8A-0` | Screen 0 — Onboarding Modal |
| 1 | `F6-0` | Screen 1 — Knowledge Graph (V2) |
| 2 | `H9-0` | Screen 2 — Population Sampling (V2) |
| 3 | `9U-0` | Screen 3 — Simulation (V2) |
| 4 (drawer) | `CZ-0` | Screen 4 — Report + Chat Drawer |
| 4 (split) | `NW-0` | Screen 5 — Report + Chat (Option A Split) |
| 5 (full chat) | `PN-0` | Screen 6 — Full Page Chat (Option C) |
| Viz components | `K5-0` | Report Metrics Visualizations |

---

## Archived V1 Documentation

All V1 documents are preserved in `archive/v1/` for reference:
- `archive/v1/BRD.md` — Original Singapore-only BRD
- `archive/v1/Progress.md` — V1 progress tracker (Phases A–O)
- `archive/v1/UserInput.md` — Original user requirements
- `archive/v1/architecture.md`, `decision_log.md` — V1 architecture notes
- `archive/v1/handoffs/latest_handoff.md` — Last V1 handoff
- `archive/v1/progress/` — All V1 phase files (phaseA–P)
