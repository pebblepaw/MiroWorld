# Progress Tracker

## Global Status
**Project:** McKAInsey — AI-Powered Population Simulation Consulting Service
**Status:** Phase A completed (Mode 1 path). Ready for Phase B execution.

## Phase Checklist
- [x] Phase A — Data Pipeline & LightRAG Integration — [progress/phaseA.md](progress/phaseA.md)
- [ ] Phase B — OASIS Simulation Engine Setup — [progress/phaseB.md](progress/phaseB.md)
- [ ] Phase C — Agent Memory (Zep Cloud Integration) — [progress/phaseC.md](progress/phaseC.md)
- [ ] Phase D — ReportAgent & Analysis Pipeline — [progress/phaseD.md](progress/phaseD.md)
- [ ] Phase E — Dashboard & Frontend — [progress/phaseE.md](progress/phaseE.md)
- [ ] Phase F — Integration Testing & Evaluation — [progress/phaseF.md](progress/phaseF.md)

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
- [ ] B1 EC2 instance setup
	- [ ] B1.1 Provision EC2 instance with Python 3.11+
	- [ ] B1.2 Install camel-oasis and dependencies
	- [ ] B1.3 Configure Gemini API via OpenAI SDK compatibility
- [ ] B2 Nemotron-to-OASIS agent loading
	- [ ] B2.1 Script to convert Nemotron JSON personas to OASIS agent profiles
	- [ ] B2.2 Inject LightRAG subgraph context per agent
	- [ ] B2.3 Test: 50 agents loaded with correct persona characteristics
- [ ] B3 Stage 3a — Immediate reactions pipeline
	- [ ] B3.1 Each agent generates individual opinion (no interaction)
	- [ ] B3.2 Collect and store pre-deliberation opinion scores
- [ ] B4 Stage 3b — OASIS Reddit-mode deliberation
	- [ ] B4.1 Configure Reddit platform in OASIS
	- [ ] B4.2 Run N-round simulation with batched intra-step LLM calls
	- [ ] B4.3 Collect post-deliberation opinion scores
	- [ ] B4.4 Verify opinion shift between Stage 3a and 3b

### Phase C — Agent Memory (Zep Cloud)
- [ ] C1 Zep Cloud account + SDK setup
- [ ] C2 Agent interaction → Zep episode pipeline
- [ ] C3 Temporal fact extraction validation
- [ ] C4 Post-simulation memory query API
- [ ] C5 Memory-informed agent chat endpoint

### Phase D — ReportAgent & Analysis
- [ ] D1 ReportAgent with tool functions (query DB, compute metrics)
- [ ] D2 Structured report output (JSON schema)
- [ ] D3 ReportAgent chat interface
- [ ] D4 Individual agent chat (highlight influential agents)
- [ ] D5 Influence score + friction index calculation

### Phase E — Dashboard & Frontend
- [ ] E1 React project setup on EC2
- [ ] E2 Scenario submission form (document upload + filters)
- [ ] E3 Simulation progress indicator
- [ ] E4 Results views: approval charts, opinion-shift timelines
- [ ] E5 Friction heatmap (55 planning areas)
- [ ] E6 Consensus tracker
- [ ] E7 ReportAgent chat panel
- [ ] E8 Individual agent chat panel

### Phase F — Integration Testing
- [ ] F1 End-to-end integration test (submit → simulate → report → chat)
- [ ] F2 Performance benchmarks (latency, cost, scale)
- [ ] F3 Cost comparison (cached vs uncached, batched vs unbatched)
- [ ] F4 Simulation quality analysis
- [ ] F5 Final documentation updates
