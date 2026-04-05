# Screen 1 — Knowledge Graph (Document Upload)

> **Paper MCP Reference**: Artboard `F6-0` ("Screen 1 — Knowledge Graph (V2)")
> **UserInput Refs**: C1, C2, C3, A5

## Overview

Two-panel layout. Left: document upload controls, guiding prompts, and extraction stats. Right: interactive force-directed knowledge graph visualization.

## Layout

```
┌─────────────── 1440px ─────────────────┐
│  ┌──── 480px ────┐  ┌──── flex:1 ────┐ │
│  │  Left Panel   │  │  Graph Panel   │ │
│  │  - Upload     │  │  Interactive   │ │
│  │  - Prompts    │  │  Force Graph   │ │
│  │  - Actions    │  │                │ │
│  │  - Stats      │  │                │ │
│  └───────────────┘  └────────────────┘ │
└────────────────────────────────────────┘
```

## Left Panel

### 1. Header
- Title: "Document Upload"
- Subtitle: "Upload policy documents to build a knowledge graph using LightRAG"

### 2. Use-Case Badge
- Small pill showing current use case + country: `Policy Review · Singapore`
- Read-only indicator (set in onboarding)

### 3. Upload Zone (`MultiDocUpload.tsx`)
- **Drag-and-drop area** with dashed green border
- Supported formats: PDF, DOCX, TXT, MD, HTML, JSON, CSV, YAML
- **Multi-file support**: Each uploaded file shows as a row with:
  - File icon + filename
  - File size
  - Progress bar during upload/parsing
  - Remove (×) button
- **URL scraper**: Input field at bottom — paste URL → backend fetches + parses
  - Endpoint: `POST /api/v2/console/session/{id}/scrape` with `{url: string}`
- **Paste text**: "Or paste text directly" — expandable textarea
  - Submits as inline document to the same upload pipeline

### 4. Guiding Prompt Card
- Title: "Guiding Prompt"
- Content: Pre-populated from `config/prompts/{use_case}.yaml → guiding_prompt`
- **Editable**: User can modify the text before extraction
- Custom prompts: "Add custom prompt" button → appends new editable text field

### 5. Action Buttons (side by side)
- **"Extract Knowledge Graph"** (orange, primary): Triggers LightRAG extraction
  - Merges graphs from all uploaded documents into one combined graph
  - Endpoint: existing upload + LightRAG pipeline
- **"Proceed →"** (green, secondary): Navigate to Screen 2

### 6. Stats Row
After extraction completes, show:
- **Entities**: count (e.g., "47")
- **Relations**: count (e.g., "83")
- **Paragraphs**: count (e.g., "12")

## Right Panel — Knowledge Graph

### Component: `InteractiveKnowledgeGraph.tsx`

- **Force-directed graph** using D3.js or react-force-graph
- **Node colors by type**: Organization (gray), Persons (green), Location (amber), Concept (cyan)
- **Draggable nodes**: User can click and drag nodes to explore the graph
  - Reference: This feature existed in the deprecated frontend V2: https://github.com/pebblepaw/Nemotron-Frontend-V2.0
- **Legend**: Color-coded at top-right corner
- **Filter chips** below header: "All" (active/orange), "Nemotron Entities", "Other"
  - Matches existing filter system from V1 (bucket filters)
- **Bottom-right hint**: "Interactive Force Graph · Drag nodes to explore"

### Backend Requirements
- Existing LightRAG pipeline handles extraction
- `POST /api/v2/console/session/{id}/scrape` — NEW endpoint for URL scraping
  - Uses `requests` + `BeautifulSoup` to fetch and extract text from URLs
  - Returns `{text: string, title: string, length: number}`
- Multi-file merge: When multiple documents are uploaded, LightRAG processes each and merges entity/relation lists into a single graph

### Tests

**Frontend**:
- [ ] Drag-and-drop adds files to upload list
- [ ] Progress bars show during upload
- [ ] Multiple files display simultaneously
- [ ] URL scraper input accepts URLs and shows scraped content
- [ ] Paste-text area submits correctly
- [ ] Guiding prompt is pre-populated from config
- [ ] Guiding prompt is editable
- [ ] Graph nodes are draggable
- [ ] Filter chips filter visible nodes
- [ ] Stats row updates after extraction

**Backend**:
- [ ] URL scraper handles valid URLs and returns text
- [ ] URL scraper returns 400 for invalid URLs
- [ ] Multi-file upload merges graphs correctly
- [ ] Guiding prompt loads from YAML config
