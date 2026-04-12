from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

from miroworld.config import Settings
from miroworld.services.console_service import ConsoleService


def _make_settings(tmp_path: Path) -> Settings:
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
        console_demo_output_path=str(tmp_path / "demo-output.json"),
        console_demo_frontend_output_path=str(tmp_path / "frontend-demo-output.json"),
        huggingface_api_key="",
    )


def _write_country(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        dedent(
            """
            name: "Singapore"
            code: "singapore"
            available: true
            dataset:
              local_paths: ["data/nemotron/singapore/train-*.parquet"]
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


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


def test_create_v2_demo_session_falls_back_to_prompt_questions_when_demo_bundle_has_none(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _make_settings(tmp_path)
    _write_country(Path(settings.config_countries_dir) / "singapore.yaml")
    _write_prompt(Path(settings.config_prompts_dir) / "public-policy-testing.yaml")
    Path(settings.console_demo_output_path).write_text(
        json.dumps(
            {
                "session": {"session_id": "demo-session"},
                "analysis_questions": None,
                "source_run": {"analysis_questions": None},
            }
        ),
        encoding="utf-8",
    )

    service = ConsoleService(settings)
    monkeypatch.setattr(service.country_datasets, "ensure_country_ready", lambda *_: str(tmp_path / "dataset.parquet"))

    payload = service.create_v2_session(
        country="singapore",
        use_case="public-policy-testing",
        provider="ollama",
        model="qwen3:4b-instruct-2507-q4_K_M",
        mode="demo",
        session_id="session-demo-questions",
    )

    session_config = service._read_session_config(payload["session_id"])

    assert payload == {"session_id": "session-demo-questions"}
    assert session_config["analysis_questions"] == [
        {
            "question": "What do you think?",
            "type": "open-ended",
        }
    ]