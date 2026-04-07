# Backend — Controversy Boost

## Overview

Controversy boost modifies the OASIS hot-score logic so high-engagement controversial posts are not suppressed as aggressively as in the default Reddit-style ranking.

## Current Product Behavior

The current frontend exposes controversy boost as a binary switch:

- off -> `0.0`
- on -> `0.5`

This is the implemented runtime behavior and should be treated as the current contract.

## Current Flow

1. Screen 3 sends `controversy_boost` with the simulation request
2. `simulation_service.py` forwards it into the OASIS runner
3. `oasis_reddit_runner.py` threads it into hot-score ranking

## Simulation Seeding Note

This mechanism is separate from discussion seeding.

Current seeding rule:

- initial discussion threads come from the session’s analysis questions
- generic kickoff posts are obsolete for new runs

## Validation

Changes in this area should verify:

- `0.0` preserves default behavior
- `0.5` increases visibility of controversial high-engagement content
- ranking changes do not reintroduce generic kickoff-thread assumptions
