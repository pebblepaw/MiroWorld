# McKAInsey V2 — Implementation Plan: Cloud Hosting, Memory Backend & Bug Fixes

> Date: 2026-04-09  
> Status: Draft for review — contains decision points marked with ❓  
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
9. [Implementation Phases](#9-implementation-phases)
10. [Open Questions for Owner](#10-open-questions-for-owner)

---

## 1. Executive Summary

This plan addresses four interconnected concerns:

| Concern | Finding | Recommendation |
|:--------|:--------|:---------------|
| Is Graphiti working? | **No.** Graphiti is not writing memory during simulation, and lazy-sync during chat is fragile. | Replace with simpler SQLite-based retrieval or adopt Zep Cloud for hosted version |
| Do we need Graphiti? | **Not for typical workloads** (50–200 agents, 5–10 rounds). SQLite handles it fine. For 1000+ agents with hundreds of rounds, a graph DB adds value. | Phase out Graphiti for now; design for optional graph backend later |
| Cloud hosting | **Yes, BYOK makes this feasible and cheap.** | AWS ECS Fargate + RDS/S3, or simpler Railway/Fly.io path |
| Screen 3 state persistence bug | **Frontend-only bug.** `simulationState` is local component state, destroyed on navigation. | Move `simulationState` to AppContext |

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

❓ **Decision needed:** Do you want to pursue the hosted version now, or focus on stabilizing the open-source version first? The hosted version requires solving hosting, auth, multi-tenancy, and payment (even if free tier).

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

**Recommendation: Phase out Graphiti now, design for optional graph backend later.**

### 4.2 Proposed Memory Architecture

#### Option A: SQLite-Only Memory (Recommended for Phase 1)

The simulation already writes everything to SQLite. The chat grounding just needs better retrieval from SQLite:

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

**Advantages:**
- Zero additional infrastructure (no FalkorDB, no Docker)
- Already have all the data in SQLite
- Works identically local and hosted
- Can handle 1000+ agents easily

**What MiroFish's Zep does that we'd replicate in SQLite:**
- ✅ Full-text search of agent activities — SQLite FTS5
- ✅ Agent-scoped memory — WHERE agent_id = ?
- ✅ Temporal ordering — ORDER BY timestamp
- ✅ Episode grouping — GROUP BY round_num
- ❌ Semantic similarity — not available in SQLite alone (but can use LLM reranking)
- ❌ Entity/relationship extraction — not available (but not critical for chat grounding)

#### Option B: SQLite + Zep Cloud (For Hosted Version)

For the cloud-hosted version, Zep Cloud could be re-introduced as an optional premium feature:

```
Simulation → SQLite + ZepGraphMemoryUpdater (background thread, à la MiroFish)
                ↓
Chat Query → Zep Cloud semantic search (primary) + SQLite (fallback)
```

This follows MiroFish's proven architecture exactly. Zep Cloud's free tier (see https://app.getzep.com/) may be sufficient for moderate usage.

#### Option C: Keep Graphiti but Fix It (Not Recommended)

Would require:
1. Writing a real-time ingestion worker (like MiroFish's `ZepGraphMemoryUpdater`)
2. Running FalkorDB as infrastructure
3. Handling FalkorDB ops (backups, scaling, monitoring)
4. Testing across all provider/model combinations

This adds significant complexity for marginal benefit over SQLite FTS5.

❓ **Decision needed:** Option A (SQLite-only, simplest) or Option A+B (SQLite for local, Zep Cloud for hosted)?

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
   User ──HTTPS──▶ │  CloudFront (CDN)                           │
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

❓ **Decision needed:** AWS (more control, uses your credits) or Railway/Fly.io (simpler, cheaper at low scale)?

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

| Approach | Complexity | Isolation |
|:---------|:-----------|:----------|
| **Per-user SQLite DB** | Low | Good — separate files per user |
| **PostgreSQL with row-level security** | Medium | Best — standard multi-tenant pattern |
| **Separate container per user** | High | Perfect isolation but expensive |

**Recommendation:** Start with per-user SQLite databases on EFS. Migrate to PostgreSQL if you exceed ~100 concurrent users.

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
| Database | SQLite file | SQLite on EFS (or PostgreSQL) | `DATABASE_URL` env var |
| File uploads | Local filesystem | EFS or S3 | `UPLOAD_STORAGE=local|s3` env var |
| Auth | None (local user) | API key or OAuth | Add auth middleware, gated by `AUTH_ENABLED` env var |
| Memory backend | SQLite FTS5 | SQLite FTS5 (or Zep Cloud) | `MEMORY_BACKEND=sqlite|zep` env var |
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

### 7.2 Graphiti Cleanup (Priority: MEDIUM)

**Problem:** Dead Graphiti code adds complexity, confuses new contributors, and masks the real memory retrieval path.

**Fix (Phase 1 — Simplify):**

1. Set `MEMORY_BACKEND=sqlite` as the default
2. In `MemoryService.agent_chat_realtime()`, skip Graphiti entirely when backend is `sqlite`
3. Implement proper SQLite-based agent context retrieval:
   - Query `interactions` WHERE `agent_id = ?` ORDER BY `created_at` DESC LIMIT 50
   - Query `simulation_checkpoints` WHERE `agent_id = ?`
   - Format into structured memory prompt (see Section 4.3)

4. Keep Graphiti code behind `MEMORY_BACKEND=graphiti` flag for future use, but mark as experimental

**Fix (Phase 2 — Optional, if you want Zep Cloud for hosted):**

1. Add `MEMORY_BACKEND=zep` option
2. Implement a `ZepMemoryWriter` that runs during simulation (like MiroFish's `ZepGraphMemoryUpdater`)
3. Write every agent action to Zep Cloud in real-time during OASIS simulation
4. For chat, use Zep Cloud search API

**Estimated effort:**
- Phase 1: 3–4 hours
- Phase 2: 1–2 days

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
| **Remove `falkordb` service** | Delete from `docker-compose.yml`. Remove `depends_on: falkordb` from backend. | 15 min |
| **Fix Ollama connectivity** | Three options: (A) Add an `ollama` service to docker-compose that runs Ollama in a container, (B) use `network_mode: host` so containers can reach host Ollama, or (C) default Docker to OpenRouter/Gemini and tell users to set `LLM_BASE_URL=http://host.docker.internal:11434/v1/` if they want host Ollama. Option C is simplest. | 1 hr |
| **Merge OASIS into backend container** | Currently `Dockerfile` is Python 3.12-only and `Dockerfile.oasis` is Python 3.11-only. Two options: (A) Keep the two-container split (current approach, but verify `oasis_server` module works), or (B) use a multi-stage Dockerfile that installs both Python 3.12 and 3.11 in one image. Option A is simpler if the sidecar already works. | 2–4 hr |
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

❓ **Decision needed (Q9):** Should both paths be ready for the initial open-source release, or ship source code first and add Docker support later? Docker adds ~6–8 hours of work but significantly lowers the barrier for non-developer users.

---

## 9. Implementation Phases

### Phase 1: Stabilize (1–2 days)
*Goal: Fix bugs, simplify memory, ship a clean open-source version.*

- [ ] **7.1** Fix Screen 3 state persistence (move `simulationState` to AppContext)
- [ ] **7.2 Phase 1** Switch to SQLite-only memory backend, keep Graphiti as optional
- [ ] **7.3** Implement proper SQLite-based agent memory retrieval for chat
- [ ] Update `quick_start.sh` to not require FalkorDB by default
- [ ] Run full E2E test: onboarding → knowledge → sampling → simulation → report → chat → analytics
- [ ] Update documentation to reflect SQLite memory backend

### Phase 2: Open Source Prep (1–2 days)
*Goal: Make the project ready for public GitHub release with both deployment paths.*

- [ ] Review and clean up `.env.example` with all required variables
- [ ] Write clear README with setup instructions for: macOS, Linux, Docker
- [ ] Add AGPL-3.0 LICENSE file
- [ ] Add OpenRouter setup guide with screenshots
- [ ] Remove any hardcoded paths, secrets, or personal credentials
- [ ] **Source code path**: Remove FalkorDB dependency from `quick_start.sh`, document Python 3.11 requirement
- [ ] **Docker path**: Update `docker-compose.yml` (remove FalkorDB, add healthchecks, fix Ollama access, add boot mode)
- [ ] **Docker path**: Verify OASIS sidecar container works end-to-end
- [ ] **Docker path**: Add production frontend build (nginx or caddy instead of Vite dev server)
- [ ] Add GitHub Actions CI for lint + test
- [ ] Tag v2.0.0 release

### Phase 3: Cloud Hosting MVP (3–5 days)
*Goal: Deploy a working BYOK instance accessible via URL.*

- [ ] **Auth**: Add simple API-key-based auth middleware (`AUTH_ENABLED=true`)
- [ ] **Multi-tenancy**: Scope all DB operations to `user_id`
- [ ] **Storage**: Switch file uploads to S3 (env-configurable)
- [ ] **Deployment**: Push to chosen hosting platform (AWS ECS or Railway)
- [ ] **DNS/SSL**: Configure custom domain with HTTPS
- [ ] **Monitoring**: Add basic health checks and error logging (CloudWatch or equivalent)
- [ ] **Landing page**: Create onboarding page explaining BYOK + OpenRouter free tier

### Phase 4: Enhancement (ongoing)
*Goal: Improve hosted experience based on user feedback.*

- [ ] Rate limiting per user
- [ ] Session auto-cleanup (delete sessions older than 30 days)
- [ ] Optional Zep Cloud integration for premium memory
- [ ] Usage analytics dashboard
- [ ] Multi-language support

---

## 10. Open Questions for Owner

Please answer these so the next agent can execute without ambiguity:

### Architecture Decisions

**Q1: Memory backend**  
Option A: SQLite-only (simplest, works everywhere)  
Option B: SQLite for local + Zep Cloud for hosted  
Recommendation: Start with A, add B later if needed.  
**Your choice:** ___

**Q2: Hosting platform**  
Option A: AWS ECS Fargate (~$35–50/month, uses your $200 credits, more control)  
Option B: Railway (~$5–20/month, deploy in 10 minutes, simpler)  
Option C: Fly.io (~$5–15/month, good container support, global)  
Recommendation: B or C for MVP speed, migrate to A if you scale.  
**Your choice:** ___

**Q3: Open source first or hosted first?**  
Option A: Stabilize → open source → then build hosted version  
Option B: Build hosted version first, open source later  
Recommendation: A — stabilize first, open source gives you community testing.  
**Your choice:** ___

### Product Decisions

**Q4: Authentication for hosted version**  
Option A: Email/password (traditional, you manage passwords)  
Option B: OAuth only (Google/GitHub login, no password management)  
Option C: Magic link (email-based, passwordless)  
Recommendation: B (OAuth via GitHub/Google), simplest and most secure.  
**Your choice:** ___

**Q5: Free tier limits for hosted version**  
What limits should free users have? Suggestions:  
- Max sessions: 10 active  
- Max agents per simulation: 100  
- Max rounds: 10  
- Storage retention: 30 days  
**Your preferences:** ___

**Q6: Do you want to test OpenRouter free models now?**  
Before promising this path, we should verify simulation quality with free models. This requires running a full simulation with a free OpenRouter model and evaluating output quality.  
**Your preference:** ___

### Technical Decisions

**Q7: Should we remove Graphiti code entirely or keep it behind a flag?**  
Option A: Remove completely (cleaner codebase)  
Option B: Keep behind `MEMORY_BACKEND=graphiti` flag (future flexibility)  
Recommendation: B — low maintenance cost to keep it as an option.  
**Your choice:** ___

**Q8: Database for hosted multi-tenancy**  
Option A: Per-user SQLite files on EFS (simple, works up to ~100 users)  
Option B: PostgreSQL from day 1 (standard, scales better, costs $15/month for RDS)  
Recommendation: A for MVP, migrate to B if/when needed.  
**Your choice:** ___

**Q9: Ship both source code and Docker for initial open-source release?**  
Option A: Source code only first (faster to ship, ~4 hours of cleanup)  
Option B: Both source code and Docker (adds ~6–8 hours, but lowers barrier for non-developers)  
Recommendation: B — Docker is what turns "interesting GitHub repo" into "tool I actually tried". See Section 8 for full breakdown.  
**Your choice:** ___

---

## Appendix A: Cost Comparison

### Hosting Cost (Monthly, BYOK so no LLM costs)

| Component | AWS ECS | Railway | Fly.io |
|:----------|:--------|:--------|:-------|
| Compute (backend) | $15–30 | $5–10 | $5–10 |
| Load balancer/routing | $16 | Included | Included |
| Storage (EFS/Volume) | $1–5 | $1–5 | $1–5 |
| CDN/Frontend | $1 | Included | N/A |
| SSL/Domain | Free | Free | Free |
| **Total** | **$33–52** | **$6–15** | **$6–15** |

### LLM Cost to Users (BYOK)

| Provider | Model | Cost per Simulation (50 agents, 5 rounds) |
|:---------|:------|:------------------------------------------|
| OpenRouter (free) | Llama 3.1 8B | $0.00 |
| OpenRouter (paid) | GPT-4o Mini | ~$0.50–1.00 |
| Gemini | gemini-2.5-flash-lite | ~$0.30–0.80 |
| Ollama (local) | Any | $0.00 (your hardware) |

## Appendix B: File References

Key files investigated for this plan:

| File | Relevance |
|:-----|:----------|
| `backend/src/mckainsey/services/memory_service.py` | Graphiti/memory retrieval logic |
| `backend/src/mckainsey/services/graphiti_service.py` | Graphiti client wrapper |
| `backend/src/mckainsey/services/simulation_service.py` | Simulation execution (writes to SQLite only) |
| `backend/src/mckainsey/services/console_service.py` | Chat endpoint orchestration |
| `backend/src/mckainsey/services/simulation_stream_service.py` | Event persistence and state snapshots |
| `backend/src/mckainsey/services/storage.py` | SQLite schema and queries |
| `frontend/src/pages/Simulation.tsx` | Screen 3 component with state persistence bug |
| `frontend/src/contexts/AppContext.tsx` | Global state management |
| `frontend/src/App.tsx` | Router (switch/case unmount pattern) |
| `docker-compose.yml` | Current containerized deployment |
| `quick_start.sh` | Local startup script |
