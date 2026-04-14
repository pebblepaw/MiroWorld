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


def test_v2_provider_catalog_keeps_google_key_required_even_when_server_key_is_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _make_settings(tmp_path).model_copy(update={"gemini_api": "server-key"})
    service = ConsoleService(settings)
    monkeypatch.setattr(service, "list_provider_models", lambda provider_id: {"models": []})

    payload = service.v2_provider_catalog()

    gemini = next(item for item in payload if item["name"] == "gemini")
    assert gemini["requires_api_key"] is True


def test_create_v2_session_requires_explicit_api_key_for_remote_provider(
    tmp_path: Path,
) -> None:
    settings = _make_settings(tmp_path).model_copy(update={"gemini_api": "server-key"})
    _write_country(Path(settings.config_countries_dir) / "singapore.yaml")
    _write_prompt(Path(settings.config_prompts_dir) / "public-policy-testing.yaml")
    service = ConsoleService(settings)

    try:
        service.create_v2_session(
            country="singapore",
            use_case="public-policy-testing",
            provider="google",
            model="gemini-2.5-flash-lite",
            mode="live",
        )
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "status_code", None) == 422
        assert "API key is required" in str(getattr(exc, "detail", exc))
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected create_v2_session to reject remote providers without an explicit API key.")


def test_session_model_payload_does_not_fallback_to_server_key_for_remote_provider(
    tmp_path: Path,
) -> None:
    settings = _make_settings(tmp_path).model_copy(update={"gemini_api": "server-key"})
    service = ConsoleService(settings)

    payload = service.create_session(
        requested_session_id="session-explicit-key",
        mode="live",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        api_key="user-key",
    )
    assert payload["api_key_configured"] is True

    service.store.upsert_console_session(
        session_id="session-explicit-key",
        mode="live",
        status="created",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        embed_model_name="gemini-embedding-001",
        api_key="",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    session_payload = service.get_session_model_config("session-explicit-key")
    assert session_payload["api_key_configured"] is False
    assert session_payload["api_key_masked"] is None


def test_cached_v2_report_requires_bullet_schema(tmp_path: Path) -> None:
    service = ConsoleService(_make_settings(tmp_path))

    legacy_shaped = {
        "session_id": "session-demo",
        "metric_deltas": [],
        "sections": [
            {
                "question": "What changed?",
                "report_title": "Summary",
                "type": "open-ended",
                "answer": "Legacy prose blob.",
            }
        ],
        "insight_blocks": [],
        "preset_sections": [
            {
                "title": "Recommendations",
                "answer": "Legacy preset prose.",
            }
        ],
    }
    current_shaped = {
        "session_id": "session-demo",
        "metric_deltas": [],
        "sections": [
            {
                "question": "What changed?",
                "report_title": "Summary",
                "type": "open-ended",
                "bullets": ["Point one."],
            }
        ],
        "insight_blocks": [],
        "preset_sections": [
            {
                "title": "Recommendations",
                "bullets": ["Point one."],
            }
        ],
    }

    assert service._is_cached_v2_report_payload(legacy_shaped) is False
    assert service._is_cached_v2_report_payload(current_shaped) is True
