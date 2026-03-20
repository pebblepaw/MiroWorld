

## STITCH — Policy Sentiment Simulation Platform

A futuristic, dark-themed consulting tool for Singapore government that simulates public opinion on policy documents using AI agents. The design features glassmorphism, bold accent colors (cyan/teal primary, amber secondary), dark navy/charcoal backgrounds, and glowing UI elements.

### Navigation & Layout
- **Sidebar** with collapsible icon mode, showing 5 steps with icons and labels (Upload → Agents → Simulation → Analysis → Chat)
- **Step progress indicator** at the top of the main content area showing current phase (1/5, 2/5, etc.) with a connected progress bar
- Steps unlock sequentially — completed steps are clickable, future steps are locked/dimmed
- App name "STITCH" with a subtle logo in the sidebar header

### Design System
- Dark background (near-black navy `#0a0e1a`) with subtle grid/dot pattern
- Glassmorphic cards: semi-transparent backgrounds with backdrop blur, subtle glowing borders
- Primary accent: cyan/teal (`#00d4ff`), Secondary: amber (`#f59e0b`), Success: emerald, Danger: rose
- Typography: Inter or similar clean sans-serif, with monospace accents for data labels
- Animated gradient borders and subtle pulse effects on active elements
- All charts and graphs use the accent color palette against dark backgrounds

---

### Screen 1: Policy Upload & Knowledge Graph
- **Left panel**: Drag-and-drop file upload zone (PDF, DOCX) with animated border, a text area for the "guiding prompt" (what to extract from the policy), and an "Extract" button
- **Right panel**: Interactive force-directed knowledge graph (using react-force-graph-2d) showing entities as glowing nodes (color-coded: policies=cyan, institutions=amber, people=emerald) and edges as labeled relationship lines
- Nodes are draggable with hover tooltips showing entity details
- Graph populates with mock data after "extraction" — animated node appearance
- Stats bar below: entity count, relationship count, document pages processed

### Screen 2: Agent Configuration & Agent Graph
- **Top section**: Slider to select number of agents (100–5000) with real-time demographic breakdown
- **Demographics panel**: Bar charts / donut charts showing distribution by age group, occupation, planning area, ethnicity, income bracket — all using mock Nemotron-style Singaporean demographic data
- **Bottom section**: Force-directed Agent Graph showing agent clusters by planning area, with cluster nodes sized by population count
- Hovering a cluster shows demographic summary of that group
- "Generate Agents" button with loading animation, then "Proceed to Simulation" button

### Screen 3: Social Media Simulation (OASIS)
- **Config bar at top**: Round selector (1–10 rounds), estimated time display, "Start Simulation" button
- **Main area**: Live-updating Reddit-style thread feed showing top posts per round
  - Each post shows: agent avatar (generated initials), agent name + demographic tag, post title, upvote/downvote counts, comment count, timestamp
  - Expandable comment threads under each post
  - Posts stream in with subtle slide-up animations
- **Sidebar stats panel**: Current round indicator, total posts, total comments, sentiment gauge (positive/neutral/negative donut), top trending topics as tags
- Round progress bar with live counter
- All data is mocked with realistic Singapore policy discussion content
- "Complete & Generate Report" button appears when simulation finishes

### Screen 4: Analysis Dashboard (3 tabs)
**Tab 1 — Planning Area Map**
- Custom SVG map of Singapore's 55 planning areas
- Color-graded heatmap: green (high approval) → yellow → red (low approval)
- Hover shows planning area name + approval % + agent count
- Legend and overall approval score displayed
- Click a planning area to see demographic breakdown of sentiment

**Tab 2 — Report & Key Insights**
- Split layout: left side has the full generated report (markdown rendered with sections, headers, blockquotes — styled like the MiroFish reference)
- Right side: Key Insights cards — top 5 findings as numbered glassmorphic cards with icons, headline, and brief description
- Report has a table of contents that auto-scrolls

**Tab 3 — Most Influential Posts**
- Ranked list of the most impactful posts from the simulation
- Each shows: rank badge, post content, author demographic, upvotes, reply count, influence score bar
- Clicking a post expands the full thread

### Screen 5: Agent Chat
- **Left panel**: Searchable/filterable agent list with avatar, name, occupation, planning area, and sentiment indicator (colored dot)
- Filters: by planning area, by sentiment, by occupation
- **Right panel**: Chat interface with the selected agent
- Chat bubbles styled with glassmorphic treatment
- Agent responses are mocked with realistic persona-based replies about the policy
- Shows agent's demographic card at top of chat panel
- Supports switching between agents while preserving chat history per agent

### Mock Data Strategy
All screens use pre-built realistic mock data:
- Policy content about Singapore HDB housing policy
- ~500 mock agent profiles with Singaporean demographics
- Pre-generated Reddit threads discussing housing affordability
- Pre-written report with insights about public sentiment on housing policy
- Pre-scripted agent chat responses based on demographic persona

