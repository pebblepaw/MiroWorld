# Frontend Status Check — Updated 2026-04-09

This file is retained as a lightweight implementation-status note. The per-screen specs are authoritative; this file summarizes the current frontend state after the live linking, bug-fix, and multi-metric passes.

## Current Status

### Screen 0

- Live country/provider/model hydration is implemented
- Canonical V2 use cases are used in the onboarding flow
- Current Gemini defaults prefer active models

### Screen 1

- Analysis questions are session-scoped
- Custom questions persist back to session config
- Metadata generation and extraction run in parallel
- Live extraction shows short runtime/provider errors

### Screen 2

- Dynamic filter rendering is wired to backend data
- Token estimate display is live

### Screen 3

- Live simulation status, feed, and counters are wired
- New runs seed from analysis questions, not a generic- New runs seed from analysis questions, not a generic- New runs seed from analysis questions, not a d directly
- Names are preferred - Names are preferred - Names are preferred -ath- Names are preferred - Names are preferred - Names are preferred -ath- Names are preferred - Names are preferred - Names are preferred -ath- Names are preferred - Names are preferred - Names are preferred -ath-senter/1:1 segment tab- Namefunction- Names are preferred - Names are preferred - Names ng - Names are preferred - Names are preferred - Namesds liv- Names are preferred - Names are preferred * filters polarization, opinion flow, and demographic sentiment map
- Polarization and opinion flow refetch - Polarization and opinion flow refetch - Polarizoint- Polarization and opinion flow refetch - Polarizatiomplete-data warning states are present
- Leader and viral-post cards normalize names and viewpoint summaries
- Influence and cascade sections are metric-agnostic and do not refetch on metric change

## Remaining Quality Watchouts

- Older sessions can still display pre-fix historical artifacts
- Analytics quality still depends heavily on simulation quality and checkpoint signal
- Any future screen-level behavior changes should update the corresponding screen spec immediately
- `opinion_pre`/`opinion_post` on the agents table are always 10.0 in current simulations — analytics and chat scoring use checkpoint-based data instead
