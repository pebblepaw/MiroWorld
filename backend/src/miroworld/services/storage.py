from __future__ import annotations

import contextvars
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from miroworld.config import get_settings

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # noqa: BLE001
    psycopg = None
    dict_row = None


_STORE_USER_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("miroworld_store_user_id", default=None)


def set_store_user_context(user_id: str | None) -> contextvars.Token[str | None]:
    return _STORE_USER_ID.set(str(user_id or "").strip() or None)


def reset_store_user_context(token: contextvars.Token[str | None]) -> None:
    _STORE_USER_ID.reset(token)


def current_store_user_id() -> str | None:
    return _STORE_USER_ID.get()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: Any, *, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:  # noqa: BLE001
            return default
    return default


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


class SimulationStore:
    _initialized_backends: set[str] = set()
    _init_lock = threading.Lock()

    def __init__(self, db_path: str):
        settings = get_settings()
        self.backend = settings.app_state_backend
        self.db_path = db_path
        self.postgres_url = settings.supabase_postgres_url
        self._ensure_ready()

    @property
    def is_postgres(self) -> bool:
        return self.backend == "postgres"

    def _current_user_id(self) -> str | None:
        return current_store_user_id()

    def _ensure_ready(self) -> None:
        key = self.postgres_url if self.is_postgres else self.db_path
        if not key:
            raise RuntimeError("Storage backend is not configured.")
        with self._init_lock:
            if key in self._initialized_backends:
                return
            if self.is_postgres:
                self._init_postgres()
            else:
                self._init_sqlite()
            self._initialized_backends.add(key)

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self.is_postgres:
            if psycopg is None:
                raise RuntimeError("psycopg is required for postgres app-state storage.")
            assert self.postgres_url
            with psycopg.connect(self.postgres_url, autocommit=True, row_factory=dict_row) as conn:
                yield conn
            return

        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            yield conn

    def _init_sqlite(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS simulations (
                    simulation_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    subject_summary TEXT NOT NULL,
                    rounds INTEGER NOT NULL,
                    agent_count INTEGER NOT NULL,
                    runtime TEXT NOT NULL DEFAULT 'heuristic',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS agents (
                    simulation_id TEXT NOT NULL,
                    user_id TEXT,
                    agent_id TEXT NOT NULL,
                    persona_json TEXT NOT NULL,
                    opinion_pre REAL,
                    opinion_post REAL,
                    PRIMARY KEY (simulation_id, agent_id)
                );

                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    simulation_id TEXT NOT NULL,
                    user_id TEXT,
                    round_no INTEGER NOT NULL,
                    actor_agent_id TEXT NOT NULL,
                    target_agent_id TEXT,
                    action_type TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    delta REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS report_cache (
                    simulation_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    report_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS console_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
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

                CREATE TABLE IF NOT EXISTS session_configs (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    country TEXT,
                    use_case TEXT,
                    provider TEXT,
                    model TEXT,
                    guiding_prompt TEXT,
                    analysis_questions TEXT,
                    config_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS session_token_usage (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    model TEXT NOT NULL,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_cached_tokens INTEGER NOT NULL DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    artifact_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS population_artifacts (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    artifact_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS simulation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS simulation_state_snapshots (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    state_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_stream_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_state_snapshots (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    state_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS memory_sync_state (
                    simulation_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    last_interaction_id INTEGER NOT NULL DEFAULT 0,
                    last_checkpoint_id INTEGER NOT NULL DEFAULT 0,
                    synced_events INTEGER NOT NULL DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS interaction_transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    channel TEXT NOT NULL,
                    agent_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS simulation_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    checkpoint_kind TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    stance_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS report_runs (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    state_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _init_postgres(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS simulations (
                simulation_id TEXT PRIMARY KEY,
                user_id TEXT,
                subject_summary TEXT NOT NULL,
                rounds INTEGER NOT NULL,
                agent_count INTEGER NOT NULL,
                runtime TEXT NOT NULL DEFAULT 'heuristic',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agents (
                simulation_id TEXT NOT NULL,
                user_id TEXT,
                agent_id TEXT NOT NULL,
                persona_json JSONB NOT NULL,
                opinion_pre DOUBLE PRECISION,
                opinion_post DOUBLE PRECISION,
                PRIMARY KEY (simulation_id, agent_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id BIGSERIAL PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                user_id TEXT,
                round_no INTEGER NOT NULL,
                actor_agent_id TEXT NOT NULL,
                target_agent_id TEXT,
                action_type TEXT NOT NULL,
                title TEXT,
                content TEXT,
                delta DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS report_cache (
                simulation_id TEXT PRIMARY KEY,
                user_id TEXT,
                report_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS console_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                model_provider TEXT,
                model_name TEXT,
                embed_model_name TEXT,
                api_key TEXT,
                base_url TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS session_configs (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                country TEXT,
                use_case TEXT,
                provider TEXT,
                model TEXT,
                guiding_prompt TEXT,
                analysis_questions JSONB,
                config_json JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS session_token_usage (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                model TEXT NOT NULL,
                total_input_tokens INTEGER NOT NULL DEFAULT 0,
                total_output_tokens INTEGER NOT NULL DEFAULT 0,
                total_cached_tokens INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                artifact_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS population_artifacts (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                artifact_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS simulation_events (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT,
                event_type TEXT NOT NULL,
                event_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS simulation_state_snapshots (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                state_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_stream_events (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT,
                event_type TEXT NOT NULL,
                event_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_state_snapshots (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                state_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS memory_sync_state (
                simulation_id TEXT PRIMARY KEY,
                user_id TEXT,
                last_interaction_id BIGINT NOT NULL DEFAULT 0,
                last_checkpoint_id BIGINT NOT NULL DEFAULT 0,
                synced_events INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS interaction_transcripts (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT,
                channel TEXT NOT NULL,
                agent_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS simulation_checkpoints (
                id BIGSERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT,
                checkpoint_kind TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                stance_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS report_runs (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                state_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_console_sessions_user_id ON console_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_session_configs_user_id ON session_configs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_interactions_simulation_user ON interactions(simulation_id, user_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_sim_events_session_user ON simulation_events(session_id, user_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_knowledge_events_session_user ON knowledge_stream_events(session_id, user_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_transcripts_session_user ON interaction_transcripts(session_id, user_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_checkpoints_session_user ON simulation_checkpoints(session_id, user_id, id)",
        ]
        with self._connect() as conn:
            for statement in statements:
                conn.execute(statement)
            for statement in self._postgres_rls_statements():
                conn.execute(statement)

    def _postgres_rls_statements(self) -> list[str]:
        statements: list[str] = []
        for table_name in self._postgres_table_names():
            policy_name = f"{table_name}_owner_only"
            statements.append(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
            statements.append(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_policies
                        WHERE schemaname = 'public'
                          AND tablename = '{table_name}'
                          AND policyname = '{policy_name}'
                    ) THEN
                        EXECUTE 'CREATE POLICY {policy_name} ON public.{table_name} FOR ALL TO authenticated USING (auth.uid()::text = user_id) WITH CHECK (auth.uid()::text = user_id)';
                    END IF;
                END $$;
                """
            )
        return statements

    @staticmethod
    def _postgres_table_names() -> tuple[str, ...]:
        return (
            "simulations",
            "agents",
            "interactions",
            "report_cache",
            "console_sessions",
            "session_configs",
            "session_token_usage",
            "knowledge_artifacts",
            "population_artifacts",
            "simulation_events",
            "simulation_state_snapshots",
            "knowledge_stream_events",
            "knowledge_state_snapshots",
            "memory_sync_state",
            "interaction_transcripts",
            "simulation_checkpoints",
            "report_runs",
        )

    def _maybe_decode_session_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload:
            return {}
        merged = dict(payload)
        raw_json = merged.get("config_json")
        if raw_json:
            merged.update(_json_loads(raw_json, default={}))
        raw_questions = merged.get("analysis_questions")
        merged["analysis_questions"] = [
            item
            for item in _json_loads(raw_questions, default=[])
            if isinstance(item, dict)
        ]
        return merged

    def upsert_simulation(
        self,
        simulation_id: str,
        subject_summary: str,
        rounds: int,
        agent_count: int,
        runtime: str = "heuristic",
    ) -> None:
        user_id = self._current_user_id()
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO simulations(simulation_id, user_id, subject_summary, rounds, agent_count, runtime)
                    VALUES(%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(simulation_id) DO UPDATE SET
                        user_id = COALESCE(simulations.user_id, EXCLUDED.user_id),
                        subject_summary = EXCLUDED.subject_summary,
                        rounds = EXCLUDED.rounds,
                        agent_count = EXCLUDED.agent_count,
                        runtime = EXCLUDED.runtime
                    WHERE simulations.user_id IS NOT DISTINCT FROM EXCLUDED.user_id
                       OR simulations.user_id IS NULL
                       OR EXCLUDED.user_id IS NULL
                    """,
                    (simulation_id, user_id, subject_summary, int(rounds), int(agent_count), runtime),
                )
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO simulations(simulation_id, user_id, subject_summary, rounds, agent_count, runtime)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(simulation_id) DO UPDATE SET
                    user_id=COALESCE(simulations.user_id, excluded.user_id),
                    subject_summary=excluded.subject_summary,
                    rounds=excluded.rounds,
                    agent_count=excluded.agent_count,
                    runtime=excluded.runtime
                """,
                (simulation_id, user_id, subject_summary, int(rounds), int(agent_count), runtime),
            )

    def replace_agents(self, simulation_id: str, agents: list[dict[str, Any]]) -> None:
        user_id = self._current_user_id()
        with self._connect() as conn:
            if self.is_postgres:
                conn.execute("DELETE FROM agents WHERE simulation_id = %s AND (%s IS NULL OR user_id = %s)", (simulation_id, user_id, user_id))
                conn.execute("DELETE FROM report_cache WHERE simulation_id = %s AND (%s IS NULL OR user_id = %s)", (simulation_id, user_id, user_id))
                for agent in agents:
                    conn.execute(
                        """
                        INSERT INTO agents(simulation_id, user_id, agent_id, persona_json, opinion_pre, opinion_post)
                        VALUES(%s, %s, %s, %s::jsonb, %s, %s)
                        """,
                        (
                            simulation_id,
                            user_id,
                            agent["agent_id"],
                            _json_dumps(agent["persona"]),
                            agent.get("opinion_pre"),
                            agent.get("opinion_post"),
                        ),
                    )
            else:
                conn.execute("DELETE FROM agents WHERE simulation_id = ?", (simulation_id,))
                conn.execute("DELETE FROM report_cache WHERE simulation_id = ?", (simulation_id,))
                conn.executemany(
                    """
                    INSERT INTO agents(simulation_id, user_id, agent_id, persona_json, opinion_pre, opinion_post)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            simulation_id,
                            user_id,
                            agent["agent_id"],
                            _json_dumps(agent["persona"]),
                            agent.get("opinion_pre"),
                            agent.get("opinion_post"),
                        )
                        for agent in agents
                    ],
                )

    def replace_interactions(self, simulation_id: str, interactions: list[dict[str, Any]]) -> None:
        user_id = self._current_user_id()
        with self._connect() as conn:
            if self.is_postgres:
                conn.execute("DELETE FROM interactions WHERE simulation_id = %s AND (%s IS NULL OR user_id = %s)", (simulation_id, user_id, user_id))
                conn.execute("DELETE FROM report_cache WHERE simulation_id = %s AND (%s IS NULL OR user_id = %s)", (simulation_id, user_id, user_id))
                conn.execute("DELETE FROM memory_sync_state WHERE simulation_id = %s AND (%s IS NULL OR user_id = %s)", (simulation_id, user_id, user_id))
                for item in interactions:
                    conn.execute(
                        """
                        INSERT INTO interactions(
                            simulation_id, user_id, round_no, actor_agent_id, target_agent_id, action_type, title, content, delta
                        ) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            simulation_id,
                            user_id,
                            int(item["round_no"]),
                            item["actor_agent_id"],
                            item.get("target_agent_id"),
                            item["action_type"],
                            item.get("title"),
                            item.get("content"),
                            item.get("delta", 0),
                        ),
                    )
            else:
                conn.execute("DELETE FROM interactions WHERE simulation_id = ?", (simulation_id,))
                conn.execute("DELETE FROM report_cache WHERE simulation_id = ?", (simulation_id,))
                conn.execute("DELETE FROM memory_sync_state WHERE simulation_id = ?", (simulation_id,))
                conn.executemany(
                    """
                    INSERT INTO interactions(simulation_id, user_id, round_no, actor_agent_id, target_agent_id, action_type, title, content, delta)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            simulation_id,
                            user_id,
                            int(item["round_no"]),
                            item["actor_agent_id"],
                            item.get("target_agent_id"),
                            item["action_type"],
                            item.get("title"),
                            item.get("content"),
                            item.get("delta", 0),
                        )
                        for item in interactions
                    ],
                )

    def get_agents(self, simulation_id: str) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT agent_id, persona_json, opinion_pre, opinion_post FROM agents WHERE simulation_id = %s"
            params: list[Any] = [simulation_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute("SELECT agent_id, persona_json, opinion_pre, opinion_post FROM agents WHERE simulation_id = ?", (simulation_id,)).fetchall()
        return [
            {
                "agent_id": row["agent_id"],
                "persona": _json_loads(row["persona_json"], default={}),
                "opinion_pre": row.get("opinion_pre"),
                "opinion_post": row.get("opinion_post"),
            }
            for row in map(_row_dict, rows)
        ]

    def get_interactions(self, simulation_id: str) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT * FROM interactions WHERE simulation_id = %s"
            params: list[Any] = [simulation_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            sql += " ORDER BY round_no, id"
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM interactions WHERE simulation_id = ? ORDER BY round_no, id", (simulation_id,)).fetchall()
        return [dict(_row_dict(row)) for row in rows]

    def search_interactions_fts(self, simulation_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized = str(query or "").strip()
        if not normalized:
            return []
        user_id = self._current_user_id()
        pattern = "%" + "%".join(normalized.split()) + "%"
        if self.is_postgres:
            sql = "SELECT * FROM interactions WHERE simulation_id = %s AND COALESCE(content, '') ILIKE %s"
            params: list[Any] = [simulation_id, pattern]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            sql += " ORDER BY id DESC LIMIT %s"
            params.append(int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM interactions WHERE simulation_id = ? AND COALESCE(content, '') LIKE ? ORDER BY id DESC LIMIT ?",
                    (simulation_id, pattern, int(limit)),
                ).fetchall()
        return [dict(_row_dict(row)) for row in rows]

    def get_interactions_after_id(self, simulation_id: str, last_interaction_id: int, limit: int | None = None) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT * FROM interactions WHERE simulation_id = %s AND id > %s"
            params: list[Any] = [simulation_id, int(last_interaction_id)]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            sql += " ORDER BY id"
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            sql = "SELECT * FROM interactions WHERE simulation_id = ? AND id > ? ORDER BY id"
            params: tuple[Any, ...] = (simulation_id, int(last_interaction_id))
            if limit is not None:
                sql += " LIMIT ?"
                params = (simulation_id, int(last_interaction_id), int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        return [dict(_row_dict(row)) for row in rows]

    def get_simulation(self, simulation_id: str) -> dict[str, Any] | None:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT * FROM simulations WHERE simulation_id = %s"
            params: list[Any] = [simulation_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM simulations WHERE simulation_id = ?", (simulation_id,)).fetchone()
        payload = _row_dict(row)
        return payload or None

    def cache_report(self, simulation_id: str, report: dict[str, Any]) -> None:
        user_id = self._current_user_id()
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO report_cache(simulation_id, user_id, report_json)
                    VALUES(%s, %s, %s::jsonb)
                    ON CONFLICT(simulation_id) DO UPDATE SET
                        user_id = COALESCE(report_cache.user_id, EXCLUDED.user_id),
                        report_json = EXCLUDED.report_json
                    WHERE report_cache.user_id IS NOT DISTINCT FROM EXCLUDED.user_id
                       OR report_cache.user_id IS NULL
                       OR EXCLUDED.user_id IS NULL
                    """,
                    (simulation_id, user_id, _json_dumps(report)),
                )
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_cache(simulation_id, user_id, report_json)
                VALUES(?, ?, ?)
                ON CONFLICT(simulation_id) DO UPDATE SET
                    user_id=COALESCE(report_cache.user_id, excluded.user_id),
                    report_json=excluded.report_json
                """,
                (simulation_id, user_id, _json_dumps(report)),
            )

    def get_cached_report(self, simulation_id: str) -> dict[str, Any] | None:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT report_json FROM report_cache WHERE simulation_id = %s"
            params: list[Any] = [simulation_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute("SELECT report_json FROM report_cache WHERE simulation_id = ?", (simulation_id,)).fetchone()
        if not row:
            return None
        return _json_loads(_row_dict(row)["report_json"], default=None)

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
        user_id = self._current_user_id()
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO console_sessions(
                        session_id, user_id, mode, status, model_provider, model_name, embed_model_name, api_key, base_url
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(session_id) DO UPDATE SET
                        user_id = COALESCE(console_sessions.user_id, EXCLUDED.user_id),
                        mode = EXCLUDED.mode,
                        status = EXCLUDED.status,
                        model_provider = COALESCE(EXCLUDED.model_provider, console_sessions.model_provider),
                        model_name = COALESCE(EXCLUDED.model_name, console_sessions.model_name),
                        embed_model_name = COALESCE(EXCLUDED.embed_model_name, console_sessions.embed_model_name),
                        api_key = COALESCE(EXCLUDED.api_key, console_sessions.api_key),
                        base_url = COALESCE(EXCLUDED.base_url, console_sessions.base_url),
                        updated_at = NOW()
                    WHERE console_sessions.user_id IS NOT DISTINCT FROM EXCLUDED.user_id
                       OR console_sessions.user_id IS NULL
                       OR EXCLUDED.user_id IS NULL
                    """,
                    (session_id, user_id, mode, status, model_provider, model_name, embed_model_name, api_key, base_url),
                )
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO console_sessions(
                    session_id, user_id, mode, status, model_provider, model_name, embed_model_name, api_key, base_url
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id=COALESCE(console_sessions.user_id, excluded.user_id),
                    mode=excluded.mode,
                    status=excluded.status,
                    model_provider=COALESCE(excluded.model_provider, console_sessions.model_provider),
                    model_name=COALESCE(excluded.model_name, console_sessions.model_name),
                    embed_model_name=COALESCE(excluded.embed_model_name, console_sessions.embed_model_name),
                    api_key=COALESCE(excluded.api_key, console_sessions.api_key),
                    base_url=COALESCE(excluded.base_url, console_sessions.base_url),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (session_id, user_id, mode, status, model_provider, model_name, embed_model_name, api_key, base_url),
            )

    def get_console_session(self, session_id: str) -> dict[str, Any] | None:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT * FROM console_sessions WHERE session_id = %s"
            params: list[Any] = [session_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM console_sessions WHERE session_id = ?", (session_id,)).fetchone()
        payload = _row_dict(row)
        return payload or None

    def upsert_session_config(self, session_id: str, payload: dict[str, Any]) -> None:
        user_id = self._current_user_id()
        country = payload.get("country")
        use_case = payload.get("use_case")
        provider = payload.get("provider")
        model = payload.get("model")
        guiding_prompt = payload.get("guiding_prompt")
        analysis_questions = payload.get("analysis_questions") or []
        config_json = payload.get("config_json") or {}
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO session_configs(
                        session_id, user_id, country, use_case, provider, model, guiding_prompt, analysis_questions, config_json
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    ON CONFLICT(session_id) DO UPDATE SET
                        user_id = COALESCE(session_configs.user_id, EXCLUDED.user_id),
                        country = EXCLUDED.country,
                        use_case = EXCLUDED.use_case,
                        provider = EXCLUDED.provider,
                        model = EXCLUDED.model,
                        guiding_prompt = EXCLUDED.guiding_prompt,
                        analysis_questions = EXCLUDED.analysis_questions,
                        config_json = EXCLUDED.config_json,
                        updated_at = NOW()
                    WHERE session_configs.user_id IS NOT DISTINCT FROM EXCLUDED.user_id
                       OR session_configs.user_id IS NULL
                       OR EXCLUDED.user_id IS NULL
                    """,
                    (
                        session_id,
                        user_id,
                        country,
                        use_case,
                        provider,
                        model,
                        guiding_prompt,
                        _json_dumps(analysis_questions),
                        _json_dumps(config_json),
                    ),
                )
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_configs(
                    session_id, user_id, country, use_case, provider, model, guiding_prompt, analysis_questions, config_json
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id=COALESCE(session_configs.user_id, excluded.user_id),
                    country=excluded.country,
                    use_case=excluded.use_case,
                    provider=excluded.provider,
                    model=excluded.model,
                    guiding_prompt=excluded.guiding_prompt,
                    analysis_questions=excluded.analysis_questions,
                    config_json=excluded.config_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    user_id,
                    country,
                    use_case,
                    provider,
                    model,
                    guiding_prompt,
                    _json_dumps(analysis_questions),
                    _json_dumps(config_json),
                ),
            )

    def get_session_config(self, session_id: str) -> dict[str, Any]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT * FROM session_configs WHERE session_id = %s"
            params: list[Any] = [session_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM session_configs WHERE session_id = ?", (session_id,)).fetchone()
        return self._maybe_decode_session_config(_row_dict(row))

    def upsert_session_token_usage(
        self,
        session_id: str,
        *,
        model: str,
        total_input_tokens: int,
        total_output_tokens: int,
        total_cached_tokens: int,
    ) -> None:
        user_id = self._current_user_id()
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO session_token_usage(
                        session_id, user_id, model, total_input_tokens, total_output_tokens, total_cached_tokens
                    ) VALUES(%s, %s, %s, %s, %s, %s)
                    ON CONFLICT(session_id) DO UPDATE SET
                        user_id = COALESCE(session_token_usage.user_id, EXCLUDED.user_id),
                        model = EXCLUDED.model,
                        total_input_tokens = EXCLUDED.total_input_tokens,
                        total_output_tokens = EXCLUDED.total_output_tokens,
                        total_cached_tokens = EXCLUDED.total_cached_tokens,
                        updated_at = NOW()
                    WHERE session_token_usage.user_id IS NOT DISTINCT FROM EXCLUDED.user_id
                       OR session_token_usage.user_id IS NULL
                       OR EXCLUDED.user_id IS NULL
                    """,
                    (session_id, user_id, model, int(total_input_tokens), int(total_output_tokens), int(total_cached_tokens)),
                )
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_token_usage(
                    session_id, user_id, model, total_input_tokens, total_output_tokens, total_cached_tokens
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id=COALESCE(session_token_usage.user_id, excluded.user_id),
                    model=excluded.model,
                    total_input_tokens=excluded.total_input_tokens,
                    total_output_tokens=excluded.total_output_tokens,
                    total_cached_tokens=excluded.total_cached_tokens,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (session_id, user_id, model, int(total_input_tokens), int(total_output_tokens), int(total_cached_tokens)),
            )

    def get_session_token_usage(self, session_id: str) -> dict[str, Any] | None:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT * FROM session_token_usage WHERE session_id = %s"
            params: list[Any] = [session_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM session_token_usage WHERE session_id = ?", (session_id,)).fetchone()
        payload = _row_dict(row)
        return payload or None

    def save_knowledge_artifact(self, session_id: str, artifact: dict[str, Any]) -> None:
        self._upsert_json_blob("knowledge_artifacts", "artifact_json", session_id, artifact)

    def get_knowledge_artifact(self, session_id: str) -> dict[str, Any] | None:
        return self._get_json_blob("knowledge_artifacts", "artifact_json", session_id)

    def clear_knowledge_artifact(self, session_id: str) -> None:
        self._clear_by_session("knowledge_artifacts", session_id)

    def save_population_artifact(self, session_id: str, artifact: dict[str, Any]) -> None:
        self._upsert_json_blob("population_artifacts", "artifact_json", session_id, artifact)

    def get_population_artifact(self, session_id: str) -> dict[str, Any] | None:
        return self._get_json_blob("population_artifacts", "artifact_json", session_id)

    def clear_population_artifact(self, session_id: str) -> None:
        self._clear_by_session("population_artifacts", session_id)

    def append_simulation_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        self._append_event_rows("simulation_events", session_id, events)

    def append_knowledge_events(self, session_id: str, events: list[dict[str, Any]]) -> None:
        self._append_event_rows("knowledge_stream_events", session_id, events)

    def list_simulation_events(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        return self._list_event_rows("simulation_events", session_id, limit=limit)

    def list_knowledge_events(self, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        return self._list_event_rows("knowledge_stream_events", session_id, limit=limit)

    def clear_simulation_events(self, session_id: str) -> None:
        self._clear_by_session("simulation_events", session_id)

    def clear_knowledge_events(self, session_id: str) -> None:
        self._clear_by_session("knowledge_stream_events", session_id)

    def save_simulation_state_snapshot(self, session_id: str, state: dict[str, Any]) -> None:
        self._upsert_json_blob("simulation_state_snapshots", "state_json", session_id, state)

    def save_knowledge_state_snapshot(self, session_id: str, state: dict[str, Any]) -> None:
        self._upsert_json_blob("knowledge_state_snapshots", "state_json", session_id, state)

    def get_simulation_state_snapshot(self, session_id: str) -> dict[str, Any] | None:
        return self._get_json_blob("simulation_state_snapshots", "state_json", session_id)

    def get_knowledge_state_snapshot(self, session_id: str) -> dict[str, Any] | None:
        return self._get_json_blob("knowledge_state_snapshots", "state_json", session_id)

    def clear_simulation_state_snapshot(self, session_id: str) -> None:
        self._clear_by_session("simulation_state_snapshots", session_id)

    def clear_knowledge_state_snapshot(self, session_id: str) -> None:
        self._clear_by_session("knowledge_state_snapshots", session_id)

    def clear_report_cache(self, simulation_id: str) -> None:
        self._clear_by_session("report_cache", simulation_id, key_column="simulation_id")

    def save_report_state(self, session_id: str, state: dict[str, Any]) -> None:
        self._upsert_json_blob("report_runs", "state_json", session_id, state)

    def get_report_state(self, session_id: str) -> dict[str, Any] | None:
        return self._get_json_blob("report_runs", "state_json", session_id)

    def clear_report_state(self, session_id: str) -> None:
        self._clear_by_session("report_runs", session_id)

    def get_memory_sync_state(self, simulation_id: str) -> dict[str, Any] | None:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT * FROM memory_sync_state WHERE simulation_id = %s"
            params: list[Any] = [simulation_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM memory_sync_state WHERE simulation_id = ?", (simulation_id,)).fetchone()
        payload = _row_dict(row)
        return payload or None

    def save_memory_sync_state(self, simulation_id: str, last_interaction_id: int, synced_events: int, *, last_checkpoint_id: int | None = None) -> None:
        existing = self.get_memory_sync_state(simulation_id) or {}
        checkpoint_id = int(last_checkpoint_id if last_checkpoint_id is not None else existing.get("last_checkpoint_id", 0))
        user_id = self._current_user_id()
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO memory_sync_state(simulation_id, user_id, last_interaction_id, last_checkpoint_id, synced_events)
                    VALUES(%s, %s, %s, %s, %s)
                    ON CONFLICT(simulation_id) DO UPDATE SET
                        user_id = COALESCE(memory_sync_state.user_id, EXCLUDED.user_id),
                        last_interaction_id = EXCLUDED.last_interaction_id,
                        last_checkpoint_id = EXCLUDED.last_checkpoint_id,
                        synced_events = EXCLUDED.synced_events,
                        updated_at = NOW()
                    WHERE memory_sync_state.user_id IS NOT DISTINCT FROM EXCLUDED.user_id
                       OR memory_sync_state.user_id IS NULL
                       OR EXCLUDED.user_id IS NULL
                    """,
                    (simulation_id, user_id, int(last_interaction_id), checkpoint_id, int(synced_events)),
                )
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_sync_state(simulation_id, user_id, last_interaction_id, last_checkpoint_id, synced_events)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(simulation_id) DO UPDATE SET
                    user_id=COALESCE(memory_sync_state.user_id, excluded.user_id),
                    last_interaction_id=excluded.last_interaction_id,
                    last_checkpoint_id=excluded.last_checkpoint_id,
                    synced_events=excluded.synced_events,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (simulation_id, user_id, int(last_interaction_id), checkpoint_id, int(synced_events)),
            )

    def reset_memory_sync_state(self, simulation_id: str) -> None:
        self._clear_by_session("memory_sync_state", simulation_id, key_column="simulation_id")

    def append_interaction_transcript(self, session_id: str, channel: str, role: str, content: str, agent_id: str | None = None) -> None:
        user_id = self._current_user_id()
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO interaction_transcripts(session_id, user_id, channel, agent_id, role, content)
                    VALUES(%s, %s, %s, %s, %s, %s)
                    """,
                    (session_id, user_id, channel, agent_id, role, content),
                )
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO interaction_transcripts(session_id, user_id, channel, agent_id, role, content)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, channel, agent_id, role, content),
            )

    def list_interaction_transcript(self, session_id: str, channel: str, agent_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT role, content, created_at FROM interaction_transcripts WHERE session_id = %s AND channel = %s"
            params: list[Any] = [session_id, channel]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            if agent_id is not None:
                sql += " AND agent_id = %s"
                params.append(agent_id)
            sql += " ORDER BY id DESC LIMIT %s"
            params.append(int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            sql = "SELECT role, content, created_at FROM interaction_transcripts WHERE session_id = ? AND channel = ?"
            params: list[Any] = [session_id, channel]
            if agent_id is not None:
                sql += " AND agent_id = ?"
                params.append(agent_id)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        return [dict(_row_dict(row)) for row in reversed(rows)]

    def get_interaction_transcripts(self, session_id: str, agent_id: str | None = None, channel: str | None = None) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT id, session_id, channel, agent_id, role, content, created_at FROM interaction_transcripts WHERE session_id = %s"
            params: list[Any] = [session_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            if agent_id is not None:
                sql += " AND agent_id = %s"
                params.append(agent_id)
            if channel is not None:
                sql += " AND channel = %s"
                params.append(channel)
            sql += " ORDER BY id"
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            sql = "SELECT id, session_id, channel, agent_id, role, content, created_at FROM interaction_transcripts WHERE session_id = ?"
            params: list[Any] = [session_id]
            if agent_id is not None:
                sql += " AND agent_id = ?"
                params.append(agent_id)
            if channel is not None:
                sql += " AND channel = ?"
                params.append(channel)
            sql += " ORDER BY id"
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        return [dict(_row_dict(row)) for row in rows]

    def search_interaction_transcripts_fts(self, session_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized = str(query or "").strip()
        if not normalized:
            return []
        user_id = self._current_user_id()
        pattern = "%" + "%".join(normalized.split()) + "%"
        if self.is_postgres:
            sql = "SELECT * FROM interaction_transcripts WHERE session_id = %s AND COALESCE(content, '') ILIKE %s"
            params: list[Any] = [session_id, pattern]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            sql += " ORDER BY id DESC LIMIT %s"
            params.append(int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM interaction_transcripts WHERE session_id = ? AND COALESCE(content, '') LIKE ? ORDER BY id DESC LIMIT ?",
                    (session_id, pattern, int(limit)),
                ).fetchall()
        return [dict(_row_dict(row)) for row in rows]

    def clear_interaction_transcripts(self, session_id: str) -> None:
        self._clear_by_session("interaction_transcripts", session_id)

    def replace_checkpoint_records(self, session_id: str, checkpoint_kind: str, records: list[dict[str, Any]]) -> None:
        user_id = self._current_user_id()
        with self._connect() as conn:
            if self.is_postgres:
                if user_id is None:
                    conn.execute(
                        "DELETE FROM simulation_checkpoints WHERE session_id = %s AND checkpoint_kind = %s",
                        (session_id, checkpoint_kind),
                    )
                else:
                    conn.execute(
                        "DELETE FROM simulation_checkpoints WHERE session_id = %s AND checkpoint_kind = %s AND user_id = %s",
                        (session_id, checkpoint_kind, user_id),
                    )
                for record in records:
                    conn.execute(
                        """
                        INSERT INTO simulation_checkpoints(session_id, user_id, checkpoint_kind, agent_id, stance_json)
                        VALUES(%s, %s, %s, %s, %s::jsonb)
                        """,
                        (session_id, user_id, checkpoint_kind, str(record.get("agent_id")), _json_dumps(record)),
                    )
            else:
                conn.execute(
                    "DELETE FROM simulation_checkpoints WHERE session_id = ? AND checkpoint_kind = ?",
                    (session_id, checkpoint_kind),
                )
                conn.executemany(
                    """
                    INSERT INTO simulation_checkpoints(session_id, user_id, checkpoint_kind, agent_id, stance_json)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    [
                        (session_id, user_id, checkpoint_kind, str(record.get("agent_id")), _json_dumps(record))
                        for record in records
                    ],
                )

    def list_checkpoint_records(self, session_id: str, checkpoint_kind: str | None = None) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT checkpoint_kind, stance_json FROM simulation_checkpoints WHERE session_id = %s"
            params: list[Any] = [session_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            if checkpoint_kind is not None:
                sql += " AND checkpoint_kind = %s"
                params.append(checkpoint_kind)
            sql += " ORDER BY checkpoint_kind, id"
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            sql = "SELECT checkpoint_kind, stance_json FROM simulation_checkpoints WHERE session_id = ?"
            params: list[Any] = [session_id]
            if checkpoint_kind is not None:
                sql += " AND checkpoint_kind = ?"
                params.append(checkpoint_kind)
            sql += " ORDER BY checkpoint_kind, id"
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        records: list[dict[str, Any]] = []
        for row in map(_row_dict, rows):
            record = _json_loads(row["stance_json"], default={})
            record.setdefault("checkpoint_kind", row["checkpoint_kind"])
            records.append(record)
        return records

    def list_checkpoint_records_after_id(self, session_id: str, last_checkpoint_id: int, limit: int | None = None) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = "SELECT id, checkpoint_kind, stance_json, created_at FROM simulation_checkpoints WHERE session_id = %s AND id > %s"
            params: list[Any] = [session_id, int(last_checkpoint_id)]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            sql += " ORDER BY id"
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            sql = "SELECT id, checkpoint_kind, stance_json, created_at FROM simulation_checkpoints WHERE session_id = ? AND id > ? ORDER BY id"
            params: tuple[Any, ...] = (session_id, int(last_checkpoint_id))
            if limit is not None:
                sql += " LIMIT ?"
                params = (session_id, int(last_checkpoint_id), int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        records: list[dict[str, Any]] = []
        for row in map(_row_dict, rows):
            record = _json_loads(row["stance_json"], default={})
            record.setdefault("checkpoint_kind", row["checkpoint_kind"])
            record["id"] = int(row["id"])
            record["created_at"] = row["created_at"]
            records.append(record)
        return records

    def clear_checkpoint_records(self, session_id: str) -> None:
        self._clear_by_session("simulation_checkpoints", session_id)

    def _upsert_json_blob(self, table: str, column: str, session_id: str, payload: dict[str, Any]) -> None:
        user_id = self._current_user_id()
        if self.is_postgres:
            with self._connect() as conn:
                conn.execute(
                    f"""
                    INSERT INTO {table}(session_id, user_id, {column})
                    VALUES(%s, %s, %s::jsonb)
                    ON CONFLICT(session_id) DO UPDATE SET
                        user_id = COALESCE({table}.user_id, EXCLUDED.user_id),
                        {column} = EXCLUDED.{column},
                        created_at = NOW()
                    WHERE {table}.user_id IS NOT DISTINCT FROM EXCLUDED.user_id
                       OR {table}.user_id IS NULL
                       OR EXCLUDED.user_id IS NULL
                    """,
                    (session_id, user_id, _json_dumps(payload)),
                )
            return
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {table}(session_id, user_id, {column})
                VALUES(?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    user_id=COALESCE({table}.user_id, excluded.user_id),
                    {column}=excluded.{column},
                    created_at=CURRENT_TIMESTAMP
                """,
                (session_id, user_id, _json_dumps(payload)),
            )

    def _get_json_blob(self, table: str, column: str, session_id: str) -> dict[str, Any] | None:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = f"SELECT {column} FROM {table} WHERE session_id = %s"
            params: list[Any] = [session_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            with self._connect() as conn:
                row = conn.execute(sql, params).fetchone()
        else:
            with self._connect() as conn:
                row = conn.execute(f"SELECT {column} FROM {table} WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            return None
        return _json_loads(_row_dict(row)[column], default=None)

    def _append_event_rows(self, table: str, session_id: str, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        user_id = self._current_user_id()
        with self._connect() as conn:
            if self.is_postgres:
                for event in events:
                    conn.execute(
                        f"INSERT INTO {table}(session_id, user_id, event_type, event_json) VALUES(%s, %s, %s, %s::jsonb)",
                        (session_id, user_id, str(event.get('event_type', 'unknown')), _json_dumps(event)),
                    )
            else:
                conn.executemany(
                    f"INSERT INTO {table}(session_id, user_id, event_type, event_json) VALUES(?, ?, ?, ?)",
                    [
                        (session_id, user_id, str(event.get("event_type", "unknown")), _json_dumps(event))
                        for event in events
                    ],
                )

    def _list_event_rows(self, table: str, session_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        user_id = self._current_user_id()
        if self.is_postgres:
            sql = f"SELECT id, event_type, event_json FROM {table} WHERE session_id = %s"
            params: list[Any] = [session_id]
            if user_id is not None:
                sql += " AND user_id = %s"
                params.append(user_id)
            sql += " ORDER BY id"
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        else:
            sql = f"SELECT id, event_type, event_json FROM {table} WHERE session_id = ? ORDER BY id"
            params: tuple[Any, ...] = (session_id,)
            if limit is not None:
                sql += " LIMIT ?"
                params = (session_id, int(limit))
            with self._connect() as conn:
                rows = conn.execute(sql, params).fetchall()
        payloads: list[dict[str, Any]] = []
        for row in map(_row_dict, rows):
            event = _json_loads(row["event_json"], default={})
            event["id"] = int(row["id"])
            event["event_type"] = row["event_type"]
            payloads.append(event)
        return payloads

    def _clear_by_session(self, table: str, session_id: str, *, key_column: str = "session_id") -> None:
        user_id = self._current_user_id()
        with self._connect() as conn:
            if self.is_postgres:
                sql = f"DELETE FROM {table} WHERE {key_column} = %s"
                params: list[Any] = [session_id]
                if user_id is not None:
                    sql += " AND user_id = %s"
                    params.append(user_id)
                conn.execute(sql, params)
            else:
                conn.execute(f"DELETE FROM {table} WHERE {key_column} = ?", (session_id,))
