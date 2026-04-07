# Screen 4 — Report + Chat

> **Paper MCP References**: Artboards `NW-0` (Option A 60/40 split), `CZ-0` (Option B drawer), `PN-0` (Option C full-page chat)
> **UserInput Refs**: F1–F6
> **Final Decision**: 60/40 split layout with three-way view toggle

## Overview

The Report+Chat screen replaces the old separate Analysis and AgentChat pages. It combines the report and interactive focus group into a single unified experience with a view toggle.

## View Toggle (Segmented Control)

A three-way segmented control in the header bar:

| Mode | Left Panel | Right Panel | When to use |
|:-----|:-----------|:------------|:------------|
| **Report Only** | Full-width report | Hidden | Reading/exporting report |
| **Report + Chat** | 60% width report | 40% width chat | Default — simultaneous reading and questioning |
| **Chat Only** | Hidden | Full-width chat with sidebar | Deep-dive conversations |

The toggle is a `<SegmentedControl>` component with three buttons. Current mode stored in component state.

## Layout: Report + Chat Mode (Default)

```
┌────────────────────── 1440px ──────────────────────┐
│  Header: "Analysis Report" + [Toggle] + [Export]   │
├────────────── 60% ──────────┬──────── 40% ─────────┤
│  Report Panel               │  Chat Panel          │
│  (scrollable)               │  (fixed input bar)   │
└─────────────────────────────┴──────────────────────┘
```

## Report Panel

### 1. Header
- Title: "Analysis Report"
- Subtitle: "{Country} · {Use Case} · {n} agents · {rounds} rounds"
- Buttons: View Toggle + "Export DOCX"

### 2. Executive Summary Card
- Icon badge + "EXECUTIVE SUMMARY" label
- Narrative paragraph: LLM-generated summary of simulation results
- **Quick stats row** (below divider):
  - Initial metric value (green) → arrow → Final metric value (red)
  - Total agents simulated
  - Shows dramatic shift clearly

### 3. Report Sections (Generated from Guiding Prompts — F2)

The report structure mirrors the guiding prompts from Screen 1. Each prompt becomes a report section:

```
Section 1: [Guiding Prompt 1 question] → [LLM answer with evidence]
Section 2: [Guiding Prompt 2 question] → [LLM answer with evidence]
...
Section N: [Guiding Prompt N question] → [LLM answer with evidence]
```

Each section includes:
- Section title (the original guiding prompt question)
- Narrative answer (LLM-generated)
- Evidence citations: post IDs, agent IDs, excerpt quotes

### 4. Supporting vs Dissenting Views

Two side-by-side cards:
- **Supporting Views** (green header): Top arguments in favor
- **Dissenting Views** (red header): Top arguments against
- Each view is a bullet point pulled from actual agent posts
[#NEW User Input: this wouldn't make sense for the other use cases e.g. finding product market fit. Let's just remove it.]

### 5. Additional Report Sections
- **Demographic Breakdown**: Approval/score by demographic group
- **Key Recommendations**: LLM-generated action items based on simulation results
- **Methodology**: How the simulation was configured (agents, rounds, controversy boost, model)
[#NEW User Input to frontend agent: This is actually already in Screen 5 Analytics, as the grid, so maybe we can safely remove this from this Screen]

## Chat Panel

### Component: `ChatPanel.tsx`

#### Chat Header
- "Agent Chat" + mode badge ("Group" in purple)
- Close button (×) — hides chat, switches to Report Only mode

#### Segment Tabs
Row of tabs to switch chat groups:
- **Top Dissenters** (active/purple) — top 5 most influential agents with negative stance
- **Top Supporters** — top 5 most influential agents with positive stance
- **1:1 Chat** — dropdown to select individual agent

Selection algorithm (from BRD §3.11):
```
influence = 0.4 × normalized_post_engagement
          + 0.3 × normalized_comment_count
          + 0.3 × normalized_reply_received
```

#### Chat Messages

**User messages**: Right-aligned, orange-tinted bubble
**Agent messages**: Left-aligned with:
- Avatar (colored by stance): initials
- Name + role label ("Tan Li Wei · Dissenter")
- Message bubble (dark bg)

In **Group mode**: Multiple agents respond to each user question. Each agent maintains its persona and refers to its simulation posts/opinions as context.

#### Input Bar
- Text input: "Ask the group a question..."
- Send button (orange circle with arrow)
- Endpoint: `POST /api/v2/console/session/{id}/chat/group` with `{segment, message}`

### Agent Click → Side Panel (`AgentSidebar.tsx`) — F5

When any agent name/avatar is clicked in posts or chat:
- Slide-in panel from right (overlays or pushes content)
- Shows:
  - Agent avatar (large) + name + verified badge (if name confirmed)
  - Demographics: Age, occupation, location/area, income bracket
  - **Core viewpoint**: LLM-generated 1-sentence summary of their stance
  - **Stance score**: Visual indicator (1-10 scale, colored)
  - **Key posts**: List of their most-engaged posts/comments with vote counts
  - **"Chat 1:1"** button → Opens direct 1:1 conversation

## Layout: Chat Only Mode

When toggle is set to "Chat Only", the chat panel expands to full width and shows:
- Left sidebar (320px): Group segments list + 1:1 Agent Chat list (see Paper MCP artboard `PN-0`)
- Main area: Full-width chat with larger message bubbles, more context

This matches the "Screen 6 — Full Page Chat (Option C)" mockup.

## DOCX Export — F6

**Button**: "Export DOCX" in header
**Endpoint**: `GET /api/v2/console/session/{id}/report/export`
**Implementation**: `python-docx` server-side:
- Cover page: McKAInsey logo, country, use case, date, agent count
- Executive Summary section
- Each guiding prompt section with answers
- Supporting/Dissenting views
- Demographic breakdown table
- Methodology section
- Embedded chart images (polarization, etc.) rendered as PNG server-side

## Backend Requirements

### Modified: `report_service.py`
- Implement **plan-first ReportAgent** pattern:
  1. LLM generates analysis plan (list of sections to cover)
  2. Backend executes deterministic metric calculations
  3. LLM synthesizes narrative for each section, citing evidence post/agent IDs
- Structure report around guiding prompts from config

### New: `routes_analytics.py` (or extend `routes_console.py`)
- `GET /api/v2/console/session/{id}/report` → Full report JSON
- `GET /api/v2/console/session/{id}/report/export` → DOCX binary download
- `POST /api/v2/console/session/{id}/chat/group` → `{segment, message}` → array of agent responses
- `POST /api/v2/console/session/{id}/chat/agent/{agent_id}` → 1:1 response

### Tests

**Frontend**:
- [x] View toggle switches between 3 modes correctly
- [x] Report scrolls independently from chat
- [x] Chat messages display with correct alignment and styling
- [x] Segment tabs switch chat groups
- [x] Agent click opens side panel with correct data
- [x] DOCX export triggers file download
- [x] Report sections correspond to guiding prompts

**Backend**:
- [x] ReportAgent generates plan before metrics
- [x] Report sections map to guiding prompt questions
- [x] Group chat returns responses from top-N agents in segment
- [x] 1:1 chat maintains agent persona context
- [x] DOCX export includes all sections and is valid .docx
