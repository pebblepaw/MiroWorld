# Progress Tracker

## Global Status
**Project:** McKAInsey — AI-Powered Population Simulation Consulting Service
**Status:** Phase A-H completed locally. Screen 1 on the Frontend V2 shell is live, graph-hardened, and documented. Phase I planning is now active for Screen 2 sampling logic, live cohort generation, and agent graph design.

## Current Operator Status
- `./quick_start.sh --mode demo` remains the supported demo launcher path.
- `./quick_start.sh --mode live --real-oasis` is the supported live launcher path when the OASIS Python 3.11 sidecar is available.
- Stage 1 on the Frontend V2 shell accepts real uploaded files (`.pdf`, `.docx`, `.txt`, `.md`, `.html`, `.json`, `.csv`, `.yaml`, `.yml`) and persists screen-ready knowledge artifacts.
- Screen 1 graph controls are now split into:
  - `All / Nemotron Entities / Other Entities`
  - bucket filters for `Organization`, `Persons`, `Location`, `Age Group`, `Event`, `Concept`, `Industry`, `Other`
- Screen 1 hides generic placeholder nodes and non-facet low-value orphan nodes by default, while preserving them in the artifact.
- Stage 2 backend sampling from the earlier console rebuild exists, but Phase I is redefining the Frontend V2 Screen 2 logic around the local Singapore Nemotron parquet, dual sampling modes, repeatable re-sampling, and graph-aware cohort reasoning.
- Stage 3 runs native OASIS and streams live events into the console.
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

## Phase Checklist
- [x] Phase A — Data Pipeline & LightRAG Integration — [progress/phaseA.md](progress/phaseA.md)
- [x] Phase B — OASIS Simulation Engine Setup — [progress/phaseB.md](progress/phaseB.md)
- [x] Phase C — Agent Memory (Zep Cloud Integration) — [progress/phaseC.md](progress/phaseC.md)
- [x] Phase D — ReportAgent & Analysis Pipeline — [progress/phaseD.md](progress/phaseD.md)
- [x] Phase E — Dashboard & Frontend — [progress/phaseE.md](progress/phaseE.md)
- [x] Phase F — Integration Testing & Evaluation — [progress/phaseF.md](progress/phaseF.md)
- [x] Phase G — McKAInsey Console Rebuild & Real-Time Validation — [progress/phaseG.md](progress/phaseG.md)
- [x] Phase H — Screen 1 Frontend V2 Adoption & Graph Hardening — [progress/phaseH.md](progress/phaseH.md)
- [ ] Phase I — Screen 2 Sampling Logic & Agent Graph — [progress/phaseI.md](progress/phaseI.md)

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
- [ ] I5 Implement the live agent count selector and repeatable re-sampling
- [ ] I6 Implement Screen 2 backend retrieval/scoring
- [ ] I7 Implement Screen 2 agent graph styling and live integration
