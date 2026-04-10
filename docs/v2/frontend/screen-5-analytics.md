# Screen 5 — Analytics

> Last updated: 2026-04-09

## Overview

Screen 5 visualizes simulation analytics alongside the narrative report. All metric-aware components respond to a shared metric selector, allowing the user to drill into per-question analytics or view an aggregate across all metrics.

The page is implemented in [`Analytics.tsx`](../../../frontend/src/pages/Analytics.tsx).

---

## 1. Metric Selector (Analytics Filter)

### What It Is

A `<MetricSelector>` dropdown at the top of the page that filters analytics by analysis question. Same shared component as Screen 4 ([`MetricSelector.tsx`](../../../frontend/src/components/MetricSelector.tsx)).

### How It Works

1. On mount, fetches analysis questions from `GET /api/v2/session/{id}/analysis-questions` (see [`console-api.ts`](../../../frontend/src/lib/console-api.ts))
2. Filters out `open-ended` questions — only quantitative questions with a `metric_name` appear
3. Options rendered:
   - **"All (Aggregate)"** → `onChange(null)` — aggregate mode, average across all metrics
   - **Per-metric entries** → `onChange(q.metric_name)` — e.g. `"approval_rate"`, `"engagement_score"`
4. Hidden when only one quantitative question exists

### State Flow — What Responds and What Doesn't

The `selectedMetric` state in `Analytics.tsx` controls which analytics endpoints receive a `metric_name` parameter:

```
MetricSelector.onChange(metricName | null)
    → setSelectedMetric(metricName | null)
        → useEffect triggers refetch of:
            ✅ getAnalyticsPolarization(sessionId, selectedMetric)
            ✅ getAnalyticsOpinionFlow(sessionId, selectedMetric)
            ❌ getAnalyticsInfluence(sessionId)           // no metric param
            ❌ getAnalyticsCascades(sessionId)            // no metric param
        → separate useEffect triggers:
            ✅ getAnalyticsAgentStances(sessionId, selectedMetric)
```

| Component | Responds to MetricSelector? | How |
|:----------|:--------------------------|:----|
| Polarization Index | Yes | Recomputed from `checkpoint_{metric}` or aggregate scores |
| Opinion Flow | Yes | Recomputed from per-metric or aggregate pre/post buckets |
| Demographic Sentiment Map | Yes | Agent stances recalculated, sentiment overrides rebuilt |
| Key Opinion Leaders | No | Influence is engagement-based, metric-agnostic |
| Viral Posts | No | Engagement cascade depth, metric-agnostic |

### Why This Design

Per-metric filtering reveals real disagreement that aggregate scores smooth out. For example, a public policy might have 73% approval overall but only 41% support on a specific sub-question — the aggregate masks genuine opposition pockets. The metric selector lets analysts find these signals.

### Config/Prompt Connection

The available metrics come from the use-case YAML's `analysis_questions`, seeded into session config at creation. Different use cases surface different dropdown options:

- **Public Policy Testing** → `approval_rate` only (1 quantitative question, so selector is hidden)
- **Product & Market Research** → `product_interest`, `nps_score` (2 quantitative questions)
- **Campaign & Content Testing** → `conversion_intent`, `engagement_score`, `credibility_score` (3 quantitative questions)

---

## 2. Data Fetching Architecture

### Parallel Fetch Pattern

On mount and whenever `selectedMetric` changes, all four main analytics endpoints are called in parallel via `Promise.allSettled`:

```typescript
Promise.allSettled([
  getAnalyticsPolarization(sessionId, selectedMetric ?? undefined),
  getAnalyticsOpinionFlow(sessionId, selectedMetric ?? undefined),
  getAnalyticsInfluence(sessionId),
  getAnalyticsCascades(sessionId),
])
```

Results are normalized through four helper functions:
- `normalizePolarizationPayload()` — extracts the round-by-round series array
- `normalizeOpinionFlowPayload()` — restructures the flow matrix for the Sankey diagram
- `normalizeLeadersPayload()` — enriches leader cards with agent names from `agentNamesById` lookup
- `normalizeCascadesPayload()` — formats viral posts with author names from the same lookup

### Agent Stance Overrides (Separate Effect)

A second `useEffect` triggers whenever `selectedMetric` changes:

```typescript
getAnalyticsAgentStances(sessionId, selectedMetric).then((data) => {
  const overrides = new Map();
  for (const stance of data.stances) {
    overrides.set(stance.agent_id,
      stance.score >= 7 ? 'positive' :
      stance.score < 5 ? 'negative' : 'neutral'
    );
  }
  setAgentStanceOverrides(overrides);
});
```

This Map is consumed by the Demographic Sentiment Map component. When rendering each agent cell, it checks `agentStanceOverrides.get(agent.id) ?? agent.sentiment` — the override replaces the default sentiment with the metric-specific stance.

### Caching

Results are cached in `sessionStorage` with key `mckainsey-analytics-{sessionId}`.

### Error Handling

- **Live mode**: if any endpoint fails, shows a warning banner listing the missing data types
- **Demo mode**: falls back to local constants on backend failure so the page remains usable

---

## 3. Sentiment Dynamics

### 3.1 Polarization Index

#### What It Shows

A round-by-round time series chart showing how divided public opinion is. Displays Initial and Final polarization values, with a severity label (low / moderate / high / critical).

#### How Polarization Is Calculated

The exact algorithm is in [`compute_polarization()`](../../../backend/src/mckainsey/services/metrics_service.py#L130):

1. **Collect scores**: For each agent, read `agent[score_field]` (defaults to 5.0 if missing)
2. **Bucket into stances** using the same thresholds everywhere (see [`_stance_from_score()`](../../../backend/src/mckainsey/services/metrics_service.py#L41)):
   - Score >= 7.0 → supporter
   - Score 5.0–6.99 → neutral
   - Score < 5.0 → dissenter
3. **Compute percentages**: `supporter_pct = count(>= 7) / total`, `dissenter_pct = count(< 5) / total`
4. **Apply the polarization formula**:

$$\text{polarization\_index} = 2 \times \min(\text{supporter\_pct}, \text{dissenter\_pct})$$

This produces a value between 0.0 and 1.0:
- **0.0** = complete consensus (all agents on one side)
- **1.0** = perfectly split 50/50 between supporters and dissenters

5. **Classify severity**:
   - < 0.2 → `"low"`
   - 0.2–0.5 → `"moderate"`
   - 0.5–0.8 → `"high"`
   - >= 0.8 → `"critical"`

6. **Return**:
```json
{
  "polarization_index": 0.08,
  "severity": "low",
  "distribution": {
    "supporter_pct": 82.0,
    "neutral_pct": 14.0,
    "dissenter_pct": 4.0
  }
}
```

#### How the Backend Produces the Time Series

In [`ConsoleService.get_analytics_polarization()`](../../../backend/src/mckainsey/services/console_service.py#L1592):

1. Load two sets of agents (one for baseline scores, one for final scores)
2. Load baseline and final checkpoint records from `simulation_checkpoints`
3. **If `metric_name` is provided (per-metric)**:
   - `post_field = "checkpoint_{metric_name}"`, `pre_field = "checkpoint_pre_{metric_name}"`
   - Calls [`_enrich_agents_metric_score()`](../../../backend/src/mckainsey/services/console_service.py#L1664) twice — once for each checkpoint set
   - Each agent gets their specific metric answer parsed via `_extract_metric_score()`
4. **If `metric_name` is null (aggregate)**:
   - `post_field = "agg_post_score"`, `pre_field = "agg_pre_score"`
   - Calls [`_enrich_agents_aggregate_scores()`](../../../backend/src/mckainsey/services/console_service.py#L1687) twice
   - Each agent gets the average of ALL parseable metric scores from their checkpoints
5. Calls `compute_polarization()` on both sets → returns `[{round: "Initial", ...}, {round: "R5", ...}]`

#### Why Per-Metric Matters

Aggregate polarization can be misleadingly low when agents disagree on different dimensions. For example: Agent A scores approval_rate=9 but credibility=3, Agent B scores the opposite. Their averages are both ~6, showing no aggregate polarization — but per-metric polarization reveals deep disagreement.

### 3.2 Opinion Flow

#### What It Shows

A Sankey/alluvial diagram showing how agents moved between stance buckets (supporter → neutral → dissenter) from the initial checkpoint to the final checkpoint.

#### How Opinion Flow Is Calculated

The exact algorithm is in [`compute_opinion_flow()`](../../../backend/src/mckainsey/services/metrics_service.py#L170):

1. **Define bucketing function** (same thresholds): >= 7 → supporter, >= 5 → neutral, < 5 → dissenter
2. **For each agent**, read their pre-score and post-score from the enriched fields
3. **Count initial and final buckets**: `initial = {supporter: N, neutral: N, dissenter: N}`
4. **Count flow transitions**: each (pre_bucket → post_bucket) pair gets a count
5. **Return**:
```json
{
  "initial": {"supporter": 50, "neutral": 0, "dissenter": 0},
  "final": {"supporter": 41, "neutral": 9, "dissenter": 0},
  "flows": [
    {"from": "supporter", "to": "supporter", "count": 41},
    {"from": "supporter", "to": "neutral", "count": 9}
  ]
}
```

#### Backend Data Path

In [`ConsoleService.get_analytics_opinion_flow()`](../../../backend/src/mckainsey/services/console_service.py#L1637):

- Same pattern as polarization: loads baseline + final checkpoints, enriches agents with metric or aggregate scores
- **Per-metric**: Each agent's score is their specific `metric_answers[metric_name]` value from the checkpoint
- **Aggregate**: Each agent's score is the average of all parseable metric answers

---

## 4. Demographic Sentiment Map

### What It Shows

A grouped grid of agent cells, colored by stance (positive = green, neutral = amber, negative = red). Users select a dimension via chips:

- Industry
- Occupation
- Planning area
- Income bracket
- Age
- Gender

### How Sentiment Overrides Work

The demographic map data source depends on the metric selector state:

**When aggregate (null) or no metric selected:**
- Uses default `agent.sentiment` from the simulation data
- No API call to agent-stances

**When a specific metric is selected:**
1. `Analytics.tsx` calls `getAnalyticsAgentStances(sessionId, selectedMetric)` → `GET /api/v2/console/session/{id}/analytics/agent-stances?metric_name=...`
2. Backend: [`ConsoleService.get_agent_stances()`](../../../backend/src/mckainsey/services/console_service.py#L1738) calls `_agents_with_checkpoint_metrics()` to enrich agents with metric-specific scores
3. Returns per-agent: `{agent_id, score, planning_area, age_group, archetype}`
4. Frontend builds an overrides Map:
   - `score >= 7` → `"positive"`
   - `score < 5` → `"negative"`
   - else → `"neutral"`
5. When rendering agent cells: `overrides.get(agent.id) ?? agent.sentiment`

This means the demographic map colors change live when the user switches metrics in the selector.

---

## 5. Key Opinion Leaders

### What It Shows

Leader cards displaying the most influential agents from the simulation:

- Agent name (not raw serial id)
- Stance label (supporter / neutral / dissenter)
- Influence score
- Concise top-viewpoint summary

### How Influence Is Computed

Uses the influence graph from [`build_influence_graph()`](../../../backend/src/mckainsey/services/metrics_service.py) in the backend. The ranking is based on the same composite formula as group chat selection (see Screen 4 section 3, Step 3):

- 40% engagement weight (likes + dislikes on posts)
- 30% comment count weight
- 30% replies received weight

### Why It Doesn't Respond to the Metric Selector

Influence is an engagement-based metric — it measures _who drives discussion_, not _what they believe_. An agent can be highly influential regardless of their stance on any particular metric. Making influence metric-dependent would conflate activity with opinion.

---

## 6. Viral Posts

### What It Shows

Cards for the top posts by engagement cascade depth:

- Author name and stance
- Post title and body content
- Nested comment summaries
- Engagement counts (likes, dislikes, tree_size)

### Why It Doesn't Respond to the Metric Selector

Viral posts are about cascade depth and discussion intensity, not opinion direction. A controversial post that triggers 30 nested comments is a viral moment regardless of which metric the user is examining.

---

## 7. Insight Blocks — Per Use Case

Insight blocks are defined in the use-case YAML and dispatched by [`MetricsService.compute_insight_block()`](../../../backend/src/mckainsey/services/metrics_service.py#L815). Different use cases define different insight block configurations:

### Public Policy Testing
([`config/prompts/public-policy-testing.yaml`](../../../config/prompts/public-policy-testing.yaml))

| Block Type | Title | What It Computes |
|:-----------|:------|:----------------|
| `polarization_index` | Polarization Over Time | Bimodal clustering index per round |
| `opinion_flow` | Opinion Migration | Stance transition matrix (initial → final) |
| `top_influencers` | Key Opinion Leaders | Agents with highest engagement-weighted influence |
| `viral_cascade` | Pivotal Discussion | Thread with largest aggregate opinion shift |
| `segment_heatmap` | Demographic Sentiment Map | Per-demographic breakdown of `approval_rate` |

### Product & Market Research
([`config/prompts/product-market-research.yaml`](../../../config/prompts/product-market-research.yaml))

| Block Type | Title | What It Computes |
|:-----------|:------|:----------------|
| `segment_heatmap` | Best-Fit Segments | Per-demographic breakdown of `product_interest` |
| `top_advocates` | Top Advocates | Agents with highest scores (ideal customer profile) |

### Campaign & Content Testing
([`config/prompts/campaign-content-testing.yaml`](../../../config/prompts/campaign-content-testing.yaml))

| Block Type | Title | What It Computes |
|:-----------|:------|:----------------|
| `segment_heatmap` | Audience Segments | Per-demographic breakdown of `engagement_score` |
| `top_advocates` | Top Advocates | Agents with strongest positive reaction |
| `viral_posts` | Viral Moments | Posts that generated the most discussion |

### Insight Block Dispatcher

The dispatcher in [`compute_insight_block()`](../../../backend/src/mckainsey/services/metrics_service.py#L815) maps `block_type` strings to computation functions:

| `block_type` | Dispatches To | Notes |
|:------------|:-------------|:------|
| `polarization_index` | `compute_polarization()` | Same function as the analytics endpoint |
| `opinion_flow` | `compute_opinion_flow()` | Same function as the analytics endpoint |
| `top_influencers` | `compute_influence()` | Builds full influence graph |
| `viral_cascade` | `compute_top_cascade()` | Finds thread with largest opinion delta |
| `segment_heatmap` | `compute_segment_heatmap()` | Groups agents by demographic key |
| `reaction_spectrum` | `compute_segment_heatmap()` | Alias — same as segment_heatmap |
| `pain_points` | `extract_pain_points()` | Keyword frequency from negative-stance posts |
| `top_advocates` | `get_top_advocates()` | Highest-scoring agents with viewpoint summaries |
| `top_objections` | `extract_top_objections()` | Content from lowest-scoring agents |
| `viral_posts` | Same as viral_cascade | Top posts by engagement |

Each block receives the full `agents`, `interactions`, and `analysis_questions` lists. Block configs can also pass `metric_ref` (which metric to focus on) and `count` (how many items to return).

### Why Use Cases Have Different Blocks

The rationale is that different research contexts need different analytical emphasis:

- **Policy testing** needs polarization (is the public divided?) and opinion migration (did minds change?)
- **Product research** needs segment analysis (who is the ideal customer?) and advocates (who are the champions?)
- **Campaign testing** needs engagement analysis (what content went viral?) and audience segments (who responded?)

These blocks appear both in the Screen 4 report (as insight block sections) and inform the analytics on Screen 5.

---

## 8. Score Parsing Deep Dive

All metric-aware analytics on Screen 5 depend on parsing free-text LLM checkpoint answers into numeric scores. This happens in [`_extract_metric_score()`](../../../backend/src/mckainsey/services/console_service.py#L1811):

| Agent's Raw `metric_answers` Value | Parsed Score | Explanation |
|:-----------------------------------|:------------|:------------|
| `"7/10. I think this is good"` | 7.0 | Regex extracts first number before `/10` |
| `"Yes"` | 10.0 | Case-insensitive yes → maximum approval |
| `"No"` | 1.0 | Case-insensitive no → maximum disapproval |
| `"8.5"` | 8.5 | Direct float parse |
| `"I support this policy because..."` | `None` | No number found, skipped in all analytics |
| `""` or `null` | `None` | Empty, skipped |

Agents with unparseable scores are excluded from polarization, opinion flow, and stance computations. They do not default to 5.0 — they are simply absent from the calculation.

### Checkpoint Data Shape

Scores come from `simulation_checkpoints` table records:

```json
{
  "agent_id": "agent-42",
  "checkpoint_kind": "final",
  "stance_json": {
    "metric_answers": {
      "approval_rate": "7/10. I think this is a good start but needs refinement.",
      "policy_viewpoints": "I support the housing subsidy aspect but worry about..."
    }
  }
}
```

The loading function [`_load_checkpoint_records()`](../../../backend/src/mckainsey/services/console_service.py#L1837) tries `checkpoint_kind="post"` first, then falls back to `"final"` (and vice versa) — these are interchangeable aliases from different simulation versions.

---

## 9. API Reference

| Endpoint | Method | Query Params | Responds to Metric Selector | Response Model |
|:---------|:-------|:-------------|:---------------------------|:---------------|
| `/api/v2/console/session/{id}/analytics/polarization` | GET | `metric_name?` | Yes | `V2PolarizationResponse` |
| `/api/v2/console/session/{id}/analytics/opinion-flow` | GET | `metric_name?` | Yes | `V2OpinionFlowResponse` |
| `/api/v2/console/session/{id}/analytics/agent-stances` | GET | `metric_name?` | Yes | `dict[str, object]` |
| `/api/v2/console/session/{id}/analytics/influence` | GET | — | No | `dict[str, object]` |
| `/api/v2/console/session/{id}/analytics/cascades` | GET | — | No | `dict[str, object]` |

All endpoints are prefixed with the base URL and check for demo sessions first (serve cached demo data if available). On error, return 503 with detail.

---

## 10. Runtime Behavior

### Live Mode

- Consumes analytics endpoints directly
- Shows warning/empty states when analytics are incomplete or sparse
- Does NOT silently fall back to fake local analytics

### Demo Mode

- Local constants are allowed so the page remains usable without a backend
- Falls back to demo data on backend failure

### Edge Cases

- **Polarization of 0.0** is legitimate when all agents score similarly on a given metric (perfect consensus)
- **Empty opinion flow** occurs when no agents have parseable checkpoint scores
- **Sparse analytics** happens when the simulation produced too little structured signal — this is a simulation-quality issue, not an analytics bug
- **Repeated near-identical agent comments** are a simulation-quality issue, not an analytics-UI problem

---

## 11. Key Code References

| Component | File | Key Lines |
|:----------|:-----|:----------|
| Analytics page | [`frontend/src/pages/Analytics.tsx`](../../../frontend/src/pages/Analytics.tsx) | State, Promise.allSettled, stance overrides |
| MetricSelector component | [`frontend/src/components/MetricSelector.tsx`](../../../frontend/src/components/MetricSelector.tsx) | Filters open-ended, onChange → null or metric_name |
| Frontend API client | [`frontend/src/lib/console-api.ts`](../../../frontend/src/lib/console-api.ts) | `getAnalyticsPolarization`, `getAnalyticsAgentStances`, etc. |
| Analytics route definitions | [`backend/src/mckainsey/api/routes_analytics.py`](../../../backend/src/mckainsey/api/routes_analytics.py) | All 5 GET endpoints |
| Polarization computation | [`backend/src/mckainsey/services/metrics_service.py`](../../../backend/src/mckainsey/services/metrics_service.py) | `compute_polarization()` L130, `_stance_from_score()` L41 |
| Opinion flow computation | [`backend/src/mckainsey/services/metrics_service.py`](../../../backend/src/mckainsey/services/metrics_service.py) | `compute_opinion_flow()` L170 |
| Insight block dispatcher | [`backend/src/mckainsey/services/metrics_service.py`](../../../backend/src/mckainsey/services/metrics_service.py) | `compute_insight_block()` L815 |
| Polarization orchestration | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `get_analytics_polarization()` L1592 |
| Opinion flow orchestration | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `get_analytics_opinion_flow()` L1637 |
| Agent stances | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `get_agent_stances()` L1738 |
| Score parsing | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `_extract_metric_score()` L1811 |
| Checkpoint loading | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `_load_checkpoint_records()` L1837 |
| Agent enrichment (per-metric) | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `_enrich_agents_metric_score()` L1664 |
| Agent enrichment (aggregate) | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `_enrich_agents_aggregate_scores()` L1687 |
| Use-case YAML configs | [`config/prompts/`](../../../config/prompts/) | `insight_blocks`, `analysis_questions` per use case |
