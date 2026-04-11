from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from miroworld.api import routes_console
from miroworld.config import Settings


def _make_settings(tmp_path: Path) -> Settings:
    countries_dir = tmp_path / "countries"
    countries_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        config_countries_dir=str(countries_dir),
        huggingface_api_key="",
    )


def _write_country(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def test_v2_countries_exposes_dataset_readiness_fields(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "usa.yaml",
        """
        name: "United States"
        code: "usa"
        flag_emoji: "🇺🇸"
        available: true
        dataset_path: "backend/data/nemotron/usa/data/train-*.parquet"
        dataset:
          local_paths: ["backend/data/nemotron/usa/data/train-*.parquet"]
          repo_id: "nvidia/Nemotron-Personas-USA"
          download_dir: "backend/data/nemotron/usa"
          required_columns: ["state"]
          country_values: ["usa", "us", "united states"]
        geography:
          field: "state"
          label: "State"
          values:
            - code: "WA"
              label: "Washington"
              aliases: ["wa", "washington", "washington state"]
        """,
    )

    payload = routes_console.v2_countries(settings)

    assert len(payload) == 1
    assert payload[0].code == "usa"
    assert payload[0].dataset_ready is False
    assert payload[0].download_required is True
    assert payload[0].missing_dependency == "huggingface_api_key"
