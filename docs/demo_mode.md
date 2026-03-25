# Demo Mode Implementation

## Overview

The McKAInsey platform now supports a fully cached demo mode that operates without making any Gemini API calls. This allows users to experience the full 7-screen workflow with pre-generated data.

## How It Works

### Demo Cache Files

The demo mode uses cached data stored in:
- `backend/data/demo-output.json` - Backend cache
- `frontend/public/demo-output.json` - Frontend cache

These files contain pre-generated data for all screens:
- **Screen 1**: Knowledge Graph (75 entities from FY2026 Budget Statement)
- **Screen 2**: 250 agents from Nemotron dataset
- **Screen 3**: 6 rounds of simulation with 1496 interactions
- **Screen 4**: Analysis report with friction maps and insights
- **Screen 5**: Interaction hub with agent chat

### Demo Service

The `DemoService` class (`backend/src/mckainsey/services/demo_service.py`) provides:
- Cached data retrieval for all screens
- Demo chat responses (no API calls)
- Session management for demo mode

### Mode Detection

The system detects demo mode by:
1. Checking the session mode in the database
2. Verifying demo cache files exist
3. Serving cached data instead of making API calls

## Usage

### Starting Demo Mode

```bash
./quick_start.sh --mode demo
```

Or with the shorthand:

```bash
./quick_start.sh
```

### Starting Live Mode

```bash
./quick_start.sh --mode live
```

Live mode will:
- Use real Gemini API for knowledge extraction
- Sample agents from Nemotron dataset in real-time
- Run actual OASIS simulation (if `--real-oasis` flag is set)
- Generate reports using Gemini

### Regenerating Demo Cache

If you need to regenerate the demo cache with fresh data:

```bash
# From existing snapshot
python backend/scripts/prepare_demo_cache.py

# Or generate completely new (requires API keys)
python backend/scripts/generate_comprehensive_demo_cache.py --force
```

## Architecture

### Data Flow

```
User Request
    ↓
Routes Console (routes_console.py)
    ↓
Check: Is demo session? → Yes → DemoService
    ↓ No
ConsoleService (live mode with API calls)
```

### Key Components

1. **DemoService** (`demo_service.py`)
   - Loads and serves cached data
   - Provides demo chat responses
   - Manages demo session state

2. **ConsoleService** (`console_service.py`)
   - Checks if session is in demo mode
   - Routes to DemoService when appropriate
   - Falls back to live mode for non-demo sessions

3. **Routes Console** (`routes_console.py`)
   - API endpoints check demo mode before processing
   - Returns cached data for demo sessions

## Demo Data Details

### Screen 1: Knowledge Graph
- Source: `Sample_Inputs/fy2026_budget_statement.md`
- Entities: 75 nodes
- Relationships: Extracted from budget document
- Topics: Cost-of-living support, SkillsFuture, CPF, transport subsidies

### Screen 2: Population Sampling
- Agents: 250 personas from Nemotron dataset
- Coverage: Multiple planning areas, age groups, occupations
- Mode: Population baseline sampling

### Screen 3: Simulation
- Platform: Reddit-style deliberation
- Rounds: 6
- Interactions: 1496 (posts, comments, reactions)
- Approval shift: 97.6% → 0.0% (demo scenario)

### Screen 4: Report
- Executive summary
- Friction map by planning area
- Influential agents
- Demographic breakdown
- Sample recommendations

### Screen 5: Interaction Hub
- Report agent chat (demo responses)
- Agent chat with 250 agents
- Pre-loaded influential agents

## API Endpoints in Demo Mode

All console API endpoints support demo mode:

| Endpoint | Demo Behavior |
|----------|---------------|
| `POST /session` | Creates demo session with cached data |
| `POST /knowledge/upload` | Returns cached knowledge graph |
| `POST /sampling/preview` | Returns cached 250 agents |
| `POST /simulation/start` | Returns completed simulation state |
| `GET /simulation/state` | Returns cached state |
| `GET /report/full` | Returns cached report |
| `POST /report/generate` | Returns cached report |
| `POST /interaction-hub/report-chat` | Returns demo response |
| `POST /interaction-hub/agent-chat` | Returns demo response |

## Zep Cloud Integration

The demo cache includes metadata indicating Zep Cloud is enabled. However, actual Zep Cloud storage is not required for demo mode - the data is served from local cache files.

When running in live mode with Zep Cloud configured:
- Agent interactions are synced to Zep Cloud
- Memory search uses Zep Cloud episodes
- Agent chat retrieves context from Zep

## Testing

### Verify Demo Mode

```bash
# Start in demo mode
./quick_start.sh --mode demo

# Check demo cache is loaded
curl http://localhost:8000/api/v2/console/session/demo-session-fy2026-budget/simulation/state
```

### Verify Live Mode

```bash
# Start in live mode
./quick_start.sh --mode live

# Create new session (will use real APIs)
curl -X POST http://localhost:8000/api/v2/console/session \
  -H "Content-Type: application/json" \
  -d '{"mode": "live"}'
```

## Troubleshooting

### Demo cache not found

If you see "Demo cache not available":
```bash
# Regenerate demo cache
python backend/scripts/prepare_demo_cache.py
```

### Session not in demo mode

Check the session mode in the database:
```sql
SELECT session_id, mode, status FROM console_sessions;
```

### API calls still happening in demo mode

Verify:
1. Session was created with `mode: "demo"`
2. Demo cache files exist
3. DemoService is being invoked (check logs)

## Future Enhancements

1. **Multiple Demo Scenarios**: Support for different policy documents
2. **Configurable Agent Count**: Demo with 50/100/500 agents
3. **Interactive Demo Chat**: More sophisticated demo responses
4. **Demo Mode Indicator**: Visual indicator in UI when in demo mode
