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
    return _first_text(row, ("title", "content", "body", "summary"))


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


def compute_group_polarization(agents: list[dict[str, Any]], group_key: str = "planning_area") -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    all_scores: list[float] = []
    for agent in agents:
        key = str(agent.get("persona", {}).get(group_key, "Unknown"))
        score = _as_float(agent.get("opinion_post", 0.0))
        groups[key].append(score)
        all_scores.append(score)

    if not all_scores:
        return {
            "polarization_index": 0.0,
            "severity": "low",
            "by_group_means": {},
            "group_sizes": {},
        }

    overall_mean = _mean(all_scores)
    n = max(1, len(all_scores))
    between = sum(len(values) * ((_mean(values) - overall_mean) ** 2) for values in groups.values()) / n
    total_var = sum((score - overall_mean) ** 2 for score in all_scores) / n
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
        "by_group_means": {key: round(_mean(values), 4) for key, values in groups.items()},
        "group_sizes": {key: len(values) for key, values in groups.items()},
    }


def compute_opinion_flow(agents: list[dict[str, Any]]) -> dict[str, Any]:
    def bucket(score: float) -> str:
        if score >= 7:
            return "supporter"
        if score >= 5:
            return "neutral"
        return "dissenter"

    initial = {"supporter": 0, "neutral": 0, "dissenter": 0}
    final = {"supporter": 0, "neutral": 0, "dissenter": 0}
    flows: dict[tuple[str, str], int] = defaultdict(int)

    for agent in agents:
        pre = bucket(_as_float(agent.get("opinion_pre", 5)))
        post = bucket(_as_float(agent.get("opinion_post", 5)))
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
        score = _as_float(agent.get("opinion_post", 5))
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
        questions = payload.get("checkpoint_questions", [])
        if not isinstance(questions, list):
            return []
        return [item for item in questions if isinstance(item, dict)]

    def compute_dynamic_metrics(self, agents: list[dict[str, Any]], use_case: str, round_no: int | None = None) -> dict[str, Any]:
        del round_no
        questions = self._checkpoint_questions(use_case)
        results: dict[str, Any] = {}
        total_agents = max(len(agents), 1)

        for question in questions:
            name = question["metric_name"]
            label = question["display_label"]
            field = f"checkpoint_{name}"
            if question["type"] == "scale":
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
            elif question["type"] == "yes-no":
                yes_count = sum(1 for agent in agents if str(agent.get(field, "")).strip().lower() in {"yes", "y"})
                pct = yes_count / total_agents * 100
                results[name] = {"value": round(pct, 1), "unit": "%", "label": label}
        return results

    def compute_polarization_timeseries(self, agents_by_round: dict[int, list[dict[str, Any]]], group_key: str) -> list[dict[str, Any]]:
        return [{"round": round_no, **compute_group_polarization(agents, group_key)} for round_no, agents in agents_by_round.items()]

    def compute_group_polarization(self, agents: list[dict[str, Any]], group_key: str = "planning_area") -> dict[str, Any]:
        return compute_group_polarization(agents, group_key)

    def compute_opinion_flow(self, agents: list[dict[str, Any]]) -> dict[str, Any]:
        return compute_opinion_flow(agents)

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
    ) -> list[dict[str, Any]]:
        return select_group_chat_agents(agents, interactions, segment, top_n=top_n)
