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

### Phase 3.5: Feature Polish, Bug Fixes & Rename (5–7 days)

*Goal: Fix all user-reported bugs, add UX polish, externalize prompts, rename project, and regenerate GitHub Pages caches. Split into frontend (Agent1) and backend (Agent2) tracks for parallel work.*

> **Agent Coordination:** See `/docs/v2/AGENT_COORDINATION.md` for worktree assignments, port allocation, and communication protocol between the two agents.

---

#### Phase 3.5-A: Backend Track (Agent2)

**3.5-A1: Rename Project — McKAInsey → MiroWorld** *(2–3 hours)*

> **WARNING:** This touches ~45+ backend files and the entire Python package namespace. Must be done FIRST before other backend work to avoid merge conflicts.

| Task | Details |
|:-----|:--------|
| Rename directory | `backend/src/mckainsey/` → `backend/src/miroworld/` |
| Update all imports | Every `from mckainsey.` and `import mckainsey.` across ~45 backend files |
| Update `pyproject.toml` | Package name, entry points, any internal references |
| Update `docker-compose.yml` | Service names, image names referencing `mckainsey` |
| Update `Dockerfile` / `Dockerfile.oasis` | Any `COPY` or package references |
| Update `quick_start.sh` | Any references to `mckainsey` |
| Update config files | Check `/config/prompts/*.yaml` for "McKAInsey" in prompt text |
| Search-and-replace strings | `"McKAInsey"` → `"MiroWorld"` in all UI-visible strings, system prompts, report headers |

**Files with "McKAInsey" in visible strings (must change):**
- `backend/src/mckainsey/services/report_service.py` — report headers, system prompts
- `backend/src/mckainsey/services/console_service.py` — download filenames
- `config/prompts/*.yaml` — system prompts

**3.5-A2: Fix "Knowledge artifact not found" for USA dataset** *(2–3 hours)* `#High`

**Root cause:** `console_service.py:1108–1110` raises `HTTPException(404)` when `storage.get_knowledge_artifact(session_id)` returns `None`. This happens when USA document processing fails silently during Screen 1 upload, so no knowledge artifact exists when Screen 2 tries to read it.

**Investigation needed:**
- Check `lightrag_service.py:360–410` — LightRAG initialization may fail for USA due to missing or misformatted data
- Check `config/countries/usa.yaml` — may lack proper initialization config
- Trace the full flow: upload → `lightrag_service.process_document()` → `storage.save_knowledge_artifact()` — find where it fails silently for USA

**Fix approach:**
1. Add proper error propagation (no silent failures) in the LightRAG processing chain
2. If LightRAG fails, return a clear error to the frontend explaining what went wrong
3. Verify USA config has all required fields matching Singapore's structure
4. Add integration test: USA document upload → knowledge artifact creation

**3.5-A3: Fix Agent Name Parsing** *(3–4 hours)* `#High`

**Current state:** `persona_relevance_service.py:742–780` extracts names from persona text using 3 regex patterns. Falls back to `"Occupation (Planning Area)"` when all regexes fail.

**Problems found:**
1. Only searches `professional_persona`, `persona`, `cultural_background` columns — misses `travel_persona`, `sports_persona`, `arts_persona`
2. `NAME_WITH_VERB_PATTERN` at line 110 only catches names followed by specific verbs — misses patterns like `"At 48, John is..."`
3. `CAPITALIZED_NAME_PATTERN` grabs any capitalized words, including festival/place names
4. Checkpoint interview `confirmed_name` field IS implemented in `simulation_service.py:800` but the extracted name may not propagate back to Screen 4/5 display

**Fix — implement user's majority-vote approach:**
```
1. Extract candidate names from ALL persona columns:
   travel_persona, sports_persona, persona, professional_persona, arts_persona
2. For each column, apply improved regex:
   - Match first 1-7 sequential capitalized words at sentence start
   - Allow brackets for middle names: "Syed R. (Mogan) Lamaze"
   - Skip leading age/detail phrases: "At 48, " prefix
3. Take majority winner across columns
4. Verify confirmed_name from checkpoint interview propagates to Screen 4/5
```

**Improved regex pattern:**
```python
# Skip leading "At \d+, " or "In \d{4}, " prefixes
LEADING_NOISE = re.compile(r"^(?:At\s+\d+,?\s*|In\s+\d{4},?\s*)")
# Match 1-7 capitalized words (allow brackets, periods, hyphens)
NAME_PATTERN = re.compile(
    r"([A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|\([A-Z][a-z]+\)|[A-Z]\.)){0,6})"
)
```

**3.5-A4: Externalize ALL Prompts to Config Files** *(4–6 hours)* `#High`

**Current state:** 3 prompts already in `/config/prompts/*.yaml`. 8+ remain hardcoded in Python.

**Prompts to externalize:**

| # | Current Location | Prompt Purpose | Target Config File |
|:--|:-----------------|:---------------|:-------------------|
| 1 | `lightrag_service.py:278–283` | Graph extraction system prompt | `/config/prompts/system/graph_extraction.yaml` |
| 2 | `lightrag_service.py:512–524` | Document summarization (per-provider) | `/config/prompts/system/document_summary.yaml` |
| 3 | `memory_service.py:138–155` | Sampling instruction parsing + memory context | `/config/prompts/system/memory_context.yaml` |
| 4 | `report_service.py:110–111` | Report agent system prompt | `/config/prompts/system/report_agent.yaml` |
| 5 | `report_service.py:260` | Report writing system prompt | (same file as #4) |
| 6 | `report_service.py:298` | Report analysis system prompt | (same file as #4) |
| 7 | `report_service.py:969` | Report editing system prompt | (same file as #4) |
| 8 | `persona_relevance_service.py:145–146` | Sampling instruction parser system prompt | `/config/prompts/system/sampling_parser.yaml` |
| 9 | `simulation_service.py:752–810` | Checkpoint interview prompt template | `/config/prompts/system/checkpoint_interview.yaml` |

**Implementation pattern:**
```python
# config/prompts/system/report_agent.yaml
description: "System prompt for the report generation agent"
prompts:
  report_writer:
    description: "Main report writing prompt — generates structured analysis"
    template: |
      You are MiroWorld ReportAgent. Return a detailed, insightful strategic summary...
  report_editor:
    description: "Report editing prompt — rewrites sections for clarity"
    template: |
      You are a policy-report editor. Return only the rewritten text.
```

**Each config file must have:**
- `description` field explaining what each prompt does
- Descriptive key names
- Comments/documentation for how the prompt is used

**3.5-A5: Fix Fake Fallback Data in Live Mode** *(2–3 hours)* `#High`

**Root cause:** User uploaded a URL to an AirBnB PDF but got "World Athletics Foundation" data. Investigation points:
- `routes_console.py:234–249` — demo mode fallback for cached data may leak into live mode
- `demo_service.py` — handles demo artifact retrieval
- Search for hardcoded "World Athletics" or other sample data strings

**Fix approach:**
1. Audit all demo/fallback data paths — ensure they ONLY activate when `BOOT_MODE=demo`
2. Add strict guards: `if boot_mode == "live" and data_source == "fallback": raise Error`
3. When LightRAG/scraping fails in live mode, return the actual error message to the frontend, not fallback data
4. Add logging to trace: URL received → scrape result → LightRAG input → output

**3.5-A6: Integrate MarkItDown for Document Parsing** *(2–3 hours)* `#High`

**Current state:** `document_parser.py:25–56` supports only PDF (pypdf), DOCX (python-docx), and text files. PPT, images, HTML are not supported.

**Fix:**
1. Add `markitdown` to `pyproject.toml` dependencies
2. Replace custom parsers with MarkItDown unified interface:
   ```python
   from markitdown import MarkItDown
   md = MarkItDown()
   result = md.convert(file_path)
   return result.text_content
   ```
3. Supported formats via MarkItDown: PDF, PPT, DOCX, XLSX, images (with OCR), HTML, CSV, JSON, XML, ZIP
4. Update frontend upload card text to list all supported formats
5. Add tests for each format

**3.5-A7: Fix Strategic Parameters LLM Parsing** *(3–4 hours)* `#High`

**Current state:** `persona_relevance_service.py:131–175` uses LLM to parse natural language filters. The system prompt says "Singapore population-sampling system" — hardcoded to Singapore.

**Problems:**
1. System prompt references Singapore specifically — won't work for USA/other countries
2. `SUPPORTED_INSTRUCTION_FIELDS` at line 70–82 lists fields like `planning_area` which is Singapore-specific
3. Each country's config should define its own filterable columns

**Fix:**
1. Move `SUPPORTED_INSTRUCTION_FIELDS` to `/config/countries/{country}.yaml`:
   ```yaml
   # config/countries/singapore.yaml
   filterable_columns:
     - field: planning_area
       description: "Sub-region or planning area within Singapore"
       type: categorical
     - field: age
       description: "Age of the person"
       type: range
     - field: occupation
       type: categorical
   ```
2. Make the LLM parsing prompt country-aware — inject the country's available columns
3. Update `_build_instruction_prompt()` to use country-specific column definitions
4. Test with "more samples from planning area Bishan" (Singapore) and "more samples from state California" (USA)

**3.5-A8: Fix Post Title Generation** *(1–2 hours)*

**Problem:** Post titles are sometimes just the first sentence truncated.

**Investigation:** Check the simulation agent prompt — confirm it asks for a `title` field in the JSON output. If it does, the issue is the LLM not consistently generating good titles. If it doesn't, add it.

**Fix is part of prompt externalization (3.5-A4)** — ensure the checkpoint/post generation prompt explicitly requires: `"title": "A descriptive title summarizing the post's point"`

**3.5-A9: Fix Screen 4 Analysis Write-ups — Too Short** *(2–3 hours)* `#High`

**Root cause:** `report_service.py:1445–1448` truncates input data to the report LLM:
- Population artifact: truncated to 6,000 chars
- Checkpoint records: truncated to 12,000 chars
- Influential posts: truncated to 6,000 chars

These caps starve the LLM of evidence, resulting in shallow write-ups.

**Fix:**
1. Increase truncation limits (or remove them if model context window allows):
   - With Gemini 2.5 Flash (1M context): increase to 50k chars each
   - With GPT-4o (128k context): increase to 20k chars each
2. Update the report prompt to explicitly ask for "detailed, evidence-rich analysis of 300–500 words per question"
3. Include specific instructions: "Cite specific agent quotes, demographic patterns, and round-over-round opinion shifts."
4. This is part of prompt externalization — the prompt in `/config/prompts/system/report_agent.yaml` will have a `min_words_per_question` parameter

**3.5-A10: Fix Cost Estimation** *(1–2 hours)*

**Current state:** `token_tracker.py:7–14` has hardcoded pricing that may be outdated.

**Fix:**
1. Move pricing table to `/config/llm_pricing.yaml`
2. Update with current Gemini pricing (as of 2025-07):
   - `gemini-2.5-flash-lite`: input $0.015/MTok, output $0.06/MTok (much cheaper than current values)
3. Cost calculation already works (agents × rounds × tokens × price) — just needs accurate prices
4. Add date field to pricing config so users know when it was last updated

---

#### Phase 3.5-B: Frontend Track (Agent1)

**3.5-B1: Rename Project — McKAInsey → MiroWorld** *(1 hour)*

| Task | Files |
|:-----|:------|
| UI strings | `Simulation.tsx:613`, `ReportChat.tsx:100,594`, `Analytics.tsx:258` |
| Page titles | Any `<title>` or document title references |
| Sidebar/branding | `AppSidebar.tsx` if branding text exists |
| index.html | `<title>` tag |
| `package.json` | `"name"` field |
| README.md | All references |

**3.5-B2: Light Mode / Dark Mode Toggle** *(3–4 hours)* `#High`

**Current state:** Only dark mode CSS variables defined in `index.css:10–56`. `tailwind.config.ts` has `darkMode: ["class"]` but unused.

**Implementation:**
1. **index.css** — add `:root` (light) variables alongside existing `.dark` variables:
   ```css
   :root {
     --background: 0 0% 98%;        /* Near-white */
     --foreground: 0 0% 10%;        /* Near-black */
     --primary: 357 79% 46%;        /* Keep red accent */
     --muted-foreground: 0 0% 40%;  /* Darker muted for readability */
     /* ... full light palette */
   }
   .dark {
     --background: 0 0% 4%;         /* Current dark values */
     --foreground: 0 0% 93%;
     /* ... existing dark values moved here */
   }
   ```
2. **ThemeContext** — create `frontend/src/contexts/ThemeContext.tsx`:
   - `useTheme()` hook returning `{ theme, toggle }`
   - Persist preference to `localStorage`
   - Apply `.dark` class to `<html>` element
3. **Toggle button** — add Sun/Moon icon to `AppSidebar.tsx` bottom-left corner
4. **Audit all hardcoded colors** — any `bg-black`, `text-white`, `border-white/10` etc. must use CSS variables instead
   - `Analytics.tsx` has many `text-white/80`, `bg-white/[0.02]` — these need to become `text-foreground/80`, `bg-foreground/[0.02]`
   - Estimate: 50–100 hardcoded color references across 5 page files

**3.5-B3: Font Size Standardization** *(2–3 hours)*

**Problems found:**
- Page titles: `text-lg` (Screen 1), `text-2xl` (Screen 2), `text-sm` (Screen 3), `text-lg` (Screen 4)
- Body text: `text-xs` (10px) on Screen 3 posts/comments — too small
- Report body: `label-meta` (10px custom class) — too small
- Some titles uppercase, others not

**Implement 4 font size presets via CSS variables:**
```css
/* index.css */
:root {
  --text-page-title: 1.5rem;       /* 24px — all page titles */
  --text-section-header: 1.125rem; /* 18px — card headers */
  --text-body: 0.875rem;           /* 14px — posts, comments, report text */
  --text-caption: 0.75rem;         /* 12px — timestamps, labels, metadata */
}
```

**Specific fixes:**
| Element | Current | Target | File:Line |
|:--------|:--------|:-------|:----------|
| Screen 1 title | `text-lg uppercase` | `text-page-title` (no uppercase) | `PolicyUpload.tsx:1180` |
| Screen 2 title | `text-2xl` | `text-page-title` | `AgentConfig.tsx:258` |
| Screen 3 title | `text-sm` | `text-page-title` | `Simulation.tsx:643` |
| Screen 4 title | `text-lg` | `text-page-title` | `ReportChat.tsx:687` |
| Screen 3 post content | `text-xs` (10px) | `text-body` (14px) | `Simulation.tsx:782` |
| Screen 3 comments | `text-xs` (10px) | `text-body` (14px) | `Simulation.tsx:803` |
| Screen 4 report body | `label-meta` (10px) | `text-body` (14px) | `ReportChat.tsx:764,829` |
| Title casing | Mixed | Consistent title case (no ALL CAPS) | All pages |

**3.5-B4: Text Color Standardization** *(1 hour)*

**Fix:** Change `label-meta` class from `hsl(var(--muted-foreground))` to `hsl(var(--foreground))` for section headers like "Analysis Questions", or create a `label-section` class with white/foreground color.

**Audit all section labels** across screens for consistent color treatment.

**3.5-B5: Agent & Round Slider Improvements** *(2–3 hours)*

**Agent count slider** (`AgentConfig.tsx:305–306`):
- Keep max at 500
- Add color zones: green (50–300), yellow (300–400), red (400–500)
- Show tooltip: "Recommended: 50–300 agents for best quality/speed balance"

**Simulation rounds slider** (`Simulation.tsx:655–659`):
- Change max from 8 to 50
- Free tier: cap at 10 with upgrade prompt
- Color zones: green (1–20), yellow (20–35), red (35–50)
- Show estimated time: `~{agents × rounds × 0.1}min`

**Implementation:** Custom slider component with gradient track:
```tsx
const getSliderColor = (value: number, max: number) => {
  const ratio = value / max;
  if (ratio <= 0.6) return 'hsl(142, 76%, 36%)'; // green
  if (ratio <= 0.8) return 'hsl(38, 92%, 50%)';  // yellow
  return 'hsl(0, 84%, 60%)';                      // red
};
```

**3.5-B6: Screen 3 — Comment Likes/Dislikes + Button Standardization** *(2–3 hours)*

**Problem 1:** `FeedComment` type (`Simulation.tsx:21–28`) has no `likes`/`dislikes` fields.

**Fix:**
1. Add `likes: number; dislikes: number;` to `FeedComment` type
2. Parse like/dislike data from backend response (OASIS simulation already tracks this)
3. Display like/dislike counts on each comment

**Problem 2:** Like/dislike buttons differ between Screen 3 and Screen 5.

**Fix:**
1. Create shared `<ReactionButtons />` component using Screen 5's colorful style
2. Use in both Screen 3 (`Simulation.tsx`) and Screen 5 (`Analytics.tsx`)

**3.5-B7: Screen 5 — Fix Comment Likes Showing 0** *(1–2 hours)*

**Root cause:** `ViralComment` type has `likes`/`dislikes` fields but the backend may return 0 or the data isn't being mapped correctly from the analytics API response.

**Fix:** Trace the data flow: backend analytics response → frontend mapping → display. Ensure `likes` field is populated from the correct backend field.

**3.5-B8: Tab Switching Reset Bug** *(2–3 hours)* `#High`

**Root cause:** App state is in-memory React context only. When Chrome suspends the tab (or the WebSocket reconnects), the app may reset `sessionId` which triggers `AppContext.tsx:178–185` to reset ALL state to defaults, navigating back to onboarding.

**Fix:**
1. **Persist critical state to `sessionStorage`:**
   - `sessionId`, `currentStep`, `bootMode`, `uploadedFiles` metadata, `knowledgeGraphReady`, `simulationComplete`
2. **On app mount, hydrate from `sessionStorage`:**
   ```typescript
   const [state, setState] = useState<AppState>(() => {
     const saved = sessionStorage.getItem('app-state');
     return saved ? JSON.parse(saved) : defaultState;
   });
   ```
3. **Sync state changes to `sessionStorage`:**
   ```typescript
   useEffect(() => {
     sessionStorage.setItem('app-state', JSON.stringify(criticalState));
   }, [criticalState]);
   ```
4. **Do NOT persist large data** (simPosts, full report) — only metadata and navigation state

**3.5-B9: Screen 3 State Persistence** *(1–2 hours)*

**Problem:** `controversyBoostEnabled` is local `useState` in `Simulation.tsx:190` — lost on navigation. `approvalRate` and `netSentiment` are in `simulationState` which may also reset.

**Fix:**
1. Move `controversyBoostEnabled` to AppContext (alongside other simulation state)
2. Ensure `approvalRate` and `netSentiment` are included in the state that gets persisted to sessionStorage (from 3.5-B8)
3. Verify `simulationState` in AppContext includes these metrics from the backend SSE events

**3.5-B10: Update Upload Card Text for MarkItDown** *(0.5 hours)*

After backend integrates MarkItDown (3.5-A6), update the Screen 1 upload card to list supported formats:
- "Supports: PDF, PPT, DOCX, XLSX, images, HTML, CSV, MD, TXT"

**3.5-B11: Remove Campaign Use Case from UI** *(1–2 hours)*

**Decision: Remove campaign-content-testing entirely.**

1. Remove from onboarding screen use case selector
2. Remove `campaign-content-testing` option from any dropdowns/config
3. Delete `/config/prompts/campaign-content-testing.yaml`
4. Update any frontend routing that references the campaign use case
5. Verify only 2 use cases remain: public-policy-testing, product-market-research

---

#### Phase 3.5-C: GitHub Pages Cache Rebuild (after A+B complete)

**3.5-C1: Use-Case-Specific Demo Caches** *(1 day)*

**Requirement:** Onboarding screen shows different cached data per use case selection.

1. **Policy cache:** Use `/Sample_Inputs/Policy/README.md` point #1 as input, 100 agents, 20 rounds
2. **Product cache:** Use `/Sample_Inputs/Policy/Airbnb_Pitch_Example.md` as input, 100 agents, 20 rounds
3. Frontend loads `demo-cache-policy.json` or `demo-cache-product.json` based on use case selection
4. Both caches include: knowledge graph, all simulation data, analytics, approval rate, net sentiment

**3.5-C2: Fix Cache Data Gaps**
- Ensure approval rate and net sentiment are included in cached data (backend script already has `_approval_rate()` function — verify it's being called)
- Pre-load Screen 4 chat with question: "Did any post change your mind?"

**3.5-C3: Regenerate & Deploy**
- Run cache generation for both use cases
- Build frontend with new caches
- Push to `gh-pages` branch

---

#### Phase 3.5 Effort Estimate

| Track | Tasks | Estimate |
|:------|:------|:---------|
| Backend (Agent2) | 3.5-A1 through A10 | 3–4 days |
| Frontend (Agent1) | 3.5-B1 through B11 | 3–4 days |
| Cache rebuild | 3.5-C1 through C3 | 1 day (after A+B) |
| **Total (parallel)** | | **4–5 days** |

#### Phase 3.5 Dependency Graph

```
3.5-A1 (Rename backend) ──────────┐
                                   ├──→ All other A tasks
3.5-B1 (Rename frontend) ─────────┤
                                   ├──→ All other B tasks
                                   │
3.5-A4 (Prompts to config) ───────┼──→ 3.5-A8 (Post titles)
                                   ├──→ 3.5-A9 (Report length)
                                   ├──→ KOL viewpoint fix
                                   │
3.5-A6 (MarkItDown) ──────────────┼──→ 3.5-B10 (Upload card text)
                                   │
3.5-B8 (Tab persistence) ─────────┼──→ 3.5-B9 (Screen 3 persistence)
                                   │
All A + B tasks ───────────────────┴──→ 3.5-C (Cache rebuild)
```

---

### Phase 4: Cloud Hosting MVP — AWS (3–5 days)
*Goal: Deploy a working BYOK instance with free + paid tiers.*

**Infrastructure:**
- [ ] Set up AWS account, configure `us-east-1` region
- [ ] Create ECR repositories for backend + OASIS sidecar images
- [ ] Set up RDS PostgreSQL (`db.t4g.micro`, ~$15/month
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
