import asyncio
import json
import os
import sqlite3

from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

import oasis
from oasis import ActionType, ManualAction, generate_reddit_agent_graph


async def run() -> None:
    profile_path = "data/oasis_test_profiles.json"
    os.makedirs("data", exist_ok=True)
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    "user_id": 0,
                    "username": "user0",
                    "realname": "User Zero",
                    "user_name": "user0",
                    "name": "User Zero",
                    "bio": "Budget policy discussion",
                    "persona": "Middle-income resident focused on public transport affordability and tax impact.",
                    "age": 35,
                    "gender": "male",
                    "mbti": "ISTJ",
                    "country": "Singapore",
                    "karma": 100,
                    "created_at": "2024-01-01",
                },
                {
                    "user_id": 1,
                    "username": "user1",
                    "realname": "User One",
                    "user_name": "user1",
                    "name": "User One",
                    "bio": "Cost of living concerns",
                    "persona": "Senior household member concerned about inflation and healthcare support.",
                    "age": 62,
                    "gender": "female",
                    "mbti": "ISFJ",
                    "country": "Singapore",
                    "karma": 50,
                    "created_at": "2024-01-02",
                },
            ],
            f,
        )

    model = ModelFactory.create(
        model_platform=ModelPlatformType.OPENAI,
        model_type=ModelType.GPT_4O_MINI,
    )
    actions = [
        ActionType.CREATE_POST,
        ActionType.CREATE_COMMENT,
        ActionType.LIKE_POST,
        ActionType.DISLIKE_POST,
        ActionType.DO_NOTHING,
        ActionType.REFRESH,
    ]
    graph = await generate_reddit_agent_graph(
        profile_path=profile_path,
        model=model,
        available_actions=actions,
    )

    db_path = "data/oasis_test.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    env = oasis.make(
        agent_graph=graph,
        platform=oasis.DefaultPlatformType.REDDIT,
        database_path=db_path,
    )
    await env.reset()

    a0 = env.agent_graph.get_agent(0)
    a1 = env.agent_graph.get_agent(1)
    await env.step(
        {
            a0: ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": "Hello budget 2026"},
            ),
            a1: ManualAction(
                action_type=ActionType.CREATE_COMMENT,
                action_args={"post_id": "1", "content": "I disagree"},
            ),
        }
    )

    await env.close()

    conn = sqlite3.connect(db_path)
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"
        ).fetchall()
    ]
    print("tables", tables)
    for table in tables:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        print("schema", table, [c[1] for c in cols])
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print("count", table, count)
    conn.close()


if __name__ == "__main__":
    asyncio.run(run())
