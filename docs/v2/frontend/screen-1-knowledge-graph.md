# Screen 1 — Knowledge Graph

## Overview

Screen 1 handles document ingestion and question definition. The left rail manages uploads and `analysis_questions`; the right panel renders the extracted graph.

This screen is no longer centered around a user-facing guiding prompt. The main runtime object is the session-scoped `analysis_questions` array.

## Main Responsibilities

1. Load the current session’s analysis questions
2. Allow add/edit/delete for custom questions
3. Generate metadata for custom questions
4. Persist the normalized question list back to session config
5. Run knowledge extraction on uploaded documents
6. Render the merged graph artifact

## Current Question Workflow

### Preset Questions

- seeded from the active session
- initially come from the canonical use-case YAML
- marked as preset in the UI

### Custom Questions

- can be added, edited, and removed on Screen 1
- use `POST /api/v2/questions/generate-metadata`
- metadata generation infers:
  - `type`
  - `metric_name`
  - `metric_label`
  - `metric_unit`
  - `threshold` when relevant
  - `report_title`
  - `tooltip`

### Persistence

- the current question list is persisted through `PATCH /api/v2/session/{id}/config`
- later screens must consume this persisted question list, not re-read raw YAML

## Knowledge Ingestion Paths

### Supported Inputs

- file upload
- URL scrape
- pasted text

### Runtime Endpoints

- `POST /api/v2/console/session/{id}/knowledge/process`
- `POST /api/v2/console/session/{id}/knowledge/upload`
- `POST /api/v2/console/session/{id}/scrape`
- `GET /api/v2/session/{id}/analysis-questions`

## Current Extraction Behavior

- multiple documents are merged into one knowledge artifact
- metadata generation for questions runs in parallel with extraction
- live mode does not fabricate extraction output
- live failures should surface short provider/runtime messages
- demo mode may still hydrate a cached artifact when the backend is unavailable

## Graph Expectations

- draggable force graph
- bucket/type filtering
- optional relationship labels
- stats row based on the merged artifact

## Compatibility Notes

- a backend `guiding_prompt` field still exists for extraction compatibility
- the frontend currently derives that compatibility prompt from the active analysis question text when needed
- this compatibility field should not be treated as the product-level source of truth
