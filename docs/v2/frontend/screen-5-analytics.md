# Screen 5 — Analytics

## Overview

Screen 5 visualizes the live simulation outputs that sit beside the narrative report. It is fed by analytics endpoints in live mode and can still use local constants in demo mode.

## Current Blocks

### 1. Sentiment Dynamics

- Polarization Index
- Opinion Flow

### 2. Demographic Sentiment Map

- dimension chips vary by use case
- cohorts are rendered as grouped sentiment cells

### 3. KOL & Viral Posts

- key opinion leaders
- viral posts / cascades

## Current Live Endpoints

- `GET /api/v2/console/session/{id}/analytics/polarization`
- `GET /api/v2/console/session/{id}/analytics/opinion-flow`
- `GET /api/v2/console/session/{id}/analytics/influence`
- `GET /api/v2/console/session/{id}/analytics/cascades`

## Current Runtime Behavior

### Live Mode

- consume analytics endpoints directly
- normalize payload shape differences in the frontend
- show warning/empty states when analytics are incomplete
- do not silently fall back to fake local analytics in live mode

### Demo Mode

- local constants are still allowed so the page remains usable without a backend

## Current Rendering Expectations

### Polarization

- render a round-by-round time series
- show an empty state when there is no usable data
- severity labeling is derived from the normalized payload

### Opinion Flow

- initial and final stance buckets
- flow bands between buckets

### Key Opinion Leaders

Each leader card should prefer:

- agent name
- stance
- influence score
- concise top-viewpoint summary

It should not render raw serial ids when a name is available, and it should not mistake raw post titles like “Analysis Question 3” for the agent’s viewpoint summary when better data exists.

### Viral Posts

Each post card should prefer:

- author name
- stance
- readable title/body
- nested comment summaries
- engagement counts

## Notes

- some sessions may legitimately have sparse analytics if the simulation produced too little structured signal
- repeated near-identical comments are a simulation-quality issue, not an analytics-UI requirement
