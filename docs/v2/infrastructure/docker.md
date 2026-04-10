# Infrastructure — Docker Setup

## Overview

The project can run locally via direct frontend/backend processes or via Docker Compose. Docker remains the full-stack packaging reference; local development also relies on the project Python environments, especially for OASIS.

## Current Service Model

Typical services:

- frontend
- backend
- OASIS runtime / sidecar

## Environment Notes

Important runtime defaults:

- Gemini default model should prefer current active models such as `gemini-2.5-flash-lite`
- OpenRouter and OpenAI are also supported through the same provider-aware config path
- live OASIS runs require a valid Python 3.11 runtime with the required packages installed

## Local Runtime Reality

Current local manual testing often uses:

- frontend dev server
- backend app process
- `backend/.venv311` as the fallback OASIS Python runtime

The backend now validates the configured OASIS interpreter and falls back to the project runtime when the configured one is invalid.

## Validation

When touching infrastructure/runtime setup, confirm:

- frontend is reachable
- backend health/routes respond
- simulation can actually invoke OASIS
- provider/model discovery works with the configured env
