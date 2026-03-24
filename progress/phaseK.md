# Phase K — Screen 2 Redesign

**Intent:** Revamp Screen 2 (Agent Configuration & Sampling) to improve data visualization clarity, remove AI-slop anti-patterns, and provide a superior interactive cohort graphing experience.

**Inputs:** Existing `frontend/src/pages/AgentConfig.tsx` and underlying console API.
**Outputs:**
- Refactored `AgentConfig.tsx` without `GlassCard` wrappers and hero metrics.
- Horizontal BarChart for Industry Mix.
- Leaflet Choropleth Map for Top Planning Areas (`SingaporeMap.tsx`).
- Large Interactive Scatter Plot pane with demographic toggles replacing the network graph.
- Shadcn Tooltips for Semantic Rerank.

**Acceptance Criteria:**
- "Sample Seed" is hidden from primary metrics.
- Industry Mix text is fully legible.
- Planning Area Map renders accurately with color shading by count.
- Network Graph is completely replaced by a grouped scatter plot / Waffle Chart Grid.
- Side toggles allow reorganizing the Waffle Chart grid by Age, Industry, Area, Gender, Occupation.
- Pass UI Audit principles (no generic glassmorphism).
- The Waffle Chart supports extremely clear density visualization without node overlap.
- Tooltips surface 10+ parsed fields per persona (Age, Sex, MS, Location, Education, Industry, Culture, Mock Salary, Skills, Hobbies, Career Goals, Rationale Score).
- The viewport limits are massively expanded (up to 1200px height) to allow the grid chunks to breathe.
