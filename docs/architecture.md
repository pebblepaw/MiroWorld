# McKAInsey System Architecture

## Overview

McKAInsey is a 3-tier cloud architecture running primarily on AWS with multi-cloud integration (Zep Cloud for agent memory, Gemini API for LLM backbone).

## Tier 1: Frontend & Application Layer (EC2)

A single EC2 instance hosts:
- **React Dashboard** — scenario submission, demographic filter UI, result visualizations (ECharts), heatmaps, chat panels
- **Python API Backend** — REST API bridging the frontend to simulation and analysis services
- **OASIS Simulation Engine** — Reddit-mode social simulation platform, manages agent interactions
- **ReportAgent** — post-simulation analysis LLM with tool access to simulation database

Co-hosting on a single EC2 instance simplifies deployment for a prototype while demonstrating realistic cloud deployment.

## Tier 2: Data & Filtering Engine (Cold Storage)

- **Amazon S3** — stores the Nemotron-Personas-Singapore dataset as Apache Parquet files (888K personas, 38 fields). Static, read-heavy, large-scale data.
- **AWS Lambda + DuckDB** — serverless function that queries S3 Parquet files directly via HTTP range requests. Accepts demographic filter parameters, returns matching persona subset as JSON. Zero cost when idle.

## Tier 3: Memory & External APIs

- **Zep Cloud** — managed temporal knowledge graph for agent memory. Stores raw interaction episodes, auto-extracts entities and facts with time validity windows, supports hybrid retrieval (semantic + BM25 + graph traversal). Each agent has its own memory graph per simulation.
- **Gemini 2.0 Flash API** — LLM backbone for all agent reasoning, ReportAgent analysis, and LightRAG processing. Accessed via OpenAI SDK compatibility layer. Context caching reduces token costs by up to 90%.

## Data Flow (5 Stages)

```
User submits policy + filters
        │
    ┌───┴───┐
    ▼       ▼
 Lambda   LightRAG
 +DuckDB  (extract
 (sample   knowledge
  personas) graph)
    │       │
    └───┬───┘
        ▼
   OASIS on EC2
   ┌──────────────────┐
   │ Stage 3a:        │
   │ Individual        │──→ Pre-deliberation scores
   │ reactions         │
   ├──────────────────┤
   │ Stage 3b:        │
   │ Reddit forum     │──→ Posts, comments, votes
   │ deliberation     │    stored in SQLite +
   │ (N rounds)       │    Zep Cloud memory
   └───────┬──────────┘
           ▼
    ReportAgent analyses DB
    ├── Approval rates (pre vs post)
    ├── Friction clusters
    ├── Most influential agents
    └── Strategic recommendations
           │
    ┌──────┴──────┐
    ▼             ▼
 Dashboard    Interactive Chat
 (charts,     (ReportAgent Q&A,
  heatmaps,    individual agent
  consensus)   conversations)
```

## Key Integration Points

1. **Lambda → OASIS**: Lambda returns filtered personas as JSON; Python backend converts them to OASIS agent profiles with character descriptions
2. **LightRAG → OASIS**: Knowledge graph subsets are injected into each agent's system prompt based on their demographic relevance
3. **OASIS → Zep Cloud**: After each simulation step, agent interactions are stored as Zep episodes
4. **OASIS → ReportAgent**: ReportAgent has read access to OASIS SQLite database via tool functions
5. **Zep Cloud → Agent Chat**: Interactive agent chat retrieves the agent's full memory via Zep Cloud API
