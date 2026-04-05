# Screen 3 — Simulation

> **Paper MCP Reference**: Artboard `9U-0` ("Screen 3 — Simulation (V2)")
> **UserInput Refs**: E1–E8, A3, A5

## Overview

Two-panel layout. Left: simulation header, config card (rounds + controversy boost), and live post feed. Right: dynamic use-case-specific metrics, activity counters, hottest thread, and elapsed time.

## Layout

```
┌───────────────── 1440px ──────────────────┐
│  ┌──── flex: 1.4 ────┐  ┌── 340px ─────┐ │
│  │  Header + Button  │  │ Metrics      │ │
│  │  Config Card      │  │ Activity     │ │
│  │  Live Feed        │  │ Hot Thread   │ │
│  │  (scrollable)     │  │ Time         │ │
│  └───────────────────┘  └──────────────┘ │
└───────────────────────────────────────────┘
```

## Left Panel

### 1. Header Row
- Title: "Live Social Simulation"
- Subtitle: "Real-time Reddit discourse from native OASIS engine"
- **"Generate Report →"** button (green outline) — navigates to Screen 4 after simulation completes

### 2. Config Card (`SimulationConfig.tsx`)

Two sections side by side, separated by a vertical divider:

**Simulation Rounds** (left):
- Horizontal progress bar (orange fill) — replaces V1's vertical progress display
- Large number display showing current value (e.g., "5")
- Helper: "~4m 12s | 250 agents × 5 rounds"
- Slider range: 1-10
- **Progress display during simulation**: Shows "Round 3 (62%)" where percentage = (current_batch / total_batches_in_round) × 100. This replaces the confusing batch event streaming display from V1.

**Controversy Boost** (right):
- Red-accented slider: 0.0 to 1.0, step 0.1
- Current value: "0.3" in red
- **Tooltip icon (?)**: On hover, shows: *"Controversy Amplification: Controls how much the recommendation system boosts posts with high engagement regardless of whether they're liked or disliked. At 0, only universally liked posts rise. At 1.0, posts with equal likes and dislikes are treated as highly engaging. This models how real social media platforms use ragebait to amplify controversy and boost user retention. Higher values create more polarized feeds."*
- Helper text: "Models social media ragebait amplification"

### 3. Feed Card (`LiveFeed.tsx`)

**Feed Header**:
- "Topic Community" with round badge: "3/5" (current/total)
- Sort tabs: "New" (active, dark bg) | "Popular"

**Post Component** (`SimulationPost.tsx`):
Each post shows:
- **Avatar circle**: Colored by stance (green=supporter, purple=neutral, red=dissenter, etc.)
  - Shows initials (e.g., "TL")
- **Agent info**: Name, occupation, age, round posted (e.g., "Teacher, 42 · R3")
- **Occupation tag**: Small pill (e.g., "Teacher")
- **Post title**: Bold, white text
- **Post body**: Muted text, 2-3 lines
- **Engagement row**:
  - ▲ {likes} (upvote count)
  - ▼ {dislikes} (downvote count) — **NEW in V2 (E4)**
  - 💬 {comments} (comment count with likes/dislikes per comment)

**Comment display** (expandable under each post):
- Top-level comments only (no nested replies — Decision 3.7)
- Each comment shows: avatar + name + text + ▲/▼ counts

### 4. Viewport Fix (E3)
- Screen 3 must fit within `100vh` without requiring browser zoom
- Use `max-height: 100vh` on the main container
- Feed area scrolls internally: `overflow-y: auto`
- Right panel scrolls independently

## Right Panel

### 1. Dynamic Metrics Card (`DynamicMetrics.tsx`)

Header: `{USE_CASE_NAME} METRICS` in orange uppercase

Shows 2 metric cards side by side, content driven by use case:

| Use Case | Metric 1 | Metric 2 |
|:---------|:---------|:---------|
| Policy Review | Approval Rate (%) | Net Sentiment (1-10) |
| Ad Testing | Estimated Conversion (%) | Engagement Score |
| PMF Discovery | Product Interest (%) | Target Fit Score |
| Customer Review | Satisfaction (1-10) | Recommendation (%) |

Each metric card has:
- Label + **ⓘ tooltip** icon (explains the heuristic)
- Large number value (JetBrains Mono, colored by valence)
- Updates in real-time after each checkpoint round

**Tooltip content example** (Approval Rate):
> "Percentage of agents who rated the policy ≥ 7 out of 10 during the checkpoint interview. Agents answer: 'Do you approve of this policy? Rate 1-10.' Scores ≥ 7 count as approval."

### 2. Activity Counters
2x2 grid: Posts, Comments, Reactions, Authors
- Each shows count in JetBrains Mono, white, large

### 3. Hottest Thread
- Orange border highlight
- Shows title of most-engaged post
- Engagement badge: "29 engagement" (total likes + dislikes + comments)

### 4. Time Card
- "TIME ELAPSED" header in cyan
- Large timer: "2m 47s" (JetBrains Mono)
- Green dot + "Simulation in progress..."
- Changes to "Simulation complete" with checkmark when done

## Backend Requirements

### Modified: `simulation_service.py`
- Accept `controversy_boost` parameter (float 0.0-1.0) from simulation request
- Pass through to OASIS runner's `calculate_hot_score`

### Modified: `oasis_reddit_runner.py`
- Thread `controversy_boost` into `rec_sys_reddit` → `calculate_hot_score`

### Modified: OASIS `recsys.py`
See [docs/v2/backend/controversy-boost.md](../backend/controversy-boost.md) for exact code changes.

### New: Checkpoint interview prompts
- Loaded from `config/prompts/{use_case}.yaml → checkpoint_questions`
- Each question has: `question`, `type` (scale/yes-no), `metric_name`
- Agent name verification piggybacks on checkpoint: "Please confirm your name at the start of your response."

### API Changes
- `POST /api/v2/console/session/{id}/simulate` — now accepts `{rounds, controversy_boost}`
- `GET /api/v2/console/session/{id}/simulation/metrics` — returns real-time aggregated metrics
- SSE stream for batch progress: `{round, batch, total_batches, percentage}`

### Tests

**Frontend**:
- [ ] Config card displays rounds slider and controversy slider
- [ ] Controversy tooltip renders on hover/click
- [ ] Feed shows posts with dislikes column
- [ ] Progress shows "Round X (Y%)" during simulation
- [ ] Dynamic metrics update after each checkpoint
- [ ] Metric tooltips explain heuristics correctly
- [ ] Page fits 100vh without zoom
- [ ] Feed scrolls independently from right panel

**Backend**:
- [ ] `controversy_boost=0.0` produces identical scores to original algorithm
- [ ] `controversy_boost=1.0` correctly boosts controversial posts
- [ ] Checkpoint interview extracts numeric scores
- [ ] Name verification parses confirmed names
- [ ] Metrics aggregation computes correctly
