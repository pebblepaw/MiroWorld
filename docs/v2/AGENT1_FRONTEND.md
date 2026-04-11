# Agent1 Instructions — Frontend (Claude)

> You are the frontend agent for Phase 3.5. Read `/docs/v2/ImplementationPlan.md` Section 11, Phase 3.5-B for your full task list.

## Your Environment

- **Worktree:** Main (`/Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult`)
- **Branch:** `phase3.5-frontend`
- **Vite dev server:** port 5173
- **Backend:** port 8000
- **Playwright:** port 9515

## Progress Checklist

> **Instructions:** After completing each task, tick its checkbox by changing `- [ ]` to `- [x]` in this file. This lets the user track both agents' progress at a glance.

- [x] 3.5-B8: Tab switching persistence fix (highest user impact)
- [x] 3.5-B2: Light/Dark mode toggle
- [x] 3.5-B3: Font size standardization
- [x] 3.5-B4: Text color standardization
- [x] 3.5-B5: Slider improvements (agent count + rounds)
- [x] 3.5-B6: Comment likes/dislikes + button standardization
- [x] 3.5-B7: Screen 5 comment likes fix
- [x] 3.5-B9: Screen 3 state persistence
- [ ] 3.5-B10: Upload card text update ⏳ blocked on Agent2 MarkItDown (A6)
- [x] 3.5-B11: Remove campaign use case from UI
- [x] 3.5-B1: Rename McKAInsey → MiroWorld in frontend ⏳ blocked on Agent2 rename (A1)

## Key Context

- CSS variables are in `frontend/src/index.css` lines 10-56
- `tailwind.config.ts` already has `darkMode: ["class"]`
- AppContext is at `frontend/src/contexts/AppContext.tsx`
- Simulation page: `frontend/src/pages/Simulation.tsx`
- Analytics page: `frontend/src/pages/Analytics.tsx`
- Report page: `frontend/src/pages/ReportChat.tsx`
- Screen 1: `frontend/src/pages/PolicyUpload.tsx`
- Screen 2: `frontend/src/pages/AgentConfig.tsx`

## Rules

- Do NOT edit any files in `backend/`, `config/`, or root scripts
- Do NOT kill processes on ports 8001, 5174, 9516 (Agent2's ports)
- Update the Communication Log in `/docs/v2/AGENT_COORDINATION.md` when you complete a task
- If you need a backend API change, post a request in the Communication Log
