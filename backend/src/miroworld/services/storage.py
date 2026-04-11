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
                    runtime TEXT NOT NULL DEFAULT 'heuristic',
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

                CREATE TABLE IF NOT EXISTS console_sessions (
                    session_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_provider TEXT,
                    model_name TEXT,
                    embed_model_name TEXT,
                    api_key TEXT,
                    base_url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                    session_id TEXT PRIMARY KEY,
                    artifact_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS population_artifacts (
                    session_id TEXT PRIMARY KEY,
                    artifact_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS simulation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS simulation_state_snapshots (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_stream_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_state_snapshots (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS memory_sync_state (
                    simulation_id TEXT PRIMARY KEY,
                    last_interaction_id INTEGER NOT NULL DEFAULT 0,
                    last_checkpoint_id INTEGER NOT NULL DEFAULT 0,
                    synced_events INTEGER NOT NULL DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS interaction_transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    agent_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS simulation_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    checkpoint_kind TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    stance_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS report_runs (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS interactions_fts USING fts5(
                    content,
                    content='interactions',
                    content_rowid='id',
                    tokenize='unicode61'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS interaction_transcripts_fts USING fts5(
                    content,
                    content='interaction_transcripts',
                    content_rowid='id',
                    tokenize='unicode61'
                );

                CREATE TRIGGER IF NOT EXISTS interactions_fts_ai AFTER INSERT ON interactions BEGIN
                    INSERT INTO interactions_fts(rowid, content) VALUES (new.id, COALESCE(new.content, ''));
                END;

                CREATE TRIGGER IF NOT EXISTS interactions_fts_ad AFTER DELETE ON interactions BEGIN
                    INSERT INTO interactions_fts(interactions_fts, rowid, content)
                    VALUES ('delete', old.id, COALESCE(old.content, ''));
                END;

                CREATE TRIGGER IF NOT EXISTS interactions_fts_au AFTER UPDATE ON interactions BEGIN
                    INSERT INTO interactions_fts(interactions_fts, rowid, content)
                    VALUES ('delete', old.id, COALESCE(old.content, ''));
                    INSERT INTO interactions_fts(rowid, content) VALUES (new.id, COALESCE(new.content, ''));
                END;

                CREATE TRIGGER IF NOT EXISTS interaction_transcripts_fts_ai AFTER INSERT ON interaction_transcripts BEGIN
                    INSERT INTO interaction_transcripts_fts(rowid, content) VALUES (new.id, COALESCE(new.content, ''));
                END;

                CREATE TRIGGER IF NOT EXISTS interaction_transcripts_fts_ad AFTER DELETE ON interaction_transcripts BEGIN
                    INSERT INTO interaction_transcripts_fts(interaction_transcripts_fts, rowid, content)
                    VALUES ('delete', old.id, COALESCE(old.content, ''));
                END;

                CREATE TRIGGER IF NOT EXISTS interaction_transcripts_fts_au AFTER UPDATE ON interaction_transcripts BEGIN
                    INSERT INTO interaction_transcripts_fts(interaction_transcripts_fts, rowid, content)
                    VALUES ('delete', old.id, COALESCE(old.content, ''));
                    INSERT INTO interaction_transcripts_fts(rowid, content) VALUES (new.id, COALESCE(new.content, ''));
                END;
                """
            )
            # Backward-compatible migration for existing local DB files.
            columns = [r[1] for r in conn.execute("PRAGMA table_info(simulations)").fetchall()]
            if "runtime" not in columns:
                conn.execute("ALTER TABLE simulations ADD COLUMN runtime TEXT NOT NULL DEFAULT 'heuristic'")

            console_columns = [r[1] for r in conn.execute("PRAGMA table_info(console_sessions)").fetchall()]
            if "model_provider" not in console_columns:
                conn.execute("ALTER TABLE console_sessions ADD COLUMN model_provider TEXT")
            if "model_name" not in console_columns:
                conn.execute("ALTER TABLE console_sessions ADD COLUMN model_name TEXT")
            if "embed_model_name" not in console_columns:
                conn.execute("ALTER TABLE console_sessions ADD COLUMN embed_model_name TEXT")
            if "api_key" not in console_columns:
                conn.execute("ALTER TABLE console_sessions ADD COLUMN api_key TEXT")
            if "base_url" not in console_columns:
                conn.execute("ALTER TABLE console_sessions ADD COLUMN base_url TEXT")

            memory_sync_columns = [r[1] for r in conn.execute("PRAGMA table_info(memory_sync_state)").fetchall()]
            if "last_checkpoint_id" not in memory_sync_columns:
                conn.execute("ALTER TABLE memory_sync_state ADD COLUMN last_checkpoint_id INTEGER NOT NULL DEFAULT 0")

            interaction_count = int(conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0])
            interaction_fts_count = int(conn.execute("SELECT COUNT(*) FROM interactions_fts").fetchone()[0])
            if interaction_count and interaction_fts_count == 0:
                conn.execute("INSERT INTO interactions_fts(interactions_fts) VALUES ('rebuild')")

            transcript_count = int(conn.execute("SELECT COUNT(*) FROM interaction_transcripts").fetchone()[0])
            transcript_fts_count = int(conn.execute("SELECT COUNT(*) FROM interaction_transcripts_fts").fetchone()[0])
            if transcript_count and transcript_fts_count == 0:
                conn.execute("INSERT INTO interaction_transcripts_fts(interaction_transcripts_fts) VALUES ('rebuild')")

    def upsert_simulation(
        self,
        simulation_id: str,
        policy_summary: str,
        rounds: int,
        agent_count: int,
        runtime: str = "heuristic",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO simulations(simulation_id, policy_summary, rounds, agent_count, runtime)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(simulation_id) DO UPDATE SET
                    policy_summary=excluded.policy_summary,
                    rounds=excluded.rounds,
                    agent_count=excluded.agent_count,
                    runtime=excluded.runtime
                """,
                (simulation_id, policy_summary, rounds, agent_count, runtime),
            )

    def replace_agents(self, simulation_id: str, agents: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM agents WHERE simulation_id = ?", (simulation_id,))
            conn.execute("DELETE FROM report_cache WHERE simulation_id = ?", (simulation_id,))
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
            conn.execute("DELETE FROM report_cache WHERE simulation_id = ?", (simulation_id,))
            conn.execute("DELETE FROM memory_sync_state WHERE simulation_id = ?", (simulation_id,))
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

    def search_interactions_fts(
        self,
        simulation_id: str,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT i.*, bm25(interactions_fts) AS fts_rank
                FROM interactions_fts
                JOIN interactions AS i ON i.id = interactions_fts.rowid
                WHERE interactions_fts MATCH ?
                  AND i.simulation_id = ?
                ORDER BY bm25(interactions_fts), i.id DESC
                LIMIT ?
                """,
                (normalized_query, simulation_id, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_interactions_after_id(
        self,
        simulation_id: str,
        last_interaction_id: int,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM interactions WHERE simulation_id = ? AND id > ? ORDER BY id"
        params: tuple[Any, ...] = (simulation_id, int(last_interaction_id))
        if limit is not None:
            sql += " LIMIT ?"
            params = (simulation_id, int(last_interaction_id), int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

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

    def upsert_console_session(
        self,
        session_id: str,
        mode: str,
        status: str,
        *,
        model_provider: str | None = None,
        model_name: str | None = None,
        embed_model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO console_sessions(
                    session_id,
                    mode,
                    status,
                    model_provider,
                    model_name,
                    embed_model_name,
                    api_key,
                    base_url
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    mode=excluded.mode,
                    status=excluded.status,
                    model_provider=COALESCE(excluded.model_provider, console_sessions.model_provider),
                    model_name=COALESCE(excluded.model_name, console_sessions.model_name),
                    embed_model_name=COALESCE(excluded.embed_model_name, console_sessions.embed_model_name),
                    api_key=COALESCE(excluded.api_key, console_sessions.api_key),
                    base_url=COALESCE(excluded.base_url, console_sessions.base_url),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    mode,
                    status,
                    model_provider,
                    model_name,
                    embed_model_name,
                    api_key,
                    base_url,
                ),
            )

    def get_console_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM console_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_knowledge_artifact(self, session_id: str, artifact: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_artifacts(session_id, artifact_json)
                VALUES(?, ?)
                ON CONFLICT(session_id) DO UPDATE SET artifact_json = excluded.artifact_json
                """,
                (session_id, json.dumps(artifact, ensure_ascii=False)),
            )

    def get_knowledge_artifact(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT artifact_json FROM knowledge_artifacts WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["artifact_json"])

    def save_population_artifact(self, session_id: str, artifact: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO population_artifacts(session_id, artifact_json)
                VALUES(?, ?)
                ON CONFLICT(session_id) DO UPDATE SET artifact_json = excluded.artifact_json
                """,
                (session_id, json.dumps(artifact, ensure_ascii=False)),
            )

    def get_population_artifact(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT artifact_json FROM population_artifacts WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["artifact_json"])

    def append_simulation_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO simulation_events(session_id, event_type, event_json)
                VALUES(?, ?, ?)
                """,
                [
                    (
                        session_id,
                        str(event.get("event_type", "unknown")),
                        json.dumps(event, ensure_ascii=False),
                    )
                    for event in events
                ],
            )

    def append_knowledge_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO knowledge_stream_events(session_id, event_type, event_json)
                VALUES(?, ?, ?)
                """,
                [
                    (
                        session_id,
                        str(event.get("event_type", "unknown")),
                        json.dumps(event, ensure_ascii=False),
                    )
                    for event in events
                ],
            )

    def list_simulation_events(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT id, event_type, event_json FROM simulation_events WHERE session_id = ? ORDER BY id"
        params: tuple[Any, ...]
        params = (session_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (session_id, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            event = json.loads(row["event_json"])
            event["id"] = row["id"]
            event["event_type"] = row["event_type"]
            payloads.append(event)
        return payloads

    def list_knowledge_events(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT id, event_type, event_json FROM knowledge_stream_events WHERE session_id = ? ORDER BY id"
        params: tuple[Any, ...] = (session_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (session_id, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in rows:
            event = json.loads(row["event_json"])
            event["id"] = row["id"]
            event["event_type"] = row["event_type"]
            payloads.append(event)
        return payloads

    def clear_simulation_events(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM simulation_events WHERE session_id = ?", (session_id,))

    def clear_knowledge_events(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge_stream_events WHERE session_id = ?", (session_id,))

    def save_simulation_state_snapshot(self, session_id: str, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO simulation_state_snapshots(session_id, state_json)
                VALUES(?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (session_id, json.dumps(state, ensure_ascii=False)),
            )

    def save_knowledge_state_snapshot(self, session_id: str, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_state_snapshots(session_id, state_json)
                VALUES(?, ?)
                ON CONFLICT(session_id) DO UPDATE SET state_json = excluded.state_json
                """,
                (session_id, json.dumps(state, ensure_ascii=False)),
            )

    def get_simulation_state_snapshot(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM simulation_state_snapshots WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["state_json"])

    def get_knowledge_state_snapshot(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM knowledge_state_snapshots WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["state_json"])

    def clear_simulation_state_snapshot(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM simulation_state_snapshots WHERE session_id = ?", (session_id,))

    def clear_knowledge_state_snapshot(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM knowledge_state_snapshots WHERE session_id = ?", (session_id,))

    def clear_report_cache(self, simulation_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM report_cache WHERE simulation_id = ?", (simulation_id,))

    def save_report_state(self, session_id: str, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_runs(session_id, state_json)
                VALUES(?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (session_id, json.dumps(state, ensure_ascii=False)),
            )

    def get_report_state(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM report_runs WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["state_json"])

    def clear_report_state(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM report_runs WHERE session_id = ?", (session_id,))

    def get_memory_sync_state(self, simulation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memory_sync_state WHERE simulation_id = ?",
                (simulation_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_memory_sync_state(
        self,
        simulation_id: str,
        last_interaction_id: int,
        synced_events: int,
        *,
        last_checkpoint_id: int | None = None,
    ) -> None:
        existing = self.get_memory_sync_state(simulation_id) or {}
        checkpoint_id = int(
            last_checkpoint_id
            if last_checkpoint_id is not None
            else existing.get("last_checkpoint_id", 0)
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_sync_state(simulation_id, last_interaction_id, last_checkpoint_id, synced_events)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(simulation_id) DO UPDATE SET
                    last_interaction_id = excluded.last_interaction_id,
                    last_checkpoint_id = excluded.last_checkpoint_id,
                    synced_events = excluded.synced_events,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (simulation_id, last_interaction_id, checkpoint_id, synced_events),
            )

    def reset_memory_sync_state(self, simulation_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memory_sync_state WHERE simulation_id = ?", (simulation_id,))

    def append_interaction_transcript(
        self,
        session_id: str,
        channel: str,
        role: str,
        content: str,
        agent_id: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO interaction_transcripts(session_id, channel, agent_id, role, content)
                VALUES(?, ?, ?, ?, ?)
                """,
                (session_id, channel, agent_id, role, content),
            )

    def list_interaction_transcript(
        self,
        session_id: str,
        channel: str,
        agent_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT role, content, created_at
            FROM interaction_transcripts
            WHERE session_id = ? AND channel = ?
        """
        params: list[Any] = [session_id, channel]
        if agent_id is not None:
            sql += " AND agent_id = ?"
            params.append(agent_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_interaction_transcripts(
        self,
        session_id: str,
        agent_id: str | None = None,
        channel: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, session_id, channel, agent_id, role, content, created_at
            FROM interaction_transcripts
            WHERE session_id = ?
        """
        params: list[Any] = [session_id]
        if agent_id is not None:
            sql += " AND agent_id = ?"
            params.append(agent_id)
        if channel is not None:
            sql += " AND channel = ?"
            params.append(channel)
        sql += " ORDER BY id"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def search_interaction_transcripts_fts(
        self,
        session_id: str,
        query: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.*, bm25(interaction_transcripts_fts) AS fts_rank
                FROM interaction_transcripts_fts
                JOIN interaction_transcripts AS t ON t.id = interaction_transcripts_fts.rowid
                WHERE interaction_transcripts_fts MATCH ?
                  AND t.session_id = ?
                ORDER BY bm25(interaction_transcripts_fts), t.id DESC
                LIMIT ?
                """,
                (normalized_query, session_id, int(limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_interaction_transcripts(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM interaction_transcripts WHERE session_id = ?", (session_id,))

    def replace_checkpoint_records(
        self,
        session_id: str,
        checkpoint_kind: str,
        records: list[dict[str, Any]],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM simulation_checkpoints WHERE session_id = ? AND checkpoint_kind = ?",
                (session_id, checkpoint_kind),
            )
            conn.executemany(
                """
                INSERT INTO simulation_checkpoints(session_id, checkpoint_kind, agent_id, stance_json)
                VALUES(?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        checkpoint_kind,
                        str(record.get("agent_id")),
                        json.dumps(record, ensure_ascii=False),
                    )
                    for record in records
                ],
            )

    def list_checkpoint_records(
        self,
        session_id: str,
        checkpoint_kind: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT checkpoint_kind, stance_json
            FROM simulation_checkpoints
            WHERE session_id = ?
        """
        params: list[Any] = [session_id]
        if checkpoint_kind is not None:
            sql += " AND checkpoint_kind = ?"
            params.append(checkpoint_kind)
        sql += " ORDER BY checkpoint_kind, id"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            record = json.loads(row["stance_json"])
            record.setdefault("checkpoint_kind", row["checkpoint_kind"])
            records.append(record)
        return records

    def list_checkpoint_records_after_id(
        self,
        session_id: str,
        last_checkpoint_id: int,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT id, checkpoint_kind, stance_json, created_at
            FROM simulation_checkpoints
            WHERE session_id = ? AND id > ?
            ORDER BY id
        """
        params: tuple[Any, ...] = (session_id, int(last_checkpoint_id))
        if limit is not None:
            sql += " LIMIT ?"
            params = (session_id, int(last_checkpoint_id), int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        records: list[dict[str, Any]] = []
        for row in rows:
            record = json.loads(row["stance_json"])
            record.setdefault("checkpoint_kind", row["checkpoint_kind"])
            record["id"] = int(row["id"])
            record["created_at"] = row["created_at"]
            records.append(record)
        return records

    def clear_checkpoint_records(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM simulation_checkpoints WHERE session_id = ?", (session_id,))
