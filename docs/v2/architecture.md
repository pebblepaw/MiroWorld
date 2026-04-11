# MiroWorld V2 — Architecture

> Living document for the current implemented V2 stack. Last updated 2026-04-12.

## 1. Runtime Topology

```text
Browser
  └─ React/Vite frontend
      └─ FastAPI backend
          ├─ ConfigService
          ├─ CountryMetadataService
          ├─ CountryDatasetService
          ├─ ConsoleService
          ├─ LightRAGService
          ├─ SimulationService
          ├─ MetricsService
          ├─ ReportService
          ├─ MemoryService
          └─ SQLite + local filesystem
                ├─ session configs
                ├─ uploaded docs
                ├─ simulation artifacts
                ├─ checkpoint records
                └─ report exports
```

Optional backing systems:

- OASIS Python 3.11 runtime for live simulation
- SQLite FTS5 retrieval for report/group/agent chat grounding

## 2. Primary Data Flow

### Stage 0: Onboarding

- frontend reads country readiness from `GET /api/v2/countries`
- frontend can trigger country downloads through:
  - `POST /api/v2/countries/{country}/download`
  - `GET /api/v2/countries/{country}/download-status`
- frontend creates a V2 session
- launch is blocked in live mode until the selected country reports `dataset_ready=true`
- backend normalizes provider/use-case ids
- backend seeds `session_configs.analysis_questions` from YAML
- backend rejects session creation or country changes when the selected country dataset is not ready

### Stage 1: Knowledge Extraction

- documents enter through upload, scrape, or paste
- Screen 1 loads session-scoped analysis questions
- custom question metadata is inferred via `QuestionMetadataService`
- extraction persists a merged knowledge artifact

### Stage 2: Population Sampling

- dynamic filters are inferred from the selected country dataset
- geography field selection is country-specific and YAML-driven
- Singapore uses `planning_area`; USA uses `state`
- parser/sampler/relevance logic normalize geography through country metadata instead of hard-coded country lists
- token estimates are computed from model/provider settings
- sampled personas are stored as the cohort for the session

### Stage 3: Simulation

- OASIS runs against the selected cohort and document context
- initial discussion seed posts come from the session’s analysis questions
- checkpoint answers populate `metric_answers`
- simulation state and interactions are streamed/polled back to the frontend

### Stage 4: Report + Chat

- `ReportService` resolves session-scoped analysis questions first
- quantitative questions generate metric deltas
- all questions generate report sections
- insight blocks and preset sections are derived from the active YAML
- chat uses real simulation context plus memory/document context
- a shared `MetricSelector` component filters by analysis question (per-metric or aggregate)
- group chat participant selection uses checkpoint-based extreme scoring (min for dissenters, max for supporters)

### Stage 5: Analytics

- analytics endpoints normalize checkpoint and interaction data into:
  - polarization (metric-aware)
  - opinion flow (metric-aware)
  - agent stances (metric-aware)
  - influence leaders (metric-agnostic)
  - cascades / viral posts (metric-agnostic)
- the `MetricSelector` filters polarization, opinion flow, and demographic sentiment map
- all scores are parsed from free-text `metric_answers` via `_extract_metric_score()`

## 3. State Ownership

### Frontend

`AppContext` is the main runtime store for:

- session id and onboarding config
- uploaded files
- analysis questions
- knowledge artifact
- population artifact
- sampled agents
- simulation round count and feed posts
- chat history
- Screen 0 country/provider/model/use-case choices

This is why navigating backward within the same session should no longer wipe the Screen 3 feed.

### Backend

The backend stores:

- session lifecycle in `console_sessions`
- V2 runtime config in `session_configs`
- checkpoint records
- interactions and report state
- token usage counters

## 4. Canonical Runtime Contracts

### Session Config

`session_configs` is the canonical V2 runtime configuration table. `analysis_questions` inside this table is the first lookup point for:

- Screen 1 display
- checkpoint metric generation
- report section generation
- report metric cards

Country dataset readiness is not persisted in `session_configs`; it is derived from selected-country YAML metadata plus the local/downloaded dataset state.

### Country Readiness Payload

`GET /api/v2/countries` returns the live Screen 0 contract:

- `dataset_ready`
- `download_required`
- `download_status`
- `download_error`
- `missing_dependency`

This payload is the source of truth for whether Screen 0 may create a live session.

### Report Payload

The current Screen 4 payload contains:

- `executive_summary`
- `metric_deltas`
- `quick_stats`
- `sections`
- `insight_blocks`
- `preset_sections`

### Analytics Payloads

The frontend expects normalized payloads for:

- **polarization**: time series with `polarization_index`, `severity`, `by_group_means`, `group_sizes` per round
- **opinion flow**: flow matrix with initial/final bucket counts and transition bands (supporter/neutral/dissenter)
- **agent stances**: per-agent `{agent_id, score, geography_value, age_group, archetype}`-style payloads with `score_field` indicating data source (`checkpoint_{metric}` or `aggregate_avg`), while preserving country-specific geography fields such as `planning_area` or `state`
- **influence**: top influencers with `name`, `influence_score`, `top_view`, `top_post`
- **cascades**: viral posts with `author_name`, `stance`, `content`, `comments`, `engagement_score`, `tree_size`

Stance thresholds: ≥ 7 supporter, 5–6 neutral, < 5 dissenter. See `backend/metrics-heuristics.md` for full scoring documentation.

## 5. Checkpoint Scoring Pipeline

The checkpoint scoring pipeline is central to analytics and chat:

1. OASIS simulation writes `metric_answers` (free-text LLM responses) into `simulation_checkpoints`
2. `_extract_metric_score()` parses text → numeric 1–10 scale (handles "7/10", "Yes"/"No", plain numbers)
3. Per-metric mode: scores come from `metric_answers[metric_name]`
4. Aggregate mode: scores are averaged across all parseable metrics per agent
5. Group chat extreme mode: uses min (dissenters) or max (supporters) across all metrics

The legacy `opinion_pre`/`opinion_post` fields on the `agents` table are always 10.0 and serve only as a last-resort fallback when no checkpoint data exists.

## 6. Compatibility Layers Still Present

- use-case aliases from V1 ids to canonical V2 ids
- `guiding_prompt` as a backend compatibility field
- `report/full` and `report/generate` aliases that now return the V2 report structure
- `graphiti_context_used` as a legacy response field that now remains `false`
- `opinion_pre`/`opinion_post` fallback when no checkpoint records exist

These exist to keep older flows from breaking, not to define new product behavior.

## 7. Verification Notes

Merged `main` was verified on 2026-04-12 with:

- a full live browser run using `ollama` + `qwen3:4b-instruct-2507-q4_K_M`
- a browser-level Screen 0 dataset-readiness/download verification with mocked country readiness transitions

Observed provider caveat:

- Gemini live extraction failed during verification because the configured Gemini key hit provider rate limits
- treat that as an upstream provider/runtime issue, not as evidence that the Screen 0 country-dataset contract is broken
