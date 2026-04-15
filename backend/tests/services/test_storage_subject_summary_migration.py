from __future__ import annotations

import sqlite3
from pathlib import Path

from miroworld.services.storage import SimulationStore


def test_existing_simulations_table_migrates_policy_summary_to_subject_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "simulation.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE simulations (
                simulation_id TEXT PRIMARY KEY,
                policy_summary TEXT NOT NULL,
                rounds INTEGER NOT NULL,
                agent_count INTEGER NOT NULL,
                runtime TEXT NOT NULL DEFAULT 'heuristic',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    SimulationStore(str(db_path))

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(simulations)").fetchall()]

    assert "subject_summary" in columns
    assert "policy_summary" not in columns
