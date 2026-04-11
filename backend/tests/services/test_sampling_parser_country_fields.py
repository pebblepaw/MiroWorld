from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.persona_relevance_service import PersonaRelevanceService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def test_build_instruction_prompt_is_country_aware_for_usa(tmp_path: Path) -> None:
    service = PersonaRelevanceService(_make_settings(tmp_path))

    prompt = service._build_instruction_prompt(
        "More samples from California.",
        {"summary": "US housing policy"},
        country="usa",
    )

    assert "United States" in prompt
    assert "state" in prompt
    assert "planning_area" not in prompt


def test_normalize_parsed_instructions_keeps_country_specific_filter_fields(tmp_path: Path) -> None:
    service = PersonaRelevanceService(_make_settings(tmp_path))

    normalized = service._normalize_parsed_instructions(
        {
            "hard_filters": {
                "state": ["California"],
                "occupation": ["Teacher"],
            },
            "notes_for_ui": ["Prefer California teachers."],
        },
        source="test",
        supported_fields={"state", "occupation"},
    )

    assert normalized["hard_filters"]["state"] == ["california"]
    assert normalized["hard_filters"]["occupation"] == ["teacher"]
