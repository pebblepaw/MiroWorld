# Backend — Metrics & Heuristics

## Overview

V2 metrics are driven by two main sources:

1. checkpoint responses stored in `metric_answers`
2. OASIS interaction traces

No frontend metric card should rely on hardcoded V1 use-case assumptions anymore. Metric generation is driven from `analysis_questions`.

## 1. Dynamic Metrics

### Rule

Only quantitative questions generate numeric metrics:

- `scale`
- `yes-no`

`open-ended` questions still produce report sections but no numeric card.

### Current Value Rules

- thresholded `scale` -> percentage of agents meeting threshold
- unthresholded `scale` -> average score, usually `/10`
- `yes-no` -> percentage of “yes” answers

### Report Delta Rules

Report metric cards and section spotlights compare:

- initial checkpoint value
- final checkpoint value
- computed delta

The display contract should prefer:

- `initial_display`
- `final_display`
- `delta_display`

Example:

- `61.0% -> 73.0%`

Text-unit leaks like `0Text` are always incorrect for quantitative questions.

## 2. Canonical Built-In Metrics

### Public Policy Testing

- `approval_rate`: thresholded percentage from `Do you approve of this policy? Rate 1-10.`
- `policy_viewpoints`: open-ended qualitative section only

### Product & Market Research

- `product_interest`: thresholded percentage
- `product_feedback`: open-ended qualitative section only
- `nps_score`: thresholded percentage of promoter-style responses

### Campaign & Content Testing

- `conversion_intent`: yes/no percentage
- `engagement_score`: average `/10`
- `credibility_score`: average `/10`

### Custom Questions

Custom Screen 1 questions are normalized by `QuestionMetadataService` and join the same metric/report pipeline.

## 3. Analytics Computations

### Polarization

- computed from agent opinion distribution across a chosen group key
- current frontend usually uses planning-area style grouping when available
- empty or uniform data can legitimately yield `0.0`

### Opinion Flow

- maps initial stance to final stance
- stance buckets:
  - supporter: `>= 7`
  - neutral: `>= 5 and < 7`
  - dissenter: `< 5`

### Influence

Influence ranking enriches leader rows with:

- `name`
- `agent_name`
- `stance`
- `influence_score`
- `top_view`
- `top_post`

Frontend displays should prefer `name`/`agent_name` and `top_view`, not raw serial ids or raw nested objects.

### Cascades / Viral Posts

Cascade output enriches posts with:

- `author_name`
- `stance`
- `title`
- `content`
- `comments`
- `engagement_score`
- `tree_size`
- `total_engagement`
- `mean_opinion_delta`

## 4. Insight Block Dispatcher

Current supported insight-block types include:

- `polarization_index`
- `opinion_flow`
- `top_influencers`
- `viral_cascade`
- `segment_heatmap`
- `pain_points`
- `top_advocates`
- `competitive_mentions`
- `reaction_spectrum`
- `top_objections`
- `viral_posts`

Unsupported or under-specified blocks should return `not_applicable` instead of fabricated data.

## 5. Chat Segment Selection

Group chat participant selection still ranks by normalized influence features:

- post engagement
- comment count
- replies received

The current Screen 4 UX exposes supporters, dissenters, and 1:1 chat.
