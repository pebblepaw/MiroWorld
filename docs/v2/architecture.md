# McKAInsey V2 — Architecture

> Living document for the current implemented V2 stack.

## 1. Runtime Topology

```text
Browser
  └─ React/Vite frontend
      └─ FastAPI backend
          ├─ ConfigService
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
- FalkorDB + Graphiti for temporal memory
- Zep compatibility fallback when explicitly configured

## 2. Primary Data Flow

### Stage 0: Onboarding

- frontend creates a V2 session
- backend normalizes provider/use-case ids
- backend seeds `session_configs.analysis_questions` from YAML

### Stage 1: Knowledge Extraction

- documents enter through upload, scrape, or paste
- Screen 1 loads session-scoped analysis questions
- custom question metadata is inferred via `QuestionMetadataService`
- extraction persists a merged knowledge artifact

### Stage 2: Population Sampling

- dynamic filters are inferred from the selected country dataset
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

### Stage 5: Analytics

- analytics endpoints normalize the same simulation artifacts into:
  - polarization
  - opinion flow
  - influence leaders
  - cascades / viral posts

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

- polarization time series
- opinion flow buckets and transitions
- influence leaders with names and viewpoint summaries
- cascades / viral posts with author names and nested comments

## 5. Compatibility Layers Still Present

- use-case aliases from V1 ids to canonical V2 ids
- `guiding_prompt` as a backend compatibility field
- `report/full` and `report/generate` aliases that now return the V2 report structure
- Zep fallback inside `MemoryService`

These exist to keep older flows from breaking, not to define new product behavior.
