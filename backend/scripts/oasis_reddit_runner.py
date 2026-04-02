from __future__ import annotations

import asyncio
import json
import os
import random
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class RunnerInput:
    simulation_id: str
    policy_summary: str
    rounds: int
    personas: list[dict[str, Any]]
    model_name: str
    api_key: str
    base_url: str
    oasis_db_path: str
    events_path: str | None = None
    elapsed_offset_seconds: int = 0
    tail_checkpoint_estimate_seconds: int = 0
    oasis_semaphore: int = 128


def _to_profile(persona: dict[str, Any], idx: int) -> dict[str, Any]:
    age = int(persona.get("age") or random.randint(21, 70))
    username = f"sg_agent_{idx + 1}"
    name = str(persona.get("name") or persona.get("full_name") or f"SG Agent {idx + 1}")
    planning_area = str(persona.get("planning_area") or "Singapore")
    occupation = str(persona.get("occupation") or "Resident")
    industry = str(persona.get("industry") or "")
    agent_id = str(persona.get("agent_id") or f"agent-{idx + 1:04d}")
    relevance = float(persona.get("mckainsey_relevance_score") or 0.0)
    matched_nodes = [
        str(value).strip()
        for value in (persona.get("mckainsey_matched_context_nodes") or [])
        if str(value).strip()
    ]
    dossier = str(persona.get("mckainsey_context") or "").strip()
    subtitle_parts = [part for part in [planning_area, occupation] if part and part.lower() != "unknown"]
    subtitle = " · ".join(subtitle_parts) or "Sampled persona"
    persona_text = (
        f"{age}-year-old {occupation} in {planning_area}."
    )
    if industry:
        persona_text += f" Industry context: {industry}."
    if dossier:
        persona_text += f" Policy dossier: {dossier}"
    if matched_nodes:
        persona_text += f" Relevant knowledge graph nodes: {', '.join(matched_nodes[:6])}."
    if relevance >= 0.75:
        persona_text += " This issue is directly relevant to you, so you should feel motivated to post or reply early."
    elif relevance >= 0.45:
        persona_text += " This issue is moderately relevant to you, so you should engage when the discussion touches your situation."
    else:
        persona_text += " You may not be directly affected, but you should still react when community discussion surfaces broader Singapore-wide implications."
    return {
        "user_id": idx,
        "agent_id": agent_id,
        "username": username,
        "realname": name,
        "user_name": username,
        "name": name,
        "display_name": name,
        "subtitle": subtitle,
        "bio": persona_text,
        "persona": persona_text,
        "age": age,
        "gender": str(persona.get("sex") or persona.get("gender") or "unknown"),
        "mbti": str(persona.get("mbti") or "ISFJ"),
        "country": "Singapore",
        "karma": int(persona.get("karma") or random.randint(20, 5000)),
        "created_at": "2024-01-01",
    }


def _approval(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return len([s for s in scores if s >= 7.0]) / len(scores)


def _seed_opinion(persona: dict[str, Any]) -> float:
    base = 5.5
    age = persona.get("age")
    if isinstance(age, (int, float)):
        if age >= 60:
            base -= 0.8
        elif age <= 30:
            base += 0.4

    income = str(persona.get("income_bracket", "")).lower()
    if "$1,000" in income or "$2,000" in income or "$3,000" in income:
        base -= 0.5
    if "$10,000" in income or "$12,000" in income:
        base += 0.6

    return max(1.0, min(10.0, base + random.uniform(-1.0, 1.0)))


def _extract_title(content: str) -> str:
    text = " ".join(str(content or "").split()).strip()
    if not text:
        return "New discussion thread"
    for separator in [". ", "! ", "? ", "\n"]:
        if separator in text:
            candidate = text.split(separator, 1)[0].strip()
            if len(candidate) >= 18:
                return candidate[:84]
    return text[:84]


def _build_seed_post_content(policy_summary: str, index: int) -> str:
    summary_excerpt = " ".join(str(policy_summary or "").split()).strip()[:220]
    if not summary_excerpt:
        summary_excerpt = "Discuss this policy and how it may affect Singapore residents."
    return f"Policy thread kickoff {index + 1}: {summary_excerpt}"


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _count_table(conn: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"] if row else 0)


async def run_simulation(payload: RunnerInput) -> dict[str, Any]:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import ActionType, LLMAction, ManualAction, generate_reddit_agent_graph

    event_file = None
    if payload.events_path:
        event_path = Path(payload.events_path)
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_file = event_path.open("a", encoding="utf-8")

    def emit_event(event_type: str, **data: Any) -> None:
        if not event_file:
            return
        event = {
            "event_type": event_type,
            "session_id": payload.simulation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            **data,
        }
        event_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        event_file.flush()

    ordered_personas = sorted(
        payload.personas,
        key=lambda persona: float(persona.get("mckainsey_relevance_score") or 0.0),
        reverse=True,
    )
    print(
        f"[oasis-runner] start simulation_id={payload.simulation_id} agents={len(payload.personas)} rounds={payload.rounds}",
        flush=True,
    )
    emit_event(
        "run_started",
        round_no=0,
        agent_count=len(payload.personas),
        platform="reddit",
        planned_rounds=payload.rounds,
    )

    os.environ["OPENAI_API_KEY"] = payload.api_key
    os.environ["OPENAI_BASE_URL"] = payload.base_url

    profiles_path = Path(payload.oasis_db_path).with_suffix(".profiles.json")
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles = [_to_profile(p, idx) for idx, p in enumerate(ordered_personas)]
    profile_lookup = {
        int(profile["user_id"]): {
            "agent_id": str(profile["agent_id"]),
            "display_name": str(profile.get("display_name") or profile["name"]),
            "subtitle": str(profile.get("subtitle") or "Sampled persona"),
        }
        for profile in profiles
    }
    profiles_path.write_text(json.dumps(profiles), encoding="utf-8")

    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=payload.model_name,
    )

    available_actions = [
        ActionType.LIKE_POST,
        ActionType.DISLIKE_POST,
        ActionType.CREATE_POST,
        ActionType.CREATE_COMMENT,
        ActionType.LIKE_COMMENT,
        ActionType.DISLIKE_COMMENT,
        ActionType.SEARCH_POSTS,
        ActionType.SEARCH_USER,
        ActionType.TREND,
        ActionType.REFRESH,
        ActionType.DO_NOTHING,
        ActionType.FOLLOW,
        ActionType.MUTE,
    ]

    agent_graph = await generate_reddit_agent_graph(
        profile_path=str(profiles_path),
        model=model,
        available_actions=available_actions,
    )

    db_path = Path(payload.oasis_db_path)
    if db_path.exists():
        db_path.unlink()

    env = oasis.make(
        agent_graph=agent_graph,
        platform=oasis.DefaultPlatformType.REDDIT,
        database_path=str(db_path),
        semaphore=max(1, int(payload.oasis_semaphore)),
    )

    await env.reset()
    start_monotonic = time.monotonic()

    # Seed the policy into the discussion thread before autonomous rounds.
    seed_actions: dict[Any, Any] = {}
    seed_agents = [agent for _, agent in env.agent_graph.get_agents()][: min(5, len(profiles))]
    for i, agent in enumerate(seed_agents):
        seed_actions[agent] = ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={
                "content": _build_seed_post_content(payload.policy_summary, i)
            },
        )
    await env.step(seed_actions)
    print("[oasis-runner] seed posts injected", flush=True)
    emit_event("seed_post_created", round_no=0, count=len(seed_actions))

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    last_seen = {"post": 0, "comment": 0, "like": 0, "dislike": 0}
    _emit_incremental_db_events(
        conn,
        profile_lookup=profile_lookup,
        user_map=None,
        last_seen=last_seen,
        round_no=0,
        emit_event=emit_event,
        started_at=start_monotonic,
        planned_rounds=payload.rounds,
        elapsed_offset_seconds=payload.elapsed_offset_seconds,
        tail_checkpoint_estimate_seconds=payload.tail_checkpoint_estimate_seconds,
    )

    for i in range(payload.rounds):
        emit_event("round_started", round_no=i + 1)
        actions = {agent: LLMAction() for _, agent in env.agent_graph.get_agents()}
        await env.step(actions)
        _emit_incremental_db_events(
            conn,
            profile_lookup=profile_lookup,
            user_map=None,
            last_seen=last_seen,
            round_no=i + 1,
            emit_event=emit_event,
            started_at=start_monotonic,
            planned_rounds=payload.rounds,
            elapsed_offset_seconds=payload.elapsed_offset_seconds,
            tail_checkpoint_estimate_seconds=payload.tail_checkpoint_estimate_seconds,
        )
        emit_event("round_completed", round_no=i + 1)
        print(f"[oasis-runner] completed round {i + 1}/{payload.rounds}", flush=True)

    await env.close()
    print("[oasis-runner] env closed, collecting artifacts", flush=True)

    user_rows = conn.execute("SELECT user_id, name FROM user ORDER BY user_id").fetchall()
    user_map = {int(r["user_id"]): profile_lookup.get(int(r["user_id"]), {}).get("agent_id", f"agent-{int(r['user_id']) + 1:04d}") for r in user_rows}

    interactions: list[dict[str, Any]] = []

    post_rows = conn.execute(
        "SELECT post_id, user_id, content, created_at FROM post ORDER BY post_id"
    ).fetchall()
    for row in post_rows:
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": None,
                "action_type": "create_post",
                "content": row["content"],
                "delta": 0.08,
            }
        )

    comment_rows = conn.execute(
        "SELECT comment_id, post_id, user_id, content, created_at FROM comment ORDER BY comment_id"
    ).fetchall()
    post_owner_map = {int(r["post_id"]): int(r["user_id"]) for r in post_rows}
    for row in comment_rows:
        target_user = post_owner_map.get(int(row["post_id"]))
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": user_map.get(target_user) if target_user is not None else None,
                "action_type": "comment",
                "content": row["content"],
                "delta": 0.04,
            }
        )

    like_rows = conn.execute("SELECT user_id, post_id FROM like ORDER BY like_id").fetchall()
    for row in like_rows:
        target_user = post_owner_map.get(int(row["post_id"]))
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": user_map.get(target_user) if target_user is not None else None,
                "action_type": "like_post",
                "content": f"Liked post {row['post_id']}",
                "delta": 0.02,
            }
        )

    dislike_rows = conn.execute("SELECT user_id, post_id FROM dislike ORDER BY dislike_id").fetchall()
    for row in dislike_rows:
        target_user = post_owner_map.get(int(row["post_id"]))
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": user_map.get(target_user) if target_user is not None else None,
                "action_type": "dislike_post",
                "content": f"Disliked post {row['post_id']}",
                "delta": -0.02,
            }
        )

    trace_rows = conn.execute(
        "SELECT user_id, action, info FROM trace ORDER BY created_at"
    ).fetchall()
    for row in trace_rows:
        interactions.append(
            {
                "round_no": 1,
                "actor_agent_id": user_map.get(int(row["user_id"]), f"agent-{int(row['user_id']) + 1:04d}"),
                "target_agent_id": None,
                "action_type": "trace",
                "content": f"{row['action']}: {row['info']}",
                "delta": 0.0,
            }
        )

    simulation_elapsed_seconds = max(1, int(time.monotonic() - start_monotonic))
    counters = {
        "posts": len(post_rows),
        "comments": len(comment_rows),
        "reactions": len(like_rows) + len(dislike_rows),
        "active_authors": len({event["actor_agent_id"] for event in interactions if event["action_type"] in {"create_post", "comment"}}),
    }
    conn.close()
    if event_file:
        event_file.close()

    agents: list[dict[str, Any]] = []
    pre_scores: list[float] = []
    post_scores: list[float] = []
    actor_balance: dict[str, float] = {}
    for event in interactions:
        actor_balance[event["actor_agent_id"]] = actor_balance.get(event["actor_agent_id"], 0.0) + float(event.get("delta", 0.0))

    for idx, persona in enumerate(ordered_personas):
        agent_id = profile_lookup.get(idx, {}).get("agent_id", f"agent-{idx + 1:04d}")
        opinion_pre = _seed_opinion(persona)
        opinion_post = max(1.0, min(10.0, opinion_pre + actor_balance.get(agent_id, 0.0)))
        pre_scores.append(opinion_pre)
        post_scores.append(opinion_post)
        agents.append(
            {
                "agent_id": agent_id,
                "persona": persona,
                "opinion_pre": opinion_pre,
                "opinion_post": opinion_post,
            }
        )

    return {
        "simulation_id": payload.simulation_id,
        "agents": agents,
        "interactions": interactions,
        "stage3a_approval_rate": round(_approval(pre_scores), 4),
        "stage3b_approval_rate": round(_approval(post_scores), 4),
        "net_opinion_shift": (sum(post_scores) / len(post_scores)) - (sum(pre_scores) / len(pre_scores)),
        "runtime": "oasis",
        "oasis_db_path": str(db_path),
        "elapsed_seconds": simulation_elapsed_seconds,
        "counters": counters,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: oasis_reddit_runner.py <input_json> <output_json>")

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    payload = RunnerInput(**json.loads(input_path.read_text(encoding="utf-8")))
    result = asyncio.run(run_simulation(payload))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result), encoding="utf-8")


def _emit_incremental_db_events(
    conn: sqlite3.Connection,
    *,
    profile_lookup: dict[int, dict[str, Any]],
    user_map: dict[int, str] | None,
    last_seen: dict[str, int],
    round_no: int,
    emit_event,
    started_at: float,
    planned_rounds: int,
    elapsed_offset_seconds: int,
    tail_checkpoint_estimate_seconds: int,
) -> None:
    user_rows = conn.execute("SELECT user_id, name FROM user ORDER BY user_id").fetchall()
    resolved_user_map = user_map or {
        int(r["user_id"]): profile_lookup.get(int(r["user_id"]), {}).get("agent_id", f"agent-{int(r['user_id']) + 1:04d}")
        for r in user_rows
    }

    post_rows = conn.execute(
        "SELECT post_id, user_id, content, created_at FROM post WHERE post_id > ? ORDER BY post_id",
        (last_seen["post"],),
    ).fetchall()
    for row in post_rows:
        user_id = int(row["user_id"])
        last_seen["post"] = max(last_seen["post"], int(row["post_id"]))
        emit_event(
            "post_created",
            round_no=round_no,
            post_id=int(row["post_id"]),
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile_lookup.get(user_id, {}).get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile_lookup.get(user_id, {}).get("subtitle", "Sampled persona"),
            title=_extract_title(str(row["content"])),
            content=row["content"],
            created_at=row["created_at"],
        )

    comment_rows = conn.execute(
        "SELECT comment_id, post_id, user_id, content, created_at FROM comment WHERE comment_id > ? ORDER BY comment_id",
        (last_seen["comment"],),
    ).fetchall()
    for row in comment_rows:
        user_id = int(row["user_id"])
        last_seen["comment"] = max(last_seen["comment"], int(row["comment_id"]))
        emit_event(
            "comment_created",
            round_no=round_no,
            comment_id=int(row["comment_id"]),
            post_id=int(row["post_id"]),
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile_lookup.get(user_id, {}).get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile_lookup.get(user_id, {}).get("subtitle", "Sampled persona"),
            content=row["content"],
            created_at=row["created_at"],
        )

    like_rows = conn.execute(
        "SELECT like_id, user_id, post_id FROM like WHERE like_id > ? ORDER BY like_id",
        (last_seen["like"],),
    ).fetchall()
    for row in like_rows:
        user_id = int(row["user_id"])
        last_seen["like"] = max(last_seen["like"], int(row["like_id"]))
        emit_event(
            "reaction_added",
            round_no=round_no,
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile_lookup.get(user_id, {}).get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile_lookup.get(user_id, {}).get("subtitle", "Sampled persona"),
            reaction="like",
            post_id=int(row["post_id"]),
        )

    dislike_rows = conn.execute(
        "SELECT dislike_id, user_id, post_id FROM dislike WHERE dislike_id > ? ORDER BY dislike_id",
        (last_seen["dislike"],),
    ).fetchall()
    for row in dislike_rows:
        user_id = int(row["user_id"])
        last_seen["dislike"] = max(last_seen["dislike"], int(row["dislike_id"]))
        emit_event(
            "reaction_added",
            round_no=round_no,
            actor_agent_id=resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
            actor_name=profile_lookup.get(user_id, {}).get("display_name", f"Agent {user_id + 1}"),
            actor_subtitle=profile_lookup.get(user_id, {}).get("subtitle", "Sampled persona"),
            reaction="dislike",
            post_id=int(row["post_id"]),
        )

    comment_like_count = _count_table(conn, "comment_like")
    comment_dislike_count = _count_table(conn, "comment_dislike")
    total_like_count = _count_table(conn, "like")
    total_dislike_count = _count_table(conn, "dislike")
    total_posts = _count_table(conn, "post")
    total_comments = _count_table(conn, "comment")

    active_author_row = conn.execute(
        """
        SELECT COUNT(DISTINCT user_id) AS count
        FROM (
            SELECT user_id FROM post
            UNION ALL
            SELECT user_id FROM comment
        )
        """
    ).fetchone()
    active_authors = int(active_author_row["count"] if active_author_row else 0)

    top_threads = []
    for row in conn.execute(
        """
        SELECT
            p.post_id,
            p.user_id,
            p.content,
            COALESCE(c.comment_count, 0) AS comment_count,
            COALESCE(lp.like_count, 0) AS like_count,
            COALESCE(dp.dislike_count, 0) AS dislike_count
        FROM post p
        LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count
            FROM comment
            GROUP BY post_id
        ) c ON c.post_id = p.post_id
        LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count
            FROM like
            GROUP BY post_id
        ) lp ON lp.post_id = p.post_id
        LEFT JOIN (
            SELECT post_id, COUNT(*) AS dislike_count
            FROM dislike
            GROUP BY post_id
        ) dp ON dp.post_id = p.post_id
        ORDER BY (COALESCE(c.comment_count, 0) + COALESCE(lp.like_count, 0) + COALESCE(dp.dislike_count, 0)) DESC, p.post_id DESC
        LIMIT 3
        """
    ).fetchall():
        user_id = int(row["user_id"])
        engagement = int(row["comment_count"]) + int(row["like_count"]) + int(row["dislike_count"])
        top_threads.append(
            {
                "post_id": int(row["post_id"]),
                "title": _extract_title(str(row["content"])),
                "author_agent_id": resolved_user_map.get(user_id, f"agent-{user_id + 1:04d}"),
                "author_name": profile_lookup.get(user_id, {}).get("display_name", f"Agent {user_id + 1}"),
                "engagement": engagement,
                "comments": int(row["comment_count"]),
                "likes": int(row["like_count"]),
                "dislikes": int(row["dislike_count"]),
            }
        )

    total_reactions = total_like_count + total_dislike_count + comment_like_count + comment_dislike_count
    net_reaction = total_like_count - total_dislike_count
    if net_reaction > 0:
        dominant_stance = "support"
    elif net_reaction < 0:
        dominant_stance = "dissent"
    else:
        dominant_stance = "mixed"

    runtime_elapsed_seconds = max(1, int(time.monotonic() - started_at))
    elapsed_seconds = elapsed_offset_seconds + runtime_elapsed_seconds
    if round_no > 0:
        observed_round_seconds = max(6, runtime_elapsed_seconds / max(1, round_no))
    else:
        observed_round_seconds = 12
    estimated_total_seconds = int(
        elapsed_offset_seconds + (observed_round_seconds * max(1, planned_rounds)) + tail_checkpoint_estimate_seconds
    )
    estimated_remaining_seconds = max(0, estimated_total_seconds - elapsed_seconds)

    emit_event(
        "metrics_updated",
        round_no=round_no,
        elapsed_seconds=elapsed_seconds,
        estimated_total_seconds=estimated_total_seconds,
        estimated_remaining_seconds=estimated_remaining_seconds,
        counters={
            "posts": total_posts,
            "comments": total_comments,
            "reactions": total_reactions,
            "active_authors": active_authors,
        },
        top_threads=top_threads,
        discussion_momentum={
            "approval_delta": round(net_reaction / max(1, total_reactions), 4),
            "dominant_stance": dominant_stance,
            "likes": total_like_count,
            "dislikes": total_dislike_count,
        },
        metrics={
            "posts": total_posts,
            "comments": total_comments,
            "reactions": total_reactions,
            "active_authors": active_authors,
            "top_thread_title": top_threads[0]["title"] if top_threads else None,
        },
    )


if __name__ == "__main__":
    main()
