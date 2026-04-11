from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.console_service import ConsoleService
from miroworld.services.metrics_service import _agent_name
from miroworld.services.persona_relevance_service import PersonaRelevanceService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def test_extract_persona_display_name_uses_majority_vote_across_all_persona_columns(tmp_path: Path) -> None:
    service = PersonaRelevanceService(_make_settings(tmp_path))

    persona = {
        "occupation": "Planner",
        "planning_area": "Bishan",
        "professional_persona": "At 48, the resident manages transport accessibility programs across the city.",
        "persona": "The resident believes the proposal could improve commute reliability for families.",
        "travel_persona": "At 48, Syed R. (Mogan) Lamaze prefers rail travel when visiting other cities for work.",
        "sports_persona": "Syed R. (Mogan) Lamaze coaches a weekend football group in his neighborhood.",
        "arts_persona": "Syed R. (Mogan) Lamaze attends gallery openings after work.",
    }

    assert service._extract_persona_display_name(persona) == "Syed R. (Mogan) Lamaze"


def test_apply_checkpoint_scores_to_agents_persists_confirmed_name(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    session_id = "session-confirmed-name"

    sampled_rows = [
        {
            "agent_id": "agent-0001",
            "persona": {
                "display_name": "Planner (Bishan)",
                "occupation": "Planner",
                "planning_area": "Bishan",
            },
        }
    ]
    baseline = [
        {
            "agent_id": "agent-0001",
            "stance_score": 0.6,
            "confirmed_name": "John Tan",
        }
    ]
    final = [
        {
            "agent_id": "agent-0001",
            "stance_score": 0.7,
            "confirmed_name": "John Tan",
        }
    ]

    service._apply_checkpoint_scores_to_agents(session_id, sampled_rows, baseline, final)

    stored_agents = service.store.get_agents(session_id)

    assert stored_agents[0]["persona"]["confirmed_name"] == "John Tan"
    assert stored_agents[0]["persona"]["display_name"] == "John Tan"


def test_metrics_agent_name_prefers_confirmed_name_from_persona() -> None:
    agent = {
        "agent_id": "agent-0001",
        "persona": {
            "display_name": "Planner (Bishan)",
            "confirmed_name": "John Tan",
        },
    }

    assert _agent_name(agent, "agent-0001") == "John Tan"
