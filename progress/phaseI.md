# Phase I — Screen 2 Sampling Logic & Agent Graph

## Goal
Implement Screen 2 on the Frontend V2 shell as a real, live cohort-generation stage backed by the local Singapore Nemotron parquet, explainable retrieval/scoring, repeatable re-sampling, and a production-grade agent graph.

## Current Status
Implemented locally and verified. Screen 2 is live on the Frontend V2 shell and is ready for operator review before Screen 3 work begins.

## Data Source Locked For Screen 2
- Screen 2 uses the local Singapore Nemotron parquet in:
  - `backend/data/nemotron/data/*.parquet`
- The retrieval/scoring path is built around the real local schema:
  - `planning_area`
  - `sex`
  - `age`
  - `marital_status`
  - `education_level`
  - `occupation`
  - `industry`
  - `skills_and_expertise_list`
  - `hobbies_and_interests_list`
  - long-text persona fields such as `professional_persona`, `persona`, `cultural_background`, `skills_and_expertise`, `career_goals_and_ambitions`
- The Screen 2 pipeline does not depend on a generic fallback HF shape.

## Implemented Product Shape

### Sampling Modes
- `Affected Groups`
  - default mode
  - biases toward the people most likely to be affected by the uploaded document and the operator’s instructions
- `Population Baseline`
  - representative comparison mode
  - uses stratified baseline sampling with relevance treated as secondary/diagnostic

### Controls
- Working `Number of Agents` selector
  - now aligned with the backend contract
  - capped at `500`
- Working `Sampling Mode` toggle
- Working `Sampling Instructions` textbox
- Working `Generate Agents`
- Working `Re-sample`
  - preserves the same configuration
  - generates a fresh seed
  - returns a fresh cohort preview
- Visible `Sample Seed`
  - cohort runs are now reproducible

### Output Panels
- `Candidate Pool`
- `Sample Size`
- `Sample Seed`
- `Age Distribution`
- `Industry Mix`
- `Top Planning Areas`
- `Parsed Instructions`
- `Selection Rationale`
- `Agent Graph`

## Retrieval And Scoring Stack

### 1. Candidate Retrieval
- Stage 2 first pulls a bounded candidate pool from the local parquet through structured filtering.
- Structured filter inputs currently support:
  - age ranges
  - planning areas
  - sex
  - marital status
  - education level
  - occupation
  - industry
- Candidate pools are capped for live interactivity:
  - `Affected Groups`: min `400`, max `1000`
  - `Population Baseline`: min `600`, max `1200`

### 2. Query Profile
- Stage 2 builds a query profile from:
  - Screen 1 graph facets
  - Screen 1 document-native entities
  - Screen 1 summary
  - optional sampling instructions
- Hidden Screen 1 noise nodes are excluded from the Stage 2 issue profile.
- Non-facet location nodes are excluded from `matched_document_entities` so foreign-location noise does not dominate rationale text.

### 3. BM25 Mid-Pass
- BM25 runs over:
  - short categorical/list fields
  - hobbies / interests
  - skills / expertise
  - short persona text fragments
- This provides a transparent lexical shortlist before semantic reranking.

### 4. Semantic Rerank
- Semantic rerank runs only on a bounded shortlist.
- Long-text fields used:
  - `professional_persona`
  - `persona`
  - `cultural_background`
  - `skills_and_expertise`
  - `career_goals_and_ambitions`
- Pool caps currently enforced:
  - shortlist max `300`
  - semantic rerank max `48`

## Sampling Instructions Parser

### Live Parser Behavior
- Parser path is now:
  - Gemini JSON parse first
  - fallback deterministic parser if Gemini is unavailable, errors, or returns notes-only / non-actionable output
- Structured parser output shape:
  - `hard_filters`
  - `soft_boosts`
  - `soft_penalties`
  - `exclusions`
  - `distribution_targets`
  - `notes_for_ui`

### Parser Normalization
- Unsupported fields from Gemini output are discarded rather than trusted.
- The parser now treats empty-but-successful Gemini output as insufficient and falls back to deterministic parsing.
- Unknown extra request fields on the Screen 2 preview route are now rejected instead of silently ignored.

### Current Deterministic Coverage
- Detects:
  - planning areas and regions
  - age-cohort language such as `young`, `younger`, `student`, `youth`, `elderly`, `senior`
  - common education-worker language
- Education-worker language now biases toward:
  - `industry = public_administration_education_services`
- This was added because Gemini sometimes returned only operator notes for education/family prompts, which was too weak for `Affected Groups` mode.
- `hobby` and `skill` instruction keys now match the real Nemotron list fields:
  - `hobbies_and_interests_list`
  - `skills_and_expertise_list`

## Sampling Modes In Practice

### Affected Groups
- Uses weighted cohort generation after scoring.
- Final score blends:
  - semantic relevance
  - BM25 relevance
  - structured/facet alignment
  - geographic relevance
  - socioeconomic relevance
  - digital relevance
  - explicit filter alignment
- Additional instruction buckets now actively affect ranking:
  - `soft_boosts`
  - `soft_penalties`
  - `exclusions`
  - `distribution_targets`
- Instructions are now visible in the scored rationale through:
  - `instruction_matches`
  - parsed-summary UI

### Population Baseline
- Uses stratified baseline sampling over:
  - planning area
  - sex
  - age bucket
- Relevance remains available for diagnostics and downstream comparison.

## Screen 2 Parsed Summary UI
- The parsed summary is now rendered as a read-only operator-facing view.
- It shows:
  - `Hard Filters`
  - `Soft Boosts`
  - `Exclusions`
  - `Distribution Targets`
- This replaced the earlier notes-only state and makes the parser behavior auditable in the UI.

## Screen 2 Agent Graph
- The Frontend V2 Stage 2 graph now follows the Screen 1 visual language:
  - small nodes
  - external labels
  - visible edges
  - optional edge-label toggle
  - legend derived from live graph categories
- Current edge reasons are intentionally simple and auditable:
  - shared planning area
  - shared industry
  - shared occupation

## Public Contract Implemented
- `PopulationPreviewRequest`
  - `agent_count`
  - `sample_mode`
  - `sampling_instructions`
  - `seed`
- `PopulationArtifactResponse`
  - `candidate_count`
  - `sample_count`
  - `sample_mode`
  - `sample_seed`
  - `parsed_sampling_instructions`
  - `coverage`
  - `sampled_personas`
  - `agent_graph`
  - `representativeness`
  - `selection_diagnostics`

## Verification

### Automated
- Backend:
  - `tests/test_console_routes.py`
  - `tests/test_persona_relevance_service.py`
  - `tests/test_llm_client.py`
- Frontend:
  - `src/pages/AgentConfig.test.tsx`
  - full `npm test`
  - `tsc --noEmit -p tsconfig.app.json`
  - `npm run build`

### Live
- Verified through `./quick_start.sh --mode live --real-oasis`
- Browser flow:
  1. upload real `CNA SHrinking Birth Rate.docx`
  2. complete Screen 1 extraction
  3. proceed to Screen 2
  4. generate a live 500-agent cohort
- Verified live Screen 2 outputs:
  - real candidate pool
  - live sample seed
  - parsed instruction summary
  - selection rationale cards
  - live agent graph

## Residual Notes
- Some documents can still surface document-native entity noise in Stage 2 rationale if the source article contains broad contextual references that are not fully hidden in Screen 1.
- The current deterministic parser covers the most important operator language for Screen 2, but it is intentionally conservative rather than attempting broad free-form inference.
- Screen 2 is ready for manual operator review before moving on to Screen 3.

## Tasks
- [x] I1 Define Stage 2 product modes and retrieval strategy
- [x] I2 Define the Stage 2 UI control strategy
- [x] I3 Define the Stage 2 scoring stack
- [x] I4 Lock the local Singapore Nemotron parquet schema as the Screen 2 data source
- [x] I5 Implement backend candidate retrieval, ranking, and sampling
- [x] I6 Implement Screen 2 control panel wiring
- [x] I7 Implement repeatable re-sampling with visible seeds
- [x] I8 Implement parsed-instruction summary rendering
- [x] I9 Implement Screen 2 agent graph styling and live integration
- [x] I10 Verify Screen 2 locally in automated and live flows
