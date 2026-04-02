# Progress Tracker

## Global Status
**Project:** McKAInsey — AI-Powered Population Simulation Consulting Service
**Status:** Phase A-L completed locally. Phase N (Provider-Aware Model Selector & Runtime Routing) is in progress with Google live validation complete and provider runtime constraints under active follow-up.

## Current Operator Status
- `./quick_start.sh --mode demo` is the default launcher path - serves fully cached data with **no Gemini API calls**.
- `./quick_start.sh --mode live` is the supported live launcher path when the OASIS Python 3.11 sidecar is available.
- **Demo Mode** now serves pre-cached data for all 7 screens:
  - Screen 1: Knowledge Graph (75 entities from FY2026 Budget Statement)
  - Screen 2: 250 agents from Nemotron dataset
  - Screen 3: 6 rounds of simulation with 1496 interactions
  - Screen 4: Analysis report with friction maps
  - Screen 5: Interaction hub with demo chat responses
- Demo cache files: `backend/data/demo-output.json` and `frontend/public/demo-output.json`
- Demo service provides cached responses for all API endpoints without external API calls
- Live mode now uses provider-aware runtime routing (Google/OpenRouter/OpenAI/Ollama) plus Zep Cloud as configured.
- Stage 1 on the Frontend V2 shell accepts real uploaded files (`.pdf`, `.docx`, `.txt`, `.md`, `.html`, `.json`, `.csv`, `.yaml`, `.yml`) and persists screen-ready knowledge artifacts.
- Screen 1 graph controls are now split into:
  - `All / Nemotron Entities / Other Entities`
  - bucket filters for `Organization`, `Persons`, `Location`, `Age Group`, `Event`, `Concept`, `Industry`, `Other`
- Screen 1 hides generic placeholder nodes and non-facet low-value orphan nodes by default, while preserving them in the artifact.
- Screen 2 on the Frontend V2 shell is now live against `/api/v2/console/session/{id}/sampling/preview`.
- Screen 2 supports two explicit modes:
  - `Affected Groups`
  - `Population Baseline`
- Screen 2 now uses the local Singapore Nemotron parquet as the source-of-truth population store.
- Screen 2 request parsing now follows:
  - structured filters over local categorical fields
  - BM25 shortlist over short/list text
  - semantic rerank over bounded long-text candidates
- The `Sampling Instructions` box now feeds a real parser:
  - Gemini JSON parse first
  - deterministic fallback when Gemini is unavailable or returns notes-only / non-actionable output
- Parsed instruction buckets now affect backend behavior for:
  - hard filters
  - soft boosts
  - soft penalties
  - exclusions
  - distribution-target bias
- Screen 2 hobby / skill instruction keys now match the real Nemotron list fields instead of dead placeholder fields.
- Screen 2 shows a read-only parsed summary for:
  - hard filters
  - soft boosts
  - exclusions
  - distribution targets
- Screen 2 `Generate Agents` and `Re-sample` are both live, and the generated seed is surfaced back to the user.
- The Screen 2 agent-count control is now aligned with the backend contract and capped at `500`.
- The Stage 2 agent graph now uses the same visual language as Screen 1:
  - small nodes
  - external labels
  - always-visible edges
  - optional edge-label toggle
  - legend from live graph categories
- Screen 3 now runs native OASIS in Reddit mode and streams live posts, comments, reactions, and metrics into the console over SSE.
- Screen 3 now measures all sampled agents at the start and end of the run through baseline / final checkpoints.
- Screen 3 completion now waits for the final checkpoint instead of ending immediately after the public rounds.
- Screen 4A `Reports & Insights` is now live against structured Gemini output and async background generation.
- Screen 4B and Screen 4C remain visible mock tabs in this phase.
- `quick_start.sh --mode live` now validates and pins the dedicated Python 3.11 OASIS runtime before launching live mode.
- Stage 5 report chat and agent chat now make real Gemini and Zep Cloud API calls. No placeholder UI handlers remain.

## Recently Completed Console Rebuild
- Replaced the inherited dashboard with the 7-screen McKAInsey console shell.
- Added `/api/v2/console/...` screen-shaped backend contracts for knowledge, sampling, live simulation, report, and interaction hub flows.
- Added local parquet-backed Nemotron retrieval for faster live sampling and deterministic local operation.
- Added SSE-backed simulation event streaming and persisted simulation state snapshots.
- Regenerated the demo-cache pipeline so demo and live share the same screen contracts.
- Completed a dedicated Screen 1 hardening pass on the Frontend V2 codebase:
  - LightRAG-native graph adapter
  - explicit Screen 1 display buckets
  - facet-aware filtering
  - hidden-node logic
  - relation-label toggle fix
  - live CNA sample verification
- Completed the Screen 2 Frontend V2 implementation pass:
  - live `/sampling/preview` wiring
  - real `Affected Groups` / `Population Baseline` mode toggle
  - live count selector with repeatable re-sampling
  - local parquet candidate retrieval caps for interactive latency
  - exact → BM25 → semantic rerank scoring stack
  - parser fallback when Gemini returns notes-only output
  - read-only parsed instruction summary
  - Screen 1-style agent graph and cohort diagnostics
  - live browser validation from Screen 1 upload into Screen 2 cohort generation
- Completed the Screen 3 + Screen 4A Frontend V2 implementation pass:
  - live `/simulation/start`, `/simulation/state`, and `/simulation/stream` wiring
  - MiroFish-style append-only Reddit feed cards with auto-scroll
  - live counters, ETA, hottest-thread tile, and checkpoint status
  - graph-aware OASIS persona context routing from Screen 1 + Screen 2
  - all-agent baseline and final stance checkpoints
  - async `POST /report/generate` + `GET /report/full` Screen 4A flow
  - fixed report schema rendering for executive summary, insights, themes, demographic breakdown, influential content, recommendations, and risks
  - dedicated OASIS Python 3.11 runtime validation and pinned dependency file
  - real live validation from Screen 1 upload through Screen 4A report completion

## Phase Checklist
- [x] Phase A — Data Pipeline & LightRAG Integration — [progress/phaseA.md](progress/phaseA.md)
- [x] Phase B — OASIS Simulation Engine Setup — [progress/phaseB.md](progress/phaseB.md)
- [x] Phase C — Agent Memory (Zep Cloud Integration) — [progress/phaseC.md](progress/phaseC.md)
- [x] Phase D — ReportAgent & Analysis Pipeline — [progress/phaseD.md](progress/phaseD.md)
- [x] Phase E — Dashboard & Frontend — [progress/phaseE.md](progress/phaseE.md)
- [x] Phase F — Integration Testing & Evaluation — [progress/phaseF.md](progress/phaseF.md)
- [x] Phase G — McKAInsey Console Rebuild & Real-Time Validation — [progress/phaseG.md](progress/phaseG.md)
- [x] Phase H — Screen 1 Frontend V2 Adoption & Graph Hardening — [progress/phaseH.md](progress/phaseH.md)
- [x] Phase I — Screen 2 Sampling Logic & Agent Graph — [progress/phaseI.md](progress/phaseI.md)
- [x] Phase J — Screen 3 Live Simulation & Screen 4A Reports — [progress/phaseJ.md](progress/phaseJ.md)
- [x] Phase K — Screen 2 Agent Configuration Redesign — [progress/phaseK.md](progress/phaseK.md)
 - [x] Phase L — Demo Mode with Full Cache Support — [progress/phaseL.md](progress/phaseL.md)
- [ ] Phase M — Simulation & Analysis (Screen 3 & Screen 4) — [progress/phaseM.md](progress/phaseM.md)
- [ ] Phase N — Provider-Aware Model Selector & Runtime Routing — [progress/phaseN.md](progress/phaseN.md)

## Feature and Subtask Checklists

### Phase A — Data Pipeline & LightRAG
- [x] A1 Mode 1 local data access (HuggingFace streaming, per project directive)
	- [x] A1.1 Use streaming access for Nemotron dataset
	- [x] A1.2 Implement local query/sampling path without S3 storage
	- [x] A1.3 Defer S3/Lambda IAM path for final deployment only
- [ ] A2 Lambda + DuckDB persona filtering
	- [x] A2.1 Create API service with DuckDB-enabled persona filtering layer (local Mode 1)
	- [x] A2.2 Implement demographic filter query (age, income, planning area, etc.)
	- [x] A2.3 Return filtered personas as JSON
	- [x] A2.4 Integration-oriented unit tests for filtering edge cases
- [ ] A3 LightRAG document processing
	- [x] A3.1 Install and configure LightRAG with Gemini backend (code + config)
	- [x] A3.2 Process sample policy document into LightRAG storage via API endpoint
	- [x] A3.3 Implement demographic-relevant context extraction query flow
	- [x] A3.4 Integration smoke run: document → graph extraction → demographic context query

### Phase B — OASIS Simulation Engine
- [x] B1 EC2/runtime-compatible setup implemented for local-first path
	- [x] B1.1 Added Python 3.11 compatibility path for OASIS package installation
	- [x] B1.2 Installed and validated `camel-oasis` in Python 3.11 runtime
	- [x] B1.3 Configured Gemini-compatible backend client for simulation/report flows
- [x] B2 Nemotron-to-agent loading
	- [x] B2.1 Implemented conversion from Nemotron persona JSON to simulation agents
	- [x] B2.2 Integrated policy context usage in simulation round prompts
	- [x] B2.3 Verified 50-agent run path in end-to-end script
- [x] B3 Stage 3a — Immediate reactions pipeline
	- [x] B3.1 Added per-agent pre-deliberation opinion initialization
	- [x] B3.2 Stored Stage 3a scores in SQLite store
- [x] B4 Stage 3b — Reddit-mode deliberation flow
	- [x] B4.1 Implemented Reddit-style interaction primitives (post/comment) in simulation loop
	- [x] B4.2 Added configurable N-round deliberation execution
	- [x] B4.3 Stored post-deliberation scores and interaction traces
	- [x] B4.4 Verified measurable shift path and output comparison payload

### Phase C — Agent Memory (Zep Cloud)
- [x] C1 Zep Cloud account + SDK setup
- [x] C2 Agent interaction → Zep episode pipeline
- [x] C3 Temporal fact extraction validation (with resilient fallback if Zep endpoint unavailable)
- [x] C4 Post-simulation memory query API
- [x] C5 Memory-informed agent chat endpoint

### Phase D — ReportAgent & Analysis
- [x] D1 ReportAgent with tool functions (query DB, compute metrics)
- [x] D2 Structured report output (JSON schema)
- [x] D3 ReportAgent chat interface
- [x] D4 Individual agent chat (highlight influential agents)
- [x] D5 Influence score + friction index calculation

### Phase E — Dashboard & Frontend
- [x] E1 React project setup
- [x] E2 Scenario submission form (policy summary + simulation controls)
- [x] E3 Simulation status indicator
- [x] E4 Results views: approval charts, opinion-shift timeline
- [x] E5 Friction chart payload + frontend rendering
- [x] E6 Consensus/approval tracker in context panel
- [x] E7 ReportAgent chat panel
- [x] E8 Individual agent chat API integration path available via backend

### Phase F — Integration Testing
- [x] F1 End-to-end integration test (submit → simulate → report → chat)
- [x] F2 Performance benchmarks (latency, cost, scale)
- [x] F3 Cost comparison (cached vs uncached, batched vs unbatched) - baseline instrumentation delivered
- [x] F4 Simulation quality analysis baseline
- [x] F5 Final documentation updates

### Phase G — McKAInsey Console Rebuild & Real-Time Validation
- [x] G1 Replace legacy dashboard with the 7-screen McKAInsey console shell
- [x] G2 Add `/api/v2/console` backend contracts for all primary screens
- [x] G3 Implement real Stage 1 uploaded file parsing and knowledge artifact persistence
- [x] G4 Implement real Stage 2 document-aware Nemotron sampling with balanced hybrid selection
- [x] G5 Implement native OASIS live event streaming for Stage 3
- [x] G6 Split Stage 4 into full report, opinions, and friction-map contracts
- [x] G7 Implement real Stage 5 report chat and agent chat with Gemini + Zep Cloud
- [x] G8 Add Playwright coverage for demo and live console boot paths
- [x] G9 Verify a real multi-round OASIS run end-to-end from console session to Stage 5 chat

### Phase H — Screen 1 Frontend V2 Adoption & Graph Hardening
- [x] H1 Adopt the Frontend V2 codebase for Screen 1
- [x] H2 Wire the Screen 1 upload flow to the live Stage 1 backend
- [x] H3 Prefer native LightRAG graph output over the old presentation-only extraction path
- [x] H4 Add Screen 1 display buckets and facet metadata
- [x] H5 Add segmented family controls and bucket filters
- [x] H6 Add default hidden-node logic for placeholders / low-value orphan noise
- [x] H7 Fix the relationship-label toggle so lines remain visible
- [x] H8 Verify Screen 1 live against the CNA shrinking birth rate sample

### Phase I — Screen 2 Sampling Logic & Agent Graph
- [x] I1 Define the two-mode sampling strategy (`Affected Groups` vs `Population Baseline`)
- [x] I2 Define the exact → BM25 → semantic rerank retrieval stack
- [x] I3 Define the `Sampling Instructions` text-box parsing approach
- [x] I4 Lock the local Singapore Nemotron parquet as the Screen 2 source-of-truth schema
- [x] I5 Implement the live agent count selector and repeatable re-sampling
- [x] I6 Implement Screen 2 backend retrieval/scoring
- [x] I7 Implement Screen 2 agent graph styling and live integration

### Phase J — Screen 3 Live Simulation & Screen 4A Reports
- [x] J1 Replace Screen 3 mock UI with live SSE-driven Reddit feed
- [x] J2 Persist and stream richer OASIS round events incrementally
- [x] J3 Build graph-aware simulation context bundles from Screen 1 + Screen 2
- [x] J4 Add all-agent baseline and final opinion checkpoints
- [x] J5 Make Screen 3 completion wait for final checkpoint completion
- [x] J6 Implement Screen 4A async report generation with fixed structured schema
- [x] J7 Keep Screen 4B / 4C navigable on mock data without blocking Screen 4A
- [x] J9 Harden the native OASIS sidecar runtime with validation + pinned requirements
- [x] J10 Verify live Screen 1 → Screen 2 → Screen 3 → Screen 4A end to end

### Phase K — Screen 2 Agent Configuration Redesign
- [x] K1 Replace legacy "AI-Slop" elements (GlassCards) with structured editorial layouts
- [x] K2 Implement Singapore Map via react-leaflet for Planning Area density
- [x] K3 Increase Y-Axis width on Industry Mix BarChart to prevent truncation
- [x] K4 Strip out physics graph and scatter plots entirely
- [x] K5 Build fully responsive Flexbox-driven categorical Waffle Chart layout
- [x] K6 Restructure UI for massively tall scrollable panes (min-h: 800px)
- [x] K7 Parse and render exhaustive 10+ field persona tooltip (Education, Marital Status, Culture, Skills, Hobbies, etc.)

### Phase L — Demo Mode with Full Cache Support
- [x] L1 Create DemoService for serving cached data without API calls
- [x] L2 Prepare demo cache from existing demo-snapshot.json (250 agents, 6 rounds)
- [x] L3 Modify console routes to check demo mode and serve cached data
- [x] L4 Implement demo chat responses (report and agent chat)
- [x] L5 Ensure live mode continues to use real Gemini API and Zep Cloud
- [x] L6 Create demo cache preparation script (prepare_demo_cache.py)
- [x] L7 Create comprehensive demo cache generator (generate_comprehensive_demo_cache.py)
- [x] L8 Document demo mode architecture and usage
- [x] L9 Verify demo mode serves all 7 screens from cache
- [x] L10 Verify live mode still makes real API calls when configured

### Phase N — Provider-Aware Model Selector & Runtime Routing
- [x] N1 Add frontend settings modal in sidebar footer (provider, model, API key)
- [x] N2 Add frontend API client support for provider/model/session model config endpoints
- [x] N3 Persist session-level model config in backend storage and response contracts
- [x] N4 Add backend provider catalog/model listing and session model update routes
- [x] N5 Route runtime services (LightRAG/report/memory/simulation) via per-session model settings
- [x] N6 Set live default to Ollama (`qwen3:4b-instruct-2507-q4_K_M`) in launcher preflight
- [x] N7 Validate Google provider Screen 1 live output end-to-end
- [x] N8 Surface provider/model-specific backend detail for Screen 1 extraction failures
- [x] N9 Add lightweight Ollama Stage 1 ingestion profile (truncation + compact fallback prompt)
- [ ] N10 Validate OpenAI provider Screen 1 live output end-to-end (blocked by `insufficient_quota`)
- [ ] N11 Validate Ollama provider Screen 1 live output end-to-end (blocked by local runtime latency/timeouts)
