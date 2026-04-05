# McKAInsey Frontend (V2 Workstream)

React + Vite frontend for the McKAInsey simulation console.

## Run

1. `npm install`
2. `npm run dev`
3. Open `http://127.0.0.1:5173`

Build check:

1. `npm run build`

## Screen Map (Current)

1. Screen 0: Onboarding modal in `src/components/OnboardingModal.tsx`
2. Screen 1: Knowledge graph / upload in `src/pages/PolicyUpload.tsx`
3. Screen 2: Population sampling in `src/pages/AgentConfig.tsx`
4. Screen 3: Live simulation in `src/pages/Simulation.tsx`
5. Screen 4: Report + Chat in `src/pages/ReportChat.tsx`
6. Screen 5: Analytics in `src/pages/Analytics.tsx`

App shell and routing by step index is in `src/App.tsx` and shared state is in `src/contexts/AppContext.tsx`.

## Implemented Frontend Highlights

1. Onboarding configuration modal with country/provider/model/use-case selections and settings re-open.
2. Multi-input knowledge ingestion UI (file upload, URL input shell, paste text shell), guiding prompt editing, force graph rendering.
3. Sampling dashboard with cohort explorer waffle groups, map panel, and representativeness stats.
4. Simulation feed with round control, controversy toggle, activity stream, hottest-thread and metrics side panels.
5. Unified report + chat screen with report/chat mode toggle, segmented group chat, and agent profile drawer.
6. Analytics screen with:
	- Sentiment Dynamics (polarization chart + opinion flow)
	- Demographic Sentiment Map (chunked waffle groups)
	- KOL + Viral Posts sections

## UI Standardization Baseline (Current)

1. Proceed/step-advance CTA style is standardized to success treatment (`bg-success/20`, `border-success/30`, `text-success`) across screens.
2. Demographic waffle groups on Screen 5 use the same chunked wrapping pattern as Screen 2; only color logic differs by sentiment.
3. Screen 3 right rail density has been tightened (notably the Time Elapsed card and row heights) to reduce empty space.
4. Core semantic color roles:
	- Success/proceed: green
	- Destructive/risk: red
	- Informational/action emphasis: blue
	- Neutral scaffolding: grayscale tokens from `src/index.css`

## Backend Linking Status

The frontend intentionally supports demo/fallback behavior while backend APIs are still being linked and validated.

Pending backend connection and verification are tracked in:

1. `docs/v2/frontend/screen-0-onboarding.md`
2. `docs/v2/frontend/screen-1-knowledge-graph.md`
3. `docs/v2/frontend/screen-2-population-sampling.md`
4. `docs/v2/frontend/screen-3-simulation.md`
5. `docs/v2/frontend/screen-4-report-chat.md`
6. `docs/v2/frontend/screen-5-analytics.md`

No feature checklists are marked complete yet; completion is deferred until backend integration and end-to-end validation are finished.
