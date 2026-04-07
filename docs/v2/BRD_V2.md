# McKAInsey V2 — Business Requirements Document

> Version: 2.1  
> Date: 2026-04-07  
> Status: Implemented and documentation-synchronized

This document describes the current V2 product and engineering contract. It supersedes earlier V2 planning language that still referenced separate Screen 6 behavior, generic policy kickoff posts, retired Gemini defaults, or V1-style use-case metrics.

## 1. Product Summary

McKAInsey V2 is a local-first, multi-use-case AI population simulation platform. The current shipped flow is:

1. Screen 0: configure country, provider, model, and use case
2. Screen 1: upload one or more source documents, review/edit analysis questions, and run knowledge extraction
3. Screen 2: sample the target population using country-specific dynamic filters
4. Screen 3: run the native OASIS social simulation
5. Screen 4: read the generated report and chat with simulated agents
6. Screen 5: inspect live analytics and viral discussion patterns

## 2. Canonical V2 Scope

### 2.1 Countries

- Singapore
- United States

Country availability and dataset/filter metadata are loaded from `config/countries/*.yaml`.

### 2.2 Canonical Use Cases

- `public-policy-testing`
- `product-market-research`
- `campaign-content-testing`

Legacy ids such as `policy-review`, `customer-review`, `reviews`, `ad-testing`, and `product-market-fit` are still accepted as backward-compatibility aliases, but all runtime state should normalize to the canonical V2 ids above.

### 2.3 Source of Truth for Analysis

The source of truth is no longer a user-facing guiding prompt. The runtime source of truth is the session-scoped `analysis_questions` array stored in `session_configs`.

Current rules:

- `create_v2_session` seeds `analysis_questions` from the canonical use-case YAML.
- Screen 1 edits persist back to `PATCH /api/v2/session/{id}/config`.
- Simulation checkpoint metrics, report sections, report metric cards, and analytics all consume the session-scoped questions first.
- `guiding_prompt` remains in the backend only as a compatibility field for extraction pipelines that still accept a summary focus string.

## 3. Current Architecture

### 3.1 Main Runtime Components

- Frontend: React + Vite + TypeScript
- Backend: FastAPI
- Simulation: native OASIS runner in Python 3.11
- Knowledge extraction: LightRAG-backed processing
- Memory: Graphiti preferred; Zep compatibility fallback still exists in `MemoryService`
- Storage:
  - SQLite for sessions, session config, checkpoints, and simulation state
  - local files for uploads, exports, and run logs
  - FalkorDB for Graphiti when enabled

### 3.2 Session Model

All user-visible runtime state is keyed by `session_id`.

`session_configs` currently stores:

- `country`
- `use_case`
- `provider`
- `model`
- `guiding_prompt` (compatibility only)
- `analysis_questions`
- `config_json`

The application should behave as if `analysis_questions` is the authoritative runtime contract.

## 4. Screen Contracts

### 4.1 Screen 0 — Onboarding

Purpose:

- choose country
- choose provider/model
- configure API key when required
- choose canonical use case
- create the V2 session

Current backend compatibility endpoint:

- `GET /api/v2/countries`
- `GET /api/v2/providers`
- `POST /api/v2/session/create`

Current Gemini defaults should prefer active models such as `gemini-2.5-flash-lite`, not retired `gemini-2.0-*` models.

### 4.2 Screen 1 — Knowledge Graph

Purpose:

- ingest documents from file upload, URL scrape, or pasted text
- fetch the session-scoped analysis questions
- allow the user to add, edit, and delete custom questions
- generate metadata for custom questions via `QuestionMetadataService`
- persist question changes back to the session config
- run knowledge extraction and question-metadata generation in parallel

Current behavior:

- preset questions come from the active session, not directly from raw YAML
- live extraction surfaces short provider/runtime errors instead of fabricating fallback data
- demo mode can still hydrate a cached artifact when the backend is unavailable

### 4.3 Screen 2 — Population Sampling

Purpose:

- derive sampling controls from the selected country dataset
- preview/filter the sampled cohort
- estimate token cost before simulation

Current contracts:

- `GET /api/v2/console/session/{id}/filters`
- `GET /api/v2/token-usage/{session_id}/estimate`

### 4.4 Screen 3 — Simulation

Purpose:

- run the live discourse simulation
- stream activity, metrics, and round progress
- expose the most active threads and aggregate counters

Current behavior:

- initial seed posts come from the analysis questions only
- the legacy generic “Policy Kick-Off” thread is obsolete for new runs
- controversy boost is currently a binary UI control mapped to `0.0` or `0.5`
- live failures surface compact explanatory messages on the frontend while full details remain in backend logs
- feed state is rehydrated from app context when navigating backward

### 4.5 Screen 4 — Report + Chat

Purpose:

- display the structured V2 report
- support report-only, split, and chat-only views inside the same page
- support group chat and 1:1 agent chat
- export the report to DOCX

Current report payload:

- `status`
- `executive_summary`
- `metric_deltas`
- `quick_stats`
- `sections`
- `insight_blocks`
- `preset_sections`

Current rendering rules:

- agents should be displayed by name wherever possible
- metric cards show `initial -> final` display values
- yes/no metrics are normalized to percentages
- markdown formatting should be stripped before display
- chat-only is a Screen 4 view state, not a separate routed Screen 6

### 4.6 Screen 5 — Analytics

Purpose:

- show polarization over time
- show opinion migration
- show demographic sentiment slices
- show key opinion leaders and viral discussions

Current behavior:

- live mode reads from analytics endpoints and shows empty/error states if data is missing
- demo mode can still fall back to local constants
- KOL and viral-post displays should use agent names and viewpoint summaries, not raw serial ids

## 5. Canonical Prompt Configuration

Prompt YAML files live in `config/prompts/`:

- `public-policy-testing.yaml`
- `product-market-research.yaml`
- `campaign-content-testing.yaml`

Each file defines:

- `system_prompt`
- `agent_personality_modifiers`
- `analysis_questions`
- `insight_blocks`
- `preset_sections`

For the current public-policy YAML, the canonical built-in questions are:

1. `Do you approve of this policy? Rate 1-10.`
2. `What specific aspects of this policy do you support or oppose, and why?`

Custom Screen 1 questions are appended at the session level and participate in simulation/report generation exactly like preset questions after metadata inference.

## 6. API Contract

### 6.1 Session and Setup

- `GET /api/v2/countries`
- `GET /api/v2/providers`
- `POST /api/v2/session/create`
- `PATCH /api/v2/session/{id}/config`
- `GET /api/v2/session/{id}/analysis-questions`
- `POST /api/v2/questions/generate-metadata`

### 6.2 Knowledge and Sampling

- `POST /api/v2/console/session/{id}/knowledge/process`
- `POST /api/v2/console/session/{id}/knowledge/upload`
- `POST /api/v2/console/session/{id}/scrape`
- `GET /api/v2/console/session/{id}/filters`
- `GET /api/v2/token-usage/{session_id}/estimate`

### 6.3 Simulation

- `POST /api/v2/console/session/{id}/simulate`
- `GET /api/v2/console/session/{id}/simulation/state`
- `GET /api/v2/console/session/{id}/simulation/metrics`
- `GET /api/v2/console/session/{id}/simulation/stream`

### 6.4 Report and Chat

- `GET /api/v2/console/session/{id}/report`
- `POST /api/v2/console/session/{id}/report/generate`
- `GET /api/v2/console/session/{id}/report/export`
- `POST /api/v2/console/session/{id}/chat/group`
- `POST /api/v2/console/session/{id}/chat/agent/{agent_id}`

### 6.5 Analytics

- `GET /api/v2/console/session/{id}/analytics/polarization`
- `GET /api/v2/console/session/{id}/analytics/opinion-flow`
- `GET /api/v2/console/session/{id}/analytics/influence`
- `GET /api/v2/console/session/{id}/analytics/cascades`

## 7. Data Contracts

### 7.1 V2 Report Response

```json
{
  "session_id": "session-1234",
  "generated_at": "2026-04-07T12:00:00Z",
  "executive_summary": "Summary text",
  "metric_deltas": [
    {
      "metric_name": "approval_rate",
      "metric_label": "Approval Rate",
      "metric_unit": "%",
      "initial_value": 61.0,
      "final_value": 73.0,
      "delta": 12.0,
      "direction": "up",
      "report_title": "Policy Approval",
      "initial_display": "61.0%",
      "final_display": "73.0%",
      "delta_display": "61.0% -> 73.0%"
    }
  ],
  "quick_stats": {
    "agent_count": 180,
    "round_count": 5,
    "model": "gemini-2.5-flash-lite",
    "provider": "google"
  },
  "sections": [],
  "insight_blocks": [],
  "preset_sections": []
}
```

### 7.2 Analysis Question Metadata

Current normalized question shape:

```json
{
  "question": "Would you buy this? (yes/no)",
  "type": "yes-no",
  "metric_name": "conversion_intent",
  "metric_label": "Conversion Intent",
  "metric_unit": "%",
  "report_title": "Conversion Analysis",
  "tooltip": "Percentage of agents expressing purchase intent."
}
```

## 8. Compatibility Notes

- Canonical V2 ids are used everywhere new state is written.
- `guiding_prompt` is still accepted by some backend methods for compatibility but is no longer the user-facing analysis primitive.
- Graphiti is the preferred memory backend, but Zep compatibility code still exists for deployments that explicitly configure it.
- Old sessions created before the Screen 3 seeding fix may still contain generic kickoff content in their stored interactions; new runs should not.

## 9. Validation Standard

Changes to V2 should be considered complete only when:

1. targeted backend and frontend tests pass
2. the frontend builds successfully
3. the flow works in live mode from Screen 0 through Screen 5
4. report export and chat operate against real session data

## 10. Linked Specs

### Frontend

- [screen-0-onboarding.md](frontend/screen-0-onboarding.md)
- [screen-1-knowledge-graph.md](frontend/screen-1-knowledge-graph.md)
- [screen-2-population-sampling.md](frontend/screen-2-population-sampling.md)
- [screen-3-simulation.md](frontend/screen-3-simulation.md)
- [screen-4-report-chat.md](frontend/screen-4-report-chat.md)
- [screen-5-analytics.md](frontend/screen-5-analytics.md)

### Backend

- [config-system.md](backend/config-system.md)
- [context-caching.md](backend/context-caching.md)
- [controversy-boost.md](backend/controversy-boost.md)
- [metrics-heuristics.md](backend/metrics-heuristics.md)

### Infrastructure

- [docker.md](infrastructure/docker.md)
- [graphiti.md](infrastructure/graphiti.md)
