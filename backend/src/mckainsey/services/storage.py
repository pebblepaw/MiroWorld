from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SimulationStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS simulations (
                    simulation_id TEXT PRIMARY KEY,
                    policy_summary TEXT NOT NULL,
                    rounds INTEGER NOT NULL,
                    agent_count INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS agents (
                    simulation_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    persona_json TEXT NOT NULL,
                    opinion_pre REAL,
                    opinion_post REAL,
                    PRIMARY KEY (simulation_id, agent_id)
                );

                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    simulation_id TEXT NOT NULL,
                    round_no INTEGER NOT NULL,
                    actor_agent_id TEXT NOT NULL,
                    target_agent_id TEXT,
                    action_type TEXT NOT NULL,
                    content TEXT,
                    delta REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS report_cache (
                    simulation_id TEXT PRIMARY KEY,
                    report_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def upsert_simulation(self, simulation_id: str, policy_summary: str, rounds: int, agent_count: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO simulations(simulation_id, policy_summary, rounds, agent_count)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(simulation_id) DO UPDATE SET
                    policy_summary=excluded.policy_summary,
                    rounds=excluded.rounds,
                    agent_count=excluded.agent_count
                """,
                (simulation_id, policy_summary, rounds, agent_count),
            )

    def replace_agents(self, simulation_id: str, agents: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM agents WHERE simulation_id = ?", (simulation_id,))
            conn.executemany(
                """
                INSERT INTO agents(simulation_id, agent_id, persona_json, opinion_pre, opinion_post)
                VALUES(?, ?, ?, ?, ?)
                """,
                [
                    (
                        simulation_id,
                        a["agent_id"],
                        json.dumps(a["persona"], ensure_ascii=False),
                        a.get("opinion_pre"),
                        a.get("opinion_post"),
                    )
                    for a in agents
                ],
            )

    def replace_interactions(self, simulation_id: str, interactions: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM interactions WHERE simulation_id = ?", (simulation_id,))
            conn.executemany(
                """
                INSERT INTO interactions(simulation_id, round_no, actor_agent_id, target_agent_id, action_type, content, delta)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        simulation_id,
                        i["round_no"],
                        i["actor_agent_id"],
                        i.get("target_agent_id"),
                        i["action_type"],
                        i.get("content"),
                        i.get("delta", 0),
                    )
                    for i in interactions
                ],
            )

    def get_agents(self, simulation_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agents WHERE simulation_id = ?",
                (simulation_id,),
            ).fetchall()
        return [
            {
                "agent_id": r["agent_id"],
                "persona": json.loads(r["persona_json"]),
                "opinion_pre": r["opinion_pre"],
                "opinion_post": r["opinion_post"],
            }
            for r in rows
        ]

    def get_interactions(self, simulation_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM interactions WHERE simulation_id = ? ORDER BY round_no, id",
                (simulation_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_simulation(self, simulation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM simulations WHERE simulation_id = ?",
                (simulation_id,),
            ).fetchone()
        return dict(row) if row else None

    def cache_report(self, simulation_id: str, report: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_cache(simulation_id, report_json)
                VALUES(?, ?)
                ON CONFLICT(simulation_id) DO UPDATE SET report_json = excluded.report_json
                """,
                (simulation_id, json.dumps(report, ensure_ascii=False)),
            )

    def get_cached_report(self, simulation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT report_json FROM report_cache WHERE simulation_id = ?",
                (simulation_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["report_json"])
