# Task Plan - Phase A Implementation

## Goal
Deliver Phase A end-to-end for local development mode (HuggingFace streaming + DuckDB on HF parquet) with LightRAG processing and Zep Cloud logging.

## Constraints
- Use Mode 1 from BRD data access strategy.
- Keep documentation synchronized (`Progress.md`, `progress/index.md`, `progress/phaseA.md`, handoff).
- Attempt git push after phase completion.

## Assumptions
- `.env` contains valid Gemini and Zep Cloud credentials.
- Python 3.11+ environment is available.

## Checklist
- [x] Scaffold backend package structure
- [x] Implement persona sampling service (stream + duckdb modes)
- [x] Implement LightRAG service for policy ingestion and demographic context retrieval
- [x] Implement Zep Cloud event logging hook
- [x] Expose Phase A API endpoints via FastAPI
- [x] Add tests for health and sampler filtering
- [ ] Install dependencies and run tests locally
- [ ] Update phase documentation with evidence
- [ ] Commit and push Phase A deliverables

## Verification Plan
- Run `pytest -q` in backend.
- Manual API smoke:
  - `GET /health`
  - `POST /api/v1/phase-a/personas/sample`
  - `POST /api/v1/phase-a/knowledge/process`
- Capture command outputs in `progress/phaseA.md` evidence section.
