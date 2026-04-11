from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from miroworld.config import Settings
from miroworld.services import config_service
from miroworld.services.config_service import ConfigService


def _write_parquet(path: Path, columns: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    select_sql = ", ".join(f"{repr(value)} AS {column}" for column, value in columns.items())
    con = duckdb.connect()
    try:
        con.execute(f"COPY (SELECT {select_sql}) TO '{path}' (FORMAT PARQUET)")
    finally:
        con.close()


def test_resolve_dataset_path_does_not_scan_unrelated_cache_roots(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"

    singapore_parquet = backend_dir / "data" / "nemotron" / "data" / "train-00000-of-00002.parquet"
    _write_parquet(
        singapore_parquet,
        {
            "planning_area": "Bedok",
            "country": "Singapore",
            "occupation": "Teacher",
        },
    )

    usa_parquet = backend_dir / ".cache" / "nemotron" / "data" / "train-00000-of-00011.parquet"
    _write_parquet(
        usa_parquet,
        {
            "state": "Washington",
            "country": "USA",
            "occupation": "Teacher",
        },
    )

    monkeypatch.setattr(config_service, "REPO_ROOT", repo_root)
    monkeypatch.setattr(config_service, "BACKEND_DIR", backend_dir)

    service = ConfigService(Settings())

    with pytest.raises(FileNotFoundError):
        service.resolve_dataset_path(
            "backend/data/nemotron/usa_nemotron_cc.parquet",
            required_columns=["state"],
        )
