# Screen 0 — Onboarding Modal

## Overview

The onboarding modal creates or reconfigures the active V2 session. It is the canonical entry point for:

- country
- provider
- model
- API key
- use case

The selected environment is reflected in the sidebar after launch.

## Current Runtime Contract

### Frontend State

`OnboardingModal.tsx` owns:

- selected country
- selected provider/model
- API key input
- canonical use case id

### Backend Endpoints

- `GET /api/v2/countries`
- `GET /api/v2/providers`
- `POST /api/v2/session/create`
- `PATCH /api/v2/session/{id}/config`

## Current Behavior

### Countries

- Singapore and United States are currently available
- country availability comes from YAML-backed config, not hardcoded UI assumptions

### Providers and Models

- provider list is hydrated from `/api/v2/providers`
- Gemini entries are surfaced as `gemini` in the compatibility API even though the backend runtime provider id is `google`
- retired Gemini models should not be the default choice
- current Gemini flows should prefer active models such as `gemini-2.5-flash-lite`

### API Keys

- API key entry is required for Gemini/OpenAI
- API key input is hidden for Ollama
- provider/runtime failures should be surfaced as short actionable errors

### Use Cases

Canonical values:

- `public-policy-testing`
- `product-market-research`
- `campaign-content-testing`

Legacy ids may still be accepted by the backend, but Screen 0 should write canonical ids.

## Validation Notes

- reopening the modal should preserve current session selections
- changing provider should refresh model choices
- starting a new session should seed session-scoped `analysis_questions`
- if a previously saved session uses a retired model, later screens should surface the real provider error until the model is changed
