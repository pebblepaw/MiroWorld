# McKAInsey Frontend

Phase E React dashboard for the stage-driven simulation workflow.

## Features

- Workflow sidebar for stages 1-5
- Scenario submission controls (agent count, rounds, policy summary)
- Opinion-shift chart and friction chart (ECharts)
- ReportAgent chat prompt panel
- Context panel with simulation summary stats

## Run

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## Build

```bash
npm run build
```

## API Base URL

Set `VITE_API_BASE` in environment if backend is not at `http://localhost:8000`.
