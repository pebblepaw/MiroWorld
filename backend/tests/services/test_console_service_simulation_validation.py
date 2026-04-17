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


def test_start_simulation_rejects_summary_without_required_policy_substance(tmp_path) -> None:
    service = _make_service(tmp_path)
    service._upsert_session_config(
        "session-sim-validation",
        {
            "country": "usa",
            "use_case": "public-policy-testing",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        service.start_simulation(
            "session-sim-validation",
            subject_summary="The source discusses personalities and campaign optics without any concrete issue detail.",
            rounds=3,
        )

    assert exc_info.value.status_code == 422
    assert "concrete civic or political detail" in str(exc_info.value.detail)


def test_knowledge_summary_accepts_broad_political_issue_summary(tmp_path) -> None:
    service = _make_service(tmp_path)
    service._upsert_session_config(
        "session-sim-validation",
        {
            "country": "usa",
            "use_case": "public-policy-testing",
        },
    )

    assert service._knowledge_summary_is_usable(
        (
            "The article compares the candidates' positions on immigration enforcement, border policy, "
            "and healthcare costs for working families."
        ),
        use_case="public-policy-testing",
    )


def test_merge_knowledge_artifacts_strips_inline_markdown_bullets_from_summary(tmp_path) -> None:
    service = _make_service(tmp_path)

    artifact = service._merge_knowledge_artifacts(
        "session-sim-validation",
        artifacts=[
            {
                "summary": (
                    "AI-Powered Social Media Simulation: AI citizens interact by posting. "
                    "* Direct Interaction: Enables users to chat directly with agents."
                ),
                "document": {"document_id": "doc-1", "source_path": "memory://doc-1"},
                "entity_nodes": [],
                "relationship_edges": [],
                "processing_logs": [],
            }
        ],
        guiding_prompt=None,
        demographic_focus=None,
    )

    assert artifact["summary"] == (
        "AI-Powered Social Media Simulation: AI citizens interact by posting. "
        "Direct Interaction: Enables users to chat directly with agents."
    )
