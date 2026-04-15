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
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
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
            guiding_prompt: |
              Extract a neutral factual policy brief for {country_name}.
              Use {geography_label}-level context where relevant.
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


def test_create_v2_session_formats_country_specific_guiding_prompt(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "singapore.yaml",
        """
        name: "Singapore"
        code: "singapore"
        available: true
        dataset:
          local_paths: ["backend/data/nemotron/singapore/data/train-*.parquet"]
          repo_id: "nvidia/Nemotron-Personas-Singapore"
          download_dir: "backend/data/nemotron/singapore"
          required_columns: ["planning_area"]
          country_values: ["singapore", "sg"]
        geography:
          field: "planning_area"
          label: "Planning Area"
        filterable_columns:
          - field: "planning_area"
            type: "categorical"
        """,
    )
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
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )
    _write_prompt(Path(settings.config_prompts_dir) / "public-policy-testing.yaml")

    service = ConsoleService(settings)
    monkeypatch.setattr(service.country_datasets, "ensure_country_ready", lambda _country: "/tmp/fake.parquet")

    payload = service.create_v2_session(
        country="usa",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id="session-country-aware-prompt",
    )

    stored = service._read_session_config(payload["session_id"])
    assert stored["country"] == "usa"
    assert "United States" in stored["guiding_prompt"]
    assert "State-level" in stored["guiding_prompt"]
    assert "{country_name}" not in stored["guiding_prompt"]


def test_country_change_refreshes_default_guiding_prompt_without_overwriting_custom_prompt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "singapore.yaml",
        """
        name: "Singapore"
        code: "singapore"
        available: true
        dataset:
          local_paths: ["backend/data/nemotron/singapore/data/train-*.parquet"]
          repo_id: "nvidia/Nemotron-Personas-Singapore"
          download_dir: "backend/data/nemotron/singapore"
          required_columns: ["planning_area"]
          country_values: ["singapore", "sg"]
        geography:
          field: "planning_area"
          label: "Planning Area"
        filterable_columns:
          - field: "planning_area"
            type: "categorical"
        """,
    )
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
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )
    _write_prompt(Path(settings.config_prompts_dir) / "public-policy-testing.yaml")

    service = ConsoleService(settings)
    monkeypatch.setattr(service.country_datasets, "ensure_country_ready", lambda _country: "/tmp/fake.parquet")

    created = service.create_v2_session(
        country="usa",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id="session-country-switch",
    )

    original = service._read_session_config(created["session_id"])
    assert "United States" in original["guiding_prompt"]

    refreshed = service.update_v2_session_config(created["session_id"], country="singapore")
    assert refreshed["country"] == "singapore"
    assert "Singapore" in (refreshed["guiding_prompt"] or "")
    assert "Planning Area-level" in (refreshed["guiding_prompt"] or "")

    service.update_v2_session_config(
        created["session_id"],
        guiding_prompt="Custom hand-written prompt.",
    )
    preserved = service.update_v2_session_config(created["session_id"], country="usa")
    assert preserved["country"] == "usa"
    assert preserved["guiding_prompt"] == "Custom hand-written prompt."
