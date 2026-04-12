from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.console_service import ConsoleService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def _make_service(tmp_path: Path) -> ConsoleService:
    service = ConsoleService(_make_settings(tmp_path))
    service.create_session(
        requested_session_id="session-config",
        mode="live",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        api_key="test-key",
    )
    return service


def test_analysis_question_changes_do_not_clear_lightrag_workspace(tmp_path: Path, monkeypatch) -> None:
    service = _make_service(tmp_path)
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        service,
        "_clear_knowledge_downstream_artifacts",
        lambda session_id: calls.append(("knowledge", session_id)),
    )
    monkeypatch.setattr(
        service,
        "_clear_population_downstream_artifacts",
        lambda session_id: calls.append(("population", session_id)),
    )

    service.update_v2_session_config(
        "session-config",
        analysis_questions=[
            {
                "question": "How effective is the policy?",
                "type": "scale",
                "metric_name": "policy_effectiveness",
                "report_title": "Policy Effectiveness",
            }
        ],
    )

    assert calls == [("population", "session-config")]


def test_guiding_prompt_changes_still_clear_knowledge_workspace(tmp_path: Path, monkeypatch) -> None:
    service = _make_service(tmp_path)
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        service,
        "_clear_knowledge_downstream_artifacts",
        lambda session_id: calls.append(("knowledge", session_id)),
    )
    monkeypatch.setattr(
        service,
        "_clear_population_downstream_artifacts",
        lambda session_id: calls.append(("population", session_id)),
    )

    service.update_v2_session_config(
        "session-config",
        guiding_prompt="Focus on cost of living impacts and demographic effects.",
    )

    assert calls == [("knowledge", "session-config")]