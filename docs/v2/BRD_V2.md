# McKAInsey V2 — Business Requirements Document

> **Version**: 2.0 · **Date**: 2026-04-05 · **Status**: Approved for implementation
>
> This document is the **single source of truth** for the V2 pivot. All prior documents (`BRD.md`, `Progress.md`, `UserInput.md`) have been archived to `archive/v1/`. Sub-documents in `docs/v2/frontend/`, `docs/v2/backend/`, and `docs/v2/infrastructure/` contain implementation-level detail referenced from this BRD.

---

## 1. Executive Summary

McKAInsey V2 transforms the platform from a **Singapore-specific policy simulation tool** into a **generalized, local-first, multi-country, multi-use-case AI population simulation platform**.

### 1.1 What's Changing

| Dimension | V1 (Current) | V2 (Pivot) |
|:----------|:-------------|:-----------|
| **Scope** | Singapore policy only | 2 countries MVP (SG + USA), extensible via YAML |
| **Deployment** | Cloud-first (AWS + Zep Cloud) | Local-first Docker, AWS as stretch |
| **Memory** | Zep Cloud (external SaaS) | Graphiti (self-hosted, open-source Zep engine) with FalkorDB |
| **Use Cases** | Policy approval/dissent only | Policy Review, Ad Testing, PMF Discovery, Customer Review |
| **Prompts** | Hardcoded Python strings | Externalized YAML config per use case |
| **Filters** | Hardcoded Singapore fields | Dynamic from Parquet schema + country config |
| **Report** | Multi-tab report dashboard | 60/40 Report+Chat with view toggle (Report Only / Report+Chat / Chat Only) |
| **Visualizations** | None | Dedicated analytics screen: Polarization, Influence, Cascade, Opinion Flow |
| **Export** | None | DOCX export (server-side generation) |
| **Theme** | Dark only | Dark only (light mode = stretch goal) |
| **Agent Chat** | Individual 1:1 | Group chat (top 5-10 influential per segment) + 1:1 |
| **Token Tracking** | None | Real-time cost estimation with Gemini Context Caching savings |

### 1.2 What's Preserved (No Changes)

- OASIS simulation engine (Reddit mode)
- LightRAG document processing pipeline
- Core 5-stage pipeline: Setup → Sample → Simulate → Report → Chat
- React (Vite + TypeScript) + Python (FastAPI) backend architecture
- Demo mode caching system
- Provider-aware model routing (Gemini / OpenAI / Ollama)

### 1.3 Stretch Goals (Deferred — Do NOT implement now)

- Light/dark mode toggle (CSS variable wrapping only)
- Countries beyond SG + USA (India, Japan, Brazil, France)
- Mid-simulation variable injection ("God's-eye view")
- AWS multi-user deployment
- Frontend UI for editing YAML config files (file-editing sufficient for power users)

---

## 2. Architecture Overview

### 2.1 Local Docker Stack

```
┌──────────────────────────────────────────────────────────────┐
│                     docker-compose.yml                        │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│  frontend    │   backend    │   falkordb   │  oasis-sidecar  │
│  (Vite/React)│  (FastAPI)   │  (Redis-     │  (Python 3.11)  │
│  Port: 5173  │  Port: 8000  │  compatible) │  Internal only  │
│              │              │  Port: 6379  │                 │
└──────────────┴──────────────┴──────────────┴─────────────────┘
```

**Networking**: All services communicate over a single Docker bridge network. Inter-container latency is <1ms (localhost-equivalent). The bottleneck is always the LLM API call (100-2000ms).

**Cold start**: First `docker compose up` pulls images (~2-5 min one-time, then cached). Subsequent starts take seconds.

### 2.2 Session Architecture (Multi-User Readiness)

All state is keyed by `session_id`, which trivially maps to `user_id` for future AWS deployment:

- Session data: `./data/sim_{session_id}.db` → maps to S3/RDS later
- No global singletons for state — each simulation gets its own state container
- Config loaded per-session, not globally
- API routes namespaced under session IDs

### 2.3 Directory Structure (New/Modified)

```
Nemotron_Consult/
├── config/                          # NEW: All externalized configuration
│   ├── countries/
│   │   ├── singapore.yaml           # Country-specific field mappings, dataset paths
│   │   └── usa.yaml
│   └── prompts/
│       ├── policy-review.yaml       # Use-case specific prompts & metrics
│       ├── ad-testing.yaml
│       ├── product-market-fit.yaml
│       └── customer-review.yaml
├── docs/
│   └── v2/                          # NEW: This documentation
│       ├── BRD_V2.md                # ← You are here
│       ├── frontend/                # Per-screen frontend specs
│       ├── backend/                 # Per-feature backend specs
│       └── infrastructure/          # Docker, Graphiti, deployment
├── frontend/src/
│   ├── pages/
│   │   ├── Onboarding.tsx           # NEW: Screen 0
│   │   ├── PolicyUpload.tsx         # MODIFY: Multi-doc, use-case toggle
│   │   ├── AgentConfig.tsx          # MODIFY: Dynamic filters
│   │   ├── Simulation.tsx           # MODIFY: Controversy boost, metrics
│   │   ├── ReportChat.tsx           # NEW: Replaces Analysis.tsx
│   │   ├── Analytics.tsx            # NEW: Dedicated visualization screen
│   │   └── AgentChat.tsx            # MODIFY: Group chat + agent sidebar
│   └── components/
│       ├── OnboardingModal.tsx       # NEW
│       ├── ControversySlider.tsx     # NEW
│       ├── MetricCard.tsx            # NEW: With tooltip
│       ├── ChatDrawer.tsx            # NEW
│       ├── AgentSidebar.tsx          # NEW
│       └── CountryMap.tsx            # MODIFY: SG + USA GeoJSON
├── backend/src/mckainsey/
│   ├── services/
│   │   ├── config_service.py        # NEW: YAML config loader
│   │   ├── token_tracker.py         # NEW: Token/cost tracking
│   │   ├── graphiti_service.py      # NEW: Graphiti memory integration
│   │   ├── metrics_service.py       # NEW: Polarization, influence, cascade
│   │   ├── report_service.py        # MODIFY: Plan-first ReportAgent
│   │   ├── simulation_service.py    # MODIFY: Controversy boost, checkpoints
│   │   └── memory_service.py        # MODIFY: Swap Zep → Graphiti
│   └── api/
│       ├── routes_console.py        # MODIFY: New endpoints
│       └── routes_analytics.py      # NEW: Metrics/visualization endpoints
└── docker-compose.yml               # NEW
```

---

## 3. Resolved Design Decisions

All questions from the planning phase have been resolved. This section records each decision with its rationale.

### 3.1 Memory: Graphiti + FalkorDB (Local) / Neo4j (AWS)

**Decision**: Replace Zep Cloud entirely with Graphiti (the open-source engine that powers Zep Cloud).

| Aspect | Detail |
|:-------|:-------|
| **Engine** | Graphiti — Apache 2.0, 24.5k ★ on GitHub |
| **Local Graph DB** | FalkorDB (Redis-based, ~200MB image, minimal RAM, port 6379) |
| **AWS Graph DB** | Neo4j 5.26+ (~500MB image, 1GB+ RAM, browser UI at port 7474) |
| **LLM support** | Gemini natively: `pip install graphiti-core[google-genai]` |
| **Ollama support** | Via OpenAI-compatible API |
| **Key advantage** | Temporal facts — tracks how opinions change over time |

**Implementation**:
```python
from graphiti_core import Graphiti
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig

graphiti = Graphiti(
    "bolt://falkordb:6379", "default", "",
    llm_client=GeminiClient(config=LLMConfig(api_key=api_key, model="gemini-2.0-flash"))
)
```

**Docker**:
```yaml
services:
  falkordb:
    image: falkordb/falkordb:latest
    ports: ["6379:6379"]
    volumes: ["falkordb_data:/data"]
```

See: [docs/v2/infrastructure/graphiti.md](infrastructure/graphiti.md)

### 3.2 OASIS Controversy Boost

**Decision**: Add a `controversy_boost` parameter (0.0–1.0) to `calculate_hot_score` in OASIS's `recsys.py`.

**Problem**: Default Reddit hot-score penalizes controversial posts. A post with 50 likes + 50 dislikes scores the same as zero engagement.

**Solution**: Boost by total engagement (likes + dislikes), not just net score.

```python
def calculate_hot_score(num_likes, num_dislikes, created_at, controversy_boost=0.0):
    s = num_likes - num_dislikes
    total = num_likes + num_dislikes
    order = log(max(abs(s), 1), 10)
    sign = 1 if s > 0 else -1 if s < 0 else 0

    # Controversy component — rewards total engagement regardless of direction
    controversy = log(max(total, 1), 10) * controversy_boost

    seconds = epoch_seconds - 1134028003
    return sign * order + controversy + seconds / 45000
```

**Behavior**:
- `0.0`: Default Reddit (no change)
- `0.5`: Mildly boosts controversial posts
- `1.0`: 50-likes/50-dislikes scores like 100-likes/0-dislikes

**UI**: Slider on Screen 3 with tooltip: *"Controversy Amplification: Controls how much the recommendation system boosts posts with high engagement regardless of whether they're liked or disliked. At 0, only universally liked posts rise. At 1.0, posts with equal likes and dislikes are treated as highly engaging. This models how real social media platforms use ragebait to amplify controversy and boost user retention. Higher values create more polarized feeds."*

See: [docs/v2/backend/controversy-boost.md](backend/controversy-boost.md)

### 3.3 Gemini Context Caching

**Decision**: Cache shared prompt prefix once per simulation session; all agent calls reference the cache ID.

**Savings**: ~75% reduction on cached input tokens.

| Cached (shared) | Dynamic (per agent) |
|:-----------------|:--------------------|
| System prompt | Agent persona text |
| Policy document | Thread context (posts they've seen) |
| Guiding prompts | Current round instructions |
| Simulation rules | Specific comments to respond to |

**Cost example** (500 agents × 5 rounds):
- Without caching: ~$1.68
- With caching: ~$0.42 (shown in UI with strikethrough comparison)
- Savings badge: **-75%** in green

For OpenAI/Ollama: no caching available, full tokens charged. UI shows "N/A" for caching savings.

See: [docs/v2/backend/context-caching.md](backend/context-caching.md)

### 3.4 Name Extraction Fix

**Decision**: Zero-cost fix via interview prompt piggyback.

1. **During sampling**: Regex extracts candidate name from Persona text (current behavior)
2. **During OASIS checkpoint interview**: Add to prompt: `"Please confirm your name at the start of your response. If your name was incorrectly extracted, provide your correct name."`
3. **After response**: Parse first line for confirmed name, update `display_name`

No additional API calls — piggybacks on the existing checkpoint interview.

### 3.5 Report + Chat Layout

**Decision**: 60/40 split with a **three-way view toggle**:

| Mode | Description |
|:-----|:------------|
| **Report Only** | Full-width report panel, chat hidden |
| **Report + Chat** | 60/40 split (default) — report left, chat right |
| **Chat Only** | Full-width chat interface with agent sidebar |

The toggle is a segmented control in the header bar. The chat panel supports:
- Group segments: Top Dissenters, Top Supporters, Most Engaged (Mixed)
- 1:1 Agent Chat: Click any agent to start private conversation
- ReportAgent: Chat that can cite evidence from the report

See: [docs/v2/frontend/screen-4-report-chat.md](frontend/screen-4-report-chat.md)

### 3.6 Analytics/Visualizations Screen

**Decision**: Dedicated screen (not embedded in report) showing advanced simulation analytics:

1. **Polarization Index over Time** — Bar chart per round, color-coded severity
2. **Opinion Flow (Sankey)** — Initial → Final stance migration
3. **Influence Centrality** — Network graph, node size = influence score, color = stance
4. **Viral Cascade Analysis** — Tree view of the thread that caused biggest opinion shift

All visualizations reference post IDs and agent IDs for drill-down.

See: [docs/v2/frontend/screen-5-analytics.md](frontend/screen-5-analytics.md)

### 3.7 Comment Depth

**Decision**: Top-level comments only (no nested replies). Simpler, fewer API calls, lower cost.

### 3.8 Report Export

**Decision**: DOCX format (not PDF). Uses `python-docx` server-side.
- Includes: cover page, all report sections, embedded chart images, tables
- Users can edit after download
- Backend endpoint: `GET /api/v2/console/session/{id}/report/export`

### 3.9 Dynamic Metrics per Use Case

Each use case has specific metrics computed from checkpoint interviews. The LLM answers structured questions during checkpoints, and we aggregate responses. No separate sentiment classifier needed.

| Use Case | Metric 1 | Metric 2 | Checkpoint Question |
|:---------|:---------|:---------|:--------------------|
| **Policy Review** | Approval Rate (% of agents with score ≥ 7) | Net Sentiment (mean score) | "Do you approve of this policy? Rate 1-10." |
| **Ad Testing** | Estimated Conversion (% "would buy") | Engagement Score | "Would you try this product? (yes/no)" |
| **PMF Discovery** | Product Interest (% positive) | Target Fit Score | "Is this something you need? (1-10)" |
| **Customer Review** | Satisfaction (mean 1-10) | Recommendation (NPS: % ≥ 8) | "Would you recommend? (1-10)" |

Each metric card has an **ⓘ tooltip** explaining the heuristic in plain English.

See: [docs/v2/backend/metrics-heuristics.md](backend/metrics-heuristics.md)

### 3.10 Agent Prompts per Use Case

All prompts are externalized to YAML config files:

```yaml
# config/prompts/policy-review.yaml
agent_personality_modifiers:
  - "Express genuine concern about how this policy affects your daily life and family"
  - "When responding to other comments, engage directly with their specific arguments"
  - "If you strongly disagree, explain why with concrete personal examples"

checkpoint_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
  - question: "What is your overall sentiment? Rate 1-10."
    type: "scale"
    metric_name: "net_sentiment"
```

See: [docs/v2/backend/config-system.md](backend/config-system.md)

### 3.11 Group Chat Selection Algorithm

After simulation, compute **influence score** per agent:

```
influence = 0.4 × normalized_post_engagement
           + 0.3 × normalized_comment_count
           + 0.3 × normalized_reply_received
```

Where `engagement = total (likes + dislikes)` on their posts.

Segment by stance (positive/negative/neutral from checkpoint scores), pick top 5 per segment.

---

## 4. UI/UX Design Reference

All screens have been mocked up in Paper MCP. The artboard names and IDs are:

| Screen | Artboard Name | Paper MCP ID |
|:-------|:-------------|:-------------|
| Screen 0 | Screen 0 — Onboarding Modal | `8A-0` |
| Screen 1 | Screen 1 — Knowledge Graph (V2) | `F6-0` |
| Screen 2 | Screen 2 — Population Sampling (V2) | `H9-0` |
| Screen 3 | Screen 3 — Simulation (V2) | `9U-0` |
| Screen 4 | Screen 4 — Report + Chat Drawer (Option B) | `CZ-0` |
| Screen 4 Alt | Screen 5 — Report + Chat (Option A Split) | `NW-0` |
| Screen 5 | Screen 6 — Full Page Chat (Option C) | `PN-0` |
| Visualizations | Report Metrics Visualizations | `K5-0` |

**Design tokens** (from `frontend/src/index.css`):
- Background: `#0d0f14` (near-black)
- Card surface: `hsla(225, 30%, 8%, 0.4)` with `border: 1px solid hsla(225, 20%, 30%, 0.2)`
- Primary accent: `hsl(24, 100%, 55%)` (orange — CTAs, active states)
- Success/Supporter: `hsl(160, 84%, 42%)` (emerald green)
- Danger/Dissenter: `hsl(0, 78%, 58%)` (red)
- Neutral: `hsl(215, 20%, 55%)` (muted blue-gray)
- Warning: `hsl(38, 92%, 54%)` (amber)
- Info: `hsl(196, 92%, 56%)` (cyan)
- Purple accent: `hsl(266, 70%, 64%)`
- Fonts: `Inter` (UI), `JetBrains Mono` (data/numbers)
- Border radius: `10-14px` for cards, `99px` for pills/tags

> **Important**: Use the Paper MCP `get_jsx` tool on any artboard to extract the CSS/JSX structure for implementation reference. The mockups are static — all state management, API logic, and interactivity must be coded fresh.

See sub-documents for per-screen implementation specs:
- [Screen 0 — Onboarding](frontend/screen-0-onboarding.md)
- [Screen 1 — Knowledge Graph](frontend/screen-1-knowledge-graph.md)
- [Screen 2 — Population Sampling](frontend/screen-2-population-sampling.md)
- [Screen 3 — Simulation](frontend/screen-3-simulation.md)
- [Screen 4 — Report + Chat](frontend/screen-4-report-chat.md)
- [Screen 5 — Analytics](frontend/screen-5-analytics.md)

---

## 5. Implementation Phases

### Phase Q: Foundation & Architecture (3-4 days)

| ID | Task | Detail Doc |
|:---|:-----|:-----------|
| Q1 | Archive old docs | `BRD.md` → `archive/v1/BRD_V1.md` ✅ Done |
| Q2 | Create `config/` directory | All 4 use-case YAML files + 2 country YAMLs |
| Q3 | Config service | `config_service.py` — loads prompts, countries, metrics |
| Q4 | Refactor backend prompt loading | All hardcoded prompts → config service |
| Q5 | Remove Ollama-or-die startup | Graceful degradation: launch without Ollama |
| Q6 | Create `docker-compose.yml` | frontend, backend, falkordb, oasis-sidecar |
| Q7 | Create Dockerfiles | Multi-stage builds for frontend and backend |
| Q8 | Gemini Context Caching wrapper | `CachingLLMClient` class |
| Q9 | Session-ID all state containers | Multi-user readiness pattern |

See: [docs/v2/backend/config-system.md](backend/config-system.md), [docs/v2/infrastructure/docker.md](infrastructure/docker.md)

### Phase R: Multi-Country & Dynamic Filters (3-4 days)

| ID | Task | Detail Doc |
|:---|:-----|:-----------|
| R1 | Onboarding modal UI | Country, provider, model, API key, use case |
| R2 | Country selector with dataset auto-detection | Backend reads Parquet schema per country |
| R3 | Dynamic filter generation from Parquet | No hardcoded filter fields |
| R4 | GeoJSON maps for SG + USA | `CountryMap.tsx` component |
| R5 | Refactor persona sampling | Country-specific config paths |
| R6 | Token tracking service | Wraps LLM calls, counts tokens |
| R7 | Token/cost display UI | Shows cached vs uncached comparison |

See: [docs/v2/frontend/screen-0-onboarding.md](frontend/screen-0-onboarding.md), [docs/v2/frontend/screen-2-population-sampling.md](frontend/screen-2-population-sampling.md)

### Phase S: Screen 1 Enhancements (2-3 days)

| ID | Task | Detail Doc |
|:---|:-----|:-----------|
| S1 | Use-case mode toggle on Screen 1 | Radio buttons matching onboarding selection |
| S2 | Editable guiding prompt cards | Per use-case, loaded from config |
| S3 | Multi-document upload | Per-file progress bars, drag-and-drop |
| S4 | URL scraper | Built-in HTTP + BeautifulSoup |
| S5 | Paste-text inline input | Textarea alternative to file upload |
| S6 | Multi-document LightRAG merge | Combine graphs from multiple docs |
| S7 | Draggable graph nodes | Force-directed graph interaction |

See: [docs/v2/frontend/screen-1-knowledge-graph.md](frontend/screen-1-knowledge-graph.md)

### Phase T: Simulation Enhancements (4-5 days)

| ID | Task | Detail Doc |
|:---|:-----|:-----------|
| T1 | Horizontal progress bar | Percentage-based: "Round 3 (62%)" |
| T2 | Fix viewport CSS overflow | `max-height: 100vh` + internal scroll |
| T3 | Dislikes on posts + comment votes | Already in OASIS, just expose in UI |
| T4 | Name verification | Zero-cost interview piggyback |
| T5 | Controversy boost | `calculate_hot_score` edit + UI slider |
| T6 | Per-use-case agent prompts | From config YAML |
| T7 | Dynamic metric cards with tooltips | Per-use-case metrics from § 3.9 |
| T8 | OASIS Interview Action | Checkpoint stance extraction |

See: [docs/v2/frontend/screen-3-simulation.md](frontend/screen-3-simulation.md), [docs/v2/backend/controversy-boost.md](backend/controversy-boost.md)

### Phase U: Report & Chat Overhaul (5-6 days)

| ID | Task | Detail Doc |
|:---|:-----|:-----------|
| U1 | Build 60/40 Report+Chat layout | With view toggle (3 modes) |
| U2 | Prompt-structured report sections | Report answers guiding prompts |
| U3 | Plan-first ReportAgent | LLM generates plan → deterministic metrics → LLM synthesizes |
| U4 | Group chat | Top 5-10 per segment, labeled by stance |
| U5 | 1:1 agent chat tab | Click agent → private conversation |
| U6 | Agent side panel | Name, demographics, core viewpoint, key posts |
| U7 | DOCX export | `python-docx` server-side generation |
| U8 | Document metric heuristics | `docs/v2/backend/metrics-heuristics.md` |

See: [docs/v2/frontend/screen-4-report-chat.md](frontend/screen-4-report-chat.md)

### Phase U2: Analytics Screen (3-4 days)

| ID | Task | Detail Doc |
|:---|:-----|:-----------|
| U2-1 | Polarization Index chart | Bar chart per round |
| U2-2 | Opinion Flow Sankey | Initial → Final stance |
| U2-3 | Influence Centrality graph | Network visualization |
| U2-4 | Viral Cascade tree | Thread that caused biggest shift |
| U2-5 | Backend metrics endpoints | `/api/v2/.../metrics` |

See: [docs/v2/frontend/screen-5-analytics.md](frontend/screen-5-analytics.md), [docs/v2/backend/metrics-heuristics.md](backend/metrics-heuristics.md)

### Phase V: Memory Migration (2-3 days)

| ID | Task | Detail Doc |
|:---|:-----|:-----------|
| V1 | Integrate Graphiti + FalkorDB | Docker stack + Python client |
| V2 | Migrate agent memory from Zep | Replace `memory_service.py` internals |
| V3 | Temporal memory queries | Chat uses Graphiti for context |
| V4 | Zep Cloud optional fallback | Env var toggle |
| V5 | Test memory persistence | Across simulation sessions |

See: [docs/v2/infrastructure/graphiti.md](infrastructure/graphiti.md)

### Phase W: Polish & Integration (3-4 days)

| ID | Task |
|:---|:-----|
| W1 | End-to-end: onboard → upload → sample → simulate → report → chat |
| W2 | Demo mode cache regeneration for V2 |
| W3 | Docker compose full-stack validation |
| W4 | Performance testing |
| W5 | Update README and all docs |

---

## 6. API Contract (New/Modified Endpoints)

```
# Session management
POST   /api/v2/session/create     → {session_id, config}
PATCH  /api/v2/session/{id}/config → Update country, model, use_case

# Screen 0: Onboarding
GET    /api/v2/countries           → [{name, code, dataset_path, flag_emoji}]
GET    /api/v2/providers           → [{name, models: [...], requires_api_key: bool}]

# Screen 1: Knowledge Graph (existing + modifications)
POST   /api/v2/console/session/{id}/upload  → Multi-file upload
POST   /api/v2/console/session/{id}/scrape  → {url: string} → scraped text

# Screen 2: Population Sampling (existing + modifications)
GET    /api/v2/console/session/{id}/filters → Dynamic filter schema from Parquet

# Screen 3: Simulation
POST   /api/v2/console/session/{id}/simulate → {rounds, controversy_boost, ...}
GET    /api/v2/console/session/{id}/simulation/metrics → Real-time dynamic metrics

# Screen 4: Report + Chat
GET    /api/v2/console/session/{id}/report → Full report JSON
GET    /api/v2/console/session/{id}/report/export → DOCX file download
POST   /api/v2/console/session/{id}/chat/group → {segment, message} → agent responses
POST   /api/v2/console/session/{id}/chat/agent/{agent_id} → 1:1 agent chat

# Screen 5: Analytics
GET    /api/v2/console/session/{id}/analytics/polarization → Per-round polarization
GET    /api/v2/console/session/{id}/analytics/influence → Top influencers + graph
GET    /api/v2/console/session/{id}/analytics/cascades → Top viral threads
GET    /api/v2/console/session/{id}/analytics/opinion-flow → Sankey data

# System
GET    /api/v2/token-usage/{session_id} → {total_tokens, estimated_cost, caching_savings}
```

---

## 7. Testing Strategy

### 7.1 Backend Unit Tests (`pytest`)

| Test Area | What to Test |
|:----------|:-------------|
| Config service | YAML loading, fallback to defaults, invalid YAML handling |
| Token tracker | Token counting accuracy, cost calculation per provider |
| Metrics service | Polarization computation, influence graph scores, cascade depth |
| Controversy boost | Hot-score calculation with different boost values |
| Context caching | Cache creation, reference, cleanup |
| DOCX export | File generation, section completeness |

### 7.2 Frontend Component Tests

| Component | What to Test |
|:----------|:-------------|
| OnboardingModal | Country selection updates config, provider changes model list |
| ControversySlider | Value changes fire callback, tooltip renders |
| MetricCard | Tooltip appears on hover, metric value displays correctly |
| ReportChat | View toggle switches modes, chat messages render |

### 7.3 Integration Tests

- Full E2E: Onboard → Upload → Sample → Simulate → Report → Chat
- Cross-country: Same document, SG vs USA personas
- Token tracking: Compare tracked count vs actual API response
- DOCX export: Renders correctly in Word/Google Docs
- Docker compose: `docker compose up` → all services healthy

### 7.4 Build Validation

```bash
cd frontend && npm run build    # Production bundle compiles
cd backend && pytest tests/     # All unit tests pass
docker compose up --build       # Full stack starts cleanly
```

---

## 8. External References

| Resource | URL |
|:---------|:----|
| OASIS GitHub | https://github.com/camel-ai/oasis |
| OASIS Docs | https://docs.oasis.camel-ai.org/ |
| OASIS Paper | https://arxiv.org/abs/2411.11581 |
| MiroFish GitHub | https://github.com/666ghj/MiroFish |
| MiroFish Demo | https://666ghj.github.io/mirofish-demo/console |
| Graphiti GitHub | https://github.com/getzep/graphiti |
| FalkorDB | https://www.falkordb.com/ |
| Nemotron Frontend V2 (deprecated, has interactive graph) | https://github.com/pebblepaw/Nemotron-Frontend-V2.0 |
| Nvidia Nemotron Datasets | Various per country |

---

## 9. Sub-Document Index

### Frontend Specs
- [Screen 0 — Onboarding](frontend/screen-0-onboarding.md)
- [Screen 1 — Knowledge Graph](frontend/screen-1-knowledge-graph.md)
- [Screen 2 — Population Sampling](frontend/screen-2-population-sampling.md)
- [Screen 3 — Simulation](frontend/screen-3-simulation.md)
- [Screen 4 — Report + Chat](frontend/screen-4-report-chat.md)
- [Screen 5 — Analytics](frontend/screen-5-analytics.md)

### Backend Specs
- [Config System](backend/config-system.md)
- [Controversy Boost](backend/controversy-boost.md)
- [Context Caching](backend/context-caching.md)
- [Metrics & Heuristics](backend/metrics-heuristics.md)

### Infrastructure
- [Docker Setup](infrastructure/docker.md)
- [Graphiti + FalkorDB](infrastructure/graphiti.md)
