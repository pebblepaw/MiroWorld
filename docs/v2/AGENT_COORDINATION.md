# Agent Coordination — Phase 3.5

> Two agents working in parallel on the same repo. This file defines boundaries, ports, and communication.

## Agent Assignments

| Agent | Role | Worktree | Branch | Tasks |
|:------|:-----|:---------|:-------|:------|
| **Agent1** (Claude — Frontend) | Frontend changes | Main worktree (`/Nemotron_Consult`) | `phase3.5-frontend` | 3.5-B1 through B11 |
| **Agent2** (Backend Agent) | Backend changes | `/Nemotron_Consult/.worktrees/phase3.5-backend` | `phase3.5-backend` | 3.5-A1 through A10 |

## Port Allocation

| Port | Owner | Purpose |
|:-----|:------|:--------|
| 5173 | Agent1 (Frontend) | Vite dev server |
| 5174 | Agent2 (Backend) | Vite dev server (if testing frontend) |
| 8000 | Agent1 | FastAPI backend |
| 8001 | Agent2 | FastAPI backend |
| 9515 | Agent1 | Playwright browser |
| 9516 | Agent2 | Playwright browser |

**CRITICAL:** Do NOT kill processes on ports you don't own. Check with `lsof -i :<port>` before starting.

## Worktree Setup (Agent2 must run this first)

```bash
cd /Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult
git checkout -b phase3.5-backend
git worktree add .worktrees/phase3.5-backend phase3.5-backend
```

Agent1 works on main worktree:
```bash
git checkout -b phase3.5-frontend
```

## File Ownership (Deconfliction)

**Agent1 (Frontend) owns:**
- `frontend/src/**` — all frontend source
- `frontend/public/**`
- `frontend/index.html`
- `frontend/package.json` (for frontend deps)

**Agent2 (Backend) owns:**
- `backend/src/**` — all backend source
- `backend/pyproject.toml`
- `config/**` — all config files
- `backend/scripts/**`
- `docker-compose.yml`
- `quick_start.sh`
- `Dockerfile`, `Dockerfile.oasis`

**Shared files (coordinate before editing):**
- `README.md` — Agent2 handles content, Agent1 adds screenshots
- `.env.example` — Agent2 owns
- `frontend/src/types/**` — if backend changes API shape, post a note below

## Merge Order

1. **Agent2 merges `phase3.5-backend` into `main` FIRST** (rename is the riskiest change)
2. **Agent1 rebases `phase3.5-frontend` onto updated `main`**
3. **Agent1 merges `phase3.5-frontend` into `main`**
4. **Both verify:** full E2E test on merged main

## Rename Coordination

The `McKAInsey → MiroWorld` rename touches BOTH frontend and backend.

**Order:**
1. Agent2 renames `backend/src/mckainsey/` → `backend/src/miroworld/`, all imports, configs, prompts
2. Agent2 commits and pushes
3. Agent1 renames frontend UI strings (`McKAInsey` → `MiroWorld` in .tsx files, index.html, package.json)
4. Agent1 does NOT touch backend files

## Country Dataset Readiness Contract

**Backend status:** Agent2 has added backend-owned country dataset readiness and download APIs. Agent1 must wire the onboarding/configure UI to these APIs and must not hard-code country availability in frontend state for live mode.

**Endpoints Agent1 must use:**
- `GET /api/v2/countries`
- `POST /api/v2/countries/{country}/download`
- `GET /api/v2/countries/{country}/download-status`

**New fields on each country from `GET /api/v2/countries`:**
- `dataset_ready: boolean`
- `download_required: boolean`
- `download_status: "ready" | "missing" | "downloading" | "error"`
- `download_error: string | null`
- `missing_dependency: "huggingface_api_key" | null`

**Required frontend behavior:**
1. In live mode, do not rely on the static country fallback list for readiness. Use backend readiness fields.
2. If the selected country has `dataset_ready=false`, show a `Download dataset` action instead of allowing the user to proceed normally.
3. Clicking `Download dataset` must call `POST /api/v2/countries/{country}/download`, then poll `GET /api/v2/countries/{country}/download-status` until the status becomes `ready` or `error`.
4. The launch/create-session CTA must remain disabled until `dataset_ready=true` for the selected country.
5. If the backend reports `missing_dependency == "huggingface_api_key"` or returns error code `huggingface_api_key_missing`, show a clear message: `Add HUGGINGFACE_API_KEY to the root .env file, then restart the backend.`
6. If a dataset download is in progress, show progress/loading state and prevent duplicate download requests for the same country.
7. Once the dataset is ready, resume the normal live flow and create/update the session with that selected country.

**Backend error contract Agent1 must handle:**
- `country_dataset_missing`
- `country_dataset_invalid`
- `huggingface_api_key_missing`

**Completion signal:**
- Agent1 must append a communication-log line when the UI work is done using this exact pattern:
  `[YYYY-MM-DD HH:MM] Agent1: Country dataset readiness UI wired to /api/v2/countries and /api/v2/countries/{country}/download* endpoints; launch/create CTA now blocks until dataset_ready=true.`
- Agent2 will watch this file for that entry, then run the full E2E verification pass.

---

## Communication Log

> Agents: append status updates here. Most recent at top.

### Template
```
[YYYY-MM-DD HH:MM] Agent{1|2}: {status update}
```

### Log

[2026-04-12 15:30] Agent1: Country dataset readiness UI wired to /api/v2/countries and /api/v2/countries/{country}/download* endpoints; launch/create CTA now blocks until dataset_ready=true.
[2026-04-11 18:38] Agent2: MarkItDown integration is complete in the backend worktree. Upload parsing now routes non-text document formats through MarkItDown, with existing text normalization preserved for text-like files. Agent1 can update Screen 1 upload-card copy for the broader format support.
[2026-04-11 18:55] Agent1: All Phase 3.5-B tasks complete (B1–B11). Rebased phase3.5-frontend onto main (including Agent2's backend commits), merged into local main. E2E Playwright test passed across all 5 screens. CSS duplicate .dark block bug fixed post-merge. Ready for Phase 3.5-C (demo cache rebuild).
[2026-04-11 17:45] Agent2: Completed backend rename `McKAInsey -> MiroWorld` in `.worktrees/phase3.5-backend`, including package path, imports, Docker/runtime entrypoints, and backend-visible strings. Agent1 can proceed with B1 frontend rename and rebase onto `phase3.5-backend` after this branch is pushed.
