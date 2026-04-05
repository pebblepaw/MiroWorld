# McKAInsey V2 — Latest Handoff

> **Date**: 2026-04-05
> **From**: Planning/Orchestrator Agent
> **To**: Coding Agent

## What Changed

### Documentation (Complete)
- Created full V2 documentation suite in `docs/v2/` (13 documents + index)
- Archived all V1 docs to `archive/v1/` (BRD, Progress, UserInput, phase files, handoffs)
- Created Paper MCP mockups for all 6 screens + analytics visualizations (8 artboards)

### Design Decisions (All Resolved)
- **Report layout**: 60/40 split with 3-way view toggle (Report Only / Report+Chat / Chat Only)
- **Visualizations**: Separate dedicated analytics screen (Screen 5)
- **Memory**: Graphiti + FalkorDB (local), Neo4j (AWS stretch)
- **Controversy boost**: 0.0–1.0 slider on `calculate_hot_score`
- **Token caching**: Gemini context caching (~75% savings)
- **Config**: All prompts/countries externalized to YAML
- **Export**: DOCX via `python-docx` server-side
- **Comment depth**: Top-level only (no nested replies)
- **Group chat**: Top 5 most influential per stance segment

## What Is Stable

- Existing V1 codebase: frontend (React/Vite), backend (FastAPI), OASIS integration
- Demo mode caching system
- Provider-aware model routing (Gemini/OpenAI/Ollama)
- LightRAG document processing pipeline
- Persona sampling pipeline (needs filter generalization, not rewrite)

## What Is Risky

- **Graphiti integration**: New dependency; FalkorDB Docker image + Graphiti Python client. The existing `memory_service.py` has Zep Cloud calls that need replacement. Keep Zep as env-var fallback.
- **OASIS `recsys.py` edit**: Modifying a vendored/pip-installed package. May need to fork or patch at import time. Check how OASIS is installed in the project.
- **Context caching**: Gemini-specific feature. Non-Gemini providers must work without it (graceful degradation).
- **Dynamic Parquet filters**: Need to handle schema differences between SG and USA datasets cleanly.

## What Is Blocked

- Nothing is blocked. All design decisions are finalized. Implementation can begin immediately.

## Exact Next Actions

### Start with Phase Q (Foundation)

1. **Read**: `docs/v2/index.md` → `docs/v2/BRD_V2.md` §1 and §5
2. **Create**: `config/` directory with all YAML files from `docs/v2/backend/config-system.md`
3. **Create**: `docker-compose.yml` from `docs/v2/infrastructure/docker.md`
4. **Implement**: `ConfigService` in `backend/src/mckainsey/services/config_service.py`
5. **Implement**: `TokenTracker` in `backend/src/mckainsey/services/token_tracker.py`
6. **Implement**: `CachingLLMClient` in `backend/src/mckainsey/services/caching_llm_client.py`
7. **Fix**: Remove Ollama-or-die from `quick_start.sh` (graceful degradation)
8. **Add**: `session_id` to all state containers

### Then Phase R (Multi-Country) and so on...

Follow the phase order defined in `BRD_V2.md` §5. Each phase references specific sub-documents.

## File Links for Immediate Continuation

| Priority | File | Why |
|:---------|:-----|:----|
| 1 | [docs/v2/index.md](../docs/v2/index.md) | Start here — doc map |
| 2 | [docs/v2/BRD_V2.md](../docs/v2/BRD_V2.md) | Master requirements |
| 3 | [docs/v2/backend/config-system.md](../docs/v2/backend/config-system.md) | First implementation task |
| 4 | [docs/v2/infrastructure/docker.md](../docs/v2/infrastructure/docker.md) | Docker setup |
| 5 | [quick_start.sh](../quick_start.sh) | Fix Ollama startup check |
