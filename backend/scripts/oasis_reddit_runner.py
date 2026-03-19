from __future__ import annotations

import asyncio
import json
import os
import random
import sqlite3
import sys
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
    gemini_api_key: str
    openai_base_url: str
    oasis_db_path: str


def _to_profile(persona: dict[str, Any], idx: int) -> dict[str, Any]:
    age = int(persona.get("age") or random.randint(21, 70))
    username = f"sg_agent_{idx + 1}"
    name = str(persona.get("name") or f"SG Agent {idx + 1}")
    planning_area = str(persona.get("planning_area") or "Singapore")
    income = str(persona.get("income_bracket") or "Unknown income")
    occupation = str(persona.get("occupation") or "Resident")
    persona_text = (
        f"{age}-year-old {occupation} in {planning_area}, income {income}. "
        "Evaluates FY2026 budget impacts on household affordability and social support."
    )
    return {
        "user_id": idx,
        "username": username,
        "realname": name,
        "user_name": username,
        "name": name,
        "bio": persona_text,
        "persona": persona_text,
        "age": age,
        "gender": str(persona.get("gender") or "unknown"),
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


async def run_simulation(payload: RunnerInput) -> dict[str, Any]:
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import ActionType, LLMAction, ManualAction, generate_reddit_agent_graph

    print(
        f"[oasis-runner] start simulation_id={payload.simulation_id} agents={len(payload.personas)} rounds={payload.rounds}",
        flush=True,
    )

    os.environ["OPENAI_API_KEY"] = payload.gemini_api_key
    os.environ["OPENAI_BASE_URL"] = payload.openai_base_url

    profiles_path = Path(payload.oasis_db_path).with_suffix(".profiles.json")
    profiles_path.parent.mkdir(parents=True, exist_ok=True)
    profiles = [_to_profile(p, idx) for idx, p in enumerate(payload.personas)]
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
    )

    await env.reset()

    # Seed the policy into the discussion thread before autonomous rounds.
    seed_actions: dict[Any, Any] = {}
    seed_agents = [agent for _, agent in env.agent_graph.get_agents()][: min(5, len(profiles))]
    for i, agent in enumerate(seed_agents):
        seed_actions[agent] = ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={
                "content": (
                    f"Policy thread kickoff {i+1}: FY2026 budget summary and concerns - "
                    f"{payload.policy_summary[:220]}"
                )
            },
        )
    await env.step(seed_actions)
    print("[oasis-runner] seed posts injected", flush=True)

    for i in range(payload.rounds):
        actions = {agent: LLMAction() for _, agent in env.agent_graph.get_agents()}
        await env.step(actions)
        print(f"[oasis-runner] completed round {i + 1}/{payload.rounds}", flush=True)

    await env.close()
    print("[oasis-runner] env closed, collecting artifacts", flush=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    user_rows = conn.execute("SELECT user_id, name FROM user ORDER BY user_id").fetchall()
    user_map = {int(r["user_id"]): f"agent-{int(r['user_id']) + 1:04d}" for r in user_rows}

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

    conn.close()

    agents: list[dict[str, Any]] = []
    pre_scores: list[float] = []
    post_scores: list[float] = []
    actor_balance: dict[str, float] = {}
    for event in interactions:
        actor_balance[event["actor_agent_id"]] = actor_balance.get(event["actor_agent_id"], 0.0) + float(event.get("delta", 0.0))

    for idx, persona in enumerate(payload.personas):
        agent_id = f"agent-{idx + 1:04d}"
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


if __name__ == "__main__":
    main()
