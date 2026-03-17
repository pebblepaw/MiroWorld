# Phase A - Data Pipeline & LightRAG Integration

## Goal
Implement local Mode 1 persona data access (HuggingFace streaming + DuckDB over HF parquet), plus LightRAG processing with Zep Cloud logging.

## Current Status
Completed (Mode 1)

## Tasks
- [x] A1.1 Set up backend code scaffold
- [x] A2.1 Create persona sampler service with streaming mode
- [x] A2.2 Add DuckDB filtering mode against HF parquet
- [x] A3.1 Add LightRAG processing service
- [x] A3.2 Add Zep Cloud event logging integration hook
- [x] A2.4 Add initial automated tests
- [x] A2.3 Validate API behavior against live Nemotron data
- [x] A3.4 Validate document -> graph -> demographic query with real Gemini key

## Completed Work
- Added `backend/` package with FastAPI app and endpoints.
- Added persona sampling API and service for `stream` and `duckdb` modes.
- Added LightRAG async service for insert/query.
- Added Zep Cloud logging helper for simulation-scoped memory events.
- Added initial test coverage for health endpoint and sampler filtering logic.
- Converted `Sample_Inputs/fy2026_budget_statement.pdf` into markdown for reusable demo input.
- Added default demo document support in `POST /api/v1/phase-a/knowledge/process`.

## Open Issues
- OASIS package compatibility and runtime strategy remains for Phase B.

## Decisions Made
- Support both canonical and legacy env variable names: `GEMINI_API_KEY|GEMINI_API`, `ZEP_API_KEY|ZEP_CLOUD`.
- Phase A uses Mode 1 only; no S3/Lambda provisioning in implementation path.

## Next Actions
1. Start Phase B by selecting/installing OASIS runtime package and building two-stage simulation flow.
2. Add DB schema for Stage 3a and Stage 3b outputs.
3. Integrate persona sample output from Phase A into Phase B agent loading.

## Evidence
- `pip install -e .[dev]` succeeded in `backend/`.
- `pytest -q` result: `3 passed, 2 warnings`.
- Live Mode 1 sampling check succeeded: `count=2` from `nvidia/Nemotron-Personas-Singapore` with Woodlands filter.
- Live LightRAG smoke succeeded: document processed, entities/relations extracted, and demographic context query returned with `ok=True`.
- Converted markdown file created: `Sample_Inputs/fy2026_budget_statement.md` (3178 lines).
- Full budget doc LightRAG ingest succeeded with `summary_ok=True` and `demographic_ok=True`.
- Latest backend tests after demo-default endpoint addition: `4 passed, 2 warnings`.
