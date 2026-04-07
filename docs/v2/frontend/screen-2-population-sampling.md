# Screen 2 — Population Sampling

## Overview

Screen 2 samples the simulated population from the selected country dataset. The UI is driven by backend-discovered filters and a token/cost estimate.

## Current Responsibilities

1. fetch the country-specific filter schema
2. let the user configure sample size and sampling instructions
3. preview the sampled cohort
4. show token estimate for the selected provider/model

## Current Endpoints

- `GET /api/v2/console/session/{id}/filters`
- `GET /api/v2/token-usage/{session_id}/estimate`
- population preview / sampling routes under `/api/v2/console/session/{id}/sampling/...`

## Current Behavior

### Dynamic Filters

Filters are inferred from the selected country dataset and config file. The frontend should not assume a hardcoded Singapore-only schema.

Supported control types:

- `range`
- `multi-select-chips`
- `single-select-chips`
- `dropdown`

### Token Estimate

The estimate reflects the active model and provider for the current session.

- Gemini can show cached vs uncached estimates
- OpenAI shows no caching savings
- Ollama shows local/free semantics

### Cohort Visualization

The screen still uses the sampled cohort artifact as the source for:

- map view
- distribution summaries
- cohort explorer / waffle-style grouping

## Notes

- this screen should remain country-agnostic
- filter options should come from backend data whenever available
- fallback schema is acceptable only for non-live/demo-style flows
