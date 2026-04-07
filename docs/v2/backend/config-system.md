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
- list use cases
- load use-case YAML
- expose:
  - `system_prompt`
  - `analysis_questions`
  - `insight_blocks`
  - `preset_sections`
  - `agent_personality_modifiers`
- resolve legacy use-case aliases to canonical V2 ids
- resolve dataset paths for filter discovery

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
