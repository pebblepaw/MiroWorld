from __future__ import annotations

from collections import defaultdict
from statistics import mean as _mean
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:  # noqa: BLE001
        return int(default)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _summarize_text(value: Any, limit: int = 160) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _first_text(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _clean_text(row.get(key))
        if value:
            return value
    return ""


def _stance_from_score(score: float) -> str:
    if score >= 7:
        return "supporter"
    if score >= 5:
        return "neutral"
    return "dissenter"


def _stance_from_text(text: str) -> str:
    lowered = text.lower()
    support_hits = sum(1 for token in ("support", "agree", "upside", "benefit", "positive", "yes", "pro") if token in lowered)
    dissent_hits = sum(1 for token in ("risk", "concern", "oppose", "against", "problem", "negative", "no", "worry") if token in lowered)
    if support_hits > dissent_hits:
        return "supporter"
    if dissent_hits > support_hits:
        return "dissenter"
    return "neutral"


def _row_stance(row: dict[str, Any], agent: dict[str, Any] | None = None) -> str:
    stance = _clean_text(row.get("stance") or row.get("segment"))
    if stance:
        return stance
    if agent:
        agent_stance = _stance_from_score(_as_float(agent.get("opinion_post", agent.get("opinion_pre", 5.0))))
        if agent_stance:
            return agent_stance
    delta = _as_float(row.get("delta", 0.0))
    if delta > 0:
        return "supporter"
    if delta < 0:
        return "dissenter"
    text = _first_text(row, ("content", "body", "title", "summary"))
    return _stance_from_text(text) if text else "neutral"


def _agent_name(agent: dict[str, Any] | None, fallback: str) -> str:
    if not agent:
        return fallback
    for key in ("name", "agent_name", "display_name", "label"):
        value = _clean_text(agent.get(key))
        if value:
            return value
    persona = agent.get("persona")
    if isinstance(persona, dict):
        for key in ("name", "agent_name", "display_name", "label"):
            value = _clean_text(persona.get(key))
            if value:
                return value
    return fallback


def _actor_id(row: dict[str, Any]) -> str:
    return _clean_text(row.get("actor_agent_id") or row.get("author_agent_id") or row.get("agent_id") or row.get("author") or row.get("name"))


def _row_id(row: dict[str, Any]) -> str:
    return _clean_text(row.get("id") or row.get("post_id") or row.get("comment_id") or row.get("interaction_id"))


def _post_text(row: dict[str, Any]) -> str:
    return _first_text(row, ("content", "body", "summary", "title"))


def _is_discourse_interaction(row: dict[str, Any]) -> bool:
    action_type = _clean_text(row.get("action_type") or row.get("type")).lower()
    if action_type == "trace":
        return False
    content = _clean_text(row.get("content") or row.get("body") or row.get("title"))
    if not content:
        return False
    if content.startswith(("sign_up:", "refresh:", "search_posts:", "search_user:", "like_comment:", "like_post:")):
        return False
    return True


def _engagement_score(row: dict[str, Any]) -> float:
    likes = _as_int(row.get("likes", row.get("upvotes", 0)))
    dislikes = _as_int(row.get("dislikes", row.get("downvotes", 0)))
    delta = abs(_as_float(row.get("delta", 0.0)))
    return float(likes + dislikes) + delta


def _numeric_engagement(row: dict[str, Any]) -> tuple[int, int]:
    likes = _as_int(row.get("likes", row.get("upvotes", 0)))
    dislikes = _as_int(row.get("dislikes", row.get("downvotes", 0)))
    return likes, dislikes


def compute_polarization(agents: list[dict[str, Any]], score_field: str = "opinion_post") -> dict[str, Any]:
    """Compute polarization as bimodal clustering at opinion extremes.

    Polarization is high when agents cluster at both ends (≥7 and <5).
    It is 0 when all agents agree (consensus) and 1.0 when perfectly split 50/50.
    Formula: ``2 * min(supporter_pct, dissenter_pct)``.
    """
    scores = [_as_float(agent.get(score_field, 5.0)) for agent in agents]
    if not scores:
        return {
            "polarization_index": 0.0,
            "severity": "low",
            "distribution": {"supporter_pct": 0.0, "neutral_pct": 0.0, "dissenter_pct": 0.0},
        }

    total = len(scores)
    supporters = sum(1 for s in scores if s >= 7) / total
    neutrals = sum(1 for s in scores if 5 <= s < 7) / total
    dissenters = sum(1 for s in scores if s < 5) / total

    polarization_index = round(2 * min(supporters, dissenters), 4)

    severity = (
        "low" if polarization_index < 0.2 else
        "moderate" if polarization_index < 0.5 else
        "high" if polarization_index < 0.8 else
        "critical"
    )

    return {
        "polarization_index": polarization_index,
        "severity": severity,
        "distribution": {
            "supporter_pct": round(supporters * 100, 1),
            "neutral_pct": round(neutrals * 100, 1),
            "dissenter_pct": round(dissenters * 100, 1),
        },
    }


def compute_opinion_flow(
    agents: list[dict[str, Any]],
    score_field: str = "opinion_post",
    pre_field: str | None = None,
) -> dict[str, Any]:
    def bucket(score: float) -> str:
        if score >= 7:
            return "supporter"
        if score >= 5:
            return "neutral"
        return "dissenter"

    actual_pre_field = pre_field or ("opinion_pre" if score_field == "opinion_post" else score_field)

    initial = {"supporter": 0, "neutral": 0, "dissenter": 0}
    final = {"supporter": 0, "neutral": 0, "dissenter": 0}
    flows: dict[tuple[str, str], int] = defaultdict(int)

    for agent in agents:
        pre = bucket(_as_float(agent.get(actual_pre_field, 5)))
        post = bucket(_as_float(agent.get(score_field, 5)))
        initial[pre] += 1
        final[post] += 1
        flows[(pre, post)] += 1

    return {
        "initial": initial,
        "final": final,
        "flows": [{"from": source, "to": target, "count": count} for (source, target), count in flows.items()],
    }


def build_influence_graph(interactions: list[dict[str, Any]], agents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in (agents or [])
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }
    edges: dict[tuple[str, str], float] = {}
    actor_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    node_scores: dict[str, float] = defaultdict(float)
    for event in interactions:
        actor = _actor_id(event)
        target = _clean_text(event.get("target_agent_id") or event.get("target") or event.get("reply_to_agent_id"))
        if not actor:
            continue
        if not _is_discourse_interaction(event):
            continue
        actor_rows[actor].append(event)
        engagement_score = _engagement_score(event)
        node_scores[actor] += abs(_as_float(event.get("delta", 0.0))) + (engagement_score * 0.1) + (0.25 if _clean_text(event.get("action_type")).lower() == "comment" else 0.5)
        if not target:
            continue
        weight = abs(_as_float(event.get("delta", 0.0)))
        edges[(str(actor), str(target))] = edges.get((str(actor), str(target)), 0.0) + weight

    top_influencers = sorted(node_scores.items(), key=lambda item: item[1], reverse=True)[:10]
    top_ids = {agent_id for agent_id, _score in top_influencers}
    enriched_influencers: list[dict[str, Any]] = []
    for agent_id, score in top_influencers:
        rows = actor_rows.get(agent_id, [])
        agent = agent_lookup.get(agent_id)
        if rows:
            rows_sorted = sorted(rows, key=lambda row: (_engagement_score(row), abs(_as_float(row.get("delta", 0.0)))), reverse=True)
            top_row = rows_sorted[0]
        else:
            top_row = {}
        top_content = _post_text(top_row)
        viewpoint = _summarize_text(top_content or top_row.get("content") or top_row.get("body") or top_row.get("title"), 160)
        stance = _row_stance(top_row, agent)
        name = _agent_name(agent, agent_id)
        enriched_influencers.append(
            {
                "agent_id": agent_id,
                "name": name,
                "agent_name": name,
                "stance": stance,
                "segment": stance,
                "influence": round(score, 4),
                "influence_score": round(score, 4),
                "score": round(score, 4),
                "top_view": viewpoint,
                "core_viewpoint": viewpoint,
                "top_post": {
                    "post_id": _row_id(top_row) or None,
                    "title": _clean_text(top_row.get("title")) or None,
                    "content": _clean_text(top_row.get("content") or top_row.get("body")) or None,
                    "body": _clean_text(top_row.get("body") or top_row.get("content")) or None,
                    "likes": _numeric_engagement(top_row)[0],
                    "dislikes": _numeric_engagement(top_row)[1],
                    "stance": stance,
                },
            }
        )

    return {
        "top_influencers": enriched_influencers,
        "leaders": [dict(item) for item in enriched_influencers],
        "items": [dict(item) for item in enriched_influencers],
        "nodes": [
            {
                "id": item["agent_id"],
                "name": item["name"],
                "agent_name": item["agent_name"],
                "stance": item["stance"],
                "influence_score": item["influence_score"],
                "top_view": item["top_view"],
                "top_post": item["top_post"],
            }
            for item in enriched_influencers
        ],
        "edges": [
            {"source": actor, "target": target, "weight": round(weight, 4)}
            for (actor, target), weight in edges.items()
            if actor in top_ids or target in top_ids
        ],
        "total_nodes": len(node_scores),
        "total_edges": len(edges),
    }


def compute_top_cascade(posts: list[dict[str, Any]], comments: list[dict[str, Any]], agents: list[dict[str, Any]]) -> dict[str, Any]:
    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in agents
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }
    posts_by_id: dict[str, dict[str, Any]] = {}
    posts_by_actor_round: dict[tuple[str, int], str] = {}
    posts_by_actor: dict[str, list[str]] = defaultdict(list)
    for post in posts:
        post_id = _row_id(post)
        if not post_id:
            continue
        posts_by_id[post_id] = post
        actor_id = _actor_id(post)
        round_no = _as_int(post.get("round_no", 0))
        if actor_id:
            posts_by_actor_round[(actor_id, round_no)] = post_id
            posts_by_actor[actor_id].append(post_id)

    comments_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for comment in comments:
        parent = _clean_text(
            comment.get("parent_post_id")
            or comment.get("parent_id")
            or comment.get("root_post_id")
            or comment.get("reply_to_post_id")
            or comment.get("post_id")
        )
        if not parent:
            actor_id = _actor_id(comment)
            round_no = _as_int(comment.get("round_no", 0))
            target_agent = _clean_text(comment.get("target_agent_id"))
            if actor_id and (actor_id, round_no) in posts_by_actor_round:
                parent = posts_by_actor_round[(actor_id, round_no)]
            elif target_agent and posts_by_actor.get(target_agent):
                parent = posts_by_actor[target_agent][-1]
            elif posts:
                parent = _row_id(posts[-1])
        if parent:
            comments_by_parent[parent].append(comment)

    def build_comment_node(comment: dict[str, Any]) -> dict[str, Any]:
        actor_id = _actor_id(comment)
        agent = agent_lookup.get(actor_id)
        children = [build_comment_node(child) for child in comments_by_parent.get(_row_id(comment), []) if _row_id(child) != _row_id(comment)]
        likes, dislikes = _numeric_engagement(comment)
        stance = _row_stance(comment, agent)
        node = {
            "comment_id": _row_id(comment) or None,
            "author": actor_id or None,
            "author_name": _agent_name(agent, actor_id or "unknown"),
            "stance": stance,
            "content": _clean_text(comment.get("content") or comment.get("body")) or None,
            "body": _clean_text(comment.get("body") or comment.get("content")) or None,
            "likes": likes,
            "upvotes": likes,
            "dislikes": dislikes,
            "downvotes": dislikes,
        }
        if children:
            node["comments"] = children
        return node

    viral_posts: list[dict[str, Any]] = []
    for post in posts:
        post_id = _row_id(post)
        if not post_id:
            continue
        actor_id = _actor_id(post)
        agent = agent_lookup.get(actor_id)
        thread_comments = [build_comment_node(comment) for comment in comments_by_parent.get(post_id, [])]
        comment_count = len(thread_comments)
        comment_likes = sum(int(comment.get("likes", 0) or 0) for comment in thread_comments)
        comment_dislikes = sum(int(comment.get("dislikes", 0) or 0) for comment in thread_comments)
        post_likes, post_dislikes = _numeric_engagement(post)
        raw_likes = post_likes + comment_likes + max(0, int(round(_as_float(post.get("delta", 0.0)) * 2)))
        raw_dislikes = post_dislikes + comment_dislikes + max(0, int(round(abs(min(0.0, _as_float(post.get("delta", 0.0)))) * 2)))
        discussion_deltas: list[float] = []
        engaged_agents = {actor_id} if actor_id else set()
        for comment in comments_by_parent.get(post_id, []):
            comment_actor = _actor_id(comment)
            if comment_actor:
                engaged_agents.add(comment_actor)
            if comment_actor and (agent := agent_lookup.get(comment_actor)):
                discussion_deltas.append(_as_float(agent.get("opinion_post", 0.0)) - _as_float(agent.get("opinion_pre", 0.0)))
        if actor_id and (agent := agent_lookup.get(actor_id)):
            discussion_deltas.append(_as_float(agent.get("opinion_post", 0.0)) - _as_float(agent.get("opinion_pre", 0.0)))
        mean_delta = _mean(discussion_deltas) if discussion_deltas else 0.0
        content = _post_text(post)
        title = _clean_text(post.get("title")) or _summarize_text(content, 80) or f"Post {post_id}"
        stance = _row_stance(post, agent)
        engagement_score = _engagement_score(post) + comment_count + sum(abs(delta) for delta in discussion_deltas)
        viral_posts.append(
            {
                "post_id": post_id,
                "author": actor_id or None,
                "author_name": _agent_name(agent, actor_id or "unknown"),
                "stance": stance,
                "segment": stance,
                "title": title,
                "content": content or None,
                "body": _clean_text(post.get("body") or content) or None,
                "likes": raw_likes,
                "upvotes": raw_likes,
                "dislikes": raw_dislikes,
                "downvotes": raw_dislikes,
                "comments": thread_comments,
                "engagement_score": round(engagement_score, 4),
                "tree_size": comment_count,
                "total_engagement": raw_likes + raw_dislikes,
                "mean_opinion_delta": round(mean_delta, 4),
                "engaged_agents": sorted(engaged_agents),
            }
        )

    viral_posts.sort(key=lambda item: (item["engagement_score"], item["total_engagement"], item["tree_size"]), reverse=True)
    best = viral_posts[0] if viral_posts else {
        "post_id": None,
        "author": None,
        "author_name": None,
        "stance": "neutral",
        "segment": "neutral",
        "title": None,
        "content": None,
        "body": None,
        "likes": 0,
        "upvotes": 0,
        "dislikes": 0,
        "downvotes": 0,
        "comments": [],
        "engagement_score": 0.0,
        "tree_size": 0,
        "total_engagement": 0,
        "mean_opinion_delta": 0.0,
        "engaged_agents": [],
    }

    return {
        "viral_posts": viral_posts,
        "cascades": viral_posts,
        "top_threads": viral_posts,
        "posts": viral_posts,
        "post_id": best["post_id"],
        "tree_size": best["tree_size"],
        "total_engagement": best["total_engagement"],
        "mean_opinion_delta": best["mean_opinion_delta"],
        "engaged_agents": best["engaged_agents"],
    }


def select_group_chat_agents(
    agents: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
    segment: str,
    top_n: int = 5,
    score_field: str = "opinion_post",
) -> list[dict[str, Any]]:
    influence: dict[str, dict[str, float]] = {}
    for agent in agents:
        agent_id = str(agent.get("id") or agent.get("agent_id") or "")
        if not agent_id:
            continue
        agent_posts = [item for item in interactions if str(item.get("actor_agent_id")) == agent_id]
        post_engagement = sum(int(item.get("likes", 0) or 0) + int(item.get("dislikes", 0) or 0) for item in agent_posts)
        comment_count = sum(1 for item in agent_posts if item.get("type") == "comment")
        replies_received = sum(1 for item in interactions if str(item.get("target_agent_id")) == agent_id)
        influence[agent_id] = {
            "raw_engagement": float(post_engagement),
            "raw_comments": float(comment_count),
            "raw_replies": float(replies_received),
        }

    if not influence:
        return []

    max_eng = max((value["raw_engagement"] for value in influence.values()), default=1.0) or 1.0
    max_com = max((value["raw_comments"] for value in influence.values()), default=1.0) or 1.0
    max_rep = max((value["raw_replies"] for value in influence.values()), default=1.0) or 1.0

    agent_lookup = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in agents
        if (agent.get("id") is not None or agent.get("agent_id") is not None)
    }

    def get_stance(agent_id: str) -> str:
        agent = agent_lookup.get(agent_id)
        if not agent:
            return "unknown"
        score = _as_float(agent.get(score_field, 5))
        if score >= 7:
            return "supporter"
        if score >= 5:
            return "neutral"
        return "dissenter"

    ranked: list[tuple[str, dict[str, float]]] = []
    for agent_id, value in influence.items():
        value["score"] = (
            0.4 * (value["raw_engagement"] / max_eng)
            + 0.3 * (value["raw_comments"] / max_com)
            + 0.3 * (value["raw_replies"] / max_rep)
        )
        ranked.append((agent_id, value))

    ranked.sort(key=lambda item: item[1]["score"], reverse=True)
    if segment != "engaged":
        ranked = [item for item in ranked if get_stance(item[0]) == segment]

    return [{"agent_id": agent_id, "influence_score": round(value["score"], 4)} for agent_id, value in ranked[: max(0, int(top_n))]]


class MetricsService:
    """Compute simulation analytics metrics from checkpoint and trace data."""

    def __init__(self, config_service: Any) -> None:
        self.config = config_service

    def _checkpoint_questions(self, use_case: str) -> list[dict[str, Any]]:
        # Try new V2 analysis_questions first
        getter = getattr(self.config, "get_analysis_questions", None)
        if callable(getter):
            try:
                questions = getter(use_case)
                if isinstance(questions, list) and questions:
                    return [item for item in questions if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                pass
        # Fallback to V1 checkpoint_questions
        getter = getattr(self.config, "get_checkpoint_questions", None)
        if callable(getter):
            try:
                questions = getter(use_case)
                if isinstance(questions, list):
                    return [item for item in questions if isinstance(item, dict)]
            except Exception:  # noqa: BLE001
                return []
        use_case_getter = getattr(self.config, "get_use_case", None)
        if not callable(use_case_getter):
            return []
        try:
            payload = use_case_getter(use_case)
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(payload, dict):
            return []
        questions = payload.get("analysis_questions", payload.get("checkpoint_questions", []))
        if not isinstance(questions, list):
            return []
        return [item for item in questions if isinstance(item, dict)]

    def compute_dynamic_metrics(self, agents: list[dict[str, Any]], use_case: str, round_no: int | None = None) -> dict[str, Any]:
        del round_no
        questions = self._checkpoint_questions(use_case)
        results: dict[str, Any] = {}
        total_agents = max(len(agents), 1)

        for question in questions:
            q_type = question.get("type", "scale")
            name = question.get("metric_name", "")
            if not name:
                continue
            # V2 uses metric_label, V1 uses display_label
            label = question.get("metric_label", question.get("display_label", name))
            field = f"checkpoint_{name}"

            # Skip open-ended questions — no numeric metric to compute
            if q_type == "open-ended":
                continue

            if q_type == "scale":
                scores = [_as_float(agent.get(field, 5)) for agent in agents]
                if "threshold" in question:
                    threshold = _as_float(question["threshold"], 7)
                    direction = question.get("threshold_direction", "gte")
                    if direction == "gte":
                        pct = sum(1 for score in scores if score >= threshold) / total_agents * 100
                    else:
                        pct = sum(1 for score in scores if score <= threshold) / total_agents * 100
                    results[name] = {"value": round(pct, 1), "unit": "%", "label": label}
                else:
                    results[name] = {"value": round(_mean(scores) if scores else 0.0, 1), "unit": "/10", "label": label}
            elif q_type == "yes-no":
                yes_count = sum(1 for agent in agents if str(agent.get(field, "")).strip().lower() in {"yes", "y"})
                pct = yes_count / total_agents * 100
                results[name] = {"value": round(pct, 1), "unit": "%", "label": label}
        return results

    # ── Existing analytics methods ──

    def compute_polarization_timeseries(self, agents_by_round: dict[int, list[dict[str, Any]]], score_field: str = "opinion_post") -> list[dict[str, Any]]:
        return [{"round": round_no, **compute_polarization(agents, score_field)} for round_no, agents in agents_by_round.items()]

    def compute_polarization(self, agents: list[dict[str, Any]], score_field: str = "opinion_post") -> dict[str, Any]:
        return compute_polarization(agents, score_field)

    def compute_opinion_flow(self, agents: list[dict[str, Any]], score_field: str = "opinion_post", pre_field: str | None = None) -> dict[str, Any]:
        return compute_opinion_flow(agents, score_field, pre_field)

    def compute_influence(self, interactions: list[dict[str, Any]], agents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return build_influence_graph(interactions, agents)

    def compute_cascades(self, posts: list[dict[str, Any]], comments: list[dict[str, Any]], agents: list[dict[str, Any]]) -> dict[str, Any]:
        return compute_top_cascade(posts, comments, agents)

    def select_group_chat_agents(
        self,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        segment: str,
        top_n: int = 5,
        score_field: str = "opinion_post",
    ) -> list[dict[str, Any]]:
        return select_group_chat_agents(agents, interactions, segment, top_n=top_n, score_field=score_field)

    # ── New V2 insight-block methods ──

    def compute_segment_heatmap(
        self,
        agents: list[dict[str, Any]],
        analysis_questions: list[dict[str, Any]],
        group_key: str = "planning_area",
    ) -> dict[str, Any]:
        """Compute metric scores broken out by demographic segment.

        Returns a heatmap-ready structure: {segments: [{segment, metrics: {name: value}}]}.
        Only quantitative analysis_questions are included.
        """
        quantitative = [q for q in analysis_questions if q.get("type") in ("scale", "yes-no")]
        if not quantitative:
            return {"status": "not_applicable", "reason": "No quantitative analysis questions to segment."}

        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for agent in agents:
            key = str(agent.get("persona", {}).get(group_key, "Unknown"))
            groups[key].append(agent)

        segments: list[dict[str, Any]] = []
        for segment_name, segment_agents in sorted(groups.items(), key=lambda x: -len(x[1])):
            metrics: dict[str, float] = {}
            total = max(len(segment_agents), 1)
            for q in quantitative:
                field = f"checkpoint_{q['metric_name']}"
                if q["type"] == "scale":
                    scores = [_as_float(a.get(field, 5)) for a in segment_agents]
                    if "threshold" in q:
                        threshold = _as_float(q["threshold"], 7)
                        metrics[q["metric_name"]] = round(sum(1 for s in scores if s >= threshold) / total * 100, 1)
                    else:
                        metrics[q["metric_name"]] = round(_mean(scores) if scores else 0.0, 1)
                elif q["type"] == "yes-no":
                    yes_count = sum(1 for a in segment_agents if str(a.get(field, "")).strip().lower() in {"yes", "y"})
                    metrics[q["metric_name"]] = round(yes_count / total * 100, 1)
            segments.append({"segment": segment_name, "count": len(segment_agents), "metrics": metrics})

        return {"segments": segments[:15]}

    def extract_pain_points(
        self,
        interactions: list[dict[str, Any]],
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Extract top pain points from negative-sentiment interactions.

        Uses a simple heuristic: interactions with negative delta or dissenting stance.
        Returns ranked list of complaint themes with frequency counts.
        """
        negative_content: list[str] = []
        for row in interactions:
            if not _is_discourse_interaction(row):
                continue
            delta = _as_float(row.get("delta", 0.0))
            content = _clean_text(row.get("content") or row.get("body") or "")
            if delta < 0 and content:
                negative_content.append(content)

        if not negative_content:
            return {"status": "not_applicable", "reason": "No negative interactions found to extract pain points."}

        # Simple keyword frequency extraction as a heuristic
        # In production, this would use LLM-assisted theme extraction
        word_freq: dict[str, int] = defaultdict(int)
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "i", "my", "me",
                       "this", "that", "it", "to", "of", "in", "for", "and", "or", "not", "with",
                       "but", "on", "at", "by", "from", "as", "do", "does", "did", "have", "has",
                       "will", "would", "could", "should", "can", "may", "no", "so", "if", "we"}
        for text in negative_content:
            words = text.lower().split()
            for word in words:
                cleaned = "".join(c for c in word if c.isalnum())
                if len(cleaned) > 3 and cleaned not in stop_words:
                    word_freq[cleaned] += 1

        top_terms = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
        pain_points = [{"term": term, "frequency": freq, "sample_count": len(negative_content)} for term, freq in top_terms]
        return {"pain_points": pain_points, "total_negative_posts": len(negative_content)}

    def extract_top_objections(
        self,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        metric_name: str,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Extract top objections from agents who scored low on a metric."""
        field = f"checkpoint_{metric_name}"
        low_agents = {
            str(a.get("id") or a.get("agent_id"))
            for a in agents
            if _as_float(a.get(field, 5)) < 4
        }

        if not low_agents:
            return {"status": "not_applicable", "reason": "No agents scored low enough to extract objections."}

        objection_texts: list[dict[str, Any]] = []
        for row in interactions:
            if not _is_discourse_interaction(row):
                continue
            actor = _actor_id(row)
            if actor in low_agents:
                content = _clean_text(row.get("content") or row.get("body") or "")
                if content:
                    objection_texts.append({
                        "agent_id": actor,
                        "content": _summarize_text(content, 200),
                        "round_no": _as_int(row.get("round_no", 0)),
                    })

        objection_texts.sort(key=lambda x: _engagement_score(x) if isinstance(x, dict) else 0, reverse=True)
        return {"objections": objection_texts[:top_n], "low_scoring_agents": len(low_agents)}

    def get_top_advocates(
        self,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        metric_name: str | None = None,
        top_n: int = 3,
    ) -> dict[str, Any]:
        """Get agents with highest scores on a given metric, plus their key posts."""
        if metric_name:
            field = f"checkpoint_{metric_name}"
            scored = [(a, _as_float(a.get(field, 5))) for a in agents]
        else:
            scored = [(a, _as_float(a.get("opinion_post", 5))) for a in agents]

        scored.sort(key=lambda x: x[1], reverse=True)
        top_agents = scored[:top_n]

        advocates: list[dict[str, Any]] = []
        for agent, score in top_agents:
            agent_id = str(agent.get("id") or agent.get("agent_id") or "")
            # Find their best post
            agent_posts = [
                row for row in interactions
                if _actor_id(row) == agent_id and _is_discourse_interaction(row)
            ]
            agent_posts.sort(key=lambda r: _engagement_score(r), reverse=True)
            best_post = agent_posts[0] if agent_posts else {}
            advocates.append({
                "agent_id": agent_id,
                "name": _agent_name(agent, agent_id),
                "score": round(score, 1),
                "key_post": _summarize_text(_post_text(best_post), 200) if best_post else None,
                "persona_summary": _build_persona_summary(agent),
            })

        return {"advocates": advocates}

    def get_viral_posts(
        self,
        interactions: list[dict[str, Any]],
        top_n: int = 3,
    ) -> dict[str, Any]:
        """Get posts sorted by total engagement (likes + dislikes + comments)."""
        posts = [
            row for row in interactions
            if str(row.get("action_type", "")).lower() in {"create_post", "post_created", "post"}
        ]
        if not posts:
            return {"status": "not_applicable", "reason": "No posts found in simulation data."}

        enriched: list[dict[str, Any]] = []
        for post in posts:
            engagement = _engagement_score(post)
            likes, dislikes = _numeric_engagement(post)
            enriched.append({
                "post_id": _row_id(post),
                "author": _actor_id(post),
                "content": _summarize_text(_post_text(post), 200),
                "likes": likes,
                "dislikes": dislikes,
                "engagement_score": round(engagement, 2),
                "round_no": _as_int(post.get("round_no", 0)),
            })

        enriched.sort(key=lambda x: x["engagement_score"], reverse=True)
        return {"viral_posts": enriched[:top_n]}

    def compute_reaction_distribution(
        self,
        agents: list[dict[str, Any]],
        metric_name: str,
    ) -> dict[str, Any]:
        """Compute histogram distribution of a metric across agents."""
        field = f"checkpoint_{metric_name}"
        scores = [_as_float(a.get(field, 5)) for a in agents]
        if not scores:
            return {"status": "not_applicable", "reason": "No scores found for this metric."}

        # Build histogram buckets (1-10 scale)
        buckets = {i: 0 for i in range(1, 11)}
        for score in scores:
            bucket = max(1, min(10, int(round(score))))
            buckets[bucket] += 1

        return {
            "metric_name": metric_name,
            "distribution": [{"score": k, "count": v} for k, v in sorted(buckets.items())],
            "mean": round(_mean(scores), 2),
            "total_agents": len(scores),
        }

    def compute_insight_block(
        self,
        block_type: str,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        analysis_questions: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Dispatch an insight block computation by type.

        Returns the computed data, or a not_applicable status if data is insufficient.
        """
        if block_type == "polarization_index":
            return self.compute_polarization(agents)
        elif block_type == "opinion_flow":
            return self.compute_opinion_flow(agents)
        elif block_type == "top_influencers":
            return self.compute_influence(interactions, agents)
        elif block_type == "viral_cascade":
            posts = [r for r in interactions if str(r.get("action_type", "")).lower() in {"create_post", "post_created", "post"}]
            comments = [r for r in interactions if "comment" in str(r.get("action_type", "")).lower()]
            return compute_top_cascade(posts, comments, agents)
        elif block_type == "segment_heatmap":
            return self.compute_segment_heatmap(agents, analysis_questions, kwargs.get("group_key", "planning_area"))
        elif block_type == "reaction_spectrum":
            # Alias: treat reaction_spectrum as segment_heatmap
            return self.compute_segment_heatmap(agents, analysis_questions, kwargs.get("group_key", "planning_area"))
        elif block_type == "pain_points":
            return self.extract_pain_points(interactions, top_n=kwargs.get("count", 5))
        elif block_type == "top_advocates":
            metric_ref = kwargs.get("metric_ref")
            return self.get_top_advocates(agents, interactions, metric_name=metric_ref, top_n=kwargs.get("count", 3))
        elif block_type == "top_objections":
            metric_ref = kwargs.get("metric_ref", "conversion_intent")
            return self.extract_top_objections(agents, interactions, metric_ref, top_n=kwargs.get("count", 5))
        elif block_type == "viral_posts":
            return self.get_viral_posts(interactions, top_n=kwargs.get("count", 3))
        else:
            raise ValueError(f"Unknown insight block type: {block_type}")


def _build_persona_summary(agent: dict[str, Any]) -> str:
    """Build a short persona summary from agent data."""
    persona = agent.get("persona", {})
    parts: list[str] = []
    for key in ("age", "occupation", "planning_area", "income_bracket"):
        val = _clean_text(persona.get(key))
        if val:
            parts.append(val)
    return ", ".join(parts) if parts else "Unknown"
