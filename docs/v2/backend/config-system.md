# Backend — Config System

## Overview

The config system externalizes country metadata and use-case prompt definitions into YAML. It also preserves a compatibility layer for legacy use-case ids while normalizing all newly written runtime state to canonical V2 ids.

## Canonical Config Files

### Countries

- `config/countries/singapore.yaml`
- `config/countries/usa.yaml`

### Use Cases

- `config/prompts/public-policy-testing.yaml`
- `config/prompts/product-market-research.yaml`
- `config/prompts/campaign-content-testing.yaml`

## Current `ConfigService` Responsibilities

- list countries
- load a country config by canonical id or common alias
- expose declared dataset metadata for a country
- expose declared geography metadata for a country
- list use cases
- load use-case YAML
- expose:
  - `system_prompt`
  - `analysis_questions`
  - `insight_blocks`
  - `preset_sections`
  - `agent_personality_modifiers`
- resolve legacy use-case aliases to canonical V2 ids
- expose YAML-declared dataset paths instead of guessing from generic cache roots

## Country YAML Contract

Each country YAML now acts as the source of truth for:

- `dataset.local_paths`
- `dataset.download_dir`
- `dataset.repo_id`
- `dataset.allow_patterns`
- `dataset.required_columns`
- `dataset.country_values`
- `geography.field`
- `geography.label`
- `geography.values`
- `geography.groups` where relevant

This is what allows Singapore and USA geography/filter logic to remain separated without hard-coding country lists in backend service code.

## Country Dataset Readiness Contract

The backend now derives live country readiness from declared YAML metadata plus the local filesystem.

Primary APIs:

- `GET /api/v2/countries`
- `POST /api/v2/countries/{country}/download`
- `GET /api/v2/countries/{country}/download-status`

Live response fields:

- `dataset_ready`
- `download_required`
- `download_status`
- `download_error`
- `missing_dependency`

Live error codes:

- `country_dataset_missing`
- `country_dataset_invalid`
- `huggingface_api_key_missing`

`CountryDatasetService` owns this runtime contract. `ConsoleService` enforces it during session creation and country changes.

## Alias Policy

Accepted legacy ids still map into canonical V2 ids:

- `policy-review` -> `public-policy-testing`
- `reviews`, `customer-review`, `pmf-discovery`, `product-market-fit` -> `product-market-research`
- `ad-testing` -> `campaign-content-testing`

These aliases are compatibility helpers only. New session state should always be written using canonical ids.

## Session Config Contract

The backend persists V2 runtime config in `session_configs`.

Current important fields:

- `country`
- `use_case`
- `provider`
- `model`
- `guiding_prompt`
- `analysis_questions`
- `config_json`

Related session runtime data in `console_sessions`:

- `mode` (`demo` or `live`)
- `model_provider`
- `model_name`
- `embed_model_name`
- `api_key`
- `base_url`

These `console_sessions` fields are what the runtime uses to build provider-aware clients per session for knowledge extraction, simulation, and chat/report generation.

## `analysis_questions` Rules

`analysis_questions` is the runtime source of truth.

Current lifecycle:

1. `create_v2_session` seeds the questions from the active YAML
2. Screen 1 fetches the session-scoped question list
3. custom question metadata is generated through `QuestionMetadataService`
4. Screen 1 persists the edited list with `PATCH /api/v2/session/{id}/config`
5. report generation and checkpoint metrics resolve the session-scoped list first

## `guiding_prompt` Compatibility

The config system still exposes a compatibility fallback:

- `get_system_prompt()` returns `system_prompt` and falls back to `guiding_prompt` only if needed
- some extraction paths still accept a `guiding_prompt` string

This field remains for compatibility only and should not be treated as the user-facing analysis primitive.

## Runtime Config Resolution

When the backend resolves provider/model settings at runtime, it uses:

1. session overrides from `console_sessions`
2. provider defaults from `Settings`

Resolved values include provider, chat model, embed model, API key, and base URL.

This means config changes on Screen 0 or session model settings directly affect live knowledge extraction, simulation, and chat behavior.

### Live activation coupling

- `console_sessions.mode == live` is the gate used by `ConsoleService` when deciding whether chat calls run in live memory mode.
- In live mode, group and 1:1 agent chat request SQLite-backed memory retrieval from persisted interactions, transcripts, and checkpoints.

## Question Metadata

`QuestionMetadataService` normalizes user-defined Screen 1 questions into the same shape used by preset questions.

Expected fields include:

- `question`
- `type`
- `metric_name`
- `metric_label`
- `metric_unit`
- `threshold` when relevant
- `report_title`
- `tooltip`

## Notes

- if a use-case YAML has no explicit `analysis_questions`, compatibility fallbacks still exist for older `checkpoint_questions` layouts
- report configuration is currently derived from `analysis_questions` plus `preset_sections`
- no external memory host/port is required for the current local runtime
- geography normalization should always go through country metadata, not direct `if field == "planning_area"` / `if field == "state"` branches scattered across generic logic
- `opinion_pre`/`opinion_post` on the `agents` table are always 10.0 in current simulations — analytics and chat scoring now use checkpoint-based `metric_answers` from `simulation_checkpoints` instead. See `backend/metrics-heuristics.md` for scoring details.
