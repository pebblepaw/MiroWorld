# MiroWorld — Rehearse the Future Before It Happens

> Conference on SaaS & Cloud Services · April 2026

---

## 1. Business Pitch

**What if you could stress-test a policy, product, or campaign on a digital population before real-world launch?**

MiroWorld is a multi-agent AI simulation platform that constructs a high-fidelity digital society from real population data. Upload any source document — a policy draft, product brief, or ad campaign — and within minutes, a demographically-representative population of AI agents reads, debates, and reacts to it across a simulated social network. You get a structured analysis report, live discourse logs, and direct conversation with any agent about their stance.

**Core value proposition:**
- Zero-risk rehearsal for decisions that affect real people
- Grounded in real population demographics, not generic "average users"
- BYOK (Bring Your Own Key) — no hidden LLM costs; users supply their own API key
- Local-first & open source (AGPL), with an optional hosted cloud tier
- Three use cases: Public Policy Testing · Product & Market Research · Campaign & Content Testing

**Stack:** React + Vite (frontend) · FastAPI + Python (backend) · OASIS multi-agent engine · LightRAG knowledge extraction · SQLite FTS5 (local) / PostgreSQL (cloud)

---

## 2. The Nemotron Population Dataset (NVIDIA)

Population realism is the foundation of the simulation. MiroWorld draws from **NVIDIA's Nemotron-Personas** datasets on Hugging Face, which provide synthetic-but-demographically-grounded population personas for specific geographies.

**Currently supported:**
- `nvidia/Nemotron-Personas-Singapore` — profiles keyed by HDB Planning Area (28 districts)
- `nvidia/Nemotron-Personas-USA` — profiles keyed by US State

**What a persona contains:**
- Age, gender, education, occupation, income bracket
- Residential area / geographic region
- Cultural and social background descriptors
- Values and general disposition markers

**How it is used:**
- Stored as Parquet files on disk, queried at runtime via DuckDB
- Population filter controls on Screen 2 are dynamically derived from the dataset schema — no hardcoded assumptions
- Personas are injected into agent system prompts verbatim, giving each agent a consistent identity throughout the simulation

**Limitation:** Nemotron datasets are synthetic and reflect a point-in-time snapshot. Demographic changes and current events post-dataset-creation are not reflected.

---

## 3. Screen 1 — Knowledge Extraction (LightRAG)

**Goal:** Convert uploaded documents into a structured knowledge graph that grounds the simulation.

**Inputs accepted:**
- File upload (PDF, DOCX, TXT)
- URL scraping
- Pasted text

**Process:**
1. User uploads one or more source documents
2. Backend calls `LightRAGService.process_document()` → LightRAG performs entity and relation extraction
3. Extracted entities (concepts, organisations, persons, policies) and their relations are merged into a session-scoped knowledge graph
4. Knowledge graph rendered in the browser as an interactive force-directed graph (react-force-graph-2d) — draggable, filterable by entity type

**Analysis questions:**
- Seeded from the selected use-case YAML (e.g., `approval_rate` scale question, `policy_viewpoints` open-ended)
- User can add, edit, and delete custom questions directly on this screen
- Custom question metadata (`type`, `metric_name`, `threshold`, etc.) is auto-generated via `POST /questions/generate-metadata`
- The final question list is persisted to the session config and governs all downstream scoring, reporting, and analytics

**Session design:** Each run is scoped to a `session_id`. All analysis questions, extracted knowledge, and simulation results are isolated per session.

---

## 4. Screen 2 — Population Sampling

**Goal:** Construct a demographically-representative cohort from the Nemotron dataset.

**How sampling works:**
1. Backend reads the country YAML to determine available filter dimensions
2. Filter controls are dynamically generated from dataset schema — no hardcoded country assumptions
3. User configures:
   - Sample size (n agents)
   - Geographic scope (Planning Area for SG; State for USA)
   - Age range, gender, education, income (range sliders & multi-select chips)
   - Free-text sampling instruction for targeting a specific demographic profile
4. Backend queries the Parquet dataset via DuckDB → returns a cohort preview
5. A token-cost estimate is shown before simulation launch, reflecting the active LLM provider and model
   - Gemini: shows cached vs. uncached token cost separately
   - OpenAI / OpenRouter: standard token estimate
   - Ollama: displayed as free (local)

**Cohort visualisation:**
- Geographic distribution map
- Demographic breakdown charts (age, gender, education)
- Waffle-style agent explorer

**Tier-gated limits:**
- Free tier: max 100 agents, max 10 rounds
- Paid tier: max 1,000 agents, max 50 rounds

---

## 5. Screen 3 — Social Simulation (OASIS Engine)

**Goal:** Run a live multi-round social media discourse simulation.

**Engine:** [OASIS (Open Agent Social Interaction Simulations)](https://github.com/camel-ai/oasis) by CAMEL-AI, running in a Python 3.11 sidecar process.

**Simulation flow:**
1. Each analysis question seeds an initial discussion thread
2. In each round, every agent reads the current feed and chooses an action: post, comment, like, dislike, repost
3. Agent actions are LLM-generated, conditioned on the agent's Nemotron persona and current feed state
4. After each round, checkpoint metrics are recorded — every agent answers all quantitative analysis questions on a 1–10 scale
5. Simulation proceeds for N rounds (default 6, up to 50 on paid tier)

**Feed ranking:**
- Reddit-style "hot score" by default
- **Controversy boost** switch: off = `0.0`, on = `0.5` — elevates high-engagement controversial posts that would otherwise be suppressed

**Live UI elements:**
- Round counter & elapsed time
- Post/comment/reaction activity counters
- Dynamic metric cards (approval %, NPS trend, etc.) updating each round
- Hottest thread display
- Full live feed with expandable comment threads

**Persistence:** Simulation state is stored in AppContext and SQLite. Navigating to earlier screens and back does not reset the feed or counters.

**Backend streaming:** Frontend subscribes to `GET /simulation/stream` via SSE for real-time updates. Short, user-readable error messages appear on-screen for failures; full diagnostics stay in backend logs.

---

## 6. Screen 4 — Report & Chat

**Goal:** Deliver structured analysis and enable direct conversation with simulated agents.

### 6a. Generated Report
- Triggered automatically on simulation completion
- Pipeline: load agents + interactions → resolve analysis questions → compute metric deltas → generate per-question LLM analysis → assemble executive summary
- **Metric delta cards:** each quantitative question shows `initial → final` value with direction indicator
  - `yes/no` questions → % of agents answering yes
  - `scale` with threshold → % meeting threshold
  - `scale` without threshold → mean score
- Report sections include supporting quotes drawn from actual agent posts
- Export to DOCX available

### 6b. Chat Panel (three view modes: Report Only / Split / Chat Only)
- **Group chat:** message all agents simultaneously; supporters and dissenters respond in character, grounded in their simulation history
- **1:1 agent chat:** pick any agent and have a direct conversation; agent responds consistent with their persona and their simulation activity
- **MetricSelector filter:** dropdown lets user focus group chat on a specific analysis question — filters which agents appear as supporters/dissenters
- **Memory backend:** SQLite FTS5 full-text search over interactions, transcripts, and checkpoint records — no external graph database required
- Each chat query retrieves: agent's own posts, comments received, checkpoint answers → assembled into context for the LLM

---

## 7. Screen 5 — Analytics

**Goal:** Surface aggregate and per-metric behavioural trends across the simulated population.

*[Screenshots to be inserted by author]*

**Key visualisations:**
- **Polarization Index** — stance distribution (supporter/neutral/dissenter) over simulation rounds; per-metric or aggregate
- **Opinion Flow (Sankey)** — how agents migrated between stances from baseline to final checkpoint
- **Demographic Sentiment Map** — geographic or demographic breakdown of agent sentiment; responds to metric selector
- **Key Opinion Leaders** — agents ranked by engagement influence (replies attracted, reposts triggered)
- **Viral Discussion Cascades** — top threads by engagement depth and reach

**MetricSelector:** all metric-aware visualisations respond to a shared dropdown. Example: a campaign may show 73% aggregate conversion intent but only 41% on a specific credibility sub-question — the selector surfaces hidden pockets of resistance.

**Stance thresholds (uniform across the system):**
- Score ≥ 7.0 → supporter
- Score 5.0–6.9 → neutral
- Score < 5.0 → dissenter

---

## 8. Cloud Hosting Architecture

### 8a. Design Philosophy: BYOK + Configuration-Driven Deployment

MiroWorld is **Bring Your Own Key** — users supply their LLM API key (Gemini, OpenAI, OpenRouter, or local Ollama). The platform never pays LLM costs on behalf of users. Hosting costs are therefore compute and storage only, making cloud deployment economically viable.

One codebase, multiple deployment targets — switched via environment variables (`DATABASE_URL`, `UPLOAD_STORAGE`, `AUTH_ENABLED`, `BOOT_MODE`).

### 8b. AWS Architecture (Primary)

```
User ──HTTPS──▶ CloudFront (CDN)
                  │
                  ├── S3 (React static build)       ~$0.02/mo
                  │
                  └── ALB (Application Load Balancer) ~$16/mo
                        │
                        ▼
                  ECS Fargate (FastAPI + OASIS)      ~$15–30/mo
                        │
                        ├── EFS (SQLite + uploads)   ~$0.30/GB/mo
                        │
                        └── RDS PostgreSQL           ~$15/mo
                              (multi-tenant sessions,
                               FTS chat memory,
                               user accounts)
```

**Why ECS Fargate over Lambda:** OASIS simulations run for minutes (not milliseconds), need persistent state across rounds, and require a filesystem for SQLite. Lambda's 15-minute timeout and stateless model are incompatible.

**Total estimated cost: ~$35–50/month.** Startup AWS credits ($200) cover 4–6 months.

### 8c. Scaling & Cost Management Techniques

| Technique | Purpose | Implementation |
|-----------|---------|----------------|
| **Fargate scale-to-zero** | Cut compute cost when idle | Scheduled stop at night; auto-start on first request |
| **Tier-gated simulation limits** | Prevent runaway LLM spend by power users | Free: 100 agents, 10 rounds. Paid: 1,000 agents, 50 rounds |
| **Gemini context caching** | Reduce repeated token spend on shared simulation context | `token_tracker.py` tracks cached vs. uncached tokens; estimated savings shown on Screen 2 |
| **Session TTL & garbage collection** | Reclaim storage from expired sessions | Free tier: 14-day retention. Cron job deletes expired sessions + uploaded files |
| **Per-user rate limiting** | Prevent abuse even with BYOK | FastAPI middleware throttles concurrent simulation requests per user |
| **PostgreSQL row-level security** | User data isolation without application-level filtering | `WHERE user_id = current_setting('app.user_id')` enforced at DB level |
| **BYOK API key encryption** | Protect stored credentials | AES encryption at rest using server-side `ENCRYPTION_KEY`; keys never logged |
| **S3 + CloudFront for frontend** | Eliminate compute cost for static assets | React build to S3; CloudFront CDN with aggressive cache headers |
| **EFS for shared storage** | Persistent volume across Fargate restarts | Per-session SQLite files and uploads survive container replacement |

### 8d. Authentication & Payments

**Auth:** OAuth (Google / GitHub) + magic link email — no password management overhead.

**Payments (Stripe):**
- Free: 5 active sessions, 100 agents, 10 rounds, 14-day retention
- Paid (~$9–19/month TBD): unlimited sessions, 1,000 agents, 50 rounds, unlimited retention
- Stripe Checkout → `checkout.session.completed` webhook → backend updates `user.tier` in PostgreSQL
- Zero upfront Stripe cost; 2.9% + $0.30 per transaction only

### 8e. Local Deployment (Open Source)

Both deployment paths supported from the same repository (AGPL license):

**Source code path** (developers):
```bash
git clone <repo> && cd miroworld
python3 -m venv .venv && source .venv/bin/activate
pip install -e backend/
cd frontend && npm install && cd ..
./quick_start.sh --mode live
```
Requires: Python 3.12, Python 3.11 (OASIS), Node.js 20+. No Docker needed.

**Docker path** (evaluators):
```bash
cp .env.example .env   # add your LLM API key
docker compose up
```
Requires: Docker Desktop only.

---

## 9. Future Work & Limitations

### Current Limitations

- **Nemotron dataset is not real-time** — personas are a synthetic snapshot; demographic shifts and post-release events are not captured
- **Only Singapore and USA datasets available** — other geographies require new Nemotron-equivalent datasets or alternative population data sources
- **Simulation quality is LLM-dependent** — agent diversity and realism vary with the chosen model; free/small models may produce repetitive responses
- **Single-machine OASIS runner** — large simulations (1,000 agents × 50 rounds) are CPU-intensive; no distributed simulation support yet
- **LightRAG graph streaming is batch** — knowledge graph appears all at once after ingestion completes; real-time node-by-node streaming is planned but not yet implemented

### Planned Future Work

- **Additional country datasets** — expand Nemotron-Personas support to EU, ASEAN, and other regions; explore integration with national census APIs
- **LightRAG real-time graph streaming** — chunked SSE ingestion so nodes appear incrementally as the document is processed (designed, not yet implemented)
- **Distributed OASIS simulation** — shard agent populations across workers for large-scale runs
- **Longitudinal simulation** — multi-session runs that persist agent memory and track opinion evolution over time
- **Company / organisation personas** — simulate institutional actors (regulators, firms, NGOs) alongside individual citizen agents
- **Richer analytics export** — raw interaction logs, per-agent stance timelines, and cohort comparison exports for downstream research use
