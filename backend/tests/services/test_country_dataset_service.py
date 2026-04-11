from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import duckdb

from miroworld.config import Settings
from miroworld.services.country_dataset_service import CountryDatasetService


def _make_settings(tmp_path: Path, *, huggingface_api_key: str | None = None) -> Settings:
    countries_dir = tmp_path / "countries"
    countries_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        config_countries_dir=str(countries_dir),
        huggingface_api_key=huggingface_api_key,
    )


def _write_country(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def _write_parquet(path: Path, columns: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    select_sql = ", ".join(f"{repr(value)} AS {column}" for column, value in columns.items())
    con = duckdb.connect()
    try:
        con.execute(f"COPY (SELECT {select_sql}) TO '{path}' (FORMAT PARQUET)")
    finally:
        con.close()


def test_country_status_reports_missing_dataset_and_missing_key(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "usa.yaml",
        f"""
        name: "United States"
        code: "usa"
        available: true
        dataset:
          local_paths: ["{tmp_path / 'datasets' / 'usa' / 'data' / 'train-*.parquet'}"]
          repo_id: "nvidia/Nemotron-Personas-USA"
          download_dir: "{tmp_path / 'datasets' / 'usa'}"
          required_columns: ["state"]
          country_values: ["usa", "us", "united states"]
        geography:
          field: "state"
          label: "State"
          values:
            - code: "WA"
              label: "Washington"
              aliases: ["wa", "washington", "washington state"]
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )

    service = CountryDatasetService(settings)
    status = service.country_status("usa")

    assert status["dataset_ready"] is False
    assert status["download_required"] is True
    assert status["download_status"] == "missing"
    assert status["missing_dependency"] == "huggingface_api_key"


def test_country_status_reports_ready_when_local_dataset_matches_schema(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    parquet_path = tmp_path / "datasets" / "usa" / "data" / "train-00000-of-00001.parquet"
    _write_parquet(
        parquet_path,
        {
            "state": "WA",
            "country": "USA",
            "occupation": "Teacher",
            "age": 35,
        },
    )
    _write_country(
        Path(settings.config_countries_dir) / "usa.yaml",
        f"""
        name: "United States"
        code: "usa"
        available: true
        dataset:
          local_paths: ["{tmp_path / 'datasets' / 'usa' / 'data' / 'train-*.parquet'}"]
          repo_id: "nvidia/Nemotron-Personas-USA"
          download_dir: "{tmp_path / 'datasets' / 'usa'}"
          required_columns: ["state"]
          country_values: ["usa", "us", "united states"]
        geography:
          field: "state"
          label: "State"
          values:
            - code: "WA"
              label: "Washington"
              aliases: ["wa", "washington", "washington state"]
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )

    service = CountryDatasetService(settings)
    status = service.country_status("usa")

    assert status["dataset_ready"] is True
    assert status["download_required"] is False
    assert status["download_status"] == "ready"
    assert status["resolved_dataset_path"] == str(parquet_path)


def test_start_download_uses_country_yaml_repo_id_and_marks_ready(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path, huggingface_api_key="hf-test")
    download_dir = tmp_path / "datasets" / "usa"
    parquet_path = download_dir / "data" / "train-00000-of-00001.parquet"
    _write_country(
        Path(settings.config_countries_dir) / "usa.yaml",
        f"""
        name: "United States"
        code: "usa"
        available: true
        dataset:
          local_paths: ["{download_dir / 'data' / 'train-*.parquet'}"]
          repo_id: "nvidia/Nemotron-Personas-USA"
          download_dir: "{download_dir}"
          required_columns: ["state"]
          country_values: ["usa", "us", "united states"]
        geography:
          field: "state"
          label: "State"
          values:
            - code: "WA"
              label: "Washington"
              aliases: ["wa", "washington", "washington state"]
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )

    captured: dict[str, object] = {}

    def fake_snapshot_download(*, repo_id: str, repo_type: str, allow_patterns: list[str], local_dir: str, max_workers: int, token: str | None = None):
        captured["repo_id"] = repo_id
        captured["repo_type"] = repo_type
        captured["allow_patterns"] = allow_patterns
        captured["local_dir"] = local_dir
        captured["token"] = token
        _write_parquet(
            parquet_path,
            {
                "state": "WA",
                "country": "USA",
                "occupation": "Teacher",
                "age": 35,
            },
        )
        return str(download_dir)

    class _ImmediateThread:
        def __init__(self, *, target, args=(), kwargs=None, daemon=None):  # noqa: ANN001
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self) -> None:
            self._target(*self._args, **self._kwargs)

    monkeypatch.setattr("miroworld.services.country_dataset_service.snapshot_download", fake_snapshot_download)
    monkeypatch.setattr("miroworld.services.country_dataset_service.threading.Thread", _ImmediateThread)

    service = CountryDatasetService(settings)
    initial = service.start_download("usa")
    final_status = service.download_status("usa")

    assert initial["download_status"] in {"downloading", "ready"}
    assert captured["repo_id"] == "nvidia/Nemotron-Personas-USA"
    assert captured["token"] == "hf-test"
    assert final_status["dataset_ready"] is True
    assert final_status["download_status"] == "ready"
