from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from fastapi import HTTPException

from miroworld.config import Settings
from miroworld.services.console_service import ConsoleService


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


def _write_prompt(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        dedent(
            """
            name: "Public Policy Testing"
            code: "public-policy-testing"
            guiding_prompt: "Test prompt"
            analysis_questions:
              - question: "What do you think?"
                type: "open-ended"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_create_v2_session_rejects_missing_country_dataset(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "usa.yaml",
        """
        name: "United States"
        code: "usa"
        available: true
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
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )
    _write_prompt(Path(settings.config_prompts_dir) / "public-policy-testing.yaml")

    service = ConsoleService(settings)

    with pytest.raises(HTTPException) as exc_info:
        service.create_v2_session(
            country="usa",
            use_case="public-policy-testing",
            provider="google",
            model="gemini-2.5-flash-lite",
            api_key="test-key",
            mode="live",
            session_id="session-missing-country-data",
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["code"] == "country_dataset_missing"
    assert exc_info.value.detail["country"] == "usa"
