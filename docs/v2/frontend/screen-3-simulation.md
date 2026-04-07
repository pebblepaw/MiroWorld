# Screen 3 — Simulation

## Overview

Screen 3 renders the live social feed and the simulation status rail. It is backed by native OASIS output, checkpoint metrics, and streamed/polled session state.

## Current Runtime Contract

### Start + Status

- `POST /api/v2/console/session/{id}/simulate`
- `GET /api/v2/console/session/{id}/simulation/state`
- `GET /api/v2/console/session/{id}/simulation/metrics`
- `GET /api/v2/console/session/{id}/simulation/stream`

### Primary UI Areas

- rounds card
- controversy control
- live feed
- hottest thread
- elapsed time
- activity counters
- dynamic metric cards

## Current Behavior

### Initial Posts

New simulations should seed discussion from the session’s analysis questions only.

Important:

- generic “Policy Kick-Off” threads are obsolete for new runs
- each seed post should still include policy/document context so agents know what they are discussing

### Dynamic Metrics

Metric cards are generated only from quantitative analysis questions:

- thresholded `scale` questions render percentages
- `yes-no` questions render percentages
- unthresholded `scale` questions render `/10`
- `open-ended` questions do not produce numeric cards

### Controversy Boost

The current UI is a binary switch:

- off = `0.0`
- on = `0.5`

This is the current implemented behavior and should be documented instead of the earlier full 0.0–1.0 slider plan.

### Error Handling

- the frontend should show short explanatory simulation errors
- raw traceback text, subprocess dumps, and log paths should stay out of the main UI
- backend logs remain the place for full diagnostics

### Navigation Persistence

The simulation feed is mirrored into app context. Navigating back to earlier screens within the same session should not wipe the feed and counters.

## Feed Expectations

Each thread should render:

- author name
- basic persona subtitle
- post title/body
- likes, dislikes, comments
- visible comments when expanded

Repeated cloned replies are a simulation-quality issue, not a rendering feature.
