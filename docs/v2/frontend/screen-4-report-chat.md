# Screen 4 — Report + Chat

> Last updated: 2026-04-09

## Overview

Screen 4 is the unified report and chat surface. It is a single routed page containing three view modes:

- **Report Only** — full structured report with metric deltas, analysis sections, evidence, and insight blocks
- **Report + Chat** — split view: report on the left, chat panel on the right
- **Chat Only** — full-width chat panel

There is no separate routed Screen 6 in the current implementation — "Chat Only" is a view mode within Screen 4.

The page is implemented in [`ReportChat.tsx`](../../../frontend/src/pages/ReportChat.tsx).

---

## 1. Metric Selector (Chat Filter)

### What It Is

A `<MetricSelector>` dropdown that filters which analysis question the group chat focuses on. This is a shared component ([`MetricSelector.tsx`](../../../frontend/src/components/MetricSelector.tsx)) also used on Screen 5.

### How It Works

1. On mount, `MetricSelector` fetches analysis questions from `GET /api/v2/session/{id}/analysis-questions` (see [`console-api.ts`](../../../frontend/src/lib/console-api.ts) `getAnalysisQuestions()`)
2. It filters out `open-ended` questions — only quantitative questions with a `metric_name` appear
3. Options rendered:
   - **"All (Aggregate)"** → `onChange(null)` — aggregate mode
   - **Per-metric entries** → `onChange(q.metric_name)` — e.g. `"approval_rate"`, `"conversion_intent"`
4. Hidden when only one quantitative question exists (no filtering needed)

### State Flow

```
MetricSelector.onChange(metricName | null)
    → setChatMetric(metricName | null)         // ReportChat state
        → sendGroupChatMessage(sessionId, {
              segment,
              message,
              metric_name: chatMetric ?? undefined   // passed to backend
          })
```

The `chatMetric` state is declared in `ReportChat.tsx` and passed as a query param in the group chat API call body. The backend uses it to decide which agents qualify as dissenters/supporters and how to score them (see section 4 below).

### Config/Prompt Connection

The analysis questions available in the dropdown originate from the use-case YAML files in [`config/prompts/`](../../../config/prompts/):

- [`public-policy-testing.yaml`](../../../config/prompts/public-policy-testing.yaml) → `approval_rate` (scale), `policy_viewpoints` (open-ended, filtered out)
- [`product-market-research.yaml`](../../../config/prompts/product-market-research.yaml) → `product_interest` (scale), `nps_score` (scale), `product_feedback` (open-ended, filtered out), `pain_points` (open-ended, filtered out), `competitive_landscape` (open-ended, filtered out)
- [`campaign-content-testing.yaml`](../../../config/prompts/campaign-content-testing.yaml) → `conversion_intent` (yes-no), `engagement_score` (scale), `credibility_score` (scale), `objections` (open-ended, filtered out)

These are seeded into `session_configs.analysis_questions` at session creation by `ConfigService`, then potentially edited by the user on Screen 1. The MetricSelector always reads the session-scoped list, not the raw YAML.

---

## 2. Report

### Data Flow

1. On mount (or when simulation completes), `ReportChat.tsx` calls `getStructuredReport(sessionId)` → [`GET /api/v2/console/session/{id}/report`](../../../backend/src/mckainsey/api/routes_console.py)
2. If no report exists yet, it calls `generateReport(sessionId)` → [`POST /api/v2/console/session/{id}/report/generate`](../../../backend/src/mckainsey/api/routes_console.py) which triggers async generation
3. Report state is polled every 1500ms (`POLL_INTERVAL_MS`) while status is `'running'`

### Report Generation — Backend Pipeline

Report generation happens in [`ReportService.build_v2_report()`](../../../backend/src/mckainsey/services/report_service.py#L327). The pipeline is:

1. **Load agents and interactions** from the simulation store
2. **Resolve analysis questions** from the session config (session-scoped, not raw YAML) via `_resolve_analysis_questions()`
3. **Resolve insight block configs and preset section configs** from the use-case YAML via [`_resolve_insight_blocks()`](../../../backend/src/mckainsey/services/report_service.py#L1107)
4. **Build the evidence pool** from all interactions — extracts quotes, agent ids, post ids
5. **Compute metric deltas** for each quantitative question:
   - Load baseline and final checkpoint records
   - For each question: compute initial value from baseline agents, final value from final agents
   - Value computation via `_compute_metric_value()`:
     - `yes-no` → percentage of agents scoring ≥ 7
     - `scale` with threshold → percentage meeting threshold
     - `scale` without threshold → average score
   - Output: `{metric_name, initial_value, final_value, delta, direction, initial_display, final_display}`
6. **Generate analysis sections** for every question (including open-ended):
   - Calls `_answer_guiding_question()` which prompts the LLM with the question, agents, interactions, and document context
   - Selects up to 4 evidence items per section
   - Adds a `metric` spotlight entry for quantitative questions
7. **Compute insight blocks** — iterates the use-case's `insight_blocks` config and dispatches each to [`MetricsService.compute_insight_block()`](../../../backend/src/mckainsey/services/metrics_service.py#L815)
8. **Generate preset sections** — LLM-authored sections from use-case prompts (e.g. "Recommendations", "Best-Fit Demographics")
9. **Build executive summary** from the computed metric deltas

### Rendered Payload Shape

```json
{
  "session_id": "...",
  "generated_at": "2026-04-09T...",
  "executive_summary": "...",
  "metric_deltas": [
    {
      "metric_name": "approval_rate",
      "metric_label": "Approval Rate",
      "metric_unit": "%",
      "initial_value": 61.0,
      "final_value": 73.0,
      "delta": 12.0,
      "direction": "up",
      "initial_display": "61.0%",
      "final_display": "73.0%",
      "delta_display": "61.0% -> 73.0%"
    }
  ],
  "quick_stats": { "agent_count": 50, "round_count": 5, "model": "...", "provider": "..." },
  "sections": [
    {
      "question": "...",
      "report_title": "Policy Approval",
      "type": "scale",
      "answer": "...",
      "evidence": [{ "agent_id": "...", "quote": "...", "post_id": "..." }],
      "metric": {}
    }
  ],
  "insight_blocks": [
    { "type": "polarization_index", "title": "Polarization Over Time", "description": "...", "data": {} }
  ],
  "preset_sections": [
    { "title": "Recommendations", "answer": "..." }
  ]
}
```

### Frontend Rendering Rules

- **Executive Summary** — plain-text narrative, no markdown rendering
- **Metric Delta Cards** — shows label, initial → final with direction indicator. `0Text` or raw text-unit leakage is always a bug
- **Analysis Sections** — header with `report_title`, question text, answer text, evidence rows. Evidence rows prefer `agent_name` over raw serial ids. Clicking evidence calls `openEvidenceDrilldown(agentId)` which switches to 1:1 chat with that agent
- **Text cleanup** — report view does not render markdown, so `**` and backticks are stripped before display via `_clean_report_text()` in the backend

---

## 3. Chat Panel

### Segment Tabs

Three segment tabs:

| Tab | State Value | Backend Segment Key | Description |
|:----|:-----------|:-------------------|:------------|
| Top Dissenters | `'dissenters'` | `'dissenter'` | Agents most opposed to the policy/product |
| Top Supporters | `'supporters'` | `'supporter'` | Agents most in favor |
| 1:1 Chat | `'one-on-one'` | — | Direct chat with a selected agent |

Clicking a tab updates `chatSegment` state. For dissenters/supporters, the panel shows a horizontal scrollable list of the top 5 agents for that segment. For 1:1, it shows an agent search input and selection UI.

### Group Chat: How It Finds Top Dissenters and Supporters

This is the most complex data flow on Screen 4. The full pipeline:

#### Step 1: Frontend sends the request

```typescript
sendGroupChatMessage(sessionId, {
  segment: 'dissenter' | 'supporter',
  message: "What concerns you most?",
  metric_name: chatMetric ?? undefined      // from MetricSelector
})
```

API: `POST /api/v2/console/session/{id}/chat/group` — defined in [`routes_console.py`](../../../backend/src/mckainsey/api/routes_console.py)

#### Step 2: Backend scores agents via checkpoint data

In [`ConsoleService.group_chat()`](../../../backend/src/mckainsey/services/console_service.py#L1345):

**If `metric_name` is null (aggregate) AND segment is supporter/dissenter:**

Calls [`_agents_with_aggregate_extreme_scores(session_id, segment)`](../../../backend/src/mckainsey/services/console_service.py#L1892)

This function uses **extreme scoring** — the rationale is that in aggregate mode, we want to find agents who feel _most strongly_ about _any_ metric, not agents whose average is middle-of-the-road:

1. Load final checkpoint records (`checkpoint_kind="post"`, falling back to `"final"`)
2. For each agent, collect ALL parseable numeric scores across all `metric_answers`
3. **Dissenter segment** → uses `min(all_scores)` — any agent with ANY strong objection on any metric
4. **Supporter segment** → uses `max(all_scores)` — any agent with ANY strong approval on any metric
5. Score field: `"aggregate_extreme"`

The parsing runs through [`_extract_metric_score()`](../../../backend/src/mckainsey/services/console_service.py#L1811) which handles free-text LLM answers:
- `"Yes"` → 10.0, `"No"` → 1.0
- `"7/10. Great policy"` → 7.0
- `"8.5"` → 8.5
- Unparseable text → `None` (skipped)

**If `metric_name` is provided (per-metric):**

Calls [`_agents_with_checkpoint_metrics(session_id, metric_name)`](../../../backend/src/mckainsey/services/console_service.py#L1850)

This enriches each agent with their specific metric score from checkpoint data:
- Score field: `"checkpoint_{metric_name}"` (e.g. `"checkpoint_approval_rate"`)
- Falls back to legacy `"opinion_post"` if no checkpoints exist

#### Step 3: Rank by influence and filter by stance

Calls [`MetricsService.select_group_chat_agents()`](../../../backend/src/mckainsey/services/metrics_service.py#L442):

1. **Compute influence score for every agent** from interaction traces:
   - `post_engagement` = sum of likes + dislikes across all of the agent's posts
   - `comment_count` = number of comments the agent wrote
   - `replies_received` = number of interactions targeting this agent
   - **Normalized composite score** = `0.4 * (engagement / max_engagement) + 0.3 * (comments / max_comments) + 0.3 * (replies / max_replies)`

2. **Filter by stance** — only agents matching the requested segment (supporter/dissenter) are kept. Stance is determined by the score field from Step 2:
   - Score >= 7.0 → supporter
   - Score 5.0–6.99 → neutral
   - Score < 5.0 → dissenter

3. **Sort by influence score** descending, return top N (default 5)

#### Step 4: LLM generates responses for each selected agent

For each selected agent, calls `MemoryService.agent_chat_realtime()` which:
- In live mode: uses Graphiti-backed memory search grounded in the agent's simulation context
- In demo mode: uses demo response generation

Responses are appended to the interaction transcript store and returned as:
```json
{
  "session_id": "...",
  "segment": "dissenter",
  "responses": [
    {
      "agent_id": "agent-42",
      "response": "As a retiree from Tampines, I worry about...",
      "influence_score": 0.87,
      "memory_used": true,
      "memory_backend": "graphiti"
    }
  ]
}
```

#### Step 5: Frontend renders responses

Each response appears as a chat bubble with the agent's name (resolved from the agents list, not raw serial id), stance badge, and the response text. The typing indicator shows a pulsing text banner while waiting for responses.

### 1:1 Agent Chat

When the `one-on-one` tab is selected:

1. User searches for an agent by name
2. User selects an agent, which sets `selectedAgent` state
3. Messages are sent via `sendAgentChatMessage(sessionId, { agent_id, message })` → `POST /api/v2/console/session/{id}/chat/agent/{agent_id}`
4. Backend: [`ConsoleService.agent_chat_v2()`](../../../backend/src/mckainsey/services/console_service.py#L1539) calls `MemoryService.agent_chat_realtime()` for a single agent
5. Response rendered as a chat bubble

### Typing Indicator

While `chatPending` is true, a pulsing text banner is shown:

```html
<p class="text-xs text-muted-foreground animate-[livePulse_2s_ease-in-out_infinite]">
  Waiting for live agent response…
</p>
```

The `livePulse` keyframe is defined in [`tailwind.config.ts`](../../../frontend/tailwind.config.ts) — it animates opacity from 0.4 → 1.0 → 0.4 over a 2-second cycle. This replaced the earlier 3-dot bubble animation.

---

## 4. DOCX Export

### How It Works

1. User clicks the Export button on the report view
2. Frontend calls [`exportReportDocx(sessionId)`](../../../frontend/src/lib/console-api.ts) → `GET /api/v2/console/session/{id}/report/export`
3. Backend: [`routes_console.py`](../../../backend/src/mckainsey/api/routes_console.py) calls [`ConsoleService.export_v2_report_docx(session_id)`](../../../backend/src/mckainsey/services/console_service.py#L1336), which delegates to [`ReportService.export_v2_report_docx()`](../../../backend/src/mckainsey/services/report_service.py#L481)
4. The report is first built (or reused if already cached) via `build_v2_report()`
5. A `python-docx` `Document()` is constructed

### DOCX Structure

| Section | Content Source |
|:--------|:-------------|
| Title + session info | Session id, generation timestamp |
| Executive Summary | `payload.executive_summary` |
| Quick Stats | Agent count, round count, model, provider |
| Metric Deltas | Bullet list: `"Label: initial → final (+delta)"` per quantitative question |
| Analysis Question Sections | H2 heading per question, question text, answer text, evidence bullet list |
| Use-Case Insights | H2 heading per insight block, title + description |
| Preset Sections | H2 heading per preset, LLM-generated answer text |
| Analytics Summary | Per-metric breakdown from checkpoint data, per-agent metrics |

6. The DOCX binary is returned as a `StreamingResponse` with `Content-Disposition: attachment`
7. Frontend creates an object URL from the blob and triggers a download as `mckainsey-report-{sessionId}.docx`

### Data Sources

The DOCX export serializes the exact same report payload as the on-screen report. It does NOT re-run LLM generation — it reuses the cached `build_v2_report()` output. The analytics summary section at the bottom enriches agents with checkpoint metrics from the `simulation_checkpoints` table and resolves analysis questions from the config.

---

## 5. How Config/Prompts Drive Screen 4

### Session Config Resolution Chain

```
config/prompts/{use-case}.yaml
    → (seeded at session creation by ConfigService)
session_configs.analysis_questions
    → (potentially edited by user on Screen 1)
GET /api/v2/session/{id}/analysis-questions
    → (consumed by MetricSelector + ReportService)
```

### What Each YAML Field Controls on Screen 4

| YAML Field | Screen 4 Feature |
|:-----------|:----------------|
| `analysis_questions[].question` | Report section question text, LLM prompt for generating section answers |
| `analysis_questions[].type` | Determines if metric delta card is generated (`scale`/`yes-no` = yes, `open-ended` = no) |
| `analysis_questions[].metric_name` | Key into `metric_answers` for checkpoint-based scoring |
| `analysis_questions[].threshold` | Binary classification threshold for percentage metrics |
| `analysis_questions[].report_title` | Section heading in the report |
| `analysis_questions[].metric_label` | Label on metric delta card |
| `analysis_questions[].metric_unit` | `"%"` or `"/10"` — display unit |
| `insight_blocks[].type` | Dispatches to [`compute_insight_block()`](../../../backend/src/mckainsey/services/metrics_service.py#L815) |
| `insight_blocks[].title` | Display title in report insight block |
| `preset_sections[].title` | Display title for LLM-generated section |
| `preset_sections[].prompt` | LLM prompt that generates the section content |
| `system_prompt` | System prompt used when generating agent personas and simulation behavior |
| `guiding_prompt` | Compatibility fallback for knowledge extraction |
| `agent_personality_modifiers` | Personality instructions injected into agent simulation behavior |
| `report_writer_instructions` | Tone/voice instructions for LLM-generated report text |

---

## 6. API Reference

| Endpoint | Method | Params | Purpose |
|:---------|:-------|:-------|:--------|
| `/api/v2/console/session/{id}/report` | GET | — | Fetch current report state |
| `/api/v2/console/session/{id}/report/generate` | POST | — | Trigger report generation |
| `/api/v2/console/session/{id}/report/export` | GET | — | Download DOCX binary |
| `/api/v2/console/session/{id}/chat/group` | POST | `{segment, message, metric_name?, top_n?}` | Send group chat message |
| `/api/v2/console/session/{id}/chat/agent/{agent_id}` | POST | `{message}` | Send 1:1 agent chat |
| `/api/v2/session/{id}/analysis-questions` | GET | — | Fetch session analysis questions |

---

## 7. Key Code References

| Component | File | Key Lines |
|:----------|:-----|:----------|
| ReportChat page | [`frontend/src/pages/ReportChat.tsx`](../../../frontend/src/pages/ReportChat.tsx) | State decl, MetricSelector, chat send |
| MetricSelector component | [`frontend/src/components/MetricSelector.tsx`](../../../frontend/src/components/MetricSelector.tsx) | Filters open-ended, onChange callback |
| Frontend API client | [`frontend/src/lib/console-api.ts`](../../../frontend/src/lib/console-api.ts) | `sendGroupChatMessage`, `exportReportDocx`, etc. |
| Chat route definition | [`backend/src/mckainsey/api/routes_console.py`](../../../backend/src/mckainsey/api/routes_console.py) | POST endpoints |
| Group chat logic | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `group_chat()` L1345, `_agents_with_aggregate_extreme_scores()` L1892 |
| Score parsing | [`backend/src/mckainsey/services/console_service.py`](../../../backend/src/mckainsey/services/console_service.py) | `_extract_metric_score()` L1811 |
| Agent selection and influence | [`backend/src/mckainsey/services/metrics_service.py`](../../../backend/src/mckainsey/services/metrics_service.py) | `select_group_chat_agents()` L442 |
| Report builder | [`backend/src/mckainsey/services/report_service.py`](../../../backend/src/mckainsey/services/report_service.py) | `build_v2_report()` L327 |
| DOCX export | [`backend/src/mckainsey/services/report_service.py`](../../../backend/src/mckainsey/services/report_service.py) | `export_v2_report_docx()` L481 |
| Use-case YAML configs | [`config/prompts/`](../../../config/prompts/) | `analysis_questions`, `insight_blocks`, `preset_sections` |
| Stance thresholds | [`backend/src/mckainsey/services/metrics_service.py`](../../../backend/src/mckainsey/services/metrics_service.py) | `_stance_from_score()` L41 |
