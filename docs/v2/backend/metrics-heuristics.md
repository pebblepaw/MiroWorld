# Backend: Metrics & Heuristics

> **Implements**: Phase U (U4, U8, U2-5), Phase T (T7)
> **UserInput Refs**: F3, E2

## Overview

All simulation metrics are computed from two data sources:
1. **Checkpoint interviews**: Structured Q&A at the start and end of simulation (1-10 scale or yes/no)
2. **OASIS trace data**: Interaction records (posts, comments, likes, dislikes)

No external sentiment classifiers are used. All metrics are heuristic-based, derived from the agent's own structured responses and platform behavior.

## Metric Definitions

### Per-Use-Case Metrics (Screen 3 — Dynamic Cards)

#### Policy Review

| Metric | Formula | Data Source |
|:-------|:--------|:------------|
| **Approval Rate** | `count(agents where opinion_score >= 7) / total_agents × 100` | Checkpoint interview: "Rate 1-10" |
| **Net Sentiment** | `mean(all opinion_scores)` | Checkpoint interview: "Rate 1-10" |

**Tooltip (Approval Rate)**: "Percentage of agents who rated the policy ≥ 7 out of 10 during the checkpoint interview. Agents answer: 'Do you approve of this policy? Rate 1-10.' Scores ≥ 7 count as approval."

**Tooltip (Net Sentiment)**: "Mean opinion score across all agents, based on the checkpoint interview question: 'What is your overall sentiment? Rate 1-10.' 1 = strongly negative, 10 = strongly positive."

#### Ad Testing

| Metric | Formula | Data Source |
|:-------|:--------|:------------|
| **Estimated Conversion** | `count(agents who answered "yes") / total_agents × 100` | Checkpoint: "Would you try/buy? (yes/no)" |
| **Engagement Score** | `(total_likes + total_comments + total_shares) / (total_agents × rounds)` | OASIS trace |

#### PMF Discovery

| Metric | Formula | Data Source |
|:-------|:--------|:------------|
| **Product Interest** | `count(agents where score >= 7) / total_agents × 100` | Checkpoint: "Is this something you need? (1-10)" |
| **Target Fit Score** | `mean(scores for target_demographic_only)` | Checkpoint + demographic filter |

#### Customer Review

| Metric | Formula | Data Source |
|:-------|:--------|:------------|
| **Satisfaction** | `mean(all satisfaction_scores)` | Checkpoint: "Rate satisfaction 1-10" |
| **Recommendation (NPS)** | `count(agents where score >= 8) / total_agents × 100` | Checkpoint: "Would you recommend? (1-10)" |

### Advanced Analytics Metrics (Screen 5 — Visualizations)

#### Polarization Index

**Definition**: Between-group variance divided by total variance of opinion scores. Measures how much the population has split into distinct opposing camps.

**Range**: 0.0 (uniform opinions) to 1.0 (perfectly bimodal split)

**Severity labels**:
- 0.0 – 0.2: "Low Polarization" (green badge)
- 0.2 – 0.5: "Moderate" (amber badge)
- 0.5 – 0.8: "High" (orange badge)
- 0.8 – 1.0: "Highly Polarized" (red badge)

```python
def compute_group_polarization(agents: list[dict], group_key: str = "planning_area") -> dict:
    from collections import defaultdict
    from statistics import mean as _mean

    groups = defaultdict(list)
    all_scores = []
    for a in agents:
        key = str(a.get("persona", {}).get(group_key, "Unknown"))
        score = float(a.get("opinion_post", 0.0))
        groups[key].append(score)
        all_scores.append(score)

    overall_mean = _mean(all_scores)
    n = max(1, len(all_scores))
    between = sum(len(v) * ((_mean(v) - overall_mean) ** 2) for v in groups.values()) / n
    total_var = sum((s - overall_mean) ** 2 for s in all_scores) / n
    polarization_index = (between / total_var) if total_var > 0 else 0.0

    severity = (
        "low" if polarization_index < 0.2 else
        "moderate" if polarization_index < 0.5 else
        "high" if polarization_index < 0.8 else
        "critical"
    )

    return {
        "polarization_index": round(polarization_index, 4),
        "severity": severity,
        "by_group_means": {k: round(_mean(v), 4) for k, v in groups.items()},
        "group_sizes": {k: len(v) for k, v in groups.items()},
    }
```

#### Influence Centrality

**Definition**: Weighted out-degree in the interaction graph. Weight = absolute opinion delta caused by an agent's posts on other agents.

```python
def build_influence_graph(interactions: list[dict]) -> dict:
    edges = {}
    for ev in interactions:
        a = ev.get("actor_agent_id")
        t = ev.get("target_agent_id")
        if not a or not t:
            continue
        w = abs(float(ev.get("delta", 0.0)) or 0.0)
        edges[(a, t)] = edges.get((a, t), 0.0) + w

    node_scores = {}
    for (a, t), w in edges.items():
        node_scores[a] = node_scores.get(a, 0.0) + w

    top_influencers = sorted(node_scores.items(), key=lambda x: x[1], reverse=True)[:10]

    # Build graph data for frontend visualization
    nodes = []
    for agent_id, score in top_influencers:
        nodes.append({
            "id": agent_id,
            "influence_score": round(score, 4),
            # stance and name populated from agent lookup
        })

    edge_list = [
        {"source": a, "target": t, "weight": round(w, 4)}
        for (a, t), w in edges.items()
        if a in dict(top_influencers) or t in dict(top_influencers)
    ]

    return {
        "top_influencers": [
            {"agent_id": aid, "score": round(s, 4)}
            for aid, s in top_influencers
        ],
        "nodes": nodes,
        "edges": edge_list,
        "total_nodes": len(node_scores),
        "total_edges": len(edges),
    }
```

#### Opinion Flow (Sankey)

**Definition**: Mapping of agents from initial stance to final stance.

**Stance buckets**: Based on checkpoint scores:
- Score 1-4: Dissenter
- Score 5-6: Neutral
- Score 7-10: Supporter

```python
def compute_opinion_flow(agents: list[dict]) -> dict:
    def bucket(score):
        if score >= 7: return "supporter"
        elif score >= 5: return "neutral"
        else: return "dissenter"

    initial = {"supporter": 0, "neutral": 0, "dissenter": 0}
    final = {"supporter": 0, "neutral": 0, "dissenter": 0}
    flows = defaultdict(int)

    for a in agents:
        pre = bucket(float(a.get("opinion_pre", 5)))
        post = bucket(float(a.get("opinion_post", 5)))
        initial[pre] += 1
        final[post] += 1
        flows[(pre, post)] += 1

    return {
        "initial": initial,
        "final": final,
        "flows": [
            {"from": f, "to": t, "count": c}
            for (f, t), c in flows.items()
        ],
    }
```

#### Cascade Analysis

**Definition**: Find the post thread that caused the largest aggregate opinion shift among agents who engaged with it.

```python
def compute_top_cascade(posts: list[dict], comments: list[dict],
                        agents: list[dict]) -> dict:
    # Build parent-child tree
    # For each root post, compute:
    #   1. Tree size (number of comments)
    #   2. Total engagement (sum of likes + dislikes across thread)
    #   3. Mean opinion delta of agents who engaged with the thread
    # Return the cascade with highest |mean delta|

    # Simplified: uses the OASIS runner SQLite DB for exact post-comment relationships
    # Implementation left to coding agent — use post.comment tables
    pass
```

## Group Chat Participant Selection

```python
def select_group_chat_agents(agents: list[dict], interactions: list[dict],
                              segment: str, top_n: int = 5) -> list[dict]:
    """Select top-N most influential agents from a stance segment.

    Args:
        segment: "supporter" | "dissenter" | "neutral" | "engaged"
        top_n: Number of agents to select (default 5)
    """
    # Compute influence scores
    influence = {}
    for a in agents:
        agent_id = a["id"]
        agent_posts = [i for i in interactions if i["actor_agent_id"] == agent_id]

        post_engagement = sum(
            int(p.get("likes", 0)) + int(p.get("dislikes", 0))
            for p in agent_posts
        )
        comment_count = len([p for p in agent_posts if p.get("type") == "comment"])
        replies_received = len([
            i for i in interactions
            if i.get("target_agent_id") == agent_id
        ])

        # Normalize each component to 0-1 range before combining
        influence[agent_id] = {
            "raw_engagement": post_engagement,
            "raw_comments": comment_count,
            "raw_replies": replies_received,
        }

    # Normalize
    max_eng = max((v["raw_engagement"] for v in influence.values()), default=1) or 1
    max_com = max((v["raw_comments"] for v in influence.values()), default=1) or 1
    max_rep = max((v["raw_replies"] for v in influence.values()), default=1) or 1

    for aid, v in influence.items():
        v["score"] = (
            0.4 * (v["raw_engagement"] / max_eng) +
            0.3 * (v["raw_comments"] / max_com) +
            0.3 * (v["raw_replies"] / max_rep)
        )

    # Filter by segment
    def get_stance(agent_id):
        agent = next((a for a in agents if a["id"] == agent_id), None)
        if not agent: return "unknown"
        score = float(agent.get("opinion_post", 5))
        if score >= 7: return "supporter"
        elif score >= 5: return "neutral"
        else: return "dissenter"

    if segment == "engaged":
        # Top by raw influence regardless of stance
        ranked = sorted(influence.items(), key=lambda x: x[1]["score"], reverse=True)
    else:
        ranked = [
            (aid, v) for aid, v in sorted(
                influence.items(), key=lambda x: x[1]["score"], reverse=True
            )
            if get_stance(aid) == segment
        ]

    return [
        {"agent_id": aid, "influence_score": round(v["score"], 4)}
        for aid, v in ranked[:top_n]
    ]
```

## MetricsService Class

```python
# backend/src/mckainsey/services/metrics_service.py

class MetricsService:
    """Computes all simulation analytics metrics."""

    def __init__(self, config_service: ConfigService):
        self.config = config_service

    def compute_dynamic_metrics(self, agents, use_case, round_no=None):
        """Compute use-case-specific metrics for Screen 3 cards."""
        questions = self.config.get_checkpoint_questions(use_case)
        results = {}
        for q in questions:
            name = q["metric_name"]
            if q["type"] == "scale":
                scores = [float(a.get(f"checkpoint_{name}", 5)) for a in agents]
                if "threshold" in q:
                    threshold = q["threshold"]
                    direction = q.get("threshold_direction", "gte")
                    if direction == "gte":
                        pct = sum(1 for s in scores if s >= threshold) / max(len(scores), 1) * 100
                    results[name] = {"value": round(pct, 1), "unit": "%", "label": q["display_label"]}
                else:
                    results[name] = {"value": round(mean(scores), 1), "unit": "/10", "label": q["display_label"]}
            elif q["type"] == "yes-no":
                yes_count = sum(1 for a in agents if a.get(f"checkpoint_{name}", "").lower() in ["yes", "y"])
                pct = yes_count / max(len(agents), 1) * 100
                results[name] = {"value": round(pct, 1), "unit": "%", "label": q["display_label"]}
        return results

    def compute_polarization_timeseries(self, agents_by_round, group_key):
        """Polarization index per round for the chart."""
        return [
            {"round": r, **compute_group_polarization(agents, group_key)}
            for r, agents in agents_by_round.items()
        ]

    def compute_opinion_flow(self, agents):
        return compute_opinion_flow(agents)

    def compute_influence(self, interactions):
        return build_influence_graph(interactions)

    def compute_cascades(self, posts, comments, agents):
        return compute_top_cascade(posts, comments, agents)
```

## Tests

- [ ] Polarization index = 0 for agents with identical scores
- [ ] Polarization index = 1 for perfectly bimodal distribution (all 1s and all 10s)
- [ ] Influence score correctly weights engagement (40%), comments (30%), replies (30%)
- [ ] Opinion flow preserves total agent count (sum(initial) == sum(final))
- [ ] Stance bucketing: 1-4 = dissenter, 5-6 = neutral, 7-10 = supporter
- [ ] Group chat selection returns correct segment (e.g., "dissenter" only returns agents with score < 5)
- [ ] Dynamic metrics computation handles empty agent lists gracefully
