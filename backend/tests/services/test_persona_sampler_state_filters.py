from __future__ import annotations

from pathlib import Path

import duckdb

from miroworld.services.persona_sampler import PersonaSampler


def _write_parquet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute(
            f"""
            COPY (
                SELECT
                    'usa-1' AS uuid,
                    'Teacher persona' AS persona,
                    'Teacher' AS occupation,
                    'USA' AS country,
                    'WA' AS state,
                    35 AS age
            ) TO '{path}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()


def test_query_candidates_matches_state_filters_case_insensitively(tmp_path: Path) -> None:
    parquet_path = tmp_path / "train-00000-of-00001.parquet"
    _write_parquet(parquet_path)

    sampler = PersonaSampler("unused", "train", cache_dir=str(tmp_path))

    rows = sampler.query_candidates(
        limit=5,
        seed=7,
        dataset_path=str(parquet_path),
        country_values=["usa"],
        extra_filters={"state": ["wa"]},
    )

    assert len(rows) == 1
    assert rows[0]["state"] == "WA"
