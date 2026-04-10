# Backend — Metrics & Heuristics

> Last updated: 2026-04-10

## Overview

V2 metrics are driven by two main sources:

1. Checkpoint responses stored in `metric_answers` inside `simulation_checkpoints`
2. OASIS interaction traces (post engagement, replies, comment threads)

No frontend metric card should rely on hardcoded V1 use-case assumptions. Metric generation is driven from `analysis_questions` seeded into the session config.

## 1. Checkpoint Data Shape

### Storage

Checkpoint records live in the `simulation_checkpoints` table with:

| Field | Type | Description |
|:------|:-----|:------------|
| `session_id` | string | Session scope |
| `agent_id` | string | The agent this record belongs to |
| `checkpoint_kind` | string | `"baseline"` or `"final"` (legacy sessions may use `"pre"` / `"post"`) |
| `stance_json` | JSON | Contains `metric_answers` dict |

### `metric_answers` Format

`metric_answers` is a dictionary keyed by `analysis_questions[].metric_name` from the session-scoped config. Example:

```json
{
  "approval_rate": 7.0,
  "conversion_intent": "yes",
  "engagement_score": "8/10 because the message is memorable",
  "policy_viewpoints": "I support the overall direction but want more detail."
}
```

Normalization is handled by `_normalize_metric_answers()` in `simulation_service.py`:

- keys not present in the current checkpoint question set are dropped
- `bool` values are normalized to `"yes"` / `"no"`
- numeric values are stored as floats
- non-empty strings are preserved as text
- invalid or missing `metric_answers` payloads normalize to `{}`

## 2. Score Parsing — `_extract_metric_score()`

`ConsoleService._extract_metric_score()` converts metric answers into numeric 1–10 scores for analytics and stance classification:

| Input Pattern | Output | Example |
|:--------------|:-------|:--------|
| exact `"yes"` | `10.0` | `"yes"` → `10.0` |
| exact `"no"` | `1.0` | `"no"` → `1.0` |
| leading numeric text | first parsed number | `"7/10. Strong start"` → `7.0` |
| direct numeric text | parsed float | `"8.5"` → `8.5` |
| free text without leading number | `None` | `"I think it's good"` → `None` |

Open-ended answers may still exist in checkpoint payloads, but they are excluded from MetricSelector and skipped by numeric scoring unless they begin with a parseable number.

## 3. Stance Thresholds

All stance bucketing throughout the system uses these thresholds (defined in `MetricsService._stance_from_score()`):

| Score Range | Stance |
|:------------|:-------|
| ≥ 7.0 | supporter |
| 5.0 – 6.99 | neutral |
| < 5.0 | dissenter |

## 4. Scoring Modes

### Per-Metric Scoring

When a specific `metric_name` is provided:

- `_agents_with_checkpoint_metrics()` looks up each agent's `metric_answers[metric_name]`, parses it via `_extract_metric_score()`, and writes it to `checkpoint_{metric_name}`
- used by per-metric analytics endpoints, per-metric demographic stances, and per-metric Screen 4 supporter/dissenter selection
- if a session has no checkpoint data at all, the system can still fall back to legacy `opinion_pre` / `opinion_post`, but current V2 simulations are expected to be checkpoint-driven

### Aggregate Analytics Scoring

When `metric_name` is omitted for analytics endpoints:

- `_agents_with_checkpoint_metrics()` delegates to `_enrich_agents_aggregate_scores()`
- each agent receives the average of all parseable checkpoint metric answers
- score field name: `aggregate_avg`
- used by aggregate polarization, aggregate opinion flow, and aggregate `GET /analytics/agent-stances`

### Aggregate Group Chat Scoring

When `metric_name` is omitted for Screen 4 supporter/dissenter selection:

- `_select_group_chat_agents()` uses `_agents_with_aggregate_extreme_scores()`
- dissenters use the minimum parseable checkpoint score across all metrics
- supporters use the maximum parseable checkpoint score across all metrics
- score field name: `aggregate_extreme`

This is intentionally different from aggregate analytics. Screen 4 is selecting strongly representative voices, not computing a population average.

## 6. Dynamic Metrics

### Question Types

Only quantitative questions generate numeric metrics:

- `scale` — produces numeric scores on 1–10 scale
- `yes-no` — produces Yes/No (mapped to 10.0/1.0)
- `open-ended` — produces report sections only, no numeric card, excluded from MetricSelector

### Current Value Rules

- Thresholded `scale` → percentage of agents meeting threshold
- Unthresholded `scale` → average score, usually `/10`
- `yes-no` → percentage of "yes" answers

### Report Delta Rules

Report metric cards compare:

- Initial checkpoint value (baseline)
- Final checkpoint value
- Delta and direction (`up`, `down`, `flat`)

Question metadata such as `metric_label`, `metric_unit`, and `report_title` is resolved from the session-scoped `analysis_questions` and fed into the same report pipeline.

## 8. Analytics Computations

### Polarization and Opinion Flow

- both endpoints consume checkpoint-derived scores, never sampled `agent.sentiment`
- per-metric mode uses `checkpoint_{metric_name}`
- aggregate mode uses the average checkpoint score per agent (`aggregate_avg`)
- stance bucketing uses the shared thresholds from section 3

### Agent Stances

`GET /api/v2/console/session/{id}/analytics/agent-stances` uses the same checkpoint scoring path as the other opinion analytics:

- aggregate mode returns average checkpoint score per agent
- per-metric mode returns `checkpoint_{metric_name}` per agent
- if an agent lacks a parseable score for the requested field, `get_agent_stances()` emits `5.0` so the agent stays in the demographic map as neutral rather than disappearing from the cohort

### Group Chat Candidate Selection

Both Screen 4 live endpoints share the same selection path:

- `GET /api/v2/console/session/{id}/chat/group/agents`
- `POST /api/v2/console/session/{id}/chat/group`

They both call `_select_group_chat_agents()`:

- default `top_n` is `5`
- aggregate supporter/dissenter mode uses extreme scoring (`aggregate_extreme`)
- per-metric mode uses `checkpoint_{metric_name}`
- final ranking is influence-weighted via `MetricsService.select_group_chat_agents()`

This is what keeps the visible supporter/dissenter chip row aligned with the agents who actually answer the group chat prompt.

### Influence and Cascades

- influence and cascade endpoints are metric-agnostic
- influence ranks by post engagement, comment count, and replies received
- cascade metrics operate on interaction-tree structure rather than checkpoint stance scores
