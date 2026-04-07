# McKAInsey V2 — Use Cases, Report & Analytics Redesign

## Goal

Redesign the use-case taxonomy, unify the prompt/metric/report architecture, overhaul the report screen sections, and integrate advanced analytics — making the system more coherent, user-empowering, and valuable per use case.

---

## A. Use Case Consolidation & Renaming

### Analysis

Comparing the current 4 use cases:

| Current Name | Core Question | Checkpoint Metrics | Overlap? |
|:---|:---|:---|:---|
| **Policy Review** | "Do people approve of this policy?" | Approval rate, sentiment | Unique — public-sector focus |
| **Ad Testing** | "Will this ad drive purchases?" | Conversion %, engagement | Overlaps with Customer Review on product reactions |
| **PMF Discovery** | "Does this product fill a market gap?" | Product interest, fit score | Unique — pre-launch product validation |
| **Customer Review** | "Are existing customers satisfied?" | Satisfaction, NPS | Overlaps with Ad Testing on product feedback |

**Key overlap**: Ad Testing and Customer Review both deal with *consumer reactions to a product/service*. The difference is:
- Ad Testing = reaction to **marketing material** (an ad, a landing page, copy) → "Would you buy after seeing this?"
- Customer Review = reaction to the **product itself** → "Are you satisfied with this?"

### Proposal: Consolidate into 3 use cases

| # | New Name | Old Name(s) | Target User | Core Question |
|:---|:---|:---|:---|:---|
| 1 | **Public Policy Testing** | Policy Review | Government, think tanks, NGOs | "How will the public react to this policy?" |
| 2 | **Product & Market Research** | PMF Discovery + Customer Review | Product managers, startup founders | "Does this product meet market needs? What do consumers think?" |
| 3 | **Campaign & Content Testing** | Ad Testing | Marketers, creative agencies, PR teams | "How will the audience react to this content/ad/campaign?" |

### Rationale

- **"Public Policy Testing"** is more self-explanatory than "Policy Review" — it signals *simulation of public reaction*, not a bureaucratic document review.
- **"Product & Market Research"** merges PMF Discovery + Customer Review because the audience (PMs, founders) is the same and the questions are a superset. A founder evaluating PMF also wants satisfaction and NPS data. The guiding prompts the user edits on Screen 1 will naturally steer the simulation toward pre-launch vs post-launch framing.
- **"Campaign & Content Testing"** is broader than "Ad Testing" — it also covers PR campaigns, social media posts, press releases, political ads, movie trailers, etc. The user can upload *any content piece* and ask "How will this land?"

> [!NOTE]
> ✅ **Confirmed**: PMF Discovery and Customer Review are merged into "Product & Market Research". This serves as a market research tool — identifying which customer segments are a good fit and gathering their product feedback. "Campaign & Content Testing" is the marketing tool — users sample specific target segments to test content/ad presentation and messaging.

---

## B. Unified Prompt Architecture: `analysis_questions`

### The Problem

Currently there are 3 separate lists serving overlapping purposes:

| Current Concept | Where Used | User-Editable? | Purpose |
|:---|:---|:---|:---|
| `guiding_prompt` | Screen 1 (shown to user) | ✅ Yes | Steers the knowledge graph extraction & overall simulation focus |
| `checkpoint_questions` | During simulation (asked to agents every round) | ❌ No | Extracts quantitative metrics from agents |
| `report_sections` | Screen 4 report | ❌ No | Structures the final report output |

These 3 things are related but disconnected. The user can only edit the `guiding_prompt` freeform text, but has no control over *what the agents are actually asked* or *what the report covers*.

### Proposed New Architecture

**Merge `checkpoint_questions` and `report_sections` into a single `analysis_questions` list that is user-editable on Screen 1.** The `guiding_prompt` becomes a top-level system instruction (not user-facing).

```
┌─────────────────────────────────────────────────────────────┐
│                    YAML Config Structure                      │
├──────────────────────┬──────────────────────────────────────┤
│  system_prompt       │  Internal LLM instruction (not shown │
│                      │  to user). Defines simulation tone.  │
├──────────────────────┼──────────────────────────────────────┤
│  analysis_questions  │  User-editable on Screen 1.          │
│  (list)              │  Each becomes:                       │
│                      │  - A checkpoint Q asked to agents    │
│                      │  - A report section with findings    │
│                      │  - A tracked metric with a name      │
├──────────────────────┼──────────────────────────────────────┤
│  preset_sections     │  Non-editable report sections that   │
│                      │  always appear (e.g. Recommendations,│
│                      │  Methodology). Not checkpoint Qs.    │
├──────────────────────┼──────────────────────────────────────┤
│  agent_personality   │  Personality modifiers for agents    │
│  _modifiers          │  (internal, not user-facing)         │
└──────────────────────┴──────────────────────────────────────┘
```

### How `analysis_questions` Work End-to-End

```
Screen 1 (User Edits)          Simulation                    Report
┌─────────────────┐    ┌─────────────────────────┐    ┌──────────────────────┐
│ Q1: "Do you     │───>│ Checkpoint interview:    │───>│ Section 1: "Policy   │
│ approve of this │    │ "Do you approve? 1-10"  │    │ Approval"            │
│ policy? 1-10"   │    │ → metric: approval_rate │    │ - Metric card: 72%   │
│                 │    │                         │    │ - LLM narrative      │
├─────────────────┤    ├─────────────────────────┤    ├──────────────────────┤
│ Q2: "How will   │───>│ Checkpoint: "How will   │───>│ Section 2: "Impact   │
│ this affect     │    │ this affect your daily  │    │ on Daily Life"       │
│ your daily      │    │ life? 1-10"             │    │ - Metric card: 4.2   │
│ life? 1-10"     │    │ → metric: life_impact   │    │ - LLM narrative      │
├─────────────────┤    ├─────────────────────────┤    ├──────────────────────┤
│ Q3: (user adds  │───>│ Checkpoint: (user's     │───>│ Section 3: (user's   │
│ custom question)│    │ custom question)        │    │ question) ...        │
│                 │    │ → LLM-generated metric  │    │                      │
└─────────────────┘    └─────────────────────────┘    └──────────────────────┘
                                                      ┌──────────────────────┐
                                            preset ──>│ Recommendations      │
                                           sections   │ (always present)     │
                                                      └──────────────────────┘
```

### Analysis Questions as Simulation Seed Posts

> [!IMPORTANT]
> **Key architectural addition**: Each analysis question also becomes an **initial seed post** in the OASIS simulation. Instead of the current generic "Policy Kick-off" posts, each analysis question is posted as a discussion thread at simulation start. This means agents explicitly discuss and respond to each question during the simulation, producing richer evidence for the report.
>
> For example, if the analysis questions are:
> 1. "Do you approve of this policy? Rate 1-10."
> 2. "What specific aspects of this policy do you support or oppose?"
>
> Then the simulation starts with 2 seed posts — one for each question — and agents engage with them organically through the OASIS Reddit engine. Checkpoint interviews still ask each question directly for metric extraction, but the seed posts ensure the forum discussion is structured around these topics.

### `analysis_questions` Schema

Each analysis question in the YAML has these fields:

```yaml
analysis_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"           # "scale" (1-10) | "yes-no" | "open-ended"
    metric_name: "approval_rate"
    metric_label: "Approval Rate"
    metric_unit: "%"         # "%" or "/10" — how to display
    threshold: 7             # optional — for % metrics: count agents >= threshold
    threshold_direction: "gte"
    report_title: "Policy Approval"
    tooltip: "Percentage of agents rating approval ≥ 7 out of 10."
```

### LLM-Generated Metrics for Custom Questions

When the user adds or edits a question on Screen 1, we need to auto-generate the metric metadata. This is done with a lightweight LLM call:

**Trigger**: Runs **in parallel with "Extract Knowledge Graph"** when the user clicks the Extract button. The metric metadata generation LLM call executes simultaneously with the knowledge graph extraction. Each question card shows a loading spinner while its metadata is being generated, then transitions to a ✅ green state with the metric badge once complete.

**Edit behavior**: If the user edits an existing preset question, it is treated as a **brand new question** — the LLM re-generates all metric metadata from scratch. The old metric data is discarded.

**Prompt to LLM**:
```
Given this analysis question that will be asked to simulated agents:
"{user_question}"

Generate the following metadata as JSON:
- type: "scale" if the question asks for a 1-10 rating, "yes-no" if it asks yes/no, "open-ended" otherwise
- metric_name: a snake_case identifier (e.g., "approval_rate")
- metric_label: a short human-readable label (e.g., "Approval Rate")
- metric_unit: "%" if measuring a percentage of agents, "/10" if measuring a mean score, "text" if qualitative
- threshold: if type is "scale" and metric_unit is "%", suggest a reasonable threshold (usually 7)
- threshold_direction: "gte" (default)
- report_title: a concise section title for the report
- tooltip: a one-sentence explanation of how this metric is computed

Return valid JSON only.
```

> [!NOTE]
> For `open-ended` type questions (e.g., "Compare these 3 ads and tell me which is best", or "What product feedback do you have?"), there is no numeric metric to track. These still become report sections and seed posts, but without a metric card — the report section shows a qualitative narrative summarizing the main/common viewpoints from agent discussions. The metric badge on Screen 1 is omitted for open-ended questions (a "Qualitative 📝" type pill is shown instead). Open-ended questions are valuable for gathering concrete viewpoints that the system_prompt alone may not explicitly surface.

### What the User Sees on Screen 1

The current "Guiding Prompt" card (a single freeform textarea) is replaced with an **"Analysis Questions" card** showing an ordered list of editable question cards:

```
┌─────────────────────────────────────────┐
│  ANALYSIS QUESTIONS                     │
│  ───────────────────────────────────    │
│  These questions will be asked to every │
│  simulated agent each round. Results    │
│  become your report sections & metrics. │
│                                         │
│  ┌─ Q1 ──────────────────────────────┐  │
│  │ Do you approve of this policy?    │  │
│  │ Rate 1-10.                        │  │
│  │ [Metric: Approval Rate (%) ⓘ]    │  │
│  │                          [✎] [×]  │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌─ Q2 ──────────────────────────────┐  │
│  │ What specific aspects of this     │  │
│  │ policy do you support or oppose?  │  │
│  │ [Type: Qualitative 📝]            │  │
│  │                          [✎] [×]  │  │
│  └───────────────────────────────────┘  │
│                                         │
│  [+ Add Custom Question]               │
│                                         │
│  Expanding input field appears:         │
│  ┌───────────────────────────────────┐  │
│  │ Type your question...             │  │
│  │ Example: "Compare ads A vs B and  │  │
│  │  tell me which resonates more"    │  │
│  │                         [Save]    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

When the user clicks "Extract Knowledge Graph", metric metadata for all new/edited questions is generated in parallel. Each question card shows a loading spinner → ✅ green when its metric is resolved. Open-ended questions display no metric badge, just a "Qualitative 📝" type indicator.

> [!NOTE]
> ✅ **Confirmed**: Users can **delete any question**, including presets. If they delete all preset questions and add one custom open-ended question like "Compare these 3 ads", the system works — producing one report section with a qualitative narrative and no metric cards. **Editing** an existing question treats it as a brand-new question and re-runs the LLM metric generation.

---

## C. Report Screen (Screen 4) Overhaul

### Changes to Report Sections

Based on your feedback, here's the new report structure:

#### Section 1: Report Header (unchanged)
- Title: "Analysis Report"
- Subtitle: "{Country} · {Use Case} · {n} agents · {rounds} rounds"

#### Section 2: Executive Summary Card (redesigned)

The Executive Summary now prominently displays **metric change deltas** for each `analysis_question`:

```
┌─────────────────────────────────────────────────┐
│  📊 EXECUTIVE SUMMARY                           │
│  ─────────────────────────────────────────────   │
│  [LLM-generated narrative paragraph]             │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │Approval  │  │Life      │  │Sentiment │       │
│  │Rate      │  │Impact    │  │Score     │       │
│  │          │  │          │  │          │       │
│  │ 72%      │  │ 4.2/10   │  │ 6.8/10   │       │
│  │ ▲ +12%   │  │ ▼ -1.3   │  │ ▲ +0.4   │       │
│  │ R1→R5    │  │ R1→R5    │  │ R1→R5    │       │
│  └──────────┘  └──────────┘  └──────────┘       │
│                                                  │
│  Total Agents: 250 │ Rounds: 5 │ Model: Gemini  │
└─────────────────────────────────────────────────┘
```

Each metric mini-card shows:
- Metric label (from `analysis_question.metric_label`)
- Final value (latest checkpoint)
- Delta arrow: ▲ green if improved, ▼ red if declined
- Range label: "R1→R{n}" showing the change window

> [!NOTE]
> Only **quantitative** analysis questions (type `scale` or `yes-no`) get metric delta cards in the Executive Summary. Open-ended questions are excluded — their findings appear only in their respective report section narratives.

#### Section 3: Analysis Question Sections (one per `analysis_question`)

Each `analysis_question` becomes a report section containing:
- **Section title** (from `report_title`)
- **Metric spotlight** *(quantitative questions only)*: Larger metric card with round-over-round mini-chart (sparkline). Omitted for open-ended questions.
- **Narrative**: LLM-generated analysis citing specific agent posts and comments. For open-ended questions, this is a synthesis of the main/common viewpoints expressed by agents.
- **Evidence**: Notable quotes from agents, with agent IDs linked for drill-down. **Clicking an agent ID opens the chat panel** (since Report & Chat are on the same page in the 60/40 split layout), allowing the user to immediately start a 1:1 conversation with that agent for deeper follow-up.

#### Section 4: Use-Case-Specific Insights (NEW — see Section D below)

This is where use-case-dependent analytics get embedded. Not all appear for every use case.

#### Section 5: Preset Sections

These always appear regardless of use case:
- **Key Recommendations**: LLM-generated actionable items
- Additional use-case-specific preset sections (e.g., "Best-Fit Demographics" for Product & Market Research)

> [!NOTE]
> **Methodology removed as a standalone preset section.** Simulation config details (agent count, rounds, model, controversy boost) are already displayed in the report header subtitle and do not need a separate section. For DOCX export, a brief auto-generated methodology footer is appended.

### What Gets REMOVED

- ~~**Supporting vs Dissenting Views**~~: Removed as a standalone section. The pro/con viewpoints are naturally embedded within each analysis question section's narrative (the LLM cites supporting and opposing agent quotes when answering each question).
- ~~**Demographic Breakdown (standalone)**~~: Removed from Screen 4. Already exists as the Demographic Sentiment Map on Screen 5 (Analytics). Each analysis question section *may* mention demographic patterns in its narrative.

---

## D. Use-Case-Specific Report Insights

### What Each User Type Actually Wants

| Use Case | Target User | Key Decision | What They Need Most |
|:---|:---|:---|:---|
| **Public Policy Testing** | Government official | "Should we proceed with this policy?" | Who opposes? Why? How polarized is it? Who's influencing whom? |
| **Product & Market Research** | Product manager | "Should we launch? What to improve?" | Which segments love it? What are pain points? NPS trajectory? |
| **Campaign & Content Testing** | Marketer | "Is this ad effective? Which version?" | Conversion drivers, audience reaction, top objections |

### Use-Case-Specific Insight Blocks

Each use case gets a curated set of "insight blocks" in Section 4 of the report. These are pre-defined (not from analysis_questions) and render only for their use case.

#### Public Policy Testing — Insight Blocks

| Block | Content | Why |
|:---|:---|:---|
| **Polarization Index** | Mini bar chart showing polarization per round + severity badge | Policy makers need to know if the policy is *dividing* the population |
| **Opinion Flow** | Simplified Sankey: supporters→neutral→dissenters migration | Shows whether minds changed and in which direction |
| **Top Influencers** | Top 3 agents whose posts caused the most opinion shifts, with their key arguments | Identifies the "opinion leaders" whose framing was most persuasive |
| **Most Viral Thread** | The single discussion thread that caused the biggest aggregate opinion shift | Identifies the specific argument that was the "tipping point" |

#### Product & Market Research — Insight Blocks

| Block | Content | Why |
|:---|:---|:---|
| **Best-Fit Segments** | Mini heatmap showing metric scores by demographic segment (top 5 segments) | PMs need to know *who* the product resonates with |
| **Top Pain Points** | Ranked list of most-mentioned pain points from agent posts, with frequency counts | Directly actionable for product improvement |
| **Top Advocates** | Top 3 agents with highest satisfaction/recommendation scores + their key posts | Identifies the "ideal customer profile" (ICP) |
| **Competitive Mentions** | Extracted mentions of competing products/alternatives from agent posts | Shows what alternatives people are comparing against |

#### Campaign & Content Testing — Insight Blocks

| Block | Content | Why |
|:---|:---|:---|
| **Audience Reaction Spectrum** | Distribution of engagement scores (histogram), not just the mean | Shows if the reaction is uniform or polarized |
| **Top Objections** | Ranked list of reasons agents said "no" to conversion question | Directly actionable for creative revision |
| **Top Advocates** | Agents with strongest positive reactions + their reasoning | Identifies what messaging resonated and with whom |
| **Viral Moments** | Top 3 posts by total engagement (likes + dislikes + comments) with excerpts | Shows which specific content sparked the most discussion |

> [!TIP]
> **The Polarization Index and Opinion Flow are NOT included for Product & Market Research or Campaign Testing** because polarization is a phenomenon specific to *public opinion on contentious topics*. A product review being polarized isn't inherently meaningful the same way a policy debate is. However, if the user adds a question like "Do you think this product is ethical?", the analytics on Screen 5 would still show polarization — it's just not in the report by default.

---

## Proposed YAML Configs (Full Rewrite)

### 1. `config/prompts/public-policy-testing.yaml`

```yaml
name: "Public Policy Testing"
code: "public-policy-testing"
description: "Simulate public reaction to government policies, regulations, and proposals."
icon: "🏛️"

system_prompt: |
  You are a citizen reacting to the provided policy document.
  Express genuine opinions based on your demographic background.
  Focus on how this policy affects your daily life, family, and community.

agent_personality_modifiers:
  - "Express genuine concern about how this policy affects your daily life and family."
  - "When responding to other comments, engage directly with their specific arguments."
  - "If you strongly disagree, explain why with concrete personal examples."

analysis_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    metric_label: "Approval Rate"
    metric_unit: "%"
    threshold: 7
    threshold_direction: "gte"
    report_title: "Policy Approval"
    tooltip: "Percentage of agents who rated approval ≥ 7/10."

  - question: "What specific aspects of this policy do you support or oppose, and why?"
    type: "open-ended"
    metric_name: "policy_viewpoints"
    report_title: "Key Viewpoints"
    tooltip: "Qualitative summary of the main arguments for and against the policy."

# Note: The system_prompt already instructs agents to discuss daily life impact,
# so a separate metric for that is unnecessary. The open-ended question above
# as a seed post explicitly solicits structured pro/con viewpoints.

insight_blocks:
  - type: "polarization_index"
    title: "Polarization Over Time"
    description: "How divided is public opinion across rounds?"
  - type: "opinion_flow"
    title: "Opinion Migration"
    description: "How did stances shift from Round 1 to final?"
  - type: "top_influencers"
    title: "Key Opinion Leaders"
    count: 3
    description: "Agents whose posts drove the most opinion change."
  - type: "viral_cascade"
    title: "Pivotal Discussion"
    description: "The thread that caused the largest aggregate opinion shift."

preset_sections:
  - title: "Recommendations"
    prompt: "Provide actionable recommendations for the policy maker based on the simulation results, citing specific evidence from agent discussions."
```

### 2. `config/prompts/product-market-research.yaml`

```yaml
name: "Product & Market Research"
code: "product-market-research"
description: "Evaluate product-market fit, customer satisfaction, and improvement priorities."
icon: "📦"

system_prompt: |
  You are evaluating the provided product or service concept.
  React based on your real habits, needs, and pain points.
  Be honest about whether you would use, pay for, or recommend this.

agent_personality_modifiers:
  - "Evaluate this product based on your actual daily habits and pain points."
  - "Be direct about willingness to use or pay for this."
  - "Compare against alternatives you already use."
  - "Include specific details about what worked and what didn't."

analysis_questions:
  - question: "How interested are you in this product? Rate 1-10."
    type: "scale"
    metric_name: "product_interest"
    metric_label: "Product Interest"
    metric_unit: "%"
    threshold: 7
    threshold_direction: "gte"
    report_title: "Product Interest"
    tooltip: "Percentage of agents who rated interest ≥ 7/10."

  - question: "What would you change or improve about this product?"
    type: "open-ended"
    metric_name: "product_feedback"
    report_title: "Product Feedback"
    tooltip: "Qualitative summary of what agents liked, disliked, and want improved."

  - question: "Would you recommend this to a friend? Rate 1-10."
    type: "scale"
    metric_name: "nps_score"
    metric_label: "NPS (Promoters)"
    metric_unit: "%"
    threshold: 8
    threshold_direction: "gte"
    report_title: "Net Promoter Score"
    tooltip: "Percentage of agents who would recommend (score ≥ 8), following NPS methodology."

# Note: The system_prompt already instructs agents to discuss pain points and
# compare alternatives in their posts. The open-ended "Product Feedback" question
# as a seed post explicitly solicits this discussion, and the insight blocks below
# extract structured themes from the resulting agent posts.

insight_blocks:
  - type: "segment_heatmap"
    title: "Best-Fit Segments"
    description: "Which demographic segments show highest interest/satisfaction?"
    metric_ref: "product_interest"
  - type: "pain_points"
    title: "Top Pain Points"
    count: 5
    description: "Most frequently mentioned complaints or unmet needs. (Raw data extraction — complements the 'Improvement Priorities' preset section which synthesizes these into actionable recommendations.)"
  - type: "top_advocates"
    title: "Top Advocates"
    count: 3
    description: "Agents with the highest scores — your ideal customer profile."
  - type: "competitive_mentions"
    title: "Competitive Landscape"
    description: "Alternatives and competitors mentioned by agents."

preset_sections:
  - title: "Best-Fit Demographics"
    prompt: "Analyze which demographic segments (age, occupation, income, location) are the best fit for this product based on interest scores, feedback sentiment, and NPS. State the ideal customer profile clearly."
  - title: "Improvement Priorities"
    prompt: "Recommend prioritized product improvements based on complaint frequency, severity, and which segments they affect most."
```

### 3. `config/prompts/campaign-content-testing.yaml`

```yaml
name: "Campaign & Content Testing"
code: "campaign-content-testing"
description: "Test advertisements, PR campaigns, social media content, and creative assets with target audiences."
icon: "📢"

system_prompt: |
  You are reacting to the provided advertisement, campaign, or content piece.
  Respond authentically as a real consumer encountering this in the wild.
  Consider whether the message is compelling, credible, and relevant to you.

agent_personality_modifiers:
  - "React authentically to this content as a real consumer would."
  - "Consider whether the message actually addresses your needs or interests."
  - "Share honest feedback, including skepticism about unsupported marketing claims."
  - "Note if anything feels misleading, tone-deaf, or irrelevant to you."

analysis_questions:
  - question: "Would you try or buy this product/service after seeing this content? (yes/no)"
    type: "yes-no"
    metric_name: "conversion_intent"
    metric_label: "Conversion Intent"
    metric_unit: "%"
    report_title: "Conversion Analysis"
    tooltip: "Percentage of agents expressing intent to buy/try after seeing the content."

  - question: "How engaging is this content? Rate 1-10."
    type: "scale"
    metric_name: "engagement_score"
    metric_label: "Engagement Score"
    metric_unit: "/10"
    report_title: "Audience Engagement"
    tooltip: "Mean engagement rating across all agents (1=not engaging, 10=very engaging)."

  - question: "How credible and trustworthy does this content feel? Rate 1-10."
    type: "scale"
    metric_name: "credibility_score"
    metric_label: "Credibility"
    metric_unit: "/10"
    report_title: "Content Credibility"
    tooltip: "Mean credibility/trust rating across all agents."

insight_blocks:
  - type: "reaction_spectrum"
    title: "Audience Reaction Spectrum"
    description: "Distribution of engagement scores across the population."
    metric_ref: "engagement_score"
  - type: "top_objections"
    title: "Top Objections"
    count: 5
    description: "Most common reasons agents rejected or were skeptical."
  - type: "top_advocates"
    title: "Top Advocates"
    count: 3
    description: "Agents with the strongest positive reaction and their reasoning."
  - type: "viral_posts"
    title: "Viral Moments"
    count: 3
    description: "Posts that generated the most discussion."

preset_sections:
  - title: "Optimization Recommendations"
    prompt: "Suggest specific, actionable changes to improve content performance, conversion, and audience trust."
```

---

## Proposed Changes (by Component)

---

### Config System

#### [DELETE] [policy-review.yaml](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/config/prompts/policy-review.yaml)
#### [DELETE] [ad-testing.yaml](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/config/prompts/ad-testing.yaml)
#### [DELETE] [customer-review.yaml](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/config/prompts/customer-review.yaml)
#### [DELETE] [product-market-fit.yaml](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/config/prompts/product-market-fit.yaml)

#### [NEW] `config/prompts/public-policy-testing.yaml`
#### [NEW] `config/prompts/product-market-research.yaml`
#### [NEW] `config/prompts/campaign-content-testing.yaml`

Full contents as shown in the YAML section above.

---

### Backend — Config Service

#### [MODIFY] [config_service.py](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/backend/src/mckainsey/services/config_service.py)

Changes:
- Rename `get_checkpoint_questions()` → `get_analysis_questions()`
- Add `get_insight_blocks(use_case)` method
- Add `get_preset_sections(use_case)` method
- Remove `get_report_sections()` (replaced by `analysis_questions` + `preset_sections`)
- Add `get_system_prompt(use_case)` method (separate from guiding_prompt)

---

### Backend — Metric Generation Service

#### [NEW] `backend/src/mckainsey/services/question_metadata_service.py`

New service that handles LLM-based metadata generation for custom analysis questions:

```python
class QuestionMetadataService:
    """Generates metric metadata for user-defined analysis questions."""

    async def generate_metric_metadata(self, question_text: str) -> dict:
        """Calls LLM to generate type, metric_name, metric_label, etc."""
        # Returns: {type, metric_name, metric_label, metric_unit, threshold, 
        #           threshold_direction, report_title, tooltip}
        ...

    def validate_question(self, question: dict) -> bool:
        """Validates that a question has all required fields."""
        ...
```

#### [NEW] API Route: `POST /api/v2/console/session/{id}/questions/generate-metadata`

- **Input**: `{ "question": "user's question text" }`
- **Output**: `{ "type": "scale", "metric_name": "...", "metric_label": "...", ... }`
- Called when user adds/edits a custom question on Screen 1

---

### Backend — Report Service

#### [MODIFY] [report_service.py](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/backend/src/mckainsey/services/report_service.py)

Changes:
- Report generation now structured around `analysis_questions` (not `report_sections`)
- Each analysis question → one report section with metric spotlight + narrative
- `insight_blocks` rendered based on `type` field: calls the appropriate metrics function
- `preset_sections` appended at end
- Executive Summary card now includes metric deltas (Round 1 vs Final for each analysis question)

---

### Backend — Metrics Service

#### [MODIFY] [metrics_service.py](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/backend/src/mckainsey/services/metrics_service.py)

New methods needed for insight blocks:
- `compute_segment_heatmap(agents, analysis_questions, group_key)` → for "Best-Fit Segments"
- `extract_pain_points(posts, comments, top_n)` → LLM-assisted extraction of recurring themes
- `extract_competitive_mentions(posts, comments)` → LLM-assisted extraction of competitor names
- `compute_reaction_distribution(agents, metric_name)` → histogram data for reaction spectrum
- `extract_top_objections(agents, posts, metric_name, top_n)` → for agents who scored low, extract reasons
- `get_top_advocates(agents, metric_name, top_n)` → agents with highest scores + their key posts
- `get_viral_posts(posts, top_n)` → posts sorted by total engagement

Existing methods used by insight blocks (no changes needed):
- `compute_group_polarization()` — used by `polarization_index` block
- `compute_opinion_flow()` — used by `opinion_flow` block
- `build_influence_graph()` — used by `top_influencers` block
- `compute_top_cascade()` — used by `viral_cascade` block

> [!IMPORTANT]
> **Selective activation**: Insight block methods are activated **only for the use case that defines them** in its YAML config. If the user has heavily customized their analysis questions such that an insight block becomes irrelevant (e.g., no quantitative metrics to reference for `segment_heatmap`), the method should gracefully return `{"status": "not_applicable", "reason": "Insufficient quantitative data for this analysis"}` rather than failing. The frontend renders this as a muted "Not enough data for this analysis" card.

---

### Frontend — Screen 1 (Knowledge Graph)

#### [MODIFY] [PolicyUpload.tsx](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/frontend/src/pages/PolicyUpload.tsx)

Changes:
- Replace "Guiding Prompt" freeform textarea with **"Analysis Questions"** editable card list
- Each question card shows: question text, editable input, metric badge, edit/delete buttons
- "Add Custom Question" button → expanding text input → calls `/questions/generate-metadata` on save
- Questions are ordered (drag-to-reorder stretch goal)
- State: `analysisQuestions` array in component state, synced to session config

#### [NEW] `frontend/src/components/AnalysisQuestionCard.tsx`

Individual question card component with:
- Editable question text (click-to-edit inline)
- **Metric badge** (label + unit + tooltip) — **optional, only shown for `scale` and `yes-no` types**. Omitted for `open-ended` questions which show a "Qualitative 📝" type pill instead.
- **Loading state**: While metric metadata is being generated (during Extract Knowledge Graph), show a spinner on the badge area → transitions to ✅ green with populated metric info when complete.
- Delete (×) and edit (✎) buttons
- Visual indicator for question type (scale/yes-no/open-ended)
- Editing an existing question triggers re-generation of metric metadata (treated as a new question)

---

### Frontend — Screen 4 (Report)

#### [MODIFY] [ReportChat.tsx](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/frontend/src/pages/ReportChat.tsx)

Changes:
- **Executive Summary**: Add metric delta cards (one per `analysis_question`) showing final value + change arrow
- **Remove**: "Supporting vs Dissenting Views" standalone section
- **Remove**: "Demographic Breakdown" standalone section (already on Screen 5)
- **Report sections**: Now generated from `analysis_questions` (each question = one section with metric + narrative)
- **Add**: Use-case-specific insight blocks section (after analysis question sections, before preset sections)
- **Preset sections**: Recommendations + Methodology always at bottom

#### [NEW] `frontend/src/components/MetricDeltaCard.tsx`

Small card showing metric value + delta change with colored arrow. Only rendered for quantitative analysis questions (`scale` or `yes-no` type). Open-ended questions are excluded from delta cards.

#### [NEW] `frontend/src/components/InsightBlock.tsx`

Renders different visualization types based on `insight_block.type`:
- `polarization_index` → mini bar chart (reuses Recharts from Screen 5)
- `opinion_flow` → simplified horizontal flow diagram
- `top_influencers` → agent cards with influence scores
- `viral_cascade` → thread preview card
- `segment_heatmap` → small heatmap grid
- `pain_points` → ranked list with frequency bars
- `top_advocates` → agent cards with scores + quotes
- `competitive_mentions` → tag cloud or list
- `reaction_spectrum` → histogram
- `top_objections` → ranked list
- `viral_posts` → post cards with engagement

Each insight block includes a **"See More →"** link button that navigates the user to the corresponding full interactive visualization on **Screen 5 (Analytics)**. For blocks without a direct Screen 5 equivalent (e.g., `competitive_mentions`), the link is omitted.

---

### Frontend — Screen 0 (Onboarding)

#### [MODIFY] `frontend/src/pages/Onboarding.tsx`

- Update use case options from 4 → 3
- New names: "Public Policy Testing", "Product & Market Research", "Campaign & Content Testing"
- Update icons and descriptions

---

### Documentation Updates

#### [MODIFY] [BRD_V2.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/BRD_V2.md)

- §1.1: Update use case list from 4 → 3 with new names
- §3.9: Rewrite "Dynamic Metrics per Use Case" to reflect `analysis_questions` architecture
- §3.10: Rewrite "Agent Prompts per Use Case" to show new YAML schema

#### [MODIFY] [screen-1-knowledge-graph.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/frontend/screen-1-knowledge-graph.md)

- §4: Replace "Guiding Prompt Card" with "Analysis Questions Card" spec

#### [MODIFY] [screen-4-report-chat.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/frontend/screen-4-report-chat.md)

- §2: Redesign Executive Summary with metric deltas
- §3: Report sections now from `analysis_questions`
- §4: Remove Supporting vs Dissenting Views
- §5: Add insight blocks section
- DOCX export section updated accordingly

#### [MODIFY] [config-system.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/backend/config-system.md)

- Full rewrite of prompt config schema
- New `QuestionMetadataService` reference

#### [MODIFY] [metrics-heuristics.md](file:///Users/pebblepaw/Documents/CODING_PROJECTS/Nemotron_Consult/docs/v2/backend/metrics-heuristics.md)

- Add new insight block computation methods
- Update `MetricsService` class spec

---

## Resolved Decisions

All open questions have been resolved per user review:

| # | Question | Decision |
|:---|:---|:---|
| 1 | Merge PMF + Customer Review? | ✅ **Yes** — merged into "Product & Market Research". Market research tool for identifying customer fit + gathering product feedback. |
| 2 | Can users delete preset questions? | ✅ **Yes** — full flexibility. Editing an existing question = treated as brand new (re-runs LLM metric generation). |
| 3 | LLM metric metadata timing? | ✅ **Runs in parallel with "Extract Knowledge Graph"** click. Loading spinner on each question card → green when metric resolved. |
| 4 | Insight blocks in Report or Analytics? | ✅ **Both** — summary cards in Report (Screen 4) with **"See More →"** button linking to full interactive version on Screen 5 (Analytics). |
| 5 | Analysis questions as seed posts? | ✅ **Yes** — each analysis question becomes an initial seed post in the OASIS simulation, replacing generic kick-off posts. Agents discuss each question as a forum thread. |
| 6 | Open-ended question handling? | ✅ **Supported** — no metric tracked, no sparkline, report section shows qualitative synthesis of main viewpoints. Metric badge omitted on Screen 1. |
| 7 | Agent ID click in report? | ✅ **Opens chat panel** — clicking an agent ID in report evidence opens 1:1 chat in the adjacent chat panel (60/40 layout). |
| 8 | Methodology section? | ✅ **Removed** as standalone preset section. Config details shown in report header; brief methodology footer in DOCX export only. |

---

## Verification Plan

### Automated Tests
- Config loading: All 3 new YAML files load correctly via `ConfigService`
- `analysis_questions` field validation: type, metric_name, threshold all parsed
- `QuestionMetadataService`: mock LLM response → valid metadata JSON
- Report generation: produces N sections where N = len(analysis_questions) + len(preset_sections)
- Metric delta computation: Round 1 vs Final values computed correctly
- Insight block dispatch: correct function called per `type` field

### Manual Verification
- Screen 1: Analysis questions load from config, editable, custom question adds correctly
- Screen 3: Correct metrics display during simulation for each of 3 use cases
- Screen 4: Executive summary shows metric deltas, insight blocks render for each use case
- Screen 4→5: Clicking insight block navigates to corresponding analytics section
- DOCX export: Includes all analysis question sections + insight block summaries
