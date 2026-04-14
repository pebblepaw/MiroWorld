# Report Service Breakdown

> Reference for rewriting `backend/src/miroworld/services/report_service.py` (1937 lines).
> Created 2026-04-15. Based on investigation of the full pipeline from YAML config → backend service → frontend rendering.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Two Parallel Report Formats](#2-two-parallel-report-formats)
3. [Data Flow: Config → Backend → Frontend](#3-data-flow-config--backend--frontend)
4. [Method Inventory (all 40+ methods)](#4-method-inventory)
5. [Hardcoded Content Audit](#5-hardcoded-content-audit)
6. [Frontend Report Renderer (ReportChat.tsx)](#6-frontend-report-renderer-reportchattsx)
7. [Frontend DEMO_REPORT Constant](#7-frontend-demo_report-constant)
8. [YAML Config Files That Drive Reports](#8-yaml-config-files-that-drive-reports)
9. [Key Issues & Recommendations](#9-key-issues--recommendations)

---

## 1. Architecture Overview

```
config/prompts/public-policy-testing.yaml    ← use-case: analysis_questions, preset_sections, insight_blocks
config/prompts/system/report_agent.yaml      ← LLM prompt templates, word limits
            │
            ▼
console_service.py                           ← API router; two entry paths:
  ├── get_v2_report()           → report_service.build_v2_report()       [V2 format]
  └── _run_report_generation()  → report_service.generate_structured_report()  [Legacy format]
            │
            ▼
report_service.py (1937 lines)               ← ReportService class: LLM calls, metric computation, evidence extraction
            │
            ▼
console-api.ts                               ← Frontend API client; StructuredReportState interface
            │
            ▼
ReportChat.tsx                               ← Cascading renderer: shows V2 sections OR legacy fallback
```

---

## 2. Two Parallel Report Formats

The service produces **two completely different output schemas** depending on which method is called. They share some internal helpers but are otherwise independent code paths.

### V2 Format (`build_v2_report`, line 366)

Called by: `ConsoleService.get_v2_report()` (console_service.py:1432)

Output fields:
| Field | Type | Source |
|-------|------|--------|
| `executive_summary` | string | LLM-generated via `_build_v2_executive_summary_from_metrics()` |
| `metric_deltas[]` | array | Computed from checkpoint records (baseline vs final agent opinions) |
| `sections[]` | array | One per `analysis_question` in YAML. LLM-generated answer + evidence pool |
| `insight_blocks[]` | array | Computed by `MetricsService.compute_insight_block()` (polarization, opinion_flow, etc.) |
| `preset_sections[]` | array | One per `preset_sections` entry in YAML. LLM-generated answer |
| `quick_stats` | object | agent_count, round_count, model, provider |

### Legacy Format (`generate_structured_report`, line 79)

Called by: `ConsoleService._run_report_generation_background()` (console_service.py:2435)

Output fields:
| Field | Type | Source |
|-------|------|--------|
| `executive_summary` | string | Hardcoded template string OR LLM |
| `insight_cards[]` | array | Hardcoded fallback strings (line 1654–1682) |
| `support_themes[]` | array | First 3 interaction rows truncated to 180 chars (line 1748) |
| `dissent_themes[]` | array | Same pattern |
| `demographic_breakdown[]` | array | Heuristic bucketing by age group |
| `influential_content[]` | array | Top interactions by engagement score |
| `recommendations[]` | array | Hardcoded template strings (line 1805–1840) |
| `risks[]` | array | Hardcoded template strings (line 1841–1878) |

**The legacy format is heavily hardcoded and mostly produces template-filled strings, not genuine LLM analysis.**

---

## 3. Data Flow: Config → Backend → Frontend

### Step 1: YAML Config

File: `config/prompts/public-policy-testing.yaml`

Key sections consumed by report_service:
- `analysis_questions[]` → drives `sections[]` in V2, drives checkpoint metrics in both
- `preset_sections[]` → drives `preset_sections[]` in V2 (e.g. "Recommendations" section)
- `insight_blocks[]` → drives `insight_blocks[]` in V2 (polarization, opinion_flow, etc.)
- `report_writer_instructions[]` → injected as `{style_block}` into the LLM prompt for each section
- `guiding_prompt` → injected into structured report prompt for legacy path

### Step 2: LLM Prompt Templates

File: `config/prompts/system/report_agent.yaml`

| Prompt Key | Used By | Purpose |
|------------|---------|---------|
| `structured_seed` | Legacy `generate_structured_report` | Ask LLM to output full JSON report shell |
| `executive_summary` | Legacy `build_report` | Basic summary |
| `v2_executive_summary` | V2 `_build_v2_executive_summary` | Summary from supporting/dissenting themes |
| `metric_delta_summary` | V2 `_build_v2_executive_summary_from_metrics` | Summary from metric deltas |
| `guiding_question` | V2 `_answer_guiding_question` | Per-section evidence-rich answer |
| `recommendations` | Legacy `_recommend` | JSON array of recommendations |
| `report_chat` | `report_chat_payload` | Answer follow-up questions |

Word limits (line 2–4):
```yaml
defaults:
  min_words_per_question: 200
  max_words_per_question: 400
```

These are injected into the `guiding_question.user_template` as `{min_words_per_question}` / `{max_words_per_question}`.

### Step 3: Console Service Routing

File: `backend/src/miroworld/services/console_service.py`

- **`get_v2_report(session_id)`** (line 1432): Checks for cached V2 report, otherwise calls `report_service.build_v2_report()`. Caches result.
- **`_is_cached_v2_report_payload(payload)`** (line 1451): Detects V2 format by checking for `metric_deltas`, `sections`, `insight_blocks`, or `preset_sections` lists.
- **`_run_report_generation_background(session_id)`** (line 2435): Legacy path, calls `report_service.generate_structured_report()`.

### Step 4: Frontend API

File: `frontend/src/lib/console-api.ts`

- `StructuredReportState` interface (line 364): Union of BOTH format fields. V2 fields are optional (`?`), legacy fields are required.
- `getStructuredReport(sessionId)` (line 1592): Calls `GET /api/v2/console/{sessionId}/report`.
- `generateReport(sessionId)` (line ~1580): Calls the generation endpoint.
- `getBundledDemoOutput()`: Loads `demo-output.json` for demo mode.

### Step 5: Frontend Renderer

File: `frontend/src/pages/ReportChat.tsx`

Cascading render order (lines 720–880):
1. Executive Summary → always shown
2. `metric_deltas` → "Key Metrics" cards (if present)
3. `sections` → "Analysis Findings" per-question detail with evidence (if present)
4. `preset_sections` → rendered as titled sections (if present)
5. `insight_cards` → "Key Insights" cards — **only if NO `metric_deltas`** (legacy fallback)
6. `support_themes` / `dissent_themes` → "Supporting/Dissenting Views" — **only if NO `sections`** (legacy fallback)
7. `recommendations` → numbered list — **only if NO `preset_sections`** (legacy fallback)

---

## 4. Method Inventory

### Public API Methods

| Method | Line | Format | Purpose |
|--------|------|--------|---------|
| `generate_structured_report()` | 79 | Legacy | Full legacy report pipeline |
| `build_v2_report()` | 366 | V2 | Full V2 report pipeline |
| `build_report()` | 147 | Older legacy | Basic approval/friction report (no LLM) |
| `report_chat()` | 305 | Both | Plain-text chat response |
| `report_chat_payload()` | 326 | Both | Structured chat response with metadata |
| `export_v2_report_docx()` | 521 | V2 | DOCX export of V2 report |

### V2 Internal Methods

| Method | Line | Purpose |
|--------|------|---------|
| `_resolve_analysis_questions()` | 1200 | Load questions from session config or YAML |
| `_resolve_insight_blocks()` | 1230 | Load insight block configs from YAML |
| `_resolve_preset_sections()` | 1240 | Load preset sections from YAML |
| `_answer_guiding_question()` | 1022 | LLM call per analysis question / preset section |
| `_build_v2_executive_summary_from_metrics()` | 1302 | LLM call for summary using metric deltas |
| `_build_v2_executive_summary()` | 1136 | LLM call for summary using themes |
| `_compute_metric_value()` | 1272 | Compute approval rate / sentiment / yes-no from agent data |
| `_agents_from_checkpoint()` | 1250 | Extract agent records from checkpoint |
| `_extract_evidence()` | 738 | Build evidence pool from interactions |
| `_select_section_evidence()` | 860 | Pick best evidence for a specific section |
| `_replace_agent_id_references()` | 922 | Replace "agent-0001" with real names in LLM text |
| `_replace_post_id_references()` | 966 | Replace post IDs with quotes in LLM text |
| `_knowledge_context_lines()` | 995 | Extract knowledge document context for LLM |
| `_resolve_report_writer_instructions()` | 1085 | Load style instructions from use-case YAML |
| `_session_analysis_questions()` | 1178 | Read per-session stored analysis questions |

### Legacy Internal Methods

| Method | Line | Purpose |
|--------|------|---------|
| `_should_request_structured_report_seed()` | 141 | Skip seed for Ollama (returns false) |
| `_build_structured_report_prompt()` | 1516 | Build massive JSON-schema prompt |
| `_normalize_structured_report_payload()` | 1594 | Validate/normalize LLM JSON output |
| `_enrich_structured_report_payload()` | 1611 | Fill empty fields with hardcoded fallbacks |
| `_rank_interactions()` | 1721 | Sort interactions by opinion delta |
| `_build_theme_items()` | 1748 | Build support/dissent theme arrays (truncated content) |
| `_build_influential_content()` | 1775 | Build influential content array |
| `_build_structured_recommendations()` | 1805 | **HARDCODED** recommendation templates |
| `_build_structured_risks()` | 1841 | **HARDCODED** risk templates |
| `_build_structured_executive_summary()` | 1879 | **HARDCODED** summary template string |
| `_build_demographic_breakdown()` | 1100 | Heuristic age-bucket breakdown |
| `_build_v2_recommendations()` | 1123 | Simpler recommendation builder |
| `_recommend()` | 1366 | LLM-based recommendations with hardcoded fallback |
| `_parse_recommendations()` | 1416 | Parse LLM JSON recommendation output |
| `_algorithmic_recommendations()` | 1468 | Fully hardcoded area-based recommendations |

### Utility Functions (module-level)

| Function | Line | Purpose |
|----------|------|---------|
| `_clean_report_text()` | 21 | Strip whitespace |
| `_format_metric_value()` | 26 | Format number with unit |
| `_extract_numeric_value()` | 34 | Parse numeric from any type |
| `_parse_yes_no()` | 56 | Parse yes/no boolean |
| `_approval()` | 1903 | Compute approval rate from scores |
| `_mean()` | 1909 | Compute mean of scores |
| `_parse_json_object()` | 1915 | Parse JSON from LLM output |
| `_normalize_dict_list()` | 1924 | Validate dict lists against required keys |
| `_contains_first_person()` | 1935 | Check for first-person pronouns |

---

## 5. Hardcoded Content Audit

These are the locations where the service produces hardcoded template strings instead of LLM-generated or data-driven content.

### Line 1374–1385: `_recommend()` fallback

When `top_dissenting` is empty, returns a hardcoded recommendation:
```python
return [{
    "title": "Maintain broad-based communication cadence",
    "rationale": "No major friction clusters detected in planning-area analysis.",
    "target_demographic": "All cohorts",
    ...
    "confidence": 0.62,
}]
```

### Line 1451–1453: `_parse_recommendations()` fallback

When parsed recommendation has `< 2` execution plan items, replaces with hardcoded steps:
```python
plan_list = [
    "Run targeted messaging sessions with affected households.",
    "Track sentiment changes weekly and refine intervention messaging.",
]
```

### Line 1488–1496: `_algorithmic_recommendations()` hardcoded area templates

Generates recommendations using f-string templates — not LLM:
```python
"title": f"Targeted affordability mitigation for {area}",
"execution_plan": [
    f"Deploy area-specific budget explainers in {area} community channels.",
    "Add concrete household cashflow examples for affected segments.",
    "Collect 2-week feedback pulse and adjust subsidy messaging.",
],
```

### Line 1498–1510: `_algorithmic_recommendations()` empty fallback

Hardcoded fallback when no friction clusters found:
```python
{
    "title": "Cross-cohort message calibration",
    "rationale": "No sharply concentrated friction cluster was detected.",
    "execution_plan": [
        "Segment messages by age and income before public rollout.",
        "Prioritize FAQs around transport and cost-of-living concerns.",
    ],
    "confidence": 0.6,
}
```

### Line 1654–1682: `_enrich_structured_report_payload()` insight_cards fallback

Fills `insight_cards` with template strings when LLM seed fails:
```python
enriched["insight_cards"] = [{
    "title": f"{top_segment} drove the clearest shift",
    "summary": card_summary,  # f-string template
    "severity": "high" if abs(approval_post - approval_pre) >= 0.15 else "medium",
}]
```
Also appends "Most persuasive support argument" and "Main dissent pressure point" cards using truncated interaction content (first 240 chars).

### Line 1757–1762: `_build_theme_items()` fallback

When no interactions found:
```python
return [{
    "theme": theme_label,
    "summary": fallback_summary,  # e.g. "Support centered on concrete benefits..."
    "evidence": [],
}]
```

### Line 1805–1840: `_build_structured_recommendations()` — entirely hardcoded

Returns 3 hardcoded template recommendations using f-strings. No LLM involvement:
```python
return [
    {"title": f"Address the main friction in {top_segment}", ...},
    {"title": f"Turn the strongest support into a clearer message for {base_label}", ...},
    {"title": "Use round-by-round evidence to close credibility gaps", ...},
]
```

### Line 1841–1878: `_build_structured_risks()` — entirely hardcoded

Returns up to 3 hardcoded template risks. The third one literally says:
```python
{
    "title": "Conversation may be dominated by the most active agents",
    "summary": "Event logs show the report is driven by a small set of highly visible posts.",
    "severity": "low",
}
```

### Line 1879–1901: `_build_structured_executive_summary()` — template string

No LLM. Pure f-string:
```python
f"Across {use_case_label}, approval {direction} from {approval_pre:.2f} to {approval_post:.2f}. "
f"{top_segment} was the clearest cohort signal in the run..."
```

### Line 50–88 of ReportChat.tsx: `DEMO_REPORT` constant

Frontend fallback for demo/static mode is a fully hardcoded object with predefined insight_cards, support_themes, dissent_themes, and recommendations. This is what renders on GitHub Pages when `demo-output.json` doesn't override it with real V2 data.

---

## 6. Frontend Report Renderer (ReportChat.tsx)

File: `frontend/src/pages/ReportChat.tsx`

### Rendering Logic (lines 720–880)

The renderer is a **cascading fallback** chain — V2 fields take priority, legacy fields only render when V2 fields are absent:

```
1. Executive Summary                    → always shown if present
2. metric_deltas (V2)                   → "Key Metrics" cards
3. sections (V2)                        → "Analysis Findings" — one per analysis_question with evidence
4. preset_sections (V2)                 → titled markdown sections (e.g. "Recommendations")
5. insight_cards (legacy)               → "Key Insights" — ONLY if NO metric_deltas
6. support_themes/dissent_themes (leg.) → "Supporting/Dissenting Views" — ONLY if NO sections
7. recommendations (legacy)             → numbered list — ONLY if NO preset_sections
```

### How "bullet-point" formatting works

The demo report's nice bullet-point look for Supporting Views and Recommendations is **NOT from LLM markdown output**. It's entirely frontend rendering:

- **`ThemeCard` component** (line 849): Maps over `support_themes[]` / `dissent_themes[]` arrays. Each `{ theme, evidence_count }` becomes a bullet row with a count badge.
- **Recommendations** (line 860): Maps over `recommendations[]` array. Each `{ title, description }` becomes a numbered item with index badge.

The V2 path has no equivalent structured arrays — `preset_sections` come back as markdown prose blobs.

### `hasRenderableReportContent()` (line ~93)

Determines if a report has any content worth showing:
```tsx
Boolean(
  executive_summary ||
  metric_deltas?.length > 0 ||
  sections?.length > 0 ||
  preset_sections?.length > 0 ||
  insight_cards?.length > 0
)
```

### Report Hydration (lines 320–370)

1. On simulation complete → calls `getStructuredReport(sessionId)`
2. If that returns renderable content → display it
3. If not → auto-trigger `beginReportGeneration()` which calls `generateReport(sessionId)`
4. Demo mode → falls through to `loadDemoReport()` which loads `demo-output.json` or `DEMO_REPORT`

### Report Caching

Reports are cached in `sessionStorage` keyed by `miroworld-report-{sessionId}`. On session change, cached report is loaded before making API calls.

---

## 7. Frontend DEMO_REPORT Constant

Location: `frontend/src/pages/ReportChat.tsx`, lines 50–88

This is the **hardcoded fallback** for demo/static mode. When `demo-output.json` fails to load or lacks a report, this displays.

Contents:
- 3 `insight_cards`: "Generational Divide", "Income Correlation", "Cascade Effect"
- 3 `support_themes`: AI investment, SkillsFuture, family support
- 3 `dissent_themes`: cost of living, AI displacement, carbon tax
- 4 `demographic_breakdown` items by age group
- 2 `influential_content` items
- 3 `recommendations`: cost-of-living gap, AI transition support, carbon tax rebates

**All values are literally written as string constants.** None are generated.

**In practice**: The demo mode actually loads `demo-output.json` via `loadDemoReport()` (line ~255) and merges it: `{ ...DEMO_REPORT, ...reportFromDemo, status: 'complete' }`. Since the demo-output.json from the V2 cache generator contains `sections` and `metric_deltas`, those V2 fields take priority in the cascading renderer, and the hardcoded legacy fields in `DEMO_REPORT` are hidden by the `!(report as any).sections` / `!(report as any).metric_deltas` guards.

---

## 8. YAML Config Files That Drive Reports

### `config/prompts/public-policy-testing.yaml`

```yaml
analysis_questions:          # → V2 sections[] + metric_deltas[]
  - question: "..."
    type: "scale"            # scale | yes-no | open-ended
    metric_name: "approval_rate"
    metric_label: "Approval Rate"
    metric_unit: "%"
    threshold: 7             # for scale → what counts as "approve"
    threshold_direction: "gte"
    report_title: "Policy Approval"
    tooltip: "..."

insight_blocks:              # → V2 insight_blocks[]
  - type: "polarization_index"
  - type: "opinion_flow"
  - type: "top_influencers"
  - type: "viral_cascade"

preset_sections:             # → V2 preset_sections[]
  - title: "Recommendations"
    prompt: "Provide actionable recommendations..."

report_writer_instructions:  # → injected as {style_block} in LLM prompts
  - "Write in third-person analytical voice..."
  - "Do not use first-person pronouns..."
```

### `config/prompts/system/report_agent.yaml`

Contains all LLM prompt templates. Key tunables:

```yaml
defaults:
  min_words_per_question: 200    # ← lower these for shorter sections
  max_words_per_question: 400    # ← lower these for shorter sections
  recent_interactions_chars:
    default: 20000               # context window chars for interaction evidence
    google: 50000                # Google gets more context
```

---

## 9. Key Issues & Recommendations

### Problem 1: Two parallel formats with no shared logic

The Legacy path (`generate_structured_report`) and V2 path (`build_v2_report`) share some helpers (`_answer_guiding_question`, `_extract_evidence`) but produce completely different output schemas. The frontend has to handle both with cascading conditionals.

**Recommendation**: Deprecate the legacy format entirely. Standardize on V2. If legacy fields (insight_cards, support_themes, recommendations) are desired, generate them as part of the V2 pipeline with proper LLM calls.

### Problem 2: Massive hardcoded fallback chain

The legacy `_enrich_structured_report_payload()` (line 1611–1720) fills **every empty field** with hardcoded templates. This means reports look "complete" but contain fake content that wasn't generated from simulation data.

Hardcoded methods that should be LLM-generated or removed:
- `_build_structured_recommendations()` (line 1805)
- `_build_structured_risks()` (line 1841)
- `_build_structured_executive_summary()` (line 1879)
- `_algorithmic_recommendations()` (line 1468)
- Fallbacks in `_recommend()` (line 1374)
- Fallbacks in `_parse_recommendations()` (line 1451)

### Problem 3: Report length is hard to control

Sections are generated by `_answer_guiding_question()` which uses `min_words_per_question` / `max_words_per_question` from `report_agent.yaml` defaults (200–400 words). But there's no per-use-case override — all use cases get the same length.

**Recommendation**: Allow `report_agent.yaml` defaults to be overridden per use-case YAML.

### Problem 4: No structured theme/recommendation output in V2

The V2 path generates `preset_sections` as prose markdown. There's no way to get structured `{ title, description }` recommendation arrays or `{ theme, evidence_count }` theme arrays from the V2 pipeline.

**Recommendation**: Add a structured output mode to `preset_sections` config, e.g.:
```yaml
preset_sections:
  - title: "Recommendations"
    prompt: "..."
    output_format: "structured_list"  # → ask LLM for JSON array
```

### Problem 5: Frontend demo data masks real issues

The `DEMO_REPORT` constant ensures the demo bundle always looks polished, but this masks the fact that the live V2 pipeline produces a different (and potentially less presentable) output. The demo should use real generated data or nothing.

### Problem 6: File is 1937 lines — too large

The service handles report generation, evidence extraction, metric computation, text post-processing, DOCX export, chat responses, and multiple format builders. These should be separate modules.

Suggested split:
- `report_builder_v2.py` — V2 pipeline only
- `report_evidence.py` — evidence extraction, selection, reference replacement
- `report_metrics.py` — metric computation, checkpoint handling
- `report_export.py` — DOCX export
- `report_chat.py` — report chat handler
- `report_prompts.py` — prompt construction helpers
