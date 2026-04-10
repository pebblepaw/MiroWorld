# McKAInsey V2 — Implementation Plan: Cloud Hosting, Memory Backend & Bug Fixes

> Date: 2026-04-10  
> Status: **FINAL** — all decisions locked, ready for implementation  
> Author: Agent handoff document  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Investigation Findings](#2-investigation-findings)
3. [Decision: Open Source vs Cloud Hosting](#3-decision-open-source-vs-cloud-hosting)
4. [Memory Backend Architecture](#4-memory-backend-architecture)
5. [Cloud Hosting Architecture](#5-cloud-hosting-architecture)
6. [Code Versioning Strategy](#6-code-versioning-strategy)
7. [Bug Fixes](#7-bug-fixes)
8. [Local Deployment: Source Code vs Docker](#8-local-deployment-source-code-vs-docker)
9. [Free & Paid Tier Configuration](#9-free--paid-tier-configuration)
10. [LightRAG Real-Time Graph Streaming](#10-lightrag-real-time-graph-streaming)
11. [Implementation Phases](#11-implementation-phases)
12. [Decisions Log](#12-decisions-log)

---

## 1. Executive Summary

This plan addresses four interconnected concerns:

| Concern | Finding | Decision |
|:--------|:--------|:---------|
| Is Graphiti working? | **No.** Graphiti is not writing memory during simulation, and lazy-sync during chat is fragile. | **Remove entirely.** Delete all Graphiti code, use SQLite FTS5 locally and PostgreSQL FTS for cloud. |
| Do we need Graphiti? | **Not for typical workloads** (50–200 agents, 5–10 rounds). SQLite handles it fine. | **No.** Phase out completely. DuckDB stays for persona sampling only. |
| Cloud hosting | **Yes, BYOK makes this feasible and cheap.** | **AWS ECS Fargate + RDS PostgreSQL + S3.** Uses existing $200 credits. |
| Screen 3 state persistence bug | **Frontend-only bug.** `simulationState` is local component state, destroyed on navigation. | Move `simulationState` to AppContext |
| Authentication | OAuth is simplest with no password management | **OAuth (Google/GitHub) + Magic link** |
| Payment | Stripe has zero upfront cost | **Stripe** with free/paid tiers |
| Open source strategy | Both is standard (GitLab, Supabase, n8n) | **Both** — open source (AGPL) + hosted cloud version |
| LightRAG streaming | Current batch processing blocks UI | **Phase 1–2** — chunked ingestion with SSE graph streaming |

---

## 2. Investigation Findings

### 2.1 Graphiti Backend Status: NOT FUNCTIONAL

**Evidence:**

1. **Simulation never writes to Graphiti.** The OASIS simulation pipeline (`simulation_service.py`) writes exclusively to SQLite tables (`interactions`, `simulation_checkpoints`). There is zero Graphiti integration during simulation execution.

2. **Graphiti is only triggered on-demand during chat queries.** When a live chat request comes in, `MemoryService._search_graphiti_context()` attempts to:
   - Initialize a Graphiti client
   - Sync a small batch (default: 2 items) from SQLite into Graphiti
   - Run a Graphiti search
   - Close the client

3. **The lazy sync is too slow for real use.** With `GRAPHITI_SYNC_BATCH_SIZE=2`, a simulation producing ~500 interactions would need 250+ chat queries just to fully populate Graphiti. Users won't send 250 messages.

4. **Silent failure in non-live mode.** When Graphiti/FalkorDB is unavailable, the code catches all exceptions and returns `None`, falling back to local retrieval. The UI shows `"memory_backend": "local"` with no indication Graphiti failed.

5. **FalkorDB is only started in `--mode live`.** The default `quick_start.sh` (demo mode) never starts FalkorDB, so even if the code worked, Graphiti has no database to connect to in the usual development flow.

6. **`graphiti-core` imports are wrapped in try/except.** If the package isn't installed or has import errors, all Graphiti classes silently become `None`, and the code degrades without any indication.

**Conclusion:** Graphiti is architecturally present but not operationally functional. Chat grounding currently falls back to local SQLite-based retrieval in practice.

### 2.2 How MiroFish Does It (Reference Implementation)

MiroFish uses **Zep Cloud** (hosted SaaS) with a fundamentally different architecture:

| Aspect | MiroFish (Zep Cloud) | McKAInsey (Graphiti) |
|:-------|:--------------------|:--------------------|
| **When memory is written** | Real-time during simulation via `ZepGraphMemoryUpdater` background thread | On-demand during chat (lazy sync from SQLite) |
| **What gets written** | Every agent action: posts, comments, likes, reposts, follows, searches — converted to natural language episodes | Only interactions and checkpoints, batch of 2 at a time |
| **Write mechanism** | Background worker thread with platform-batching (5 items/batch), continuous during simulation | Synchronous during chat query |
| **Retrieval** | `ZepToolsService` with InsightForge (multi-query), PanoramaSearch (breadth), QuickSearch | Single Graphiti search per chat query |
| **Infrastructure** | Zep Cloud (zero infrastructure, API key only) | FalkorDB + Graphiti (local Docker service) |
| **Failure mode** | Falls back to local keyword matching | Silent None return in demo, RuntimeError in live |

**Key insight from MiroFish:** Memory is written **during** simulation, not retroactively during chat. This is the correct architecture because:
- The graph is fully populated by the time chat begins
- No cold-start problem for first chat messages
- No subtle bugs where early chat sees partial memory

### 2.3 Screen 3 State Persistence Bug

**Root cause: Frontend-only bug.**

The simulation metrics (round counter, post/comment/reaction counts, checkpoint status) are stored in `simulationState` — a **local** `useState` variable inside `Simulation.tsx`. When the user navigates to Screen 4 or back to Screen 1, the component unmounts and this state is destroyed.

`AppContext` stores `simPosts`, `simulationRounds`, and `simulationComplete`, but does NOT store `simulationState` (which contains `current_round`, `counters`, `metrics`, `checkpoint_status`).

On remount, the hydration effect attempts to re-fetch from `GET /simulation/state`, but has guards:
```typescript
if (!simulationComplete && simPosts.length === 0) {
  return; // exits without fetching
}
```

If `simulationComplete` wasn't set to `true` in AppContext before navigation (e.g., user navigated mid-simulation, or the completion flag wasn't properly persisted), the effect exits early and `simulationState` stays `null`, showing 0/6 and zero metrics.

**This is NOT related to Graphiti.** The backend correctly persists simulation events and can reconstruct state on demand. The fix is purely frontend.

---

## 3. Decision: Open Source vs Cloud Hosting

### Recommendation: Do Both

| Option | Pros | Cons |
|:-------|:-----|:-----|
| **Open source only** (AGPL) | Zero hosting cost, community contributions, credibility | Only tech-savvy users can run it, no revenue path, support burden |
| **Cloud hosting only** (BYOK) | Accessible to non-technical users, potential revenue | Hosting cost, ops burden, single point of failure |
| **Both** (open source + hosted) | Best of both worlds: community + accessibility | Need to maintain deployment parity |

**The "Both" approach is standard** for open-source SaaS tools (GitLab, Supabase, n8n, MiroFish themselves). AGPL license specifically enables this — it requires anyone hosting a modified version to open-source their changes, protecting your hosted offering.

### OpenRouter Free Models

This is a strong differentiator for the hosted version. The onboarding flow would be:
1. User signs up for OpenRouter (free)
2. User gets an API key
3. User pastes key into McKAInsey Screen 0
4. System uses free models (e.g., `meta-llama/llama-3.1-8b-instruct:free`, `google/gemma-2-9b-it:free`)

**Caveat:** Free models have rate limits and may be slow. You should test simulation quality with free OpenRouter models before promising this path.

**✅ Decision: Both** — open source (AGPL) first, then hosted cloud version. This is standard for open-source SaaS (GitLab, Supabase, n8n, MiroFish). AGPL license protects the hosted offering by requiring anyone hosting a modified version to open-source their changes.

---

## 4. Memory Backend Architecture

### 4.1 Do We Need Graphiti?

**For typical workloads (50–200 agents, 5–10 rounds): No.**

Math: 200 agents × 10 rounds × ~3 interactions/round = 6,000 interactions. Each interaction is ~200 bytes of text content. Total: ~1.2 MB. SQLite handles this trivially with full-text search.

**For large-scale workloads (1000+ agents, 100+ rounds): Maybe.**

Math: 1000 agents × 100 rounds × 3 interactions = 300,000 interactions. At ~200 bytes each = 60 MB. SQLite FTS5 still handles this well for keyword search. A knowledge graph adds value for:
- Semantic similarity search ("find agents who had similar concerns to Agent X")
- Temporal relationship traversal ("how did Agent Y's opinions evolve?")
- Cross-agent relationship mapping

**Decision: Remove Graphiti entirely. Use SQLite locally, PostgreSQL on cloud.**

### 4.2 Memory Architecture (Decided)

| Environment | Storage | Search Method |
|:------------|:--------|:--------------|
| **Local (source code & Docker)** | SQLite with FTS5 | Full-text search + agent-scoped queries |
| **Cloud (AWS hosted)** | PostgreSQL with `tsvector` FTS | Full-text search + row-level security per user |

#### Why Not Zep Cloud?

MiroFish uses Zep Cloud for semantic memory, but adding Zep means:
- Free users would need to sign up for yet another API key (Zep Cloud) — bad UX for non-technical users
- Paid tier would need us to absorb Zep Cloud costs
- PostgreSQL full-text search covers our needs without external dependencies

**Decision: No Zep. PostgreSQL FTS for cloud, SQLite FTS5 for local. Simpler for everyone.**

#### Why Not DuckDB for Memory?

DuckDB is already used in our codebase for persona sampling (`persona_sampler.py` queries HuggingFace parquet datasets), and it's excellent at that — OLAP workloads with bulk column scans. However, for the memory/chat workload:

- Memory operations are **OLTP** — insert 1 row at a time during simulation, read 1 agent's history during chat
- DuckDB is optimized for scanning millions of rows in aggregate, not single-row lookups — **SQLite is faster** for this pattern
- DuckDB's S3 extension reads Parquet files on S3 — it's not a hosted database and can't replace PostgreSQL for multi-tenant concurrent access
- DuckDB stays where it is (persona sampling) but shouldn't expand to memory/chat

#### Local Memory: SQLite FTS5

The simulation already writes everything to SQLite. The chat grounding needs better retrieval:

```
Simulation → SQLite (interactions, checkpoints)
                ↓
Chat Query → SQLite FTS5 Search + Recent Activity Window
                ↓
            Agent-specific context assembled for LLM prompt
```

Implementation:
1. Add SQLite FTS5 index on `interactions.content` (if not already present)
2. For agent chat: query recent interactions by `agent_id`, plus their checkpoint responses
3. For group chat: query interactions by thread/topic relevance
4. Construct memory prompt section with: agent's posts, comments received, checkpoint answers

#### Cloud Memory: PostgreSQL FTS

Same queries, translated to PostgreSQL:

```sql
-- PostgreSQL equivalent of SQLite FTS5
ALTER TABLE interactions ADD COLUMN content_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX idx_interactions_fts ON interactions USING GIN (content_tsv);

-- Search
SELECT * FROM interactions
WHERE content_tsv @@ plainto_tsquery('english', $1)
  AND session_id = $2 AND agent_id = $3
ORDER BY ts_rank(content_tsv, plainto_tsquery('english', $1)) DESC;
```

The backend should abstract this behind a `MemoryStore` interface so SQLite and PostgreSQL use the same API.

#### Migration Path

The backend should support both via a `DATABASE_URL` env var:
- `sqlite:///data/sessions.db` → SQLite (local)
- `postgresql://user:pass@host/db` → PostgreSQL (cloud)

### 4.3 Agent Memory Prompt Design

Regardless of storage backend, the chat prompt should include:

```
=== AGENT MEMORY: {agent_name} ===

## Your Profile
{agent persona from dataset}

## Your Checkpoint Responses
Baseline: {metric_answers from baseline checkpoint}
Final: {metric_answers from final checkpoint}

## Your Social Media Activity (Most Recent First)
Round {n}: Posted "{content}" — received {likes} likes, {comments} comments
Round {n}: Commented on {author}'s post: "{content}"
Round {n}: Liked {author}'s post about "{topic}"
...

## Key Discussions You Participated In
Thread: "{seed question}" — you {supported/opposed} with: "{your comment}"
...
===
```

This gives the LLM rich context to generate in-character responses, using data already in SQLite.

---

## 5. Cloud Hosting Architecture

### 5.1 Architecture Overview

Since McKAInsey is a BYOK (Bring Your Own Key) service, the hosting costs are primarily compute and storage — **not** LLM API costs. This makes it very affordable.

### 5.2 AWS Architecture (Recommended — uses your $200 credits)

```
                    ┌─────────────────────────────────────────────┐
                    │              AWS Cloud (us-east-1)          │
                    │                                             │
   User ──HTTPS──▶  │  CloudFront (CDN)                           │
                    │      │                                      │
                    │      ├── S3 (Static Frontend)               │
                    │      │     React build artifacts            │
                    │      │                                      │
                    │      └── ALB (Application Load Balancer)    │
                    │            │                                │
                    │            ▼                                │
                    │      ECS Fargate (Backend)                  │
                    │      ┌──────────────────┐                   │
                    │      │ FastAPI container │ ←── ECR image    │
                    │      │ + OASIS runtime   │                  │
                    │      └──────┬───────────┘                   │
                    │             │                               │
                    │             ▼                               │
                    │      EFS (Elastic File System)              │
                    │      └── SQLite databases                   │
                    │          └── per-session data               │
                    │          └── uploaded documents             │
                    └─────────────────────────────────────────────┘
```

### 5.3 Service-by-Service Breakdown

| AWS Service | What It Is | What It Does For Us | Estimated Cost |
|:------------|:-----------|:-------------------|:---------------|
| **S3** | Object storage | Hosts the Vite-built frontend (static HTML/JS/CSS). Serves via CloudFront. | ~$0.02/month |
| **CloudFront** | CDN (Content Delivery Network) | Caches and serves frontend globally with HTTPS. Routes API calls to backend. | ~$1/month for light usage |
| **ECS Fargate** | Serverless container runtime | Runs the FastAPI backend container without managing servers. You define CPU/memory, AWS handles the rest. No EC2 instances needed. | ~$15–30/month for 0.5 vCPU / 1 GB (can scale to zero with scheduled tasks) |
| **ECR** | Container registry | Stores your Docker images (backend + OASIS runtime). CI/CD pushes new images here. | ~$0.50/month |
| **ALB** | Application Load Balancer | Routes HTTPS traffic to your Fargate containers. Handles SSL termination. | ~$16/month (this is the expensive one at low scale) |
| **EFS** | Network file system | Persistent storage for SQLite databases and uploaded documents. Attached to Fargate tasks. | ~$0.30/GB/month |
| **Route 53** | DNS | Maps your custom domain to CloudFront. | ~$0.50/month |
| **ACM** | Certificate Manager | Free SSL/TLS certificates for HTTPS. | Free |

**Estimated total: ~$35–50/month** with your $200 credits lasting ~4–6 months.

### 5.4 Why NOT Lambda

AWS Lambda (serverless functions) seems appealing but is **wrong for this workload**:
- OASIS simulations run for minutes, not milliseconds. Lambda has a 15-minute hard timeout.
- Simulations need persistent state across rounds. Lambda is stateless.
- Lambda cold starts add 5–10 seconds of latency.
- SQLite doesn't work well on Lambda (no persistent filesystem).
- You'd need to split the backend into dozens of Lambda functions.

**ECS Fargate is the right choice**: it runs your existing Docker container as-is, with persistent storage.

### 5.5 Alternative: Railway or Fly.io (Simpler, Possibly Cheaper)

If AWS feels too complex, two simpler alternatives:

| Service | Approach | Cost | Tradeoff |
|:--------|:---------|:-----|:---------|
| **Railway** | Push Docker Compose, get HTTPS URL | ~$5–20/month | Less control, but deploy in 10 minutes |
| **Fly.io** | Push Dockerfile, get global deploy | ~$5–15/month | Good for containers, built-in persistent volumes |

These are "push and it works" platforms. No ALB, no Route 53, no CloudFront configuration. They handle SSL, DNS, and containers for you.

**✅ Decision: AWS ECS Fargate** — uses existing $200 credits, runs existing Docker containers as-is, with PostgreSQL RDS for multi-tenancy. Railway/Fly.io are documented as fallback options but not the primary path.

### 5.6 Why NOT Vercel / GitHub Pages

- **Vercel**: Great for Next.js frontends. Can host the React frontend, but the Python/FastAPI backend needs a separate host. Vercel Serverless Functions are Node.js-first and have the same Lambda limitations.
- **GitHub Pages**: Static files only. Can host the frontend, but backend needs separate hosting. No server-side processing.

You **could** host the frontend on Vercel/GitHub Pages and the backend on Railway/Fly.io, but this splits your deployment and adds CORS complexity. A unified container deployment is simpler.

### 5.7 Multi-Tenancy Considerations

For a BYOK hosted service, you need:

1. **User isolation**: Each user's sessions, data, and API keys must be isolated.
2. **API key security**: User API keys should be encrypted at rest and never logged.
3. **Session cleanup**: Old sessions should be garbage-collected to manage storage.
4. **Rate limiting**: Prevent abuse even with BYOK (someone could run 100 simulations concurrently).

Current state: The backend is single-tenant (one SQLite database for everything). For multi-tenant hosting:

**Decision: PostgreSQL with row-level security from day 1.**

| Component | Implementation |
|:----------|:--------------|
| User isolation | Row-level security policies on all tables: `WHERE user_id = current_setting('app.user_id')` |
| Session isolation | All queries scoped to `user_id` + `session_id` |
| API key security | BYOK keys encrypted with server-side `ENCRYPTION_KEY` env var, never logged |
| Session cleanup | Cron job: delete sessions + data older than retention period (14 days free, unlimited paid) |
| Rate limiting | Per-user request throttling via middleware |

Estimated cost: AWS RDS PostgreSQL `db.t4g.micro` = ~$15/month.

---

## 6. Code Versioning Strategy

### Can the Same Code Run Locally and Hosted?

**Yes, with environment-variable-driven configuration.** No separate code versions needed.

Current state already supports this pattern:
- `VITE_BOOT_MODE=live|demo` switches frontend behavior
- Backend reads provider/model from env vars or session config
- Docker Compose already defines the full stack

What needs to change for cloud deployment:

| Concern | Local | Hosted | Implementation |
|:--------|:------|:-------|:---------------|
| Frontend serving | Vite dev server | S3 + CloudFront (or container) | Build step produces static assets |
| Backend | `uvicorn` direct | `uvicorn` in container (same) | No change needed |
| Database | SQLite file | PostgreSQL (RDS) | `DATABASE_URL` env var |
| File uploads | Local filesystem | EFS or S3 | `UPLOAD_STORAGE=local|s3` env var |
| Auth | None (local user) | OAuth + Magic link | Add auth middleware, gated by `AUTH_ENABLED` env var |
| Memory backend | SQLite FTS5 | PostgreSQL FTS | Same `DATABASE_URL` — abstracted behind `MemoryStore` interface |
| OASIS runtime | Local Python 3.11 | Container sidecar | Already handled by Docker Compose |

**One codebase, configuration-driven deployment.** The `docker-compose.yml` already demonstrates this pattern.

### What's New for Hosted

1. **Auth middleware** — gate API access behind user accounts (could be simple API key auth initially)
2. **User/session isolation** — scope all database queries to `user_id`
3. **API key encryption** — encrypt stored BYOK keys with a server-side secret
4. **Health checks** — `/health` endpoint for load balancer
5. **CORS configuration** — allow your hosted frontend domain
6. **Rate limiting** — per-user request throttling

---

## 7. Bug Fixes

### 7.1 Screen 3 State Persistence (Priority: HIGH)

**Problem:** Navigating away from Screen 3 and back resets round counter to 0/6 and metrics to 0.

**Root cause:** `simulationState` (containing `current_round`, `counters`, `metrics`, `checkpoint_status`) is local component state in `Simulation.tsx`, not stored in `AppContext`.

**Fix:**

1. Add `simulationState` to `AppContext`:
```typescript
// In AppContext.tsx — add to AppState interface:
simulationState: SimulationState | null;
setSimulationState: (state: SimulationState | null) => void;
```

2. In `Simulation.tsx`, read/write `simulationState` from AppContext instead of local state:
```typescript
// Replace:
const [simulationState, setSimulationState] = useState<SimulationState | null>(null);
// With:
const { simulationState, setSimulationState } = useApp();
```

3. Remove the early-exit guard that blocks re-fetching:
```typescript
// Remove or weaken this guard:
if (!simulationComplete && simPosts.length === 0) {
  return; // This blocks fetching when state was lost
}
```

4. Always attempt to hydrate from backend when `simulationState` is null and `sessionId` exists:
```typescript
useEffect(() => {
  if (!sessionId || simulationState) return;
  getSimulationState(sessionId)
    .then(setSimulationState)
    .catch(() => {}); // Silent on error, UI shows defaults
}, [sessionId, simulationState]);
```

**Will this slow down the system?** No. It's a single GET request to an endpoint that reads a cached SQLite snapshot. Sub-10ms response time.

**Estimated effort:** 1–2 hours.

### 7.2 Graphiti Removal (Priority: HIGH)

**Problem:** Dead Graphiti code adds complexity, confuses new contributors, and masks the real memory retrieval path.

**Decision: Remove Graphiti entirely.** No flag, no optional mode — clean deletion.

**Files to modify/delete:**

1. **Delete `backend/src/mckainsey/services/graphiti_service.py`** — entire file
2. **Rewrite `backend/src/mckainsey/services/memory_service.py`**:
   - Remove all `_search_graphiti_context()`, `_sync_to_graphiti()`, and Graphiti client initialization
   - Remove `graphiti-core` imports
   - Set `MEMORY_BACKEND` to always use `sqlite` (local) or `postgresql` (cloud), selected by `DATABASE_URL` env var
   - Implement proper SQLite FTS5 / PostgreSQL FTS agent context retrieval (see Section 4.2)
3. **Remove from `backend/pyproject.toml`**: Delete `"graphiti-core>=0.28.2"` dependency
4. **Remove from `docker-compose.yml`**: Delete entire `falkordb` service block and `falkordb_data` volume
5. **Remove from `quick_start.sh`**: Delete `ensure_falkordb_runtime()`, `falkordb_reachable()`, and all FalkorDB references
6. **Remove from `.env`**: Delete any `FALKORDB_*` or `GRAPHITI_*` env vars
7. **Also remove `"zep-cloud>=3.18.0"` from `pyproject.toml`** — no longer needed

**Estimated effort:** 3–4 hours (mostly in `memory_service.py` rewrite).

### 7.3 Chat Memory Quality (Priority: MEDIUM)

Even with SQLite-only memory, chat quality can be significantly improved:

**Current behavior:** Returns some simulation context in a loose format.  
**Improved behavior:** Returns structured agent-specific memory with clear temporal ordering.

```python
def get_agent_memory_context(self, session_id: str, agent_id: str) -> str:
    """Build rich memory context for an agent from SQLite."""
    store = self.store

    # 1. Agent's own posts and comments
    own_activities = store.query("""
        SELECT content, action_type, round_no, created_at
        FROM interactions
        WHERE session_id = ? AND agent_id = ?
        ORDER BY created_at DESC LIMIT 30
    """, [session_id, agent_id])

    # 2. Interactions targeting this agent (replies, likes)
    received = store.query("""
        SELECT content, action_type, agent_id as from_agent, round_no
        FROM interactions
        WHERE session_id = ? AND target_agent_id = ?
        ORDER BY created_at DESC LIMIT 20
    """, [session_id, agent_id])

    # 3. Checkpoint responses
    checkpoints = store.query("""
        SELECT checkpoint_kind, stance_json
        FROM simulation_checkpoints
        WHERE session_id = ? AND agent_id = ?
    """, [session_id, agent_id])

    return format_agent_memory(own_activities, received, checkpoints)
```

**Estimated effort:** 2–3 hours.

---

## 8. Local Deployment: Source Code vs Docker

### 8.1 Concepts: What Docker Actually Is

A **Dockerfile** doesn't produce a single portable file. It's a recipe that builds an **image** — a frozen snapshot containing an OS, all dependencies (Python, Node.js, pip packages, npm packages), and your code. `docker-compose.yml` then orchestrates multiple images into a running system.

So the tradeoff is:

| | Source Code | Docker Compose |
|:--|:--|:--|
| **What user installs** | Python 3.12, Python 3.11, Node.js 20+, npm, Ollama — then `pip install` and `npm install` | Docker Desktop only |
| **What user runs** | `./quick_start.sh --mode live` | `docker compose up` |
| **Startup time** | Fast (seconds) after first install | Slower first run (builds images), fast after |
| **Environment isolation** | None — uses host Python/Node directly | Full — nothing touches host system |
| **Debugging** | Easy — edit code, restart | Harder — need to rebuild or use volume mounts |
| **Disk usage** | Just project + deps (~2 GB) | Docker images + runtime (~4–6 GB) |
| **Who it's for** | Developers who want to modify code | Users who just want to run it |

**Both approaches run the same code.** Docker just wraps it in a container so users don't have to set up Python venvs, Node.js, etc. manually.

### 8.2 Current State: A Broken Hybrid

Right now, **neither deployment path works cleanly end-to-end**:

#### Source code path (`quick_start.sh`)

| Component | Works? | Issue |
|:----------|:-------|:------|
| Backend (Python 3.12) | ✅ | Runs via `.venv` |
| Frontend (Node/Vite) | ✅ | Runs via `npm run dev` |
| Ollama (LLM provider) | ✅ | Auto-detected and auto-started |
| OASIS sidecar (Python 3.11) | ⚠️ | Requires a second Python version; script creates `.venv311` automatically but user needs `python3.11` installed |
| FalkorDB | ❌ | **Requires Docker** — `quick_start.sh --mode live` shells out to `docker compose up -d falkordb`. A source-code-only user with no Docker can't run live mode. |

So source code deployment has a Docker dependency buried inside it.

#### Docker path (`docker compose up`)

| Component | Works? | Issue |
|:----------|:-------|:------|
| Frontend container | ✅ | Builds and runs |
| Backend container | ⚠️ | Builds, but `Dockerfile` is Python 3.12 only — doesn't include OASIS runner (Python 3.11) |
| FalkorDB container | ✅ | Works, but irrelevant if we drop Graphiti |
| OASIS sidecar container | ⚠️ | `Dockerfile.oasis` exists but references `scripts.oasis_server` — needs verification that this module exists and works |
| Ollama | ❌ | **Not defined in `docker-compose.yml`**. User's host Ollama isn't reachable from inside Docker network by default. |
| `.env` / config | ⚠️ | `docker-compose.yml` references `.env` via `env_file`, but no `.env.example` exists with required variables |
| Demo mode | ❌ | No mechanism to run demo mode in Docker — `quick_start.sh` logic (demo cache, boot mode) isn't replicated |

So Docker deployment is a skeleton that was set up for the Graphiti architecture but never completed for full standalone operation.

### 8.3 Recommendation: Offer Both (Like MiroFish)

Yes, offer both. Each serves a different audience:

- **Source code** → Developers, contributors, people who want to customize or integrate McKAInsey into their workflow
- **Docker** → Evaluators, demo users, non-developers who just want to try it

### 8.4 What Needs to Change: Source Code Path

Once Graphiti is dropped (Section 4), the source code path becomes clean:

| Task | Detail | Effort |
|:-----|:-------|:-------|
| **Remove FalkorDB dependency** | `quick_start.sh --mode live` currently calls `docker compose up -d falkordb`. With SQLite-only memory, delete this. Source code path becomes 100% Docker-free. | 30 min |
| **Document Python 3.11 requirement** | OASIS needs Python 3.11. The script auto-creates `.venv311` but the user needs `python3.11` on PATH. README should explain: `brew install python@3.11` (macOS) or `sudo apt install python3.11` (Linux). | 30 min |
| **Create `.env.example`** | List all env vars with defaults and explanations. Currently there is no `.env.example`. | 1 hr |
| **Add provider setup guides** | Add short guides for each LLM provider: Ollama (default/free), OpenRouter (free tier), Gemini, OpenAI. Include how to get an API key and which env vars to set. | 2 hr |

After these changes, the source code setup is:
```bash
# 1. Clone
git clone https://github.com/yourorg/mckainsey.git && cd mckainsey

# 2. Backend deps (Python 3.12)
python3 -m venv .venv && source .venv/bin/activate
pip install -e backend/

# 3. Frontend deps
cd frontend && npm install && cd ..

# 4. (Optional) Install Ollama for free local LLM
# https://ollama.com/download

# 5. Run
./quick_start.sh --mode live
```

No Docker needed anywhere. This is the cleanest open-source experience.

### 8.5 What Needs to Change: Docker Path

| Task | Detail | Effort |
|:-----|:-------|:-------|
| **Remove `falkordb` service** | Delete from `docker-compose.yml`. Remove `depends_on: falkordb` from backend. Remove `falkordb_data` volume. | 15 min |
| **Fix Ollama connectivity** | **Decision: Option C.** Default Docker deployment to OpenRouter/Gemini (set in `.env.example`). Document that users who want host Ollama should set `LLM_BASE_URL=http://host.docker.internal:11434/v1/` in their `.env`. | 1 hr |
| **Verify OASIS sidecar** | **Decision: Keep two-container split.** The OASIS sidecar (`Dockerfile.oasis`) already works. Verify `scripts.oasis_server` module runs correctly in the container and that the backend can reach it at `oasis-sidecar:8001`. | 1–2 hr |
| **Add demo mode support** | Add `BOOT_MODE` env var to docker-compose. Pre-bake demo cache into the backend image (or mount a volume). Currently no way to run demo mode in Docker. | 2 hr |
| **Create `.env.example`** | Same file as source code path — Docker reads it via `env_file: .env`. | (shared with above) |
| **Add healthchecks** | Backend needs a `/health` endpoint check in docker-compose (frontend already uses Vite dev server which is fine). | 30 min |
| **Production frontend build** | Current `docker-compose.yml` uses the `dev` stage of the frontend Dockerfile (runs Vite dev server in container). For production, should use the `builder` stage → output static files → serve with nginx or caddy. | 1–2 hr |

After these changes, the Docker setup is:
```bash
# 1. Clone
git clone https://github.com/yourorg/mckainsey.git && cd mckainsey

# 2. Copy and edit config
cp .env.example .env
# Edit .env — set LLM_PROVIDER, API keys, etc.

# 3. Run 
docker compose up
```

Three commands. No Python, no Node.js, no Ollama install needed (if using OpenRouter/Gemini).

### 8.6 Updated `docker-compose.yml` (Target State)

```yaml
version: "3.9"

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: dev              # Change to 'builder' + nginx for production
    ports:
      - "5173:5173"
    environment:
      VITE_API_BASE: http://backend:8000
      VITE_BOOT_MODE: ${BOOT_MODE:-demo}
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - mckainsey

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      OASIS_SIDECAR_HOST: oasis-sidecar
      OASIS_SIDECAR_PORT: "8001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - backend_data:/app/backend/data    # Persistent SQLite + uploads
    networks:
      - mckainsey

  oasis-sidecar:
    build:
      context: .
      dockerfile: backend/Dockerfile.oasis
    ports:
      - "8001:8001"
    networks:
      - mckainsey

networks:
  mckainsey:
    driver: bridge

volumes:
  backend_data:
```

Key changes from current: FalkorDB removed, healthcheck added, persistent volume for data, boot mode configurable.

### 8.7 Comparison Summary

| | Source Code | Docker |
|:--|:--|:--|
| **Prerequisites** | Python 3.12, Python 3.11, Node.js 20+, npm | Docker Desktop |
| **Optional** | Ollama (for free local LLM) | Ollama on host (for free local LLM) |
| **Setup commands** | 5 (clone, venv, pip install, npm install, quick_start) | 3 (clone, cp .env, docker compose up) |
| **Ideal for** | Development, customization | Quick evaluation, deployment |
| **Code changes needed** | Remove FalkorDB from quick_start, add docs | Fix docker-compose, add healthchecks, fix Ollama access |
| **Estimated effort** | ~4 hours | ~6–8 hours |

**✅ Decision: Ship both.** Both source code and Docker paths will be ready for the initial open-source release. Docker is what turns "interesting GitHub repo" into "tool I actually tried".

---

## 9. Free & Paid Tier Configuration

### 9.1 Tier Limits

| Limit | Free Tier | Paid Tier |
|:------|:----------|:----------|
| Active sessions | 5 (new sessions override oldest) | Unlimited |
| Agents per simulation | 100 | 1,000 |
| Rounds per simulation | 10 | 50 |
| Storage retention | 14 days | Unlimited |
| LLM provider | BYOK (own API key) | BYOK (own API key) |
| Memory backend | PostgreSQL FTS | PostgreSQL FTS |

### 9.2 Frontend Enforcement

The frontend sliders on Screen 2 (Agent Sampling) must respect tier limits:

1. **Agent count slider**: Max capped at tier limit. If free user drags past 100, show toast: *"Free tier is limited to 100 agents. Upgrade for up to 1,000."*
2. **Round count slider**: Max capped at tier limit. Same pattern.
3. **Session management**: Add a **Past Sessions** screen (accessible from nav or Screen 0) showing:
   - List of sessions with name, date, status (active/expired)
   - If free user has 5 active sessions and starts a new one, show warning dialog: *"You have 5 active sessions. Starting a new one will replace your oldest session ({name}). Continue?"*
   - Paid users see same screen but without the override warning

### 9.3 Stripe Payment Integration

**Why Stripe:** Zero upfront cost — Stripe only charges when someone pays you (2.9% + $0.30 per transaction). No monthly fees.

**Implementation:**

1. **Stripe Checkout**: Use Stripe's hosted checkout page (simplest integration). User clicks "Upgrade" → redirected to Stripe → pays → redirected back with `session_id`.
2. **Webhook**: Stripe sends `checkout.session.completed` webhook to backend → backend sets `user.tier = 'paid'` in PostgreSQL.
3. **Subscription model**: Monthly recurring ($X/month TBD). Stripe handles billing, invoices, cancellation.
4. **Backend middleware**: Check `user.tier` on every API request. Inject tier limits into session config. Return `403` with upgrade prompt if free user exceeds limits.

**Required env vars:**
```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...        # The subscription price object
```

**Pricing TBD:** Owner needs to decide price point. Suggestion: $9–19/month for paid tier, since the main cost to you is PostgreSQL storage + compute, not LLM (BYOK).

---

## 10. LightRAG Real-Time Graph Streaming

### 10.1 Current State

LightRAG is used on Screen 1 (Policy Upload) to extract a knowledge graph from uploaded documents. Currently:
- `LightRAGService.process_document()` ingests the entire document via `rag.ainsert()` (batch)
- After ingestion, `_load_document_native_graph()` reads the full graph
- Frontend receives the complete graph and renders it all at once via `react-force-graph-2d`

### 10.2 Target: Stream Nodes As They're Discovered

Like MiroFish's graph construction animation, nodes should appear incrementally as the document is processed:

```
Document → chunk into paragraphs
    ↓
For each chunk:
    1. rag.ainsert(chunk)
    2. Read new entities/relations from LightRAG KV stores
    3. Compute delta (new nodes/edges since last chunk)
    4. Send delta via SSE → frontend
    ↓
Frontend: react-force-graph-2d receives deltas, animates new nodes appearing
```

### 10.3 Implementation Plan

**Backend changes:**

1. **New SSE endpoint**: `GET /knowledge/stream/{session_id}` — mirrors existing `SimulationStreamService` pattern
2. **Chunked ingestion**: Split document into paragraphs (~500 tokens each). For each chunk:
   - Call `rag.ainsert(chunk)`
   - Read `full_entities` and `full_relations` from LightRAG's KV stores
   - Diff against previously known entities → emit new ones as SSE events
3. **SSE event format**:
   ```json
   {"type": "node_added", "data": {"id": "...", "label": "Ministry of Finance", "type": "organization", "importance": 0.8}}
   {"type": "edge_added", "data": {"source": "...", "target": "...", "label": "oversees"}}
   {"type": "progress", "data": {"chunks_processed": 3, "total_chunks": 12}}
   {"type": "complete", "data": {"total_nodes": 45, "total_edges": 67}}
   ```

**Frontend changes:**

1. **Subscribe to SSE** instead of waiting for full response in `PolicyUpload.tsx`
2. **Incrementally update** `react-force-graph-2d` `graphData` state — new nodes animate in with a pulse effect (CSS animation like MiroFish's `node-pulse`)
3. **Progress indicator**: Show "Processing chunk 3/12..." overlay on the graph panel

**Existing infrastructure to reuse:**
- `SimulationStreamService` — SSE pattern for backend
- `react-force-graph-2d` — already renders the knowledge graph with force simulation
- `ForceGraph2D` component already supports dynamic `graphData` updates

**Estimated effort:** 2–3 days.

---

## 11. Implementation Phases

### Phase 1: Stabilize & Fix (1–2 days)
*Goal: Fix bugs, remove Graphiti, clean up memory backend.*

- [x] **7.1** Fix Screen 3 state persistence (move `simulationState` to AppContext)
- [x] **7.2** Remove Graphiti entirely: delete `graphiti_service.py`, strip from `memory_service.py`, remove `graphiti-core` and `zep-cloud` from `pyproject.toml`, remove FalkorDB from `docker-compose.yml` and `quick_start.sh`
- [x] **7.3** Implement proper SQLite FTS5 agent memory retrieval for chat
- [x] **10** Implement LightRAG real-time graph streaming (SSE chunked ingestion + frontend incremental rendering)
- [x] Verify `quick_start.sh --mode live` works end-to-end without FalkorDB
- [x] Run full E2E test: onboarding → knowledge (with streaming) → sampling → simulation → report → chat → analytics
- [ ] Test with OpenRouter free models (`OpenRouter_API_Key` in `.env`) — verify simulation quality
  User decision on 2026-04-11: skip free-model quality verification because the free OpenRouter account is immediately rate-limited even on single prompts.

### Phase 2: Open Source Prep (1–2 days)
*Goal: Make the project ready for public GitHub release with both source code and Docker deployment paths.*

- [x] Create `.env.example` with all required variables, defaults, and explanations (no real keys)
- [x] Add `.env` to `.gitignore` if not already there
- [x] Write clear README (follow MiroFish style): project overview, screenshots, quick start (source code + Docker), LLM provider setup guides (Ollama, OpenRouter, Gemini, OpenAI)
- [x] Add AGPL-3.0 `LICENSE` file
- [x] **Source code path**: Remove all FalkorDB references from `quick_start.sh`, document Python 3.11 requirement
- [x] **Docker path**: Update `docker-compose.yml` — remove FalkorDB, add healthchecks, set `BOOT_MODE` env var, default LLM to OpenRouter/Gemini with doc for Ollama (`host.docker.internal`)
- [x] **Docker path**: Verify OASIS sidecar container works end-to-end
- [x] **Docker path**: Add production frontend build stage (nginx serving static files instead of Vite dev server)
- [x] Remove any hardcoded paths, secrets, or personal credentials from all files
- [x] Remove any deadcode, you can run these two tools: https://github.com/astral-sh/ruff and https://github.com/jendrikseipp/vulture
- [x] Add GitHub Actions CI for lint + test
- [x] Test both deployment paths on a clean machine (or clean Docker environment)
- [x] Tag `v2.0.0` release, push to public GitHub

### Phase 3: GitHub Pages Demo (1 day)
*Goal: Static demo site on GitHub Pages with cached data, like MiroFish.*

- [x] Build a demo cache: run a full simulation with representative policy document, capture all output (agents, posts, checkpoints, report, analytics, knowledge graph)
- [x] Configure frontend to load cached demo data when `VITE_BOOT_MODE=demo-static` — no backend calls, all data from bundled JSON
- [x] Create `gh-pages` branch with Vite production build + cached data
- [x] Configure GitHub Pages to serve from `gh-pages` branch
- [x] Add "Live Demo" badge/link to README
- [x] Verify demo works: all screens navigable, knowledge graph renders, simulation feed shows, report displays, analytics charts work

### Phase 4: Cloud Hosting MVP — AWS (3–5 days)
*Goal: Deploy a working BYOK instance with free + paid tiers.*

**Infrastructure:**
- [ ] Set up AWS account, configure `us-east-1` region
- [ ] Create ECR repositories for backend + OASIS sidecar images
- [ ] Set up RDS PostgreSQL (`db.t4g.micro`, ~$15/month)
- [ ] Create S3 bucket for frontend static assets + uploaded documents
- [ ] Set up CloudFront CDN pointing to S3 (frontend) + ALB (API)
- [ ] Set up ECS Fargate cluster with backend + OASIS sidecar task definitions
- [ ] Configure ALB with HTTPS (ACM certificate)
- [ ] Set up Route 53 for custom domain
- [ ] GitHub Actions CD pipeline: push to `main` → build Docker images → push to ECR → deploy to ECS

**Backend changes for cloud:**
- [ ] Add `DATABASE_URL` support: detect `postgresql://` → use asyncpg/psycopg, detect `sqlite://` → use current SQLite
- [ ] Implement `MemoryStore` interface abstracting SQLite FTS5 and PostgreSQL FTS
- [ ] Add database migrations (Alembic or simple SQL scripts) for PostgreSQL schema
- [ ] **Auth**: OAuth (Google + GitHub) + Magic link via email. Use `AUTH_ENABLED=true` env var to gate. Library suggestion: `authlib` or direct OAuth2 flow.
- [ ] **Multi-tenancy**: Add `user_id` column to all tables. Row-level security policies. Scope all queries.
- [ ] **API key encryption**: Encrypt stored BYOK keys with `ENCRYPTION_KEY` env var (Fernet symmetric encryption)
- [ ] **Upload storage**: `UPLOAD_STORAGE=s3` → store uploaded documents in S3 instead of local filesystem
- [ ] **Health endpoint**: `GET /health` returning DB connectivity + service status (for ALB healthcheck)
- [ ] **CORS**: Configure for hosted frontend domain
- [ ] **Rate limiting**: Per-user request throttling middleware

**Frontend changes for cloud:**
- [ ] **Tier enforcement**: Cap agent/round sliders to tier limits. Show upgrade toast when free user exceeds limits.
- [ ] **Session management screen**: List past sessions, show active count, warn on override for free tier (5 session limit)
- [ ] **Auth UI**: Login screen with Google/GitHub OAuth buttons + magic link email input
- [ ] **Upgrade flow**: "Upgrade to Pro" button → Stripe Checkout redirect → return to app with paid tier active

**Stripe integration:**
- [ ] Create Stripe account, configure product + price object (subscription, monthly billing)
- [ ] Backend: `POST /billing/checkout` → create Stripe Checkout session, return URL
- [ ] Backend: `POST /webhooks/stripe` → handle `checkout.session.completed`, `customer.subscription.deleted`
- [ ] Store `user.tier` and `user.stripe_customer_id` in PostgreSQL
- [ ] Frontend: redirect to Stripe Checkout on upgrade, handle return URL

### Phase 5: Enhancement (ongoing)
*Goal: Improve hosted experience based on user feedback.*

- [ ] Usage analytics dashboard (how many simulations run, popular LLM providers, etc.)
- [ ] Multi-language support
- [ ] Session sharing (share simulation results via public URL)
- [ ] Webhook notifications (simulation complete, report ready)
- [ ] Admin dashboard for monitoring users and usage

---

## 12. Decisions Log

All decisions finalized — no open questions remain.

| # | Topic | Decision | Rationale |
|:--|:------|:---------|:----------|
| Q1 | Memory backend | **SQLite FTS5 local + PostgreSQL FTS cloud. No Zep.** | Simplest stack, no external dependency. PostgreSQL FTS covers cloud memory needs without Zep's cost/complexity. |
| Q2 | Hosting platform | **AWS ECS Fargate** | Uses existing $200 credits, more control, runs existing Docker containers as-is. |
| Q3 | Open source vs hosted | **Both** — open source (AGPL) first, then hosted cloud | Standard approach (GitLab, Supabase, n8n). Community testing before cloud launch. |
| Q4 | Authentication | **OAuth (Google/GitHub) + Magic link** | No password management, most secure, lowest friction. |
| Q5 | Free tier limits | **5 sessions (override oldest), 100 agents, 10 rounds, 14 days retention** | See Section 9 for full tier config. Paid: 1,000 agents, 50 rounds, unlimited retention. |
| Q6 | OpenRouter testing | **Yes, test now** | Key already in `.env`. Verify simulation quality with free models before promising path. |
| Q7 | Graphiti code | **Remove entirely** | Graphiti is non-functional. Keeping dead code increases maintenance burden. See Section 7.2 for file list. |
| Q8 | Database for multi-tenancy | **PostgreSQL from day 1** (RDS, ~$15/month) | Standard, scales better, enables RLS for multi-tenancy. No migration needed later. |
| Q9 | Deployment packaging | **Ship both source code + Docker** | Docker lowers barrier for non-developers. See Section 8 for both paths. |

---

## Appendix A: Cost Comparison

### Hosting Cost (Monthly, BYOK so no LLM costs)

| Component | AWS ECS (chosen) | Railway | Fly.io |
|:----------|:-----------------|:--------|:-------|
| Compute (backend) | $15–30 | $5–10 | $5–10 |
| Load balancer/routing | $16 | Included | Included |
| PostgreSQL RDS (db.t3.micro) | $15 | $5–10 | $5–10 |
| S3 / Storage | $1–5 | $1–5 | $1–5 |
| CDN/Frontend | $1 | Included | N/A |
| SSL/Domain | Free | Free | Free |
| Stripe fees | 2.9% + $0.30/txn | — | — |
| **Total (infra)** | **$48–67** | **$11–25** | **$11–25** |

> Note: $200 AWS credits cover ~3–4 months of operation.

### LLM Cost to Users (BYOK)

| Provider | Model | Cost per Simulation (50 agents, 5 rounds) |
|:---------|:------|:------------------------------------------|
| OpenRouter (free) | Llama 3.1 8B | $0.00 |
| OpenRouter (paid) | GPT-4o Mini | ~$0.50–1.00 |
| Gemini | gemini-2.5-flash-lite | ~$0.30–0.80 |
| Ollama (local) | Any | $0.00 (your hardware) |

## Appendix B: File References

Key files for this plan:

| File | Relevance |
|:-----|:----------|
| `backend/src/mckainsey/services/memory_service.py` | Graphiti/memory retrieval logic — **remove Graphiti paths** |
| `backend/src/mckainsey/services/graphiti_service.py` | Graphiti client wrapper — **delete entirely** |
| `backend/src/mckainsey/services/simulation_service.py` | Simulation execution (writes to SQLite only) |
| `backend/src/mckainsey/services/console_service.py` | Chat endpoint orchestration |
| `backend/src/mckainsey/services/simulation_stream_service.py` | Event persistence, state snapshots, SSE pattern reference |
| `backend/src/mckainsey/services/storage.py` | SQLite schema and queries — **add MemoryStore interface** |
| `backend/src/mckainsey/services/lightrag_service.py` | LightRAG document ingestion — **add chunked streaming** |
| `backend/src/mckainsey/services/persona_sampler.py` | DuckDB persona sampling — **keep as-is** |
| `frontend/src/pages/Simulation.tsx` | Screen 3 component with state persistence bug |
| `frontend/src/pages/PolicyUpload.tsx` | Knowledge graph rendering — **add SSE subscription** |
| `frontend/src/contexts/AppContext.tsx` | Global state management |
| `frontend/src/App.tsx` | Router (switch/case unmount pattern) |
| `docker-compose.yml` | Current containerized deployment — **remove FalkorDB** |
| `quick_start.sh` | Local startup script — **remove FalkorDB, add Ollama docs** |
| `.env` | **SECURITY: contains real API keys — rotate before open-sourcing** |
