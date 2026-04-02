# Phase H — Screen 1 Frontend V2 Adoption & Graph Hardening

## Goal
Adopt the new Frontend V2 shell for McKAInsey Screen 1, connect it to the live backend, harden the Stage 1 knowledge graph so the UI reflects real LightRAG output, and make the graph readable and auditable enough to serve as the source of truth for later screens.

## Current Status
Completed and live-verified on branch `codex/frontend-v2-screen1`.

## Tasks
- [x] H1 Archive the previous frontend and replace `frontend/` with the Frontend V2 codebase
- [x] H2 Wire Screen 1 `PolicyUpload` to the live `/api/v2/console` Stage 1 endpoints
- [x] H3 Support real uploaded file parsing for PDF, DOCX, TXT, MD, HTML, JSON, CSV, YAML
- [x] H4 Replace the old presentation-only graph path with a LightRAG-native graph adapter
- [x] H5 Add Screen 1 display taxonomy, facet metadata, and node importance metrics
- [x] H6 Add Screen 1 graph controls, filters, and visibility rules to the new UI
- [x] H7 Fix relation-label toggle behavior so it hides text but not edge lines
- [x] H8 Live-verify Screen 1 using the CNA shrinking birth rate sample

## Completed Work

### Frontend V2 Adoption
- The old frontend was archived and the V2 frontend became the active app in `frontend/`.
- Screen 1 now uses real session creation plus multipart upload against `/api/v2/console/session/{id}/knowledge/upload`.
- The `Guiding Prompt` field is live and sent as `guiding_prompt`.
- The `Generate / Extract` flow now returns real graph artifacts instead of mock data.

### Supported Document Types
- Screen 1 accepts:
  - `.pdf`
  - `.docx`
  - `.doc`
  - `.txt`
  - `.md`
  - `.markdown`
  - `.html`
  - `.htm`
  - `.json`
  - `.csv`
  - `.yaml`
  - `.yml`
- The parsed artifact records `file_name`, `file_type`, `text_length`, and `paragraph_count`.

### LightRAG Graph Source
- Stage 1 now prefers the native LightRAG entity graph when available.
- The old fallback extraction path remains only as backup if native LightRAG graph records are unavailable.
- The Screen 1 graph is therefore aligned to LightRAG extraction rather than a separate UI-only graph generator.

### Entity Families And Facets
- Screen 1 keeps one audited graph with two practical families:
  - `document` entities: policies, institutions, people, places, issues, metrics, events, concepts
  - `facet` entities: nodes with Nemotron-aligned `facet_kind`
- Current facet families are driven by controlled matching to the local Nemotron schema:
  - `planning_area`
  - `age_cohort`
  - `sex`
  - `education_level`
  - `marital_status`
  - `occupation`
  - `industry`
  - `hobby`
  - `skill`

### Facet Inference Logic
- `planning_area` remains exact-label only.
- Other facets use controlled label-based matching, not open-ended description matching.
- This was tightened after live verification because description-based matching created false positives on named people and photo-credit entities.
- Named people / credit-style labels are explicitly suppressed from facet inference.
- This keeps valid cases like `Elderly People` while preventing mis-tags such as journalist names becoming age cohorts.

### Display Buckets
- Screen 1 renders backend-produced `display_bucket` values for filtering and legend display.
- Visible buckets are:
  - `Organization`
  - `Persons`
  - `Location`
  - `Age Group`
  - `Event`
  - `Concept`
  - `Industry`
  - `Other`
- `Persons` is the display bucket for person / people / demographic / population / group-like entities.
- `Age Group` is the display bucket for `age_cohort` facet nodes.
- `Other` is the catch-all bucket for nodes outside the named display categories.

### Screen 1 Filters And Controls
- The graph has a distinct segmented family control:
  - `All`
  - `Nemotron Entities`
  - `Other Entities`
- `Nemotron Entities` means `facet_kind != null`.
- `Other Entities` means no Nemotron-aligned facet metadata.
- The family control is separate from the bucket filters to make the distinction clear.
- Bucket filters are rendered on a second row below the segmented control.
- Zero-count buckets are hidden.
- Relationship labels are controlled by a separate toggle:
  - edge lines always remain visible
  - only the edge text labels turn on/off

### Node Sizing And Importance
- Node size is driven by a hybrid importance metric:
  - `70%` deduplicated `support_count`
  - `30%` graph `degree_count`
- The backend computes:
  - `support_count`
  - `degree_count`
  - `importance_score`
- The frontend uses that score to size the graph dots while keeping labels outside the node body.

### Visibility Rules
- The backend emits three node-quality flags:
  - `generic_placeholder`
  - `low_value_orphan`
  - `ui_default_hidden`
- Visibility logic:
  - generic placeholder nodes are hidden by default
  - low-value orphan nodes are hidden by default only if they are not facet nodes
  - isolated facet nodes remain visible
- Hidden nodes are preserved in the artifact for audit and future retrieval logic.
- `Top 3 Entities` excludes `ui_default_hidden` nodes.

### Generic Placeholder Rules
- Examples of generic placeholder labels include:
  - `Concept`
  - `Event`
  - `Organization`
  - `Person`
  - `People`
  - `Entity`
  - `Policy`
  - `Program`
  - `Service`
  - `Data`
- These are treated as artifact-preserved but graph-hidden noise unless later product requirements demand an explicit reveal mode.

## Live Verification Evidence
- Live launcher:
  - `./quick_start.sh --mode live`
- Real Screen 1 upload sample:
  - `Sample_Inputs/CNA SHrinking Birth Rate.docx`
- Verified live artifact:
  - `75` entities
  - `50` relationships
  - `8` paragraphs
  - `Concept` preserved in the payload as `generic_placeholder=true` and `ui_default_hidden=true`
  - `Nemotron Entities` populated with one meaningful visible facet node:
    - `Elderly People` → `age_cohort:senior`
- Browser spot-check:
  - Screen 1 successfully loaded the live artifact
  - clicking `Nemotron Entities` no longer produced an empty graph state
  - the filtered view collapsed to the `Age Group` facet view for the CNA sample

## Decisions Made
- The Screen 1 graph must stay coupled to native LightRAG output.
- Description-driven facet inference was rejected for now because it produced poor live results on named entities.
- Hidden nodes remain in the artifact; the UI hides them by default.
- `Other` remains a display bucket, not a semantic category.

## Open Issues
- The CNA sample currently yields only one meaningful Nemotron-aligned facet node.
- This is acceptable for Screen 1 correctness, but Screen 2 will need stronger document-to-persona matching logic than Stage 1 facet extraction alone.
- The current UI has no explicit “show hidden nodes” mode; hidden nodes are artifact-visible but UI-hidden.

## Next Actions
- Use the Screen 1 graph as the source input for Screen 2 candidate retrieval.
- Define Screen 2 sampling modes and scoring logic before implementation.
- Reuse the Screen 1 graph visual language for the Stage 2 agent graph.
