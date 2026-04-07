# Implementation Tasks

## Phase 1: Config YAML Files
- [x] Delete old config files (policy-review, ad-testing, customer-review, product-market-fit)
- [x] Create `config/prompts/public-policy-testing.yaml`
- [x] Create `config/prompts/product-market-research.yaml`
- [x] Create `config/prompts/campaign-content-testing.yaml`

## Phase 2: Backend Services
- [x] Update `config_service.py` — rename methods, add new ones
- [x] Create `question_metadata_service.py` — LLM metric generation
- [x] Update `metrics_service.py` — new insight block methods + selective activation
- [x] Update `report_service.py` — analysis_questions-based report structure
  - [x] Rewrite `build_v2_report` to use analysis_questions, insight_blocks, preset_sections
  - [x] Add `_resolve_analysis_questions`, `_resolve_insight_blocks`, `_resolve_preset_sections`
  - [x] Add `_compute_metric_value`, `_agents_from_checkpoint`
  - [x] Add `_build_v2_executive_summary_from_metrics`

## Phase 3: Backend Routes
- [x] Add `POST /api/v2/questions/generate-metadata` route
- [x] Add `GET /api/v2/session/{id}/analysis-questions` route
- [x] Update report route to use new structure (already wired to ReportService)

## Phase 4: Frontend — Screen 1
- [x] Update `PolicyUpload.tsx` — Analysis Questions card list replaces Guiding Prompts textarea
- [x] Update `AppContext.tsx` — `AnalysisQuestion` type + state management
- [x] Update `console-api.ts` — V2 use case normalization + new API functions

## Phase 5: Frontend — Screen 4
- [x] Update `ReportChat.tsx` — `formatUseCase` for V2 names
- [x] Add metric delta cards rendering (grid with directional arrows)
- [x] Add analysis question sections rendering (type badges + metric spotlight)
- [x] Add insight blocks rendering with `InsightBlockData` sub-component
- [x] Add preset sections rendering
- [x] Add legacy fallback for V1 report structure
- [x] Remove unused `initialApproval`/`finalApproval` variables

## Phase 6: Frontend — Screen 0 / Screen 3
- [x] Update `OnboardingModal.tsx` — 3 V2 use cases with icons
- [x] Update `Analytics.tsx` — V2 use case names with backward compat

## Phase 7: Documentation
- [x] Update `BRD_V2.md` — use cases, config structure, analysis_questions schema
- [x] Update `screen-0-onboarding.md` — V2 use case selector
- [x] Update `screen-1-knowledge-graph.md` — Analysis Questions card list
- [x] Update `screen-4-report-chat.md` — V2 report structure (metric deltas, insight blocks, preset sections)
- [x] Update `config-system.md` — V2 YAML schema, ConfigService methods, USE_CASE_MAP
- [x] Update `metrics-heuristics.md` — V2 per-use-case metric definitions
