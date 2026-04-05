# McKAInsey V2 — Architecture

> Living document. Updated as implementation progresses.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User's Machine                            │
│                                                                   │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────────┐ │
│  │ Browser      │───▶│  Frontend     │    │   External LLM APIs  │ │
│  │ localhost:   │    │  (Vite/React) │    │   ┌────────────────┐ │ │
│  │    5173      │◀───│  Port 5173    │    │   │ Gemini API     │ │ │
│  └─────────────┘    └──────┬───────┘    │   │ OpenAI API     │ │ │
│                            │             │   │ Ollama (local) │ │ │
│                            │ HTTP        │   └───────┬────────┘ │ │
│                            ▼             │           │           │ │
│  ┌──────────────────────────────────┐   │           │           │ │
│  │         Backend (FastAPI)         │───┼───────────┘           │ │
│  │         Port 8000                 │   │                       │ │
│  │                                    │   │                       │ │
│  │  ┌────────────┐ ┌──────────────┐  │   │                       │ │
│  │  │ Config     │ │ Simulation   │  │   │                       │ │
│  │  │ Service    │ │ Service      │──┼───┤                       │ │
│  │  └────────────┘ └──────┬───────┘  │   │                       │ │
│  │  ┌────────────┐        │          │   │                       │ │
│  │  │ Metrics    │        │ gRPC/    │   │                       │ │
│  │  │ Service    │        │ HTTP     │   │                       │ │
│  │  └────────────┘        ▼          │   │                       │ │
│  │  ┌────────────┐ ┌──────────────┐  │   │                       │ │
│  │  │ Report     │ │ OASIS        │  │   │                       │ │
│  │  │ Service    │ │ Sidecar      │──┼───┘                       │ │
│  │  └────────────┘ │ (Py 3.11)   │  │                           │ │
│  │  ┌────────────┐ │ Port 8001   │  │                           │ │
│  │  │ Graphiti   │ └──────────────┘  │                           │ │
│  │  │ Service    │                    │                           │ │
│  │  └─────┬──────┘ ┌──────────────┐  │                           │ │
│  │        │        │ Token        │  │                           │ │
│  │        │        │ Tracker      │  │                           │ │
│  │        │        └──────────────┘  │                           │ │
│  └────────┼──────────────────────────┘                           │ │
│           │                                                       │ │
│           ▼                                                       │ │
│  ┌──────────────┐   ┌──────────────────┐                         │ │
│  │  FalkorDB    │   │  Local Data      │                         │ │
│  │  (Graph DB)  │   │  ├─ Parquet      │                         │ │
│  │  Port 6379   │   │  ├─ SQLite       │                         │ │
│  │  Vol: data/  │   │  ├─ YAML config  │                         │ │
│  └──────────────┘   │  └─ DOCX export  │                         │ │
│                      └──────────────────┘                         │ │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow (5-Stage Pipeline)

```
Screen 0          Screen 1           Screen 2          Screen 3          Screen 4/5
Onboarding    →   Knowledge Graph →  Population    →   Simulation    →   Report + Chat
                                      Sampling                           Analytics

Config:           Documents:         Filters:          OASIS Engine:     ReportAgent:
- Country         - PDF/DOCX/URL     - Dynamic from    - Controversy     - Plan-first
- Provider        - LightRAG         Parquet schema    boost             - Evidence-linked
- Model           extraction         - Country-        - Checkpoints     - Group chat
- Use case        - Multi-file       specific          - Metrics         - DOCX export
                  merge              - Token cost      streaming
                                     estimate
```

## Key Service Responsibilities

| Service | File | Responsibility |
|:--------|:-----|:---------------|
| **ConfigService** | `config_service.py` | Load YAML configs for countries, prompts, use cases |
| **SimulationService** | `simulation_service.py` | Orchestrate OASIS runs, checkpoint interviews, controversy boost |
| **MetricsService** | `metrics_service.py` | Compute polarization, influence, cascades, opinion flow |
| **ReportService** | `report_service.py` | Plan-first report generation, evidence linking |
| **GraphitiService** | `graphiti_service.py` | Temporal agent memory via FalkorDB |
| **TokenTracker** | `token_tracker.py` | Count tokens, estimate cost, track caching savings |
| **CachingLLMClient** | `caching_llm_client.py` | Gemini context caching wrapper |
| **DemoService** | `demo_service.py` | Serve pre-cached data for demo mode |

## Technology Stack

| Layer | Technology | Version | Purpose |
|:------|:-----------|:--------|:--------|
| Frontend | React + TypeScript | 18.x | UI |
| Build | Vite | 5.x | Dev server + bundler |
| Backend | FastAPI | 0.100+ | REST API + SSE |
| Simulation | OASIS | Latest | Multi-agent social sim |
| Graph DB | FalkorDB | Latest | Agent memory (Graphiti) |
| Memory Engine | Graphiti | Latest | Temporal knowledge graph |
| Doc Processing | LightRAG | Latest | Knowledge extraction |
| LLM Providers | Gemini, OpenAI, Ollama | Various | Agent reasoning |
| Export | python-docx | 1.x | DOCX report generation |
| Container | Docker + Compose | 24.x | Local orchestration |

## State Management

- **Frontend**: React Context (`SessionContext`) holds `session_id`, `config`, navigation state
- **Backend**: Per-session state containers keyed by `session_id`
- **Database**: SQLite per simulation (`data/sim_{session_id}.db`)
- **Graph**: FalkorDB with `group_id = session_{session_id}` scoping
- **Config**: Read-only YAML files loaded once per session

## Security Notes

- API keys stored in `.env` (gitignored), injected via Docker env
- No authentication in local mode (single-user)
- Session IDs are UUIDs, not sequential
- All file uploads validated by extension and MIME type
