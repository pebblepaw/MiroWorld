from __future__ import annotations

import pytest
from fastapi import HTTPException

from miroworld.config import Settings
from miroworld.services.console_service import ConsoleService


def _make_service(tmp_path) -> ConsoleService:
    service = ConsoleService(Settings(simulation_db_path=str(tmp_path / "simulation.db")))
    service.create_session(
        requested_session_id="session-sim-validation",
        mode="live",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        api_key="test-key",
    )
    service.store.save_population_artifact(
        "session-sim-validation",
        {
            "sampled_personas": [
                {
                    "agent_id": "agent-0001",
                    "persona": {"name": "Alex Tan", "planning_area": "Bishan"},
                }
            ]
        },
    )
    return service


def test_start_simulation_rejects_refusal_like_knowledge_summary(tmp_path) -> None:
    service = _make_service(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        service.start_simulation(
            "session-sim-validation",
            subject_summary=(
                "I am sorry, but I cannot fulfill this request. "
                "The provided document chunk does not contain policy measures."
            ),
            rounds=3,
        )

    assert exc_info.value.status_code == 422
    assert "Knowledge extraction did not produce a usable summary" in str(exc_info.value.detail)
