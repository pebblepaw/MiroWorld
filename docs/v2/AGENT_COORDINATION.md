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

---

## Communication Log

> Agents: append status updates here. Most recent at top.

### Template
```
[YYYY-MM-DD HH:MM] Agent{1|2}: {status update}
```

### Log

[2026-04-11 18:38] Agent2: MarkItDown integration is complete in the backend worktree. Upload parsing now routes non-text document formats through MarkItDown, with existing text normalization preserved for text-like files. Agent1 can update Screen 1 upload-card copy for the broader format support.
[2026-04-11 17:45] Agent2: Completed backend rename `McKAInsey -> MiroWorld` in `.worktrees/phase3.5-backend`, including package path, imports, Docker/runtime entrypoints, and backend-visible strings. Agent1 can proceed with B1 frontend rename and rebase onto `phase3.5-backend` after this branch is pushed.
