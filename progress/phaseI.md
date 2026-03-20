# Phase I — Screen 2 Sampling Logic & Agent Graph Planning

## Goal
Design the Stage 2 population sampling system for the new frontend before implementation, including the sampling modes, document-to-persona matching pipeline, the free-text control box, repeatable re-sampling, and the Stage 2 agent graph styling.

## Current Status
Planning in progress. The Screen 2 product shape is now defined, but no implementation changes have been made in this phase yet.

## Real Data Source For Screen 2
- Screen 2 should use the local bundled Singapore dataset in:
  - `backend/data/nemotron/data/*.parquet`
- This local parquet exposes the fields Screen 2 can reliably match today:
  - `professional_persona`
  - `sports_persona`
  - `arts_persona`
  - `travel_persona`
  - `culinary_persona`
  - `persona`
  - `cultural_background`
  - `skills_and_expertise`
  - `skills_and_expertise_list`
  - `hobbies_and_interests`
  - `hobbies_and_interests_list`
  - `career_goals_and_ambitions`
  - `sex`
  - `age`
  - `marital_status`
  - `education_level`
  - `occupation`
  - `industry`
  - `planning_area`
  - `country`
- The Screen 2 design should therefore target the local Singapore parquet first, not any generic fallback dataset shape.

## Planning Decisions

### Recommended Sampling Modes
- `Affected Groups`
  - Purpose: bias the sample toward the people most likely to be affected by the uploaded document.
  - Use case: education policy, transport policy, labor policy, housing policy, campaign targeting.
- `Population Baseline`
  - Purpose: produce a representative Singapore-wide baseline sample without strong document weighting.
  - Use case: quantify how broad the issue really is across the general population.

### Recommended Default
- Default the mode to `Affected Groups`.
- Reason:
  - most operators are using McKAInsey to understand reaction among the people most touched by a proposal
  - `Population Baseline` is still essential, but it works better as an explicit comparison mode than as the default first sample

### Recommended Product Shape
- Use a Screen 2 mode toggle:
  - `Affected Groups`
  - `Population Baseline`
- Keep the existing agent count selector and make it fully functional.
- Add a free-text `Sampling Instructions` box instead of many rigid demographic toggles.
- Allow `Generate Agents` to be clicked repeatedly:
  - same settings
  - new random seed
  - fresh cohort preview each time
- Expose the active sample seed back to the user so a cohort can be reproduced if needed.

### Recommended Retrieval And Scoring Pipeline
1. Build a Stage 2 query profile from:
   - Screen 1 `facet_kind` nodes
   - Screen 1 document-native entities
   - document summary
   - optional `Sampling Instructions` free-text box
2. Parse the `Sampling Instructions` box with an LLM into:
   - hard filters
   - soft boosts
   - exclusions
   - desired distribution hints
3. Candidate retrieval:
   - exact / range filtering over structured Nemotron fields
   - BM25 over list and short-text fields
   - semantic reranking over long text fields for top candidates
4. Sampling mode logic:
   - `Affected Groups`: weighted sample by document relevance
   - `Population Baseline`: representative stratified sample with minimal relevance weighting
5. Resampling:
   - same configuration
   - new seed
   - new selected cohort

## Recommended Retrieval Layers In Detail

### Structured First-Pass Retrieval
- Do not use BM25 or semantic search as the first pass for categorical Singapore fields.
- Use direct normalized matching first for:
  - `planning_area`
  - `sex`
  - `age`
  - `marital_status`
  - `education_level`
  - `occupation`
  - `industry`
- This first pass should be transparent and explainable:
  - exact match
  - alias-normalized match
  - age-range inclusion

### BM25 Mid-Pass
- Use BM25 after structured filtering for:
  - `skills_and_expertise_list`
  - `hobbies_and_interests_list`
  - short free-text persona summaries
  - parsed user instruction phrases
- This is the right place to match document-native entities that are not strict demographic facets.
- Example:
  - an education policy mentioning tutoring, schools, or exams may not map to a single categorical field, but it may surface through occupation, skills, hobbies, and short persona text.

### Semantic Rerank
- Use semantic reranking only after a bounded shortlist exists.
- Long-text fields for reranking:
  - `professional_persona`
  - `persona`
  - `cultural_background`
  - `skills_and_expertise`
  - `career_goals_and_ambitions`
- This rerank stage should improve precision, not replace the auditable structured path.

## Recommended Query Profile Shape
- The Stage 2 query profile should have four parallel sections:
  - `graph_facets`
  - `document_entities`
  - `document_summary`
  - `sampling_instructions`
- `graph_facets` should remain the most trusted source for hard filters and high-confidence boosts.
- `document_entities` should enrich retrieval when the document mentions stakeholder groups, institutions, or issues that are not direct categorical facets.
- `sampling_instructions` should be allowed to override or refine the automatic graph-derived intent.

## Recommended Sampling Instructions Parser
- The `Sampling Instructions` box should be parsed by an LLM into a structured object with:
  - `hard_filters`
  - `soft_boosts`
  - `soft_penalties`
  - `exclusions`
  - `distribution_targets`
  - `notes_for_ui`
- Example supported instructions:
  - "Bias toward younger teachers and parents in the north-east"
  - "Avoid over-concentrating on a single planning area"
  - "Include some retirees as a comparison group"
- The parsed result should be shown back to the user as readable rationale or chips before or after generation, so the operator can see what the system inferred.

## Why This Retrieval Stack Is Recommended

### Structured Fields
- Do not use semantic search as the first-pass retrieval for controlled categorical columns.
- Use direct normalized matching first for:
  - age
  - planning area
  - sex
  - education level
  - marital status
  - occupation
  - industry

### BM25 Layer
- BM25 is useful for:
  - hobbies / interests
  - skills / expertise
  - short persona text
  - parsed user sampling instructions
- It is also easier to audit than a purely semantic first pass.

### Semantic Layer
- Use semantic reranking after the exact/BM25 shortlist, not as the only retrieval stage.
- This keeps Stage 2:
  - faster
  - more transparent
  - easier to debug

## Recommended Scoring Logic

### Affected Groups Mode
- Score each candidate with weighted components:
  - graph facet alignment
  - document-native entity overlap
  - BM25 match score
  - semantic rerank score
  - optional user instruction boosts
- Then sample stochastically from the top candidate pool to avoid deterministic repetition.
- This mode should intentionally over-represent the people likely to care the most about the document, while still preserving visible diversity within that affected slice.

### Population Baseline Mode
- Use a representative sampler first.
- Relevance score becomes secondary or diagnostic only.
- The result should answer:
  - how many Singaporeans appear affected
  - whether the issue is narrow or broad
- This mode should draw from the Singapore dataset using stratified population balancing over:
  - `planning_area`
  - age buckets
  - `sex`
  - optionally `education_level` when sample size is large enough

## Recommended UI For Screen 2
- Controls:
  - agent count selector
  - sample mode toggle
  - sampling instructions text box
  - `Generate Agents`
  - `Re-sample`
- Behavior:
  - `Generate Agents` should create the first live cohort for the current configuration
  - `Re-sample` should keep the same configuration but generate a new seed and fresh cohort
  - the count selector must actually drive backend sample size
- Output panels:
  - sampled cohort summary
  - representativeness diagnostics
  - selection rationale
  - styled agent graph

## Agent Graph Styling
- Reuse the Screen 1 graph treatment:
  - small nodes with external labels
  - size by importance / centrality
  - visible edge lines
  - optional edge-label toggle
  - clear legend derived from actual node colors
- Stage 2 graph nodes should represent sampled personas, not abstract policy entities.
- Stage 2 edge logic should start simple and auditable:
  - shared planning area
  - shared occupation / industry
  - shared issue relevance clusters
- Avoid inventing opaque social edges before Stage 3 produces real interaction data.
- Stage 2 graph should feel like the Screen 1 graph’s population equivalent, not a different visualization language.

## Proposed Screen 2 Data Contract
- `candidate_count`
- `sample_count`
- `sample_mode`
- `sample_seed`
- `parsed_sampling_instructions`
- `coverage`
- `representativeness`
- `sampled_personas`
- `agent_graph`
- `selection_reason` per sampled persona

## Recommended Selection Reason Format
- Each sampled persona should carry a structured explanation:
  - `matched_facets`
  - `matched_document_entities`
  - `instruction_matches`
  - `bm25_terms`
  - `semantic_summary`
  - `selection_score`
- The goal is not only to sample a cohort, but to make the cohort explainable to the operator.

## Tasks
- [x] I1 Define Stage 2 product modes and retrieval strategy
- [x] I2 Define the Stage 2 UI control strategy
- [x] I3 Define the recommended Stage 2 scoring stack
- [x] I4 Lock the local Singapore Nemotron parquet schema as the Screen 2 data source
- [ ] I5 Implement backend candidate retrieval and scoring
- [ ] I6 Implement Screen 2 control panel wiring
- [ ] I7 Implement repeatable re-sampling with seed changes
- [ ] I8 Implement Stage 2 agent graph rendering
- [ ] I9 Add Screen 2 live verification and tests

## Open Questions
- Whether Screen 2 should ship with only two modes first, or expose a later third `Blended` mode after the first stable version.
- Whether the parsed `Sampling Instructions` should be shown back to the user as editable chips before sampling runs, or as a read-only parsed summary for the first release.
- Whether `Population Baseline` should use only dataset-proportional balancing first, or whether it should also expose a later "uniform by bucket" diagnostic mode for stress-testing.

## Recommended Next Actions
1. Lock the Stage 2 mode toggle to:
   - `Affected Groups`
   - `Population Baseline`
2. Keep `Affected Groups` as the default first-generation mode.
3. Implement the count selector and repeated re-sampling first.
4. Add the free-text `Sampling Instructions` box with an LLM parser that outputs structured boosts/filters.
5. Build the exact → BM25 → semantic rerank pipeline against the local Singapore Nemotron parquet in `backend/data/nemotron/data/*.parquet`.
6. Style the Stage 2 agent graph using the same graph language as Screen 1.
