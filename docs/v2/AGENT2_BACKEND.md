# Agent2 Instructions — Backend

> You are the backend agent for Phase 3.5. Read `/docs/v2/ImplementationPlan.md` Section 11, Phase 3.5-A for your full task list.

## Your Environment

- **Worktree:** `.worktrees/phase3.5-backend`
- **Branch:** `phase3.5-backend`
- **Backend server:** port 8001 (use `--port 8001`)
- **Vite dev server (if needed):** port 5174
- **Playwright (if needed):** port 9516

## Setup

```bash
cd /Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult
git checkout -b phase3.5-backend
git worktree add .worktrees/phase3.5-backend phase3.5-backend
cd .worktrees/phase3.5-backend
source .venv/bin/activate  # or create a new venv
```

## Progress Checklist

> **Instructions:** After completing each task, tick its checkbox by changing `- [ ]` to `- [x]` in this file. This lets the user track both agents' progress at a glance.

- [x] 3.5-A1: Rename McKAInsey → MiroWorld ⚠️ DO THIS FIRST — commit & push so Agent1 can rebase
- [x] 3.5-A2: Fix "Knowledge artifact not found" for USA
- [x] 3.5-A3: Fix agent name parsing (majority-vote across columns)
- [x] 3.5-A4: Externalize ALL prompts to `/config/prompts/system/`
- [x] 3.5-A5: Remove fake fallback data in live mode
- [x] 3.5-A6: Integrate MarkItDown for document parsing
- [x] 3.5-A7: Fix strategic parameters LLM parsing (country-aware)
- [x] 3.5-A8: Fix post title generation (part of prompt externalization)
- [x] 3.5-A9: Fix Screen 4 analysis write-ups — increase length
- [x] 3.5-A10: Fix cost estimation pricing

## Task Details

**3.5-A1: Rename McKAInsey → MiroWorld**
- `backend/src/mckainsey/` → `backend/src/miroworld/`
- Update ALL imports, pyproject.toml, docker configs
- Commit and push immediately so Agent1 can rebase

## Key Files

| File | Purpose |
|:-----|:--------|
| `backend/src/mckainsey/services/persona_relevance_service.py` | Name parsing (line 742+), filter parsing (line 131+) |
| `backend/src/mckainsey/services/lightrag_service.py` | Document processing, graph extraction |
| `backend/src/mckainsey/services/console_service.py` | API routes, knowledge artifact error (line 1108) |
| `backend/src/mckainsey/services/report_service.py` | Report generation prompts |
| `backend/src/mckainsey/services/simulation_service.py` | Checkpoint prompts (line 752+) |
| `backend/src/mckainsey/services/document_parser.py` | File parsing (replace with MarkItDown) |
| `backend/src/mckainsey/services/token_tracker.py` | Cost estimation pricing |
| `backend/src/mckainsey/services/storage.py` | SQLite schema, knowledge artifacts |
| `config/prompts/` | Existing prompt configs (3 use-case files) |
| `config/countries/` | Country configs (singapore.yaml, usa.yaml) |

## Rules

- **After completing each task, tick its checkbox in the Progress Checklist above** (`- [ ]` → `- [x]`)
- Do NOT edit any files in `frontend/src/`
- Do NOT kill processes on ports 5173, 8000, 9515 (Agent1's ports)
- Update the Communication Log in `/docs/v2/AGENT_COORDINATION.md` when you:
  - Complete the rename (Agent1 is blocked on this)
  - Change any API response shape (Agent1 needs to update types)
  - Complete MarkItDown integration (Agent1 needs to update upload card text)
- After the rename, notify via the Communication Log that Agent1 can proceed with B1 (frontend rename)

## API Shape Changes

If you change the shape of any API response, document it here so Agent1 can update frontend types:

| Endpoint | Field Changed | Old Shape | New Shape | Date |
|:---------|:-------------|:----------|:----------|:-----|
| *(none yet)* | | | | |
