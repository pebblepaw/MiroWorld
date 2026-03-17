# McKAInsey Technical Decisions Log

This document consolidates all architectural and tooling decisions made during the research and planning phase. It covers the analysis of MiroFish (a comparable open-source project), the evaluation of candidate tools, and the final technology choices for McKAInsey.

---

## 1. MiroFish Comparative Analysis

**Source:** [github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish) — a "swarm intelligence prediction engine" that went #1 on GitHub Trending in March 2026.

### Similarities with McKAInsey

| Area | MiroFish | McKAInsey |
|:-----|:---------|:----------|
| Core idea | Simulate population/group reactions to scenarios using LLM agents | Same |
| Use case | Policy testing, public opinion prediction, campaign evaluation | Same |
| Multi-agent | Thousands of agents with independent personalities | Same (via Nemotron personas) |
| Agent memory | Long-term memory across simulation rounds | Same |
| Deliberation | Agents interact and influence each other's opinions | Same |
| Report output | Automated strategic report generated post-simulation | Same (ReportAgent) |
| Interactive chat | Users can chat with any agent post-simulation | Same |
| Web dashboard | React frontend + Python backend | Same |

### Key Differences

| Area | MiroFish | McKAInsey |
|:-----|:---------|:----------|
| Persona source | Generated from seed documents via LLM extraction | Pre-built from NVIDIA Nemotron-Personas-Singapore (888K census-calibrated personas) |
| Knowledge representation | GraphRAG (entity-relationship graph from seed material) | LightRAG (knowledge graph + vector retrieval hybrid) |
| Simulation engine | OASIS (CAMEL-AI, up to 1M agents) | Also OASIS — adopted after this analysis |
| Agent memory | Zep Cloud (managed temporal knowledge graph) | Also Zep Cloud — adopted after this analysis |
| LLM | Qwen (Alibaba) via OpenAI SDK | Gemini API (Google) with context caching |
| Cloud | Self-hosted / Docker (no cloud provider) | AWS-native (S3, Lambda, EC2) |
| Scope | General-purpose prediction (politics, finance, fiction) | Singapore-specific policy & campaign consulting |

### What We Adopted From MiroFish

1. **OASIS simulation engine** — replaces our custom Step Functions scatter-gather with a battle-tested social simulation platform
2. **Zep Cloud for agent memory** — replaces raw DynamoDB for agent state, gives us temporal fact tracking out of the box
3. **ReportAgent pattern** — dedicated post-simulation analysis agent with tool access
4. **Interactive agent chat** — post-simulation chat with any individual agent
5. **5-stage workflow** — Scenario Setup → Population Sampling → Simulation → Report → Interactive Deep-Dive
6. **Two-stage output model** — immediate reactions (pre-OASIS) then post-deliberation shifts (post-OASIS)

### What We Did NOT Adopt

- **OASIS's local-only deployment** — we run it on EC2 within our AWS architecture
- **Qwen LLM** — we use Gemini for free credits
- **LLM-generated personas** — we use pre-built Nemotron census data (stronger credibility)
- **Full GraphRAG pipeline** — we use LightRAG instead (lighter weight, same benefit)

---

## 2. GraphRAG Tool Evaluation

### Options Evaluated

| Tool | What It Does | Verdict |
|:-----|:-------------|:--------|
| **[PageIndex](https://github.com/VectifyAI/PageIndex)** | Vectorless document retrieval — builds a hierarchical "table of contents" tree from PDFs. No entity/relationship extraction. | ❌ **Rejected** — not a GraphRAG at all. Builds a smart TOC, not a knowledge graph. |
| **[microsoft/graphrag](https://github.com/microsoft/graphrag)** | Microsoft's official GraphRAG. Extracts entities + relationships, builds knowledge graph, creates community summaries. Outputs Parquet files. | ✅ Viable but heavyweight |
| **[nano-graphrag](https://github.com/gusye1234/nano-graphrag)** | Lightweight single-file reimplementation of Microsoft GraphRAG (~800 lines core). | ✅ Viable, simpler |
| **[LightRAG](https://github.com/HKUDS/LightRAG)** | Combines knowledge graphs with vector retrieval. Simpler and cheaper than Microsoft's version. Supports multiple LLMs including Gemini. | ✅ **Selected** |

### Decision: LightRAG

**Rationale:**
- Combines the entity/relationship extraction we need with vector retrieval for semantic search
- Lighter weight than microsoft/graphrag — faster setup, less compute
- Supports Gemini natively — no model compatibility hacks
- The knowledge graph helps agents receive only policy details relevant to their demographic profile, reducing prompt size and improving response quality

### How LightRAG Fits the Architecture

```
User uploads policy/campaign document
        ↓
LightRAG extracts entities + relationships
(e.g., "EV Toll" → affects → "Woodlands commuters")
        ↓
Knowledge graph stored alongside simulation data
        ↓
Each agent's prompt includes only the subgraph
relevant to its demographic profile
```

---

## 3. Agent Memory Tool Evaluation

### Options Evaluated

| Tool | What It Does | Verdict |
|:-----|:-------------|:--------|
| **Amazon DynamoDB** (original plan) | Key-value NoSQL store on AWS. Manual implementation of memory summarization, relevance scoring, temporal tracking. | ❌ Too much custom code for agent memory semantics |
| **[Zep Cloud](https://www.getzep.com/)** | Managed temporal knowledge graph for AI agent memory. Auto-extracts entities/facts, validity windows, hybrid retrieval (semantic + BM25 + graph traversal). Free tier. | ✅ **Selected as primary** |
| **[Graphiti](https://github.com/getzep/graphiti)** (open-source Zep) | Open-source engine behind Zep Cloud. Requires Neo4j/FalkorDB/Kuzu graph DB backend. Supports Gemini natively. | ✅ **Stretch goal** — use if time allows, run FalkorDB on EC2 |

### Decision: Zep Cloud (primary), Graphiti (stretch goal)

**Rationale:**
- **Zep Cloud** gives us temporal fact tracking, automatic memory summarization, and semantic search — all features we'd have to build manually on DynamoDB
- **Free tier** is sufficient for the project scope
- Facts have **temporal validity windows** — when an agent changes its mind during deliberation, the old opinion is invalidated (not deleted), enabling pre-vs-post opinion shift analysis
- Presents as **multi-cloud architecture** (AWS + Zep Cloud)
- If time allows, Graphiti + FalkorDB on EC2 would replace Zep Cloud for a fully self-hosted solution

### Zep Cloud Memory Model

```
Episodes (raw events)
├── "Agent said: I oppose the toll"
├── "Agent heard: 3 others support it"
└── "Agent revised: cautiously open"
        ↓ (automatic extraction)
Entity Nodes + Fact Edges (with time validity)
├── "Agent opposes toll" [valid T1→T2]
├── "Agent cautiously open" [valid T2→∞]
└── Retrieval = semantic + BM25 + graph traversal
```

**Integration with AWS:**
- S3 + Parquet stores static persona definitions (Nemotron — never changes)
- Zep Cloud stores runtime agent memory generated during simulation (created fresh each run)
- These are completely independent — no conflict

---

## 4. Simulation Engine Decision

### Decision: OASIS (camel-ai/oasis)

OASIS is not just an orchestrator — it **is** a simulated social media platform (Twitter/Reddit-like) where agents interact through posts, comments, likes, follows, and a recommendation algorithm.

**Key capabilities:**
- 23 action types (create_post, comment, like, dislike, repost, follow, mute, etc.)
- Built-in recommendation system (interest-based + hot-score)
- Time-stepped simulation engine
- Supports up to 1M agents
- `pip install camel-oasis` — ready to use
- Uses OpenAI SDK format → compatible with Gemini's OpenAI-compatible endpoint

**Platform type:** Reddit-like (threaded discussion with upvotes/downvotes — naturally models agreement/dissent). Following MiroFish's approach of supporting both Twitter and Reddit modes.

**Deployment:** Runs on EC2 instance, LLM calls go to Gemini API, OASIS SQLite database stored on instance disk (EBS).

### Token Cost Estimates (Gemini 2.0 Flash)

| Simulation | Agents | Steps | LLM Calls | Cost |
|:-----------|:-------|:------|:----------|:-----|
| Small test | 50 | 10 | 500 | ~$0.07 |
| Full simulation | 500 | 20 | 10,000 | ~$1.40 |
| Large simulation | 1,000 | 20 | 20,000 | ~$2.80 |

**Budget:** $100 → ~70 full simulations. Plenty for development + demos.

**Batch optimization within steps:** All agent LLM calls within a single simulation step are independent (agents act on the same state). We batch all agent prompts for a given step into a single request to Gemini, reducing overhead. Cross-step batching is not possible because each step depends on the previous step's output.

---

## 5. Two-Stage Output Model

### Decision: Split output into immediate reactions and post-deliberation shifts

**Stage 1 — Immediate Reactions (Pre-OASIS):**
Each persona receives the policy/campaign prompt and generates an individual initial opinion. No agent interaction. This models people's gut reactions before any social influence.

**Stage 2 — Post-Deliberation (Post-OASIS):**
After running the OASIS simulation (N rounds of social interaction), the system captures how opinions shifted. Agents who were initially opposed may have been swayed by compelling arguments; agents who were supportive may have encountered pushback.

**Output comparison:** The dashboard shows pre-vs-post approval rates, highlighting which demographics shifted most and why. This is the core value proposition — modelling both the immediate reaction AND the social contagion effect.

---

## 6. Additional Decisions

| Decision | Choice | Rationale |
|:---------|:-------|:----------|
| **LLM** | Gemini 2.0 Flash | Free credits, context caching (90% discount on cached tokens), OpenAI SDK compatible for OASIS |
| **Persona data** | Nemotron-Personas-Singapore (S3 Parquet) | 888K census-calibrated personas, 38 demographic fields |
| **Frontend** | React on EC2 | Interactive dashboard with ECharts for high-performance charting |
| **Post-simulation chat** | ReportAgent + individual agent chat | ReportAgent has tool access to query simulation DB. Users can also chat with the most influential individual agents highlighted by the system |
| **Features removed** | PPTX generation, image generation (Nano Banana), observer agents, UN diplomatic simulation | Out of scope for MVP |
| **Related work reference** | MiroFish | Cite in proposal; differentiate via census personas, AWS architecture, Singapore focus |

---

## 7. Final Tech Stack

| Component | Tool | Where It Runs |
|:----------|:-----|:-------------|
| GraphRAG | LightRAG | EC2 (one-time pre-processing per scenario) |
| Persona data | Nemotron Parquet + DuckDB | S3 + Lambda |
| Simulation engine | OASIS (camel-oasis) | EC2 |
| Agent memory | Zep Cloud (stretch: Graphiti + FalkorDB) | Zep Cloud managed / EC2 Docker |
| LLM backbone | Gemini 2.0 Flash | Google API |
| Report generation | ReportAgent (dedicated LLM with tool access) | EC2 |
| Dashboard | React + ECharts | EC2 |
| Static storage | Amazon S3 | AWS |
