# MiroWorld V2 — Business Requirements Document

> Version: 2.2  
> Date: 2026-04-12  
> Status: Implemented, merged-main verified, and documentation-synchronized

This document describes the current V2 product and engineering contract. It supersedes earlier V2 planning language that still referenced separate Screen 6 behavior, generic policy kickoff posts, retired Gemini defaults, or V1-style use-case metrics.

## 1. Product Summary

MiroWorld V2 is a local-first, multi-use-case AI population simulation platform. The current shipped flow is:

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

Country availability, dataset download metadata, geography metadata, and filter contracts are loaded from `config/countries/*.yaml`.

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
- Country config/runtime metadata: YAML + backend country metadata service
- Country dataset readiness/download orchestration: backend country dataset service
- Simulation: native OASIS runner in Python 3.11
- Knowledge extraction: LightRAG-backed processing
- Memory: SQLite FTS5 over interactions, transcripts, and checkpoints for Screen 4 chat grounding
- Storage:
  - SQLite for sessions, session config, checkpoints, and simulation state
  - local files for uploads, exports, and run logs

### 3.2 Memory Runtime Contract

SQLite-backed retrieval is the live-memory backend for Screen 4 chat behavior.

Current dependency contract:

- session provider/model credentials must resolve from `console_sessions` or provider defaults

Current activation contract:

- live group and 1:1 agent chat route through SQLite FTS retrieval plus recent checkpoint/interactions context
- report chat uses the same underlying local memory/query context

Current ingestion contract:

- simulation interactions and checkpoints are persisted directly into SQLite
- FTS tables are maintained by triggers and queried at chat time
- no external graph database is required

### 3.3 Session Model

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
- `POST /api/v2/countries/{country}/download`
- `GET /api/v2/countries/{country}/download-status`
- `GET /api/v2/providers`
- `POST /api/v2/session/create`

Current Gemini defaults should prefer active models such as `gemini-2.5-flash-lite`, not retired `gemini-2.0-*` models.

Current live-mode rules:

- country selection is a Screen 0 UI decision, not a CLI/startup decision
- `GET /api/v2/countries` is the source of truth for dataset readiness in live mode
- if `dataset_ready=false` for the selected country, launch must remain blocked
- the user can trigger a dataset download from Screen 0 through the backend download endpoints
- if the backend reports `huggingface_api_key_missing`, the UI should instruct the user to add `HUGGINGFACE_API_KEY` to the root `.env` and restart the backend

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

Current country/geography rules:

- geography filters are derived from the selected country YAML, not from hard-coded backend lists
- Singapore uses `planning_area`
- United States uses `state`
- sampler and relevance parsing must respect the configured country geography field instead of mixing country-specific field names in generic logic

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
- support group chat and 1:1 agent chat with per-metric filtering
- export the report to DOCX

Current report payload:

- `status`
- `executive_summary`
- `metric_deltas`
- `quick_stats`
- `sections`
- `insight_blocks` (legacy — still in payload but not prominently rendered)
- `preset_sections`

Current rendering rules:

- agents should be displayed by name wherever possible
- metric cards show `initial -> final` display values
- yes/no metrics are normalized to percentages
- markdown formatting should be stripped before display
- chat-only is a Screen 4 view state, not a separate routed Screen 6

Chat metric selector:

- a `MetricSelector` dropdown above the chat panel lets the user filter group chat by a specific analysis question
- "All (Aggregate)" uses checkpoint extreme scoring for group chat: minimum score across metrics for dissenters, maximum score across metrics for supporters
- per-metric mode ranks agents by their score on the selected question only
- open-ended questions are excluded from the dropdown
- the selected metric is passed as `metric_name` in the group chat request body
- in live mode, the supporters/dissenters chip row is fetched from `GET /chat/group/agents`, which uses the same backend selector as the actual group-chat request

Current memory behavior:

- live group chat and live 1:1 agent chat use SQLite-backed retrieval from interactions, transcripts, and checkpoints
- report chat uses the same local evidence store and provider-aware runtime config
- no external graph database is required for current local or Docker flows

### 4.6 Screen 5 — Analytics

Purpose:

- show polarization over time
- show opinion migration
- show demographic sentiment slices
- show key opinion leaders and viral discussions

Metric selector:

- a `MetricSelector` dropdown below the page header lets the user filter analytics by a specific analysis question
- polarization, opinion flow, and the demographic sentiment map all respond to the selected metric
- the demographic sentiment map always calls `GET /analytics/agent-stances`; aggregate mode simply omits `metric_name`
- KOL and viral posts remain metric-agnostic (influence is about engagement, not opinion)
- open-ended questions are excluded from the dropdown

Demographic sentiment map:

- when a metric is selected, the frontend calls `GET /analytics/agent-stances?metric_name=...`
- the returned per-agent scores are mapped to sentiment overrides: `>= 7` positive, `< 5` negative, else neutral
- these overrides replace the default agent sentiment for the demographic grid rendering

Current behavior:

- live mode reads from analytics endpoints and shows empty/error states if data is missing
- demo mode can still fall back to local constants
- KOL and viral-post displays should use agent names and viewpoint summaries, not raw serial ids

## 5. Verification Snapshot

As of 2026-04-12, merged main was verified with:

- a full live browser flow using `ollama` + `qwen3:4b-instruct-2507-q4_K_M`, starting from Screen 0 and progressing through knowledge extraction, population sampling, simulation, report/chat, and analytics
- a targeted browser verification of the Screen 0 dataset-readiness contract, proving that launch is disabled while `dataset_ready=false`, that the UI calls the country download endpoints, and that launch re-enables once the country reports `dataset_ready=true`

Provider caveat:

- Gemini live extraction was rate-limited during verification on this machine. This is an external provider quota/runtime issue, not the Screen 0 country-dataset contract.

## 6. Canonical Prompt Configuration

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

## 7. API Contract

### 7.1 Session and Setup

- `GET /api/v2/countries`
- `POST /api/v2/countries/{country}/download`
- `GET /api/v2/countries/{country}/download-status`
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
- `GET /api/v2/console/session/{id}/chat/group/agents?segment=&metric_name=&top_n=` — live supporter/dissenter roster
- `POST /api/v2/console/session/{id}/chat/group`
- `POST /api/v2/console/session/{id}/chat/agent/{agent_id}`

### 6.5 Analytics

- `GET /api/v2/console/session/{id}/analytics/polarization?metric_name=` — optional per-metric filter
- `GET /api/v2/console/session/{id}/analytics/opinion-flow?metric_name=` — optional per-metric filter
- `GET /api/v2/console/session/{id}/analytics/influence` — metric-agnostic
- `GET /api/v2/console/session/{id}/analytics/cascades` — metric-agnostic
- `GET /api/v2/console/session/{id}/analytics/agent-stances?metric_name=` — per-agent scores for demographic map

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

### 7.3 Checkpoint Metric Answers

Checkpoint records are stored in `simulation_checkpoints` with `checkpoint_kind` values of `"baseline"` or `"final"`. Each record contains a `stance_json` blob with a `metric_answers` dictionary keyed by `metric_name`.

Values are free-text LLM responses, not clean numbers:

```json
{
  "approval_rate": "7/10. I think the policy has merit but needs refinement.",
  "policy_viewpoints": "I support the housing subsidy but oppose the transport levy...",
  "approval_of_initiatives": "No"
}
```

The backend `_extract_metric_score()` method parses these into numeric values:

| Input pattern | Parsed value |
|:-------------|:-------------|
| `"7/10"`, `"7/10. I think..."` | `7.0` |
| `"6.5"` | `6.5` |
| `"Yes"` | `10.0` |
| `"No"` | `1.0` |
| Free text with no leading number | `None` (excluded from scoring) |

### 7.4 Stance Thresholds

All analytics and chat selection use consistent thresholds:

| Score range | Stance |
|:-----------|:-------|
| `>= 7` | supporter |
| `>= 5` and `< 7` | neutral |
| `< 5` | dissenter |

### 7.5 Aggregate vs Per-Metric Scoring

When `metric_name` is omitted (aggregate mode):

- **Opinion flow and polarization**: compute the average of all parseable metric scores per agent from checkpoint data
- **Group chat agent selection**: use the minimum score (for dissenters) or maximum score (for supporters) across all metrics, so that an agent who dissents on *any* question is captured
- **Demographic map stances**: use the checkpoint-based average

When `metric_name` is provided:

- All endpoints score agents using only the specified metric from checkpoint data

Legacy `opinion_pre` / `opinion_post` fields on the agents table are no longer used by analytics or chat. They may still be stale from earlier implementations.

### 7.6 Agent Stances Response

`GET /analytics/agent-stances` returns:

```json
{
  "session_id": "session-819ca44a",
  "metric_name": "approval_rate",
  "score_field": "checkpoint_approval_rate",
  "stances": [
    {
      "agent_id": "agent-0001",
      "score": 7.0,
      "planning_area": "Hougang",
      "age_group": "",
      "archetype": ""
    }
  ]
}
```

## 8. Compatibility Notes

- Canonical V2 ids are used everywhere new state is written.
- `guiding_prompt` is still accepted by some backend methods for compatibility but is no longer the user-facing analysis primitive.
- SQLite is the live memory backend, and the legacy `graphiti_context_used` field remains only for response compatibility.
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
- [graphiti.md](infrastructure/graphiti.md) (historical note only)
