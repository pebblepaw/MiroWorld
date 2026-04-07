# Screen 4 — Report + Chat

## Overview

Screen 4 is the unified report and chat surface. It contains three view modes inside a single routed page:

- Report Only
- Report + Chat
- Chat Only

There is no separate routed Screen 6 in the current implementation.

## Current Report Contract

### Primary Endpoint

- `GET /api/v2/console/session/{id}/report`
- `POST /api/v2/console/session/{id}/report/generate`
- `GET /api/v2/console/session/{id}/report/export`

### Current Payload Shape

- `executive_summary`
- `metric_deltas`
- `quick_stats`
- `sections`
- `insight_blocks`
- `preset_sections`

## Rendering Rules

### Executive Summary

- plain-text narrative only
- grounded in the original document context plus simulation evidence

### Metric Delta Cards

For each quantitative analysis question:

- display label
- initial value
- final value
- delta direction
- `initial -> final` summary string

Examples:

- thresholded `scale` questions: percentage
- `yes-no` questions: percentage
- unthresholded `scale` questions: `/10`

`0Text` or raw text-unit leakage is always a bug.

### Analysis Question Sections

Every analysis question in the current session should produce a section, including user-added questions, subject to the persisted session config.

Each section may include:

- `report_title`
- original question text
- plain-text answer
- evidence rows
- optional metric spotlight for quantitative questions

### Evidence

Evidence rows should prefer:

- `agent_name`
- `agent_id` as a fallback
- `post_id`
- `quote`

Raw serial ids should not be the primary display label when a name is available.

### Text Cleanup

The report view does not render markdown. Report text should therefore be cleaned before display so literal `**` and backticks do not leak into the UI.

## Current Chat Contract

### Endpoints

- `POST /api/v2/console/session/{id}/chat/group`
- `POST /api/v2/console/session/{id}/chat/agent/{agent_id}`

### Current Modes

- Top Dissenters
- Top Supporters
- 1:1 Chat

Current chat behavior should use the real backend path in live mode. Fabricated replies are acceptable only in demo fallback flows.

## DOCX Export Contract

Current export should serialize the V2 structure only:

- executive summary
- quick stats
- metric deltas
- analysis question sections with evidence
- insight blocks
- preset sections
- short methodology footer

Legacy report sections should not be reintroduced for V2 sessions.
