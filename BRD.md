# BRD — McKAInsey: AI-Powered Population Simulation Consulting Service

## 1. Vision and Objectives

McKAInsey is a cloud-hosted SaaS platform that uses census-calibrated synthetic personas to simulate how segments of the Singaporean population would react to proposed policies or marketing campaigns. It enables policymakers and enterprise strategists to A/B test initiatives in a risk-free digital environment before real-world deployment.

**Primary Objectives:**
1. Deliver a working multi-agent simulation platform that produces measurable approval/dissent metrics for any uploaded policy or campaign document
2. Demonstrate a realistic AWS cloud architecture suitable for an academic cloud computing course submission
3. Provide two distinct output stages: immediate individual reactions and post-social-deliberation opinion shifts
4. Enable interactive post-simulation exploration via a ReportAgent and individual agent chat

**Differentiators vs. existing tools (e.g., MiroFish):**
- Census-calibrated personas (NVIDIA Nemotron-Personas-Singapore, 888K records) — not LLM-generated
- AWS-native cloud architecture with multi-cloud integration (Zep Cloud)
- Singapore-specific focus with all 55 planning areas represented

---

## 2. Problem Statement

Traditional market research and policy consultation is:
- **Slow**: Focus groups take weeks to recruit, conduct, and analyse
- **Expensive**: A single McKinsey engagement costs $500K+; focus groups cost $5K–$15K per session
- **Declining in reliability**: Survey participation rates have dropped below 6% in many markets
- **Static**: Captures only initial reactions, not how opinions evolve through social interaction

LLMs alone are insufficient because they produce homogenized, alignment-biased responses that average away the diversity of real populations. The solution requires coupling LLMs with statistically grounded demographic data and a social simulation framework.

---

## 3. Scope / Non-Goals

### In Scope (MVP)
- LightRAG document processing (entity/relationship extraction from policy documents)
- OASIS-powered multi-agent social simulation on EC2
- Two-stage output: immediate reactions → post-deliberation shifts
- Zep Cloud for agent temporal memory
- ReportAgent for structured post-simulation analysis with tool access
- Interactive chat with individual agents (highlight most influential agents)
- React dashboard with demographic friction heatmaps, opinion-shift charts, consensus tracking
- Gemini 2.0 Flash as LLM backbone with context caching
- Nemotron-Personas-Singapore dataset on S3 with DuckDB filtering via Lambda

### Non-Goals
- PPTX slide deck generation
- Image generation (Nano Banana / any visual synthesis)
- UN-style diplomatic simulation
- Observer agents
- Automated continuous monitoring / real-time streaming
- Mobile app
- Multi-language persona support (English only for MVP)
- User authentication / multi-tenancy (single-user prototype)

### Stretch Goals (if time allows)
- Replace Zep Cloud with self-hosted Graphiti + FalkorDB on EC2
- Custom OASIS actions beyond the default 23 (e.g., "petition", "rally")
- Multiple simulation runs with persistent cross-session memory (personas remember past policies)

---

## 4. Success Metrics

| Category | Metric | Target |
|:---------|:-------|:-------|
| **System Performance** | End-to-end simulation latency (50 agents, 10 steps) | < 3 minutes |
| **System Performance** | Maximum concurrent agents before bottleneck | ≥ 500 |
| **Cost Efficiency** | Cost per full simulation (500 agents × 20 steps) | < $2.00 |
| **Cost Efficiency** | Savings from context caching vs uncached baseline | ≥ 50% |
| **Simulation Quality** | Measurable opinion shift between Stage 1 and Stage 2 | Statistically significant (p < 0.05 across 3+ runs) |
| **Simulation Quality** | Persona differentiation (response variance across demographics) | Standard deviation > 0 across age/income/planning area cohorts |
| **Simulation Quality** | Correlation between agent opinions and socio-economic attributes | Detectable patterns (e.g., income-sensitive personas react more to cost-related policies) |
| **User Experience** | ReportAgent produces structured insights within 60s of simulation end | Yes |
| **User Experience** | Interactive agent chat responds in < 5s | Yes |

---

## 5. Constraints and Assumptions

### Constraints
- **Cloud provider**: AWS only (course requirement), with Zep Cloud as the sole external service
- **LLM**: Gemini API (free credits available; ~$100 budget for project)
- **Dataset**: NVIDIA Nemotron-Personas-Singapore (888K personas, 38 fields, Parquet format)
- **Team**: 5 members, primarily automated by coding agents
- **Submission deadline**: April 19, 2026
- **Proposal page limit**: 4 pages (intermediate proposal already submitted)

### Assumptions
- Gemini API remains available with current pricing and OpenAI SDK compatibility
- OASIS library (`camel-oasis`) is stable for Reddit-mode simulation with Gemini backend
- Zep Cloud free tier is sufficient for project-scale simulations (~500 agents per run)
- Nemotron dataset accurately represents Singapore census distributions
- End users have basic familiarity with demographic segmentation concepts

---

## 6. Tech Stack and Rationale

| Component | Tool | Rationale |
|:----------|:-----|:----------|
| **Cloud Provider** | AWS (S3, Lambda, EC2) | Course requirement; S3 for cold storage, Lambda for serverless filtering, EC2 for persistent compute |
| **LLM** | Gemini 2.0 Flash | Free credits, context caching (90% token discount), OpenAI SDK compatible for OASIS |
| **Persona Dataset** | Nemotron-Personas-Singapore on S3 (Parquet) | 888K census-calibrated personas, 38 fields, columnar format for efficient querying |
| **Query Engine** | DuckDB on Lambda | In-process analytical engine; queries S3 Parquet directly via HTTP range requests without loading full dataset |
| **Document Processing** | LightRAG | Combines knowledge graph extraction with vector retrieval; lighter than microsoft/graphrag; supports Gemini |
| **Simulation Engine** | OASIS (camel-oasis) on EC2 | Battle-tested social simulation platform (Reddit/Twitter-like); 23 action types; recommendation system; up to 1M agents |
| **Agent Memory** | Zep Cloud (stretch: Graphiti + FalkorDB) | Temporal knowledge graph with validity windows; auto-summarization; hybrid retrieval; free tier |
| **Frontend** | React + ECharts on EC2 | High-performance charting (Canvas rendering, 100K+ data points); co-hosted with Python API backend |
| **Report Generation** | ReportAgent (dedicated LLM with tool access) | Post-simulation analysis agent that queries simulation DB, computes metrics, generates structured insights |

Full rationale and alternatives considered: see [decision_log.md](docs/decision_log.md)

---

## 7. Project Structure Details

### System Architecture (3 tiers)

```
┌─────────────────────────────────────────┐
│  Tier 1: Frontend & Application Layer   │
│  ┌───────────────────────────────────┐  │
│  │ EC2 Instance                      │  │
│  │ ├── React Dashboard (ECharts)     │  │
│  │ ├── Python API Backend            │  │
│  │ ├── OASIS Simulation Engine       │  │
│  │ └── ReportAgent                   │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│  Tier 2: Data & Filtering (Cold)        │
│  ┌──────────────┐  ┌────────────────┐   │
│  │ AWS Lambda    │  │ Amazon S3      │   │
│  │ + DuckDB      │──│ Nemotron       │   │
│  │ (sampling)    │  │ Parquet files  │   │
│  └──────────────┘  └────────────────┘   │
├─────────────────────────────────────────┤
│  Tier 3: Memory & External APIs         │
│  ┌──────────────┐  ┌────────────────┐   │
│  │ Zep Cloud    │  │ Gemini API     │   │
│  │ (agent       │  │ (LLM backbone) │   │
│  │  memory)     │  │                │   │
│  └──────────────┘  └────────────────┘   │
└─────────────────────────────────────────┘
```

### Data Flow (5 stages, inspired by MiroFish)

**Stage 1 — Scenario Setup:**
User uploads a policy/campaign document via the React dashboard and defines simulation parameters (agent count, deliberation rounds, demographic filters). LightRAG processes the document into a knowledge graph of entities and relationships.

**Stage 2 — Population Sampling:**
Lambda + DuckDB queries the Nemotron Parquet dataset in S3 using the user's demographic filters. Returns matching personas. Each persona is loaded into OASIS as an agent with their full 38-field demographic profile as their character description.

**Stage 3 — Simulation (Two Stages):**
- **Stage 3a: Immediate Reactions** — Each agent receives the policy (or relevant subgraph from LightRAG) and generates an initial individual opinion. No agent interaction. Results in Stage 1 metrics (raw approval/dissent by demographic).
- **Stage 3b: OASIS Deliberation** — Agents are placed in a simulated Reddit-like discussion forum. They post reactions, read others' posts via the recommendation feed, upvote/downvote, comment, and respond over N rounds. OASIS manages the social dynamics. All agent interactions stored in OASIS SQLite + Zep Cloud memory.

**Stage 4 — Analysis & Report:**
After simulation completes, the ReportAgent (a dedicated LLM with tool access) analyses the simulation database:
- Computes pre-vs-post approval ratings by demographic cohort
- Identifies the most influential agents (those whose posts shifted the most opinions)
- Extracts strongest arguments for and against
- Identifies demographic friction clusters (which planning areas dissent most)
- Generates a structured strategic report

**Stage 5 — Interactive Deep-Dive:**
- **ReportAgent Chat**: User asks follow-up questions ("What would convince the Woodlands dissenters?")
- **Individual Agent Chat**: System highlights the top N most influential agents; user can chat with any one in-character, drawing on its accumulated Zep Cloud memory
- **Dashboard**: Friction heatmaps, opinion-shift timelines, consensus tracker, demographic breakdown charts

### Key Data Models

**Nemotron Persona (38 fields, from Parquet):**
- Demographics: age, gender, ethnicity, religion, marital status, household size
- Socioeconomic: income bracket, occupation, education level, housing type
- Geographic: planning area (1 of 55), region
- Digital: digital literacy score, social media usage, preferred platforms
- Contextual: political leaning, risk tolerance, trust in government, etc.

**OASIS Agent State (per simulation):**
- Agent ID, persona reference, simulation ID
- Posts created, comments made, likes/dislikes given
- Opinion score (numeric, pre and post deliberation)
- Action history per step

**Zep Cloud Memory (per agent per simulation):**
- Episodes: raw interactions (what the agent said, heard, did)
- Entity nodes: extracted concepts (the policy, other agents, specific clauses)
- Fact edges: relationships with time validity (e.g., "opposes toll" valid T1→T2, "cautiously open" valid T2→∞)

**ReportAgent Output Schema:**
- Executive summary (text)
- Approval rates: overall, by demographic cohort, pre vs post
- Top dissenting demographics with reasons
- Most influential agents (ID, persona summary, influence score)
- Key arguments for and against (extracted from simulation posts)
- Recommended mitigations (LLM-generated based on friction analysis)

### Frontend UI Design (Reference: MiroFish)

The dashboard draws strong inspiration from MiroFish's console interface — a dark-themed, stage-driven UI with a persistent workflow sidebar, a dominant visualization panel, and contextual data panels. McKAInsey extends this pattern with Singapore-specific analytics and a richer post-simulation experience.

**Global Layout:**
```
┌────────────────────────────────────────────────────────────┐
│  Top Bar                                                   │
│  [← Back] [McKAInsey Logo]                                 │
│  [📄 Knowledge Graph | 👥 Persona Graph]   ← graph toggle │
│  [Step 3/5 ● Running]  [Settings ⚙]                       │
├──────────┬───────────────────────────┬─────────────────────┤
│ Workflow │   Main Visualization      │  Context Panel      │
│ Sidebar  │   Panel (60%)             │  (25%)              │
│ (15%)    │                           │                     │
│          │  (changes per stage)      │  (changes per       │
│ 🟡 Step 1│                           │   stage)            │
│ 🔵 Step 2│                           │                     │
│ 🟣 Step 3│  Graph toggle persists    │                     │
│ ○ Step 4 │  across all stages        │                     │
│ ○ Step 5 │                           │                     │
├──────────┴───────────────────────────┴─────────────────────┤
│  System Dashboard / Log Console (collapsible)              │
└────────────────────────────────────────────────────────────┘
```

**Two-Graph Toggle (persists across all stages):**

The top bar contains a pill-toggle to switch between two independent graph views:

- **📄 Knowledge Graph** — Force-directed graph of policy entities and relationships extracted by LightRAG. Nodes represent policy concepts, demographic groups, institutions, and geographic areas. Edges represent relationships (e.g., "EV toll" → affects → "low-income commuters" → located in → "Woodlands"). Built during Stage 1, remains accessible throughout all stages for reference.

- **👥 Persona Graph** — Cluster visualization of the sampled agents. Nodes represent individual agents (or demographic clusters). Edges represent shared attributes (same planning area, income bracket, etc.). Appears after Stage 2 sampling. During Stage 3b deliberation, nodes animate to change color as opinions shift — red (oppose) → yellow (neutral) → green (support) — providing a live visual of opinion contagion spreading through the population.

**Stage-by-Stage UI Breakdown:**

**Stage 1 — Scenario Setup** 🟡
| Panel | Content |
|:------|:--------|
| Main | Document upload zone (drag-and-drop PDF/text) + live preview of extracted text. Once processed by LightRAG, transitions to a force-directed knowledge graph showing entities and relationships extracted from the policy document. Nodes colored by entity type (policy, demographic group, institution, geographic area). Entity-type toggles to filter the graph. |
| Context | Simulation settings card: agent count slider (50–1000), deliberation rounds (1–20), platform type (Reddit/Twitter). Below: demographic filter builder — cascading dropdowns for age range, income bracket, planning area, ethnicity, occupation, digital literacy. Live count of matching personas updates as filters change. |
| Log Console | LightRAG processing logs: "Extracting entities... Found 23 entities, 47 relationships." |

**Stage 2 — Population Sampling** 🔵
| Panel | Content |
|:------|:--------|
| Main | The **Persona Graph** auto-activates. Nodes appear with an animated pop-in as agents are sampled from the dataset. Each node is a persona, sized by influence potential (based on digital literacy + social media usage scores). Nodes cluster by planning area with edges showing shared demographic attributes. Hovering a node shows a persona card tooltip (name, age, occupation, planning area, key traits). The Knowledge Graph tab remains accessible for reference. |
| Context | Population statistics: pie charts for age distribution, income brackets, planning areas of the sampled cohort. "Coverage analysis" gauge showing how representative the sample is vs. the Singapore census. Persona count badge: "200 / 888K sampled". |
| Log Console | "Querying 888K personas... Filter: age 25-55, income $3K-$8K, Woodlands/Yishun... Returned 342 matching personas. Sampled 200." |

**Stage 3a — Immediate Reactions** 🟠
| Panel | Content |
|:------|:--------|
| Main | Live bar chart building in real-time as agents submit initial opinions. X-axis: opinion score (1-10 from strongly oppose to strongly support). Y-axis: agent count. Bars color-coded by demographic cohort. Tooltip on hover shows sample agent reasoning. Simultaneously, on the Persona Graph tab, nodes begin coloring by initial opinion: red (1-3), amber (4-6), green (7-10). |
| Context | Summary card: "Approval: 43% / Neutral: 22% / Dissent: 35%". Below: top 3 demographic cohorts by dissent rate with 1-line reasons. Stage 3a completion progress bar. |
| Log Console | "Agent #4821 (Malay, 62, Retired, Woodlands): Score 3/10 — 'Fixed income cannot absorb new toll costs.'" |

**Stage 3b — OASIS Deliberation** 🟣
| Panel | Content |
|:------|:--------|
| Main | **Split view (like MiroFish's dual-platform monitor)**: Left shows a simulated Reddit-like feed with agent posts, comments, and vote counts updating in real-time. Right shows a live opinion-shift line chart — each line is a demographic cohort, x-axis is round number, y-axis is average opinion score. Lines visibly converge or diverge as deliberation progresses. On the **Persona Graph tab**, nodes animate color changes in real-time as agents' opinions shift — watch the red/amber/green spread like contagion through the network. Edges glow briefly when two connected agents interact. |
| Context | Round tracker: "Round 7/15". Stats: total posts, comments, votes this round. "Hottest post" card showing the most-upvoted post with author agent info. "Biggest shifter" card showing the agent whose opinion changed the most. |
| Log Console | "Round 7: 200 agents acted. 43 posts, 127 comments, 312 votes. Net opinion shift: +0.3. Most influential post: Agent #2190 (Chinese, 34, Engineer, Tampines)." |

**Stage 4 — Report & Analysis** 🟢

The main panel becomes a **multi-tab report dashboard**. The context panel shows a persistent table-of-contents and export controls. Each tab is a full-page analytics view:

| Report Tab | Content |
|:-----------|:--------|
| **Overview** | Executive summary text generated by ReportAgent. Hero stat cards (glassmorphism, large numbers): overall approval rate, net opinion shift, most-divided demographic, most influential agent. Pre-vs-post approval donut charts side by side. |
| **Friction Map** | Interactive SVG map of Singapore's 55 planning areas. Each area color-coded on a gradient (green = high approval → red = high friction, using the Friction Index formula). Click any planning area to drill down: shows that area's demographic breakdown, top dissenting agent quotes, and area-specific approval rate. Key differentiator — MiroFish has no geographic visualization. |
| **Opinion Flow** | Sankey / alluvial diagram showing how opinion groups migrated between Stage 3a and Stage 3b. Left column: pre-deliberation bins (Strongly Oppose, Oppose, Neutral, Support, Strongly Support). Right column: post-deliberation bins. Flows show how many agents moved between groups, colored by direction (red = shifted toward opposition, green = shifted toward support, gray = unchanged). Hover a flow to see which demographics contributed most to that shift. |
| **Opinion Timeline** | Animated line chart. X-axis: deliberation round (1 → N). Y-axis: average opinion score. One line per demographic cohort (age bracket, income bracket, or planning area — togglable). Lines draw progressively with micro-animation. Tooltip on hover: exact score, sample agent quote from that round. Shows convergence or polarization over time. |
| **Influential Agents** | Ranked list of top 10 most influential agents (by Influence Score). Each entry: glassmorphism card with agent avatar, persona summary (age, occupation, planning area), influence score, opinion trajectory sparkline (their personal score over rounds), and their most-upvoted post. Click any agent to jump to Stage 5 chat with that agent. |
| **Arguments** | Two-column layout: strongest arguments FOR (left, green border) and AGAINST (right, red border). Each argument card shows the post text, author agent summary, upvote count, and which demographic cohorts resonated with it most. |
| **Recommendations** | AI-generated strategic mitigations from ReportAgent. Each recommendation card: title, rationale, target demographic, expected impact. These are actionable next steps (e.g., "Offer toll exemption for seniors in Woodlands to reduce friction by ~40%"). |

| Panel | Content |
|:------|:--------|
| Context (persistent) | Table of contents for quick-jump between report tabs. "Export as PDF" button. "Re-run with adjustments" button (jumps back to Stage 1 with pre-filled settings). Report generation progress indicator (during generation). |
| Log Console | "ReportAgent analyzing 4,312 posts across 15 rounds... Computing friction indices for 55 planning areas... Generating recommendations..." |

**Stage 5 — Interactive Deep-Dive** 🔴
| Panel | Content |
|:------|:--------|
| Main | **Chat interface** (tabbed): Tab 1 = ReportAgent chat (ask follow-up strategic questions, e.g., "What messaging would work for Woodlands dissenters?"). Tab 2+ = Individual agent chat tabs (cherry-picked influential agents). Each agent tab shows their persona card (with opinion trajectory sparkline) alongside the chat. Agent responds in-character using its Zep Cloud memory of everything it said, heard, and felt during the simulation. |
| Context | "Key Agents" panel: ranked list of the top 5-10 most influential agents with avatar, name, demographic summary, influence score, and opinion trajectory sparkline. Click any to open a chat tab. Below: quick links back to report tabs. |
| Log Console | Chat interaction logs. |

**Design System:**

Visual language inspired by the reference credit dashboard — pure black, glassmorphism, premium feel:

| Property | Value |
|:---------|:------|
| **Background** | Pure black (#050505) with subtle radial gradient glow behind hero elements |
| **Cards** | Glassmorphism — semi-transparent backgrounds (rgba(255,255,255,0.04)), backdrop blur (12px), subtle 1px border (rgba(255,255,255,0.08)), border-radius 16px |
| **Typography** | Inter (Google Fonts), white (#ffffff) primary, muted gray (#9ca3af) secondary |
| **Layout** | Pill-shaped nav tabs in top bar (like the reference dashboard's "Dashboard / Credit History / Loans" tabs) |
| **Hero numbers** | Large stat cards with oversized font-weight-700 numbers and small muted labels beneath |
| **Gradients** | Warm accent gradients on progress bars and highlights (similar to the reference's amber/green credit score bar) |

**Stage Accent Colors** (used for sidebar icons, active indicators, and stage-specific accents):

| Stage | Color | Hex | Usage |
|:------|:------|:----|:------|
| 🟡 Stage 1 — Scenario Setup | Amber/Gold | #f59e0b | Sidebar icon, LightRAG progress indicator, knowledge graph node borders |
| 🔵 Stage 2 — Population Sampling | Cyan/Teal | #06b6d4 | Sidebar icon, persona count badge, sampling progress ring |
| 🟠 Stage 3a — Immediate Reactions | Orange | #f97316 | Sidebar icon, bar chart accent, completion progress bar |
| 🟣 Stage 3b — Deliberation | Purple | #8b5cf6 | Sidebar icon, round tracker, deliberation feed highlight |
| 🟢 Stage 4 — Report | Emerald | #10b981 | Sidebar icon, report tab active indicator, recommendation cards |
| 🔴 Stage 5 — Deep-Dive | Rose | #f43f5e | Sidebar icon, chat active indicator, agent highlight ring |

**Opinion Colors** (used in Persona Graph nodes, bar charts, heatmaps):

| Opinion Range | Color | Meaning |
|:--------------|:------|:--------|
| 1–3 | Red (#ef4444) | Strongly oppose / Dissent |
| 4–6 | Amber (#f59e0b) | Neutral / Undecided |
| 7–10 | Green (#22c55e) | Support / Approve |

**Micro-Animations:**
- Persona Graph nodes pop in with spring physics on sampling
- Persona Graph node colors cross-fade smoothly as opinions shift (red → amber → green or vice versa)
- Edges glow with a brief pulse when two connected agents interact
- Bar chart bars grow from zero with eased timing
- Line chart lines draw progressively left-to-right
- Sankey flows animate as ribbons flowing from left to right
- Stat cards have number counter roll-up animation
- Cards lift with subtle scale + shadow on hover
- Stage sidebar icons pulse gently when that stage is active

**Responsive:** Desktop-first (minimum 1280px width). Analyst workstation is the primary use case. Tablet/mobile is a non-goal.

---

### Data Access Strategy

For **local prototyping**, the full S3 + Lambda pipeline is not needed. The system supports two data access modes:

**Mode 1 — HuggingFace Streaming (Local Development)**

The Nemotron-Personas-Singapore dataset can be accessed directly from HuggingFace without downloading the full dataset:

```python
from datasets import load_dataset

# Stream without downloading — fetches only requested rows
ds = load_dataset(
    "nvidia/Nemotron-Personas-Singapore",
    split="train",
    streaming=True
)

# Filter on-the-fly
filtered = ds.filter(
    lambda x: x["age"] >= 25 and x["age"] <= 55
              and x["planning_area"] == "Woodlands"
)

# Take N personas
sample = list(filtered.take(200))
```

This requires **no API key** — HuggingFace public datasets are accessible without authentication. No local storage needed beyond the streaming cache.

For advanced filtering (SQL-like queries), DuckDB can also read HuggingFace Parquet files directly:

```python
import duckdb

conn = duckdb.connect()
result = conn.execute("""
    SELECT * FROM 'hf://datasets/nvidia/Nemotron-Personas-Singapore/data/*.parquet'
    WHERE age BETWEEN 25 AND 55
      AND planning_area = 'Woodlands'
      AND income_bracket IN ('$3,000-$5,999', '$6,000-$8,999')
    ORDER BY RANDOM()
    LIMIT 200
""").fetchdf()
```

**Mode 2 — S3 + Lambda (Production / Submission)**

For the final cloud deployment and the course submission, the dataset should be uploaded to S3. This demonstrates the full AWS architecture.

**Setup instructions for S3:**

1. **Install AWS CLI** (if not already):
   ```bash
   brew install awscli
   aws configure  # Enter your AWS Access Key, Secret Key, region (ap-southeast-1 for Singapore)
   ```

2. **Create an S3 bucket:**
   ```bash
   aws s3 mb s3://mckainsey-personas --region ap-southeast-1
   ```

3. **Download the dataset from HuggingFace:**
   ```bash
   pip install huggingface_hub
   huggingface-cli download nvidia/Nemotron-Personas-Singapore --repo-type dataset --local-dir ./nemotron-sg
   ```
   This downloads ~2-3 GB of Parquet files.

4. **Upload to S3:**
   ```bash
   aws s3 sync ./nemotron-sg/ s3://mckainsey-personas/nemotron-sg/ --exclude "*.md" --exclude ".gitattributes"
   ```

5. **Verify:**
   ```bash
   aws s3 ls s3://mckainsey-personas/nemotron-sg/ --recursive --human-readable
   ```

**Recommendation:** Start with Mode 1 (HuggingFace streaming) for all development. Switch to Mode 2 only when preparing the final deployment. This saves time and avoids AWS costs during development.

---

### Required API Keys and Credentials

| Key | Where to get it | Required for | When needed |
|:----|:----------------|:-------------|:------------|
| **GEMINI_API_KEY** | [Google AI Studio](https://aistudio.google.com/apikey) | All LLM calls (OASIS agents, ReportAgent, LightRAG) | Immediately |
| **ZEP_API_KEY** | [Zep Cloud Dashboard](https://app.getzep.com/) | Agent memory storage and retrieval | Phase C |
| **AWS_ACCESS_KEY_ID** | [AWS IAM Console](https://console.aws.amazon.com/iam/) | S3 storage, Lambda, EC2 | Phase A (Mode 2 only) |
| **AWS_SECRET_ACCESS_KEY** | Same as above | Same as above | Phase A (Mode 2 only) |
| **AWS_DEFAULT_REGION** | N/A (set to `ap-southeast-1`) | AWS services | Phase A (Mode 2 only) |
| **HF_TOKEN** | Not required | HuggingFace streaming | N/A — public dataset, no token needed |

**`.env` file template:**
```env
# LLM
GEMINI_API_KEY=your_gemini_key_here

# Agent Memory
ZEP_API_KEY=your_zep_cloud_key_here

# AWS (only needed for production deployment)
AWS_ACCESS_KEY_ID=your_aws_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_here
AWS_DEFAULT_REGION=ap-southeast-1
```

---

## 8. Core Formulas

### Opinion Shift Score
```
ΔOpinion(agent) = OpinionPost - OpinionPre
```
Where `OpinionPre` is the Stage 3a score (1–10 scale) and `OpinionPost` is the score after N rounds of OASIS deliberation.

### Demographic Friction Index
```
Friction(cohort) = |mean(ΔOpinion) for cohort| × (1 - approval_rate)
```
High friction = large opinion shift AND low final approval. Identifies demographics that were swayed but still disagree.

### Agent Influence Score
```
Influence(agent) = Σ |ΔOpinion(other)| for all agents who interacted with agent's posts
```
Measures how much one agent's posts contributed to others changing their minds.

---

## 9. Phase Plan

### Phase A: Data Pipeline & LightRAG Integration
**Intent:** Establish the foundational data layer — Nemotron dataset on S3, DuckDB-powered filtering via Lambda, and LightRAG document processing.

**Inputs:** Nemotron-Personas-Singapore Parquet files from Hugging Face, sample policy documents

**Outputs:**
- S3 bucket with Nemotron Parquet data
- Lambda function that accepts demographic filters and returns matching personas as JSON
- LightRAG pipeline that processes a policy document into a knowledge graph
- Integration tests proving end-to-end: upload document → extract graph → query personas

**Dependencies:** None (first phase)

**Acceptance Criteria:**
- Lambda returns correct persona subset within 5s for any valid filter combination
- LightRAG produces entity/relationship graph from a sample policy document
- Knowledge graph can be queried for entities relevant to a specific demographic

---

### Phase B: OASIS Simulation Engine Setup
**Intent:** Deploy OASIS on EC2 with Gemini as the LLM backend, configure Reddit-mode simulation, and implement the two-stage output model.

**Inputs:** Phase A outputs (personas + knowledge graph)

**Outputs:**
- EC2 instance running OASIS with Gemini API integration
- Script that loads Nemotron personas into OASIS agents
- Stage 3a pipeline: immediate reactions (individual agent responses, no interaction)
- Stage 3b pipeline: OASIS Reddit-mode deliberation (N configurable rounds)
- SQLite database with all simulation data (posts, comments, votes, opinion scores)
- Batched intra-step LLM calls to Gemini (all agents in a step batched together)

**Dependencies:** Phase A (personas + knowledge graph)

**Acceptance Criteria:**
- 50-agent simulation (10 rounds) completes in < 3 minutes
- Pre-vs-post opinion scores show measurable shift
- OASIS actions (post, comment, like, dislike) are visible in SQLite
- Token costs per simulation match estimates (< $0.15 for 50 agents)

---

### Phase C: Agent Memory (Zep Cloud Integration)
**Intent:** Integrate Zep Cloud for agent temporal memory — agents retain context across rounds, opinions have time validity, and memory is queryable post-simulation for interactive chat.

**Inputs:** Phase B outputs (running OASIS simulation)

**Outputs:**
- Zep Cloud integration: each OASIS agent's interactions stored as Zep episodes
- Temporal fact extraction: opinions tracked with validity windows
- Post-simulation query API: retrieve any agent's memory for interactive chat
- Memory-informed deliberation: agents in later rounds recall earlier interactions

**Dependencies:** Phase B (OASIS running)

**Acceptance Criteria:**
- Agent memory persists across simulation rounds
- Zep Cloud correctly tracks opinion changes with timestamps
- Post-simulation query returns agent's full interaction history and current opinions
- Agent chat responds in-character with memory context in < 5s

---

### Phase D: ReportAgent & Analysis Pipeline
**Intent:** Build the ReportAgent — a dedicated LLM with tool access that analyses simulation results and produces structured strategic insights.

**Inputs:** Phase B + C outputs (simulation data + agent memory)

**Outputs:**
- ReportAgent with tool functions: query approval rates, find top dissenters, compute influence scores, identify friction clusters
- Structured report output (JSON schema) with executive summary, demographic breakdowns, and recommendations
- Chat interface for follow-up questions to ReportAgent
- Individual agent chat: users can chat with highlighted influential agents

**Dependencies:** Phase B (simulation data), Phase C (agent memory)

**Acceptance Criteria:**
- ReportAgent produces structured report within 60s of simulation end
- Report includes pre-vs-post approval rates, top 5 dissenters, and 3+ actionable recommendations
- ReportAgent correctly answers follow-up questions using simulation data
- Individual agent chat responds in-character with correct memory

---

### Phase E: Dashboard & Frontend
**Intent:** Build the React dashboard with all visualization and interaction features.

**Inputs:** All previous phase outputs

**Outputs:**
- React frontend deployed on EC2
- Scenario submission form (document upload + demographic filter selection)
- Simulation progress indicator
- Results views: approval/dissent charts, opinion-shift timelines, demographic breakdown
- Friction heatmap (55 planning areas of Singapore)
- Consensus tracker (opinion convergence over rounds)
- ReportAgent chat panel
- Individual agent chat panel (with highlighted influential agents)

**Dependencies:** Phase D (ReportAgent API), Phase B (simulation API)

**Acceptance Criteria:**
- End-to-end flow: submit scenario → see progress → view results → chat with agents
- Dashboard loads results within 5s of simulation completion
- Charts render smoothly with 500+ agent data points
- Heatmap displays all 55 Singapore planning areas with color-coded friction scores

---

### Phase F: Integration Testing & Evaluation
**Intent:** End-to-end testing, cost optimization measurement, and preparation for submission.

**Inputs:** All previous phases completed

**Outputs:**
- End-to-end integration test results
- Performance benchmarks (latency, cost, scale)
- Cost comparison: cached vs uncached, batched vs unbatched
- Simulation quality analysis (persona differentiation, opinion shift significance)
- Final documentation updates

**Dependencies:** All previous phases

**Acceptance Criteria:**
- All success metrics from Section 4 met
- 3+ complete simulation runs with different policy scenarios documented
- Cost savings from context caching/batching measured and reported
- No critical bugs in the end-to-end flow

---

## 10. Artifact Index

| Purpose | File | Owner | Update Rule |
|:--------|:-----|:------|:------------|
| Business requirements (source of truth) | [BRD.md](BRD.md) | Project lead | Update when scope, architecture, or constraints change |
| Progress tracking | [Progress.md](Progress.md) | Active agent | Update after completing any feature/subtask |
| Phase index | [progress/index.md](progress/index.md) | Active agent | Update when phases are added, renamed, or completed |
| Phase A details | [progress/phaseA.md](progress/phaseA.md) | Active agent | Update during Phase A execution |
| Phase B details | [progress/phaseB.md](progress/phaseB.md) | Active agent | Update during Phase B execution |
| Phase C details | [progress/phaseC.md](progress/phaseC.md) | Active agent | Update during Phase C execution |
| Phase D details | [progress/phaseD.md](progress/phaseD.md) | Active agent | Update during Phase D execution |
| Phase E details | [progress/phaseE.md](progress/phaseE.md) | Active agent | Update during Phase E execution |
| Phase F details | [progress/phaseF.md](progress/phaseF.md) | Active agent | Update during Phase F execution |
| Decision log | [docs/decision_log.md](docs/decision_log.md) | Project lead | Update when significant technical decisions are made |
| Architecture reference | [docs/architecture.md](docs/architecture.md) | Active agent | Update when architecture changes |
| Latest handoff | [docs/handoffs/latest_handoff.md](docs/handoffs/latest_handoff.md) | Active agent | Update before ending any work session |
| Archived proposals | [archive/](archive/) | — | Read-only reference |

---

## 11. External References & Repositories

All repositories below are open-source and should be cloned or installed as dependencies during the relevant phase.

| Component | Repository | Install | Used In |
|:----------|:-----------|:--------|:--------|
| **OASIS** (simulation engine) | [github.com/camel-ai/oasis](https://github.com/camel-ai/oasis) | `pip install camel-oasis` | Phase B |
| **LightRAG** (document → knowledge graph) | [github.com/HKUDS/LightRAG](https://github.com/HKUDS/LightRAG) | `pip install lightrag-hku` | Phase A |
| **Zep Cloud** (agent memory) | [getzep.com](https://www.getzep.com/) / [docs](https://help.getzep.com/) | `pip install zep-cloud` | Phase C |
| **Graphiti** (self-hosted Zep — stretch goal) | [github.com/getzep/graphiti](https://github.com/getzep/graphiti) | See repo README | Stretch |
| **MiroFish** (comparable project — reference only) | [github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish) | N/A — reference for UI patterns and architecture | — |
| **Nemotron-Personas-Singapore** (persona dataset) | [huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Singapore) | `datasets` library or DuckDB `hf://` | Phase A |
| **ECharts** (charting library) | [echarts.apache.org](https://echarts.apache.org/) | `npm install echarts` | Phase E |
| **Google Gemini API** | [ai.google.dev](https://ai.google.dev/) | `pip install google-genai` | All phases |

**Key documentation links:**
- OASIS quickstart: [github.com/camel-ai/oasis#quick-start](https://github.com/camel-ai/oasis#quick-start)
- LightRAG examples: [github.com/HKUDS/LightRAG#quick-start](https://github.com/HKUDS/LightRAG#quick-start)
- Zep Cloud Python SDK: [help.getzep.com/sdks](https://help.getzep.com/sdks)
- Gemini OpenAI compatibility: [ai.google.dev/gemini-api/docs/openai](https://ai.google.dev/gemini-api/docs/openai)
- Singapore planning area GeoJSON (for heatmap): [data.gov.sg](https://data.gov.sg/) — search "Master Plan 2019 Planning Area Boundary"
