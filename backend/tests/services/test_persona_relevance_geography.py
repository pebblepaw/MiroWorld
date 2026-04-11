from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.persona_relevance_service import PersonaRelevanceService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def test_build_population_artifact_uses_country_geography_field_and_aliases(tmp_path: Path, monkeypatch) -> None:
    service = PersonaRelevanceService(_make_settings(tmp_path))

    scored_rows = [
        {
            "persona": {
                "state": "California",
                "age": 32,
                "sex": "female",
                "occupation": "Teacher",
                "industry": "Education",
            },
            "score": 0.91,
            "component_scores": {
                "bm25_relevance": 0.1,
                "semantic_relevance": 0.2,
                "geographic_relevance": 0.3,
                "socioeconomic_relevance": 0.4,
                "digital_behavior_relevance": 0.5,
                "filter_alignment": 0.6,
                "instruction_alignment": 0.7,
                "penalty_pressure": 0.0,
            },
            "matched_facets": [],
            "matched_document_entities": [],
            "instruction_matches": [],
            "bm25_terms": [],
            "semantic_summary": "Selected for geography alignment.",
        },
        {
            "persona": {
                "state": "Texas",
                "age": 44,
                "sex": "male",
                "occupation": "Nurse",
                "industry": "Health & Social Services",
            },
            "score": 0.84,
            "component_scores": {
                "bm25_relevance": 0.1,
                "semantic_relevance": 0.2,
                "geographic_relevance": 0.3,
                "socioeconomic_relevance": 0.4,
                "digital_behavior_relevance": 0.5,
                "filter_alignment": 0.6,
                "instruction_alignment": 0.7,
                "penalty_pressure": 0.0,
            },
            "matched_facets": [],
            "matched_document_entities": [],
            "instruction_matches": [],
            "bm25_terms": [],
            "semantic_summary": "Selected for geography alignment.",
        },
    ]

    def fake_rank_personas(
        personas: list[dict[str, object]],
        *,
        knowledge_artifact: dict[str, object],
        filters: dict[str, object],
        parsed_sampling_instructions: dict[str, object] | None = None,
        shortlist_size: int | None = None,
        semantic_pool_size: int | None = None,
        live_mode: bool = False,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        del personas, knowledge_artifact, filters, parsed_sampling_instructions, shortlist_size, semantic_pool_size, live_mode
        return scored_rows, {"candidate_count": len(scored_rows)}

    monkeypatch.setattr(service, "rank_personas", fake_rank_personas)

    artifact = service.build_population_artifact(
        "session-usa",
        personas=[{"state": "California"}, {"state": "Texas"}],
        knowledge_artifact={"entity_nodes": [], "relationship_edges": []},
        filters={},
        agent_count=2,
        sample_mode="population_baseline",
        seed=7,
        parsed_sampling_instructions={"source": "runtime"},
        live_mode=False,
        country="usa",
    )

    assert artifact["geography_field"] == "state"
    assert artifact["coverage"]["planning_areas"] == ["California", "Texas"]
    assert artifact["coverage"]["geographies"] == ["California", "Texas"]
    assert artifact["representativeness"]["planning_area_distribution"] == {"California": 1, "Texas": 1}
    assert artifact["representativeness"]["geography_distribution"] == {"California": 1, "Texas": 1}
    assert artifact["representativeness"]["state_distribution"] == {"California": 1, "Texas": 1}
    assert artifact["sampled_personas"][0]["persona"]["geography_field"] == "state"
    assert artifact["sampled_personas"][0]["persona"]["geography_value"] in {"California", "Texas"}


def test_usa_state_names_are_normalized_for_matching_and_display(tmp_path: Path) -> None:
    service = PersonaRelevanceService(_make_settings(tmp_path))

    normalized = service._normalize_instruction_values("state", ["Washington", "wa"], country="usa")

    assert normalized == ["wa"]
    assert service._persona_geography_value({"state": "WA"}, "state", country="usa") == "Washington"
