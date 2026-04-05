# Screen 5 — Analytics (Simulation Visualizations)

> **Paper MCP Reference**: Artboard `K5-0` ("Report Metrics Visualizations")
> **UserInput Refs**: F3
> **Decision**: Separate dedicated screen for deep analytics — not embedded in the report

## Overview

A full-width analytics dashboard showing four advanced visualization components. Accessible after simulation completes, via sidebar navigation or a link from the Report screen.

This screen focuses on the **simulation dynamics** — showing the most influential posts, opinion shifts, and network effects that drove the outcome. It answers: *"What happened during the simulation and why?"*

## Layout

```
┌────────────────────── 1440px ──────────────────────┐
│  Header: "Simulation Analytics"                     │
│  Subtitle: "{Country} · {Use Case} · {n} agents"   │
├──────────── 50% ──────────┬──────── 50% ───────────┤
│  Polarization Index       │  Opinion Flow (Sankey)  │
│  over Time                │                         │
├───────────────────────────┼─────────────────────────┤
│  Influence Centrality     │  Viral Cascade          │
│  Network Graph            │  Analysis               │
└───────────────────────────┴─────────────────────────┘
```

## Visualization 1: Polarization Index over Time

### Component: `PolarizationChart.tsx`

**What it shows**: How polarized the population became over each simulation round.

**Chart type**: Vertical bar chart with one bar per round (R1–R5).

**Data source**: `GET /api/v2/console/session/{id}/analytics/polarization`

**Response**:
```json
{
  "rounds": [
    {"round": 1, "polarization_index": 0.12, "severity": "low"},
    {"round": 2, "polarization_index": 0.28, "severity": "moderate"},
    {"round": 3, "polarization_index": 0.45, "severity": "moderate"},
    {"round": 4, "polarization_index": 0.67, "severity": "high"},
    {"round": 5, "polarization_index": 0.82, "severity": "high"}
  ]
}
```

**Visual details**:
- Bars color-coded by severity: green (low) → amber (moderate) → orange → red/purple (high)
- Y-axis: 0.0 to 1.0 (polarization index)
- Trend line overlay: white dots connected by lines showing the trend
- Top-right badge: "Highly Polarized" (red) or "Low Polarization" (green)
- Tooltip text explaining the metric: *"Bimodal distribution coefficient of agent opinions. Higher values indicate the population has split into distinct opposing camps."*

**Backend computation** (`metrics_service.py`):
```python
def compute_polarization(agents, group_key="planning_area"):
    """Between-group variance / total variance."""
    groups = defaultdict(list)
    all_scores = []
    for a in agents:
        key = str(a.get("persona", {}).get(group_key, "Unknown"))
        score = float(a.get("opinion_post", 0.0))
        groups[key].append(score)
        all_scores.append(score)
    overall_mean = mean(all_scores)
    n = max(1, len(all_scores))
    between = sum(len(v) * ((mean(v) - overall_mean) ** 2) for v in groups.values()) / n
    total_var = sum((s - overall_mean) ** 2 for s in all_scores) / n
    return (between / total_var) if total_var > 0 else 0.0
```

## Visualization 2: Opinion Flow (Sankey Diagram)

### Component: `OpinionFlowSankey.tsx`

**What it shows**: How agents migrated between stances (Supporter → Neutral → Dissenter) from initial to final checkpoint.

**Chart type**: Horizontal Sankey-style diagram with left (Initial) and right (Final) bars.

**Data source**: `GET /api/v2/console/session/{id}/analytics/opinion-flow`

**Response**:
```json
{
  "initial": {"supporter": 162, "neutral": 38, "dissenter": 50},
  "final": {"supporter": 85, "neutral": 12, "dissenter": 153},
  "flows": [
    {"from": "supporter", "to": "supporter", "count": 80},
    {"from": "supporter", "to": "dissenter", "count": 72},
    {"from": "supporter", "to": "neutral", "count": 10},
    {"from": "neutral", "to": "dissenter", "count": 30},
    {"from": "neutral", "to": "supporter", "count": 5},
    {"from": "neutral", "to": "neutral", "count": 3},
    {"from": "dissenter", "to": "dissenter", "count": 48},
    {"from": "dissenter", "to": "supporter", "count": 2}
  ]
}
```

**Visual details**:
- Left bar: Stacked segments (green=Supporter, gray=Neutral, red=Dissenter) with percentage labels
- Right bar: Same, showing final distribution
- Flow paths: Gradient-colored bands connecting source to target segments
- Width of each band proportional to count
- Library suggestion: Use D3.js Sankey plugin or `react-flow` for the paths

## Visualization 3: Influence Centrality Graph

### Component: `InfluenceCentralityGraph.tsx`

**What it shows**: A network graph of the most influential agents and their connections. Node size indicates influence score; color indicates stance.

**Data source**: `GET /api/v2/console/session/{id}/analytics/influence`

**Response**:
```json
{
  "nodes": [
    {"id": "agent_42", "name": "Raj Kumar", "initials": "RK", "stance": "dissenter", "influence_score": 0.92},
    {"id": "agent_15", "name": "Janet Lee", "initials": "JL", "stance": "supporter", "influence_score": 0.78},
    ...
  ],
  "edges": [
    {"source": "agent_42", "target": "agent_15", "weight": 0.6},
    ...
  ],
  "top_influencers": ["agent_42", "agent_15", ...]
}
```

**Visual details**:
- Force-directed graph (D3 or react-force-graph)
- Node size: Proportional to influence score (larger = more influential)
- Node color: Green (supporter), Red (dissenter), Gray (neutral)
- Node labels: Agent initials inside circle
- Edges: Thin lines showing interaction connections (opacity = weight)
- Top-right badge: "Top 5% Influential" in orange
- Bottom-left legend: Color-coded by stance
- Top influencer nodes have a glow/shadow effect

**Backend computation**:
```python
def compute_influence(interactions):
    """Weighted out-degree influence scoring."""
    edges = {}
    for ev in interactions:
        a, t = ev.get("actor_agent_id"), ev.get("target_agent_id")
        if not a or not t: continue
        w = abs(float(ev.get("delta", 0.0)) or 0.0)
        edges[(a, t)] = edges.get((a, t), 0.0) + w
    node_scores = {}
    for (a, t), w in edges.items():
        node_scores[a] = node_scores.get(a, 0.0) + w
    return sorted(node_scores.items(), key=lambda x: x[1], reverse=True)[:10]
```

## Visualization 4: Viral Cascade Analysis

### Component: `CascadeTree.tsx`

**What it shows**: The comment thread that caused the biggest opinion shift among agents. Displayed as a vertical tree with connecting lines.

**Data source**: `GET /api/v2/console/session/{id}/analytics/cascades`

**Response**:
```json
{
  "top_cascade": {
    "root_post_id": "post_123",
    "root_author": {"name": "Raj Kumar", "initials": "RK", "stance": "dissenter"},
    "root_content": "Innovation hubs only benefit top earners and drive up local rent.",
    "root_engagement": {"likes": 142, "dislikes": 28, "comments": 28},
    "approval_shift": -0.42,
    "children": [
      {
        "author": {"name": "Tan Li Wei", "initials": "TL", "stance": "dissenter"},
        "content": "Exactly. Being a teacher, I see families moving out because of this gentrification.",
        "engagement": {"likes": 86, "dislikes": 5}
      },
      {
        "author": {"name": "Mary Santos", "initials": "MS", "stance": "shifted"},
        "content": "I was supportive initially, but this makes me reconsider the real-world impact.",
        "engagement": {"likes": 41, "dislikes": 3},
        "shift_label": "Shifted from Supporter"
      }
    ]
  }
}
```

**Visual details**:
- Root post: Prominent card with avatar, content, engagement counts
- Children: Indented cards connected by vertical/horizontal lines
- Shifted agents: Highlighted with purple label "Shifted from Supporter"
- Top-right badge: "-42% Approval Shift" in purple
- Engagement numbers colored by stance (red for dissenter upvotes)
- Vertical connecting line from root to children

## Backend Requirements

### New: `metrics_service.py`

Contains all computation functions:
- `compute_polarization(agents, group_key)` → per-round index
- `compute_influence(interactions)` → nodes + edges + top influencers
- `compute_cascades(interactions, posts)` → top cascade tree
- `compute_opinion_flow(agents)` → initial/final distribution + flows

### New API Endpoints

```
GET /api/v2/console/session/{id}/analytics/polarization
GET /api/v2/console/session/{id}/analytics/opinion-flow
GET /api/v2/console/session/{id}/analytics/influence
GET /api/v2/console/session/{id}/analytics/cascades
```

### Tests

**Frontend**:
- [ ] All 4 charts render with mock data
- [ ] Polarization bars are color-coded correctly
- [ ] Sankey flow widths are proportional to counts
- [ ] Influence graph nodes are draggable
- [ ] Cascade tree shows correct nesting and connector lines
- [ ] Tooltips explain each metric

**Backend**:
- [ ] Polarization index is 0 for uniform opinions and 1 for perfectly split
- [ ] Influence scores sum correctly across interactions
- [ ] Cascade analysis finds the thread with most opinion shift
- [ ] Opinion flow totals match input/output agent counts
