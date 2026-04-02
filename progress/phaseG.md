# Phase G — McKAInsey Console Rebuild & Real-Time Validation

## Objective
Replace the inherited dashboard with the real McKAInsey console, align the UI to the vetted mockups, move the frontend onto screen-shaped backend contracts, and verify both demo and live operation end to end.

## Scope Completed
- Rebuilt the frontend around a persistent 7-screen console shell:
  - Stage 1 knowledge graph
  - Stage 2 population sampling / agent graph
  - Stage 3 live simulation feed + analytics
  - Stage 4A full report
  - Stage 4B opinions
  - Stage 4C friction map
  - Stage 5 interaction hub
- Added `/api/v2/console/...` routes and service layer for session, knowledge, sampling, simulation, report, and interaction-hub flows.
- Added real Stage 1 uploaded document parsing for PDF, DOCX, and text-like formats.
- Added real Stage 2 document-aware sampling with balanced hybrid allocation over the Nemotron Singapore dataset.
- Added native OASIS event streaming persistence and SSE delivery for Stage 3.
- Added real Stage 5 chat paths backed by Gemini for generation and Zep Cloud for memory/context retrieval.
- Updated demo cache generation so demo mode replays the same contracts used in live mode.

## Verification Evidence
- Backend tests: `19 passed`
- Frontend build: `npm run build` passed
- Playwright: demo and live boot tests passed
- Real live verification:
  - Uploaded document parsed successfully
  - Population preview produced real sampled personas and selection reasons
  - Native OASIS completed a 2-round live run
  - Stage 5 report chat and agent chat both returned successful Gemini-backed responses

## Operator Commands
- Demo boot:
  - `./quick_start.sh --mode demo`
- Live boot:
  - `./quick_start.sh --mode live`
- Refresh demo artifacts before launch:
  - `./quick_start.sh --refresh-demo --mode demo`

## Notes
- Live boot requires the OASIS Python 3.11 sidecar at `backend/.venv311/bin/python`, or `OASIS_PY_BIN` set explicitly.
- Stage 5 live chat requires valid Gemini and Zep Cloud credentials in the environment.
