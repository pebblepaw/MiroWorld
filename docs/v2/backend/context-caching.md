# Backend — Context Caching

## Overview

Gemini context caching is used to reduce repeated prompt cost for multi-agent simulations. The cached portion is the session-wide context that every agent sees; per-agent and per-round context remains dynamic.

## Current Intent

Cache once per simulation session:

- use-case `system_prompt`
- document context
- session-scoped analysis questions
- shared simulation instructions

Then reuse that cache for repeated agent calls.

## Current Provider Model

- Gemini: native caching support
- OpenAI: no native cache path in this layer
- Ollama: no cache path, treated as local runtime

The modeled pricing and savings calculations live in `token_tracker.py`. That file is the implementation reference for current per-model estimates; this document intentionally does not hardcode external pricing tables.

## Current Runtime Notes

- the product no longer treats user-edited guiding prompts as the main shared prompt contract
- when compatibility code still needs a focus string, it should be derived from the active analysis question set or legacy session field
- session token usage is recorded in `session_token_usage`

## Current Endpoints

- `GET /api/v2/token-usage/{session_id}`
- `GET /api/v2/token-usage/{session_id}/estimate?agents={n}&rounds={r}`

## Expected UI Behavior

- Gemini can show cached vs uncached estimated cost
- OpenAI shows no caching savings
- Ollama shows local/free semantics

## Validation

Changes in this area should verify:

- token totals accumulate correctly
- estimate responses match the active model/provider
- non-Gemini providers degrade cleanly without pretending caching exists
