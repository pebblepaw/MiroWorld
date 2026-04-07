# McKAInsey V2 — Latest Handoff

> Date: 2026-04-07  
> Status: Current implementation snapshot

## 1. Current System State

The V2 flow is implemented and has been manually and automatically exercised through the main screens. The system now uses:

- canonical V2 use-case ids
- session-scoped `analysis_questions`
- current Gemini defaults in onboarding/provider selection
- analysis-question seed posts for new simulations
- V2 report payloads on Screen 4
- live analytics normalization on Screen 5

## 2. Key Fixes Landed In The Latest Pass

### Screen 1

- preset questions now load from the active session instead of raw YAML only
- custom question edits persist through `PATCH /api/v2/session/{id}/config`
- custom questions generate normalized metadata through `QuestionMetadataService`
- live extraction errors are surfaced as short provider/runtime messages

### Screen 3

- OASIS runtime falls back to the project Python 3.11 environment when the configured interpreter is invalid
- generic kickoff threads are removed from new simulation seeding
- analysis questions are the initial discussion threads
- long traceback/process dumps are no longer shown directly in the UI
- simulation feed state survives navigation back to Screen 1

### Screen 4

- report sections resolve from session-scoped analysis questions
- quantitative cards now display `initial -> final`
- yes/no metrics render as percentages
- agent evidence includes names
- report text is cleaned before display so raw markdown markers do not leak through
- chat uses the real backend path and document context

### Screen 5

- KOL and viral-post cards now prefer names and top-viewpoint summaries
- structured `top_post` payloads are normalized properly
- live mode shows incomplete-data warnings instead of silently masking missing analytics

## 3. Known Compatibility Notes

- older sessions created before the Screen 3 seeding fix may still contain stored kickoff posts in their historical data
- `guiding_prompt` is still accepted in some backend paths for extraction compatibility, but `analysis_questions` is the real V2 runtime contract
- Graphiti is preferred, but Zep compatibility code still exists in memory services

## 4. Validation Baseline

The latest implementation pass already verified:

- targeted backend regression suites
- targeted frontend regression suites
- frontend production build
- live report generation / DOCX export / chat path

Before future changes are declared complete, rerun the targeted tests relevant to the touched area and confirm the live screen flow if behavior changed.
