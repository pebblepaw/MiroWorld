# McKAInsey V2 Backend Linking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the V2 backend, wire it to the completed frontend with minimal aesthetic churn, and satisfy the unchecked requirements in `docs/v2/frontend/*.md` and `docs/v2/backend/*.md` on branch `codex/frontend-v2-screen1`.

**Architecture:** Keep the existing console/session/storage spine and add a thin V2 compatibility layer around it. Reuse `SimulationStore`, `ConsoleService`, and current routes where practical, but introduce focused services for YAML config, token estimation, metrics/analytics, scraping, report export, and memory backends so each new feature has one obvious home.

**Tech Stack:** FastAPI, Pydantic, pytest, React/Vite/TypeScript, Vitest, Playwright CLI, YAML config, SQLite-backed `SimulationStore`, `python-docx`, optional Graphiti/FalkorDB fallback layer.

---

### Task 1: Config Foundation + Onboarding Session APIs

**Files:**
- Create: `config/countries/singapore.yaml`
- Create: `config/countries/usa.yaml`
- Create: `config/prompts/policy-review.yaml`
- Create: `config/prompts/ad-testing.yaml`
- Create: `config/prompts/product-market-fit.yaml`
- Create: `config/prompts/customer-review.yaml`
- Create: `backend/src/mckainsey/services/config_service.py`
- Modify: `backend/src/mckainsey/config.py`
- Modify: `backend/src/mckainsey/models/console.py`
- Modify: `backend/src/mckainsey/api/routes_console.py`
- Modify: `backend/src/mckainsey/services/console_service.py`
- Modify: `quick_start.sh`
- Test: `backend/tests/test_v2_config_service.py`
- Test: `backend/tests/test_console_routes.py`

- [ ] **Step 1: Write failing backend tests for config loading and onboarding endpoints**

Add tests for:
- `ConfigService` loading valid YAML
- missing country/use-case raising `FileNotFoundError`
- invalid YAML returning a logged error instead of crashing discovery endpoints
- `GET /api/v2/countries`
- `GET /api/v2/providers`
- `POST /api/v2/session/create`
- `PATCH /api/v2/session/{id}/config`

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=src pytest tests/test_v2_config_service.py tests/test_console_routes.py -q`
Expected: FAIL because `ConfigService` and the V2 compatibility endpoints do not exist yet.

- [ ] **Step 3: Add YAML config files and implement `ConfigService`**

Implement country metadata, filter field declarations, geo metadata, use-case prompts, checkpoint questions, and report sections exactly once in YAML.

- [ ] **Step 4: Add V2 session/provider/country route support**

Expose or wrap:
- `GET /api/v2/countries`
- `GET /api/v2/providers`
- `POST /api/v2/session/create`
- `PATCH /api/v2/session/{id}/config`

Route handlers may delegate to existing console/session code, but the response shape must satisfy the screen docs and frontend.

- [ ] **Step 5: Normalize onboarding/provider/use-case IDs**

Resolve the current mismatch between frontend IDs (`gemini`, `reviews`) and runtime/client IDs (`google`, `customer-review` or equivalent canonical codes). Pick one canonical mapping source and apply it consistently across backend responses, `console-api.ts`, and onboarding state.

- [ ] **Step 6: Make provider detection lazy**

Remove startup-time Ollama hard failure from `quick_start.sh` and any boot path that exits before the user chooses a provider. Reachability checks should happen when models are listed or a live simulation starts.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=src pytest tests/test_v2_config_service.py tests/test_console_routes.py -q`
Expected: PASS.


### Task 2: Screen 1 Knowledge Ingestion, Multi-Document Merge, and URL Scrape

**Files:**
- Create: `backend/src/mckainsey/services/scrape_service.py`
- Modify: `backend/src/mckainsey/api/routes_console.py`
- Modify: `backend/src/mckainsey/models/console.py`
- Modify: `backend/src/mckainsey/services/console_service.py`
- Modify: `backend/src/mckainsey/services/lightrag_service.py`
- Modify: `frontend/src/lib/console-api.ts`
- Modify: `frontend/src/pages/PolicyUpload.tsx`
- Test: `backend/tests/test_v2_knowledge_routes.py`
- Test: `frontend/src/pages/PolicyUpload.test.tsx`

- [ ] **Step 1: Write failing tests for scrape + multi-doc behavior**

Backend tests:
- valid scrape returns `{text, title, length}`
- invalid URL returns `400`
- multiple uploaded documents merge into one graph/stat payload
- guiding prompt defaults from YAML when frontend has not overridden it

Frontend tests:
- URL input submits and displays scraped content
- multiple files remain visible together
- stats row reflects merged backend payload

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_v2_knowledge_routes.py -q`
- `cd frontend && npm run test -- src/pages/PolicyUpload.test.tsx`

- [ ] **Step 3: Implement scrape service and multi-document merge path**

Add a scrape endpoint and a merged extraction path that accepts uploaded files, pasted text, and scraped text under one session-level artifact.

- [ ] **Step 4: Wire guiding prompt defaults from config**

If the frontend sends no custom prompt, load `guiding_prompt` from `config/prompts/{use_case}.yaml`.

- [ ] **Step 5: Update the frontend API adapter and minimal Screen 1 wiring**

Preserve current layout. Only change data flow, loading/error handling, and request/response adaptation.

- [ ] **Step 6: Re-run tests**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_v2_knowledge_routes.py tests/test_console_routes.py -q`
- `cd frontend && npm run test -- src/pages/PolicyUpload.test.tsx`
Expected: PASS.


### Task 3: Dynamic Filters + Token Usage Estimate for Screen 2

**Files:**
- Create: `backend/src/mckainsey/services/caching_llm_client.py`
- Create: `backend/src/mckainsey/services/token_tracker.py`
- Modify: `backend/src/mckainsey/services/config_service.py`
- Modify: `backend/src/mckainsey/services/persona_sampler.py`
- Modify: `backend/src/mckainsey/services/lightrag_service.py`
- Modify: `backend/src/mckainsey/services/geo_service.py`
- Modify: `backend/src/mckainsey/api/routes_console.py`
- Modify: `backend/src/mckainsey/models/console.py`
- Modify: `backend/src/mckainsey/services/console_service.py`
- Modify: `frontend/src/lib/console-api.ts`
- Modify: `frontend/src/pages/AgentConfig.tsx`
- Test: `backend/tests/test_caching_llm_client.py`
- Test: `backend/tests/test_token_tracker.py`
- Test: `backend/tests/test_v2_filters.py`
- Test: `frontend/src/pages/AgentConfig.test.tsx`

- [ ] **Step 1: Write failing tests for `/filters` and token estimate**

Add backend tests for:
- filter schema inference from the selected country config + dataset schema
- schema differences for Singapore vs USA
- dynamic sampling keys flowing through into the actual sampler path
- token estimate formula for Gemini/OpenAI/Ollama
- caching savings forced to `0` for non-Gemini providers
- per-session runtime token usage endpoint

Add frontend tests for:
- API-driven filter rendering
- single/multi chip behavior
- token estimate rendering

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_caching_llm_client.py tests/test_token_tracker.py tests/test_v2_filters.py tests/test_persona_sampler.py tests/test_phase_b_pipeline.py -q`
- `cd frontend && npm run test -- src/pages/AgentConfig.test.tsx`

- [ ] **Step 3: Implement `CachingLLMClient`, `TokenTracker`, and token-usage endpoints**

Support:
- `GET /api/v2/token-usage/{session_id}/estimate`
- `GET /api/v2/token-usage/{session_id}`

- [ ] **Step 4: Implement dynamic filter schema endpoint and sampler refactor together**

Support:
- `GET /api/v2/console/session/{id}/filters`

Infer options from the configured country dataset and YAML field declarations, not from hardcoded Singapore fields. Update the actual sampling path to accept those dynamic keys and country-specific schema differences so Screen 2 does not become a UI-only refactor.

- [ ] **Step 5: Update Screen 2 integration**

Keep the current Screen 2 visuals. Only replace hardcoded filter/estimate sources with live data plus resilient fallback behavior.

- [ ] **Step 6: Re-run tests**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_caching_llm_client.py tests/test_token_tracker.py tests/test_v2_filters.py tests/test_persona_sampler.py tests/test_phase_b_pipeline.py tests/test_console_routes.py -q`
- `cd frontend && npm run test -- src/pages/AgentConfig.test.tsx`
Expected: PASS.


### Task 4: Simulation Upgrades, Controversy Boost, Checkpoints, and Dynamic Metrics

**Files:**
- Create: `backend/src/mckainsey/services/metrics_service.py`
- Modify: `backend/src/mckainsey/services/simulation_service.py`
- Modify: `backend/src/mckainsey/services/console_service.py`
- Modify: `backend/src/mckainsey/services/simulation_stream_service.py`
- Modify: `backend/src/mckainsey/models/console.py`
- Modify: `backend/scripts/oasis_reddit_runner.py`
- Modify: `backend/tests/test_oasis_reddit_runner.py`
- Modify: `backend/tests/test_simulation_service.py`
- Modify: `backend/tests/test_simulation_stream_service.py`
- Create: `backend/tests/test_metrics_service.py`
- Modify: `frontend/src/lib/console-api.ts`
- Modify: `frontend/src/pages/Simulation.tsx`
- Modify: `frontend/src/pages/Simulation.test.tsx`

- [ ] **Step 1: Write failing tests for controversy boost and metrics heuristics**

Cover:
- `controversy_boost=0.0` preserves old ranking
- higher boost raises controversial high-engagement posts
- YAML-driven `agent_personality_modifiers` applied to simulation prompts
- checkpoint score extraction and confirmed-name parsing
- dislikes and comment vote counts exposed to the frontend payload
- empty-agent handling
- polarization, opinion flow, influence ranking, and group selection rules
- SSE batch contract and `Round X (Y%)` semantics

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_oasis_reddit_runner.py tests/test_simulation_service.py tests/test_simulation_stream_service.py tests/test_metrics_service.py -q`
- `cd frontend && npm run test -- src/pages/Simulation.test.tsx`

- [ ] **Step 3: Thread `controversy_boost` through the simulation stack**

Pass the value from the simulation request into the OASIS runner and scoring function. Preserve current heuristic/demo mode behavior.

- [ ] **Step 4: Implement checkpoint-question config loading and dynamic metrics**

Load checkpoint questions from YAML, aggregate use-case-specific metrics, and expose a backend metrics payload that the SSE state and polling paths can both consume.

- [ ] **Step 5: Fix SSE payload semantics for Screen 3**

Ensure the frontend can render:
- `Round X (Y%)`
- counters
- top thread
- dynamic metrics
- completion state

- [ ] **Step 6: Update Screen 3 frontend wiring**

Keep the existing layout and styling. Focus on data adaptation, tooltip content, state transitions, SSE payload normalization, and persisting normalized simulation posts into `AppContext` so Screen 4 can reuse them.

- [ ] **Step 7: Re-run tests**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_oasis_reddit_runner.py tests/test_simulation_service.py tests/test_metrics_service.py tests/test_simulation_stream_service.py -q`
- `cd frontend && npm run test -- src/pages/Simulation.test.tsx`
Expected: PASS.


### Task 5: Report, Group Chat, 1:1 Chat, DOCX Export, and Analytics APIs

**Files:**
- Create: `backend/src/mckainsey/api/routes_analytics.py`
- Modify: `backend/src/mckainsey/main.py`
- Modify: `backend/src/mckainsey/services/report_service.py`
- Modify: `backend/src/mckainsey/services/memory_service.py`
- Modify: `backend/src/mckainsey/services/console_service.py`
- Modify: `backend/src/mckainsey/models/console.py`
- Modify: `frontend/src/lib/console-api.ts`
- Modify: `frontend/src/pages/ReportChat.tsx`
- Modify: `frontend/src/pages/Analytics.tsx`
- Create: `backend/tests/test_v2_report_routes.py`
- Modify: `backend/tests/test_report_service.py`
- Create: `backend/tests/test_metrics_service_routes.py`
- Create: `frontend/src/pages/ReportChat.test.tsx`
- Create: `frontend/src/pages/Analytics.test.tsx`

- [ ] **Step 1: Write failing tests for report/chat/export/analytics endpoints**

Cover:
- plan-first report generation shape
- report sections mapping to YAML prompt/report sections
- DOCX binary download validity
- group chat selecting top-N agents from the requested segment
- 1:1 chat preserving persona context
- analytics routes for polarization, opinion flow, influence, and cascades

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=src pytest tests/test_report_service.py tests/test_v2_report_routes.py tests/test_metrics_service_routes.py -q`

- [ ] **Step 3: Implement report JSON and DOCX export**

Make report sections driven by config, keep evidence IDs in payloads, and generate valid `.docx` output with `python-docx`.

- [ ] **Step 4: Implement group + 1:1 chat endpoints**

Add compatibility endpoints for:
- `POST /api/v2/console/session/{id}/chat/group`
- `POST /api/v2/console/session/{id}/chat/agent/{agent_id}`

Reuse store transcripts and memory context. If Graphiti is unavailable, degrade to a deterministic local-memory fallback instead of failing.

- [ ] **Step 5: Implement analytics routes**

Expose:
- `GET /api/v2/console/session/{id}/analytics/polarization`
- `GET /api/v2/console/session/{id}/analytics/opinion-flow`
- `GET /api/v2/console/session/{id}/analytics/influence`
- `GET /api/v2/console/session/{id}/analytics/cascades`

- [ ] **Step 6: Update Screen 4 and Screen 5 frontend wiring**

Preserve the implemented visual design. Only swap data sources, loading/error states, and download behavior.

- [ ] **Step 7: Re-run tests**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_report_service.py tests/test_v2_report_routes.py tests/test_metrics_service_routes.py tests/test_console_routes.py -q`
- `cd frontend && npm run test -- src/pages/Analysis.test.tsx`
- `cd frontend && npm run test -- src/pages/AgentConfig.test.tsx src/pages/PolicyUpload.test.tsx src/pages/Simulation.test.tsx`
Expected: PASS.


### Task 6: Graphiti/Docker/Runtime Hardening

**Files:**
- Create: `backend/src/mckainsey/services/graphiti_service.py`
- Modify: `backend/src/mckainsey/services/memory_service.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/test_graphiti_service.py`

- [ ] **Step 1: Write failing tests for memory backend fallback and Graphiti service**

Cover:
- Graphiti init contract
- add/search/cleanup methods
- `MEMORY_BACKEND=zep` fallback
- graceful no-Graphiti/no-Zep fallback for local chat

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=src pytest tests/test_graphiti_service.py tests/test_memory_service.py -q`

- [ ] **Step 3: Implement Graphiti service and backend selection**

Prefer `graphiti`, fall back to `zep`, then to local store-backed memory for dev/test environments.

- [ ] **Step 4: Add Docker files and compose stack**

Implement the documented local-first stack without breaking the existing non-Docker workflow.

- [ ] **Step 5: Re-run tests and smoke checks**

Run:
- `cd backend && PYTHONPATH=src pytest tests/test_graphiti_service.py tests/test_memory_service.py -q`
- `docker compose config`
Expected: PASS / valid compose output.


### Task 7: Docker/Runtime Hardening

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `backend/Dockerfile.oasis`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Validate the compose stack**

Run:
- `docker compose config`
- `docker compose up -d --build`
- `docker compose ps`

Expected: services build/start cleanly enough for validation, even if the OASIS sidecar still needs a follow-up server implementation.

- [ ] **Step 2: Verify basic health**

Run:
- `curl -sf http://127.0.0.1:8000/health`
- `curl -sf http://127.0.0.1:5173`

- [ ] **Step 3: Tear down cleanly**

Run: `docker compose down`


### Task 8: Minimal Frontend Integration Cleanup + Full Verification

**Files:**
- Create: `frontend/src/components/OnboardingModal.test.tsx`
- Modify: `frontend/src/components/OnboardingModal.tsx`
- Modify: `frontend/src/contexts/AppContext.tsx`
- Modify: `frontend/src/lib/console-api.ts`
- Modify: `frontend/src/pages/PolicyUpload.tsx`
- Modify: `frontend/src/pages/AgentConfig.tsx`
- Modify: `frontend/src/pages/Simulation.tsx`
- Modify: `frontend/src/pages/ReportChat.tsx`
- Modify: `frontend/src/pages/Analytics.tsx`
- Create: `output/playwright/` artifacts only

- [ ] **Step 1: Add/refresh failing frontend tests for the remaining V2 screens**

Only add tests where current coverage is missing for backend-linked behavior. Avoid aesthetic assertions.

- [ ] **Step 2: Run the frontend suite and fix integration regressions**

Run:
- `cd frontend && npm run test -- src/components/OnboardingModal.test.tsx src/pages/PolicyUpload.test.tsx src/pages/AgentConfig.test.tsx src/pages/Simulation.test.tsx src/pages/ReportChat.test.tsx src/pages/Analytics.test.tsx`
- `cd frontend && npm run build`

- [ ] **Step 3: Run backend suite**

Run: `cd backend && PYTHONPATH=src pytest`

- [ ] **Step 4: Launch the app for E2E**

Run:
- `./quick_start.sh --mode demo`
- `./quick_start.sh --mode live`

If the quick-start path is still under repair, document the blocker and use separate backend/frontend commands as a fallback.

- [ ] **Step 5: Execute Playwright CLI end-to-end flows**

Use the Playwright CLI skill and capture screenshots in `output/playwright/` for:
- Screen 0 onboarding
- Screen 1 extraction
- Screen 2 filters + token estimate
- Screen 3 simulation progress
- Screen 4 report + chat + DOCX export
- Screen 5 analytics

- [ ] **Step 6: Verify fallback behavior**

Explicitly test one failure-path flow where a live endpoint is unavailable and the frontend falls back cleanly without crashing.

- [ ] **Step 7: Update checklist evidence**

Only after unit/build/E2E verification passes, update the V2 checklist docs or handoff notes with concrete evidence of what passed.
