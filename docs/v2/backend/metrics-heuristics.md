# Backend — Metrics & Heuristics

> Last updated: 2026-04-09

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


## `metric_answers` Format
tains `metric_answers` dict |
legacy sessions may use `"pre"` / `"post"`) |
om `analysis_q start but needs refinement.",
  "conv  "conv  "conv  "conv  "c"engagement_scor  "conv  "conv  "conv  "conv  "l downstream   "conv  "conv  "conv  "conv  "c"engagement_scor  "conv  "conv  "conv  "conv  "l ck  "conv  "conv  "conv  "conv  "c"engagement_scor  "conv  "conv  "conv que  "conv  "conv  "conv  "conv  "c"engagement_scor  "conv  "conv  "conv  "conv  "l downstream   "conv  "conv  "conv  "conv  "c"engagement_scor  "conv  "conv  "turns empty list

## 2. Score Par## 2 — `_extract_metric_score()`

Converts free-text metric answers into numeric 1–10 scale scores:

| Input Pattern | Output | Example |
|:--------------|:-------|:--------|
| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `" `"No"| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `" `"No"| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes|/1| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yes| `"Yerect parse | `"8.5"` → 8.5 |
| `| `| `| `| `| `| `| `| ``No| `| `| `| `| `| `| `| `| ext (no number) | `None` | `"I think it's good"` �| `| `| `| `| `| `| `| `| ``No| `| `| `|"` to extract the first decimal number from text.

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

- `_enrich_agents_met- `_enrich_agents_met- `_enrich_agents_met- `_rget_field)` looks up each agent's `metric_answers[metric_name]`, parses i- `_enrich_agents_mtarget_field]`
- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- c scores** per agent - S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S-cip- S- S- S- S- S`_agents_w- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- Sric_- S- S- S- S- S- S- S- S- S- S- S- metrics (any agent with ANY - S- S- S- S- S- S- S- up- S- S- S- S- S- S- S-se- S- S- S- S- S- S- S- S-s all metrics (any agent with ANY strong approval)
- Score field name: `aggregate_extreme`
- Falls back to `opinio- Falls back to `opinio- Falls back to `opinio- Falls back to `opinio- Falls back to `opinio- Falls back to `opinio- Falls back to `opinio- Falls back to `opinio- Falls back current simulations. All analytics and chat scoring now uses checkpoint-based data instead. These fields remain only as a last-resort fallback when a session has no checkpoint records at all.

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
- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Final ch- Final ay- Final ch- Final ch- Final ch- Finaitat- Final ch- Final chnps- Final ch- Finalded- Final ch- Final ch- Final ch- Final ch- Final ay- n &- Final ch- Final ch- Final ch- Final ch- Final ayrcentage
- `engagement_score`: average `/10`
- `credibil- `credibil- `credibil- `credibil- `credibil- `credibil- `credibil- `credibil- `crealized by `QuestionMetadataService` and join the same metric/report pipeline.

## 8. Analytics Computations

### Polarization

`MetricsService.compute_polarizati`MetricsService.compute_polarizati`Metriclar`MetricsService.compmin(`MetricsService.cosenter_pct)``MetricsService.compute_polarizati`Mon`MetricsService.compute_polarizati`MetricsService.compute_polarizati`Metriclar`MetricsService.compmin(`MetricsService.cosenter_pct)``MetricsService.compute_polarizati`Mon`MetricsService.compute_polarizati`MetricsService.compute_polarizati`Metriclar`MetricsService.compmin(`MetricsService.cosenter_pct)``MetricsService.compute_polarizati`Mon`MetricsService.compute_polarizati`MetricsService.compute_polarizati`Metriclar`MetricsService.compmin(`MetricsService.cosenter_pct)``MetricsService.compute_polarizati`Mon`MetricsService.compute_polarizati`MetricsService.compute_polarizati`Metriclar`Metricic`MetricsService.compute_polarizatctions, agents)`:

- Ranks by post engagement, comment count, and replies received
- Returns top influencers with: `name`, `agent_name`, `stance`, `influence_score`, `top_view`, `top_post`
- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic — does not acce- Metric-agnostic —ment count
- Replies received

Pre-filtered by stance using extreme scoring (section 4):

- Dissenters: agents with minimum metric score below dissenter threshold
- Supporters: agents with maximum metric score above supporter threshold

The current Screen 4 UX exposes supporters, dissenters, and 1:1 agent chat segments.
