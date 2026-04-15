from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from miroworld.config import Settings
from miroworld.services.persona_relevance_service import PersonaRelevanceService


def _make_settings(tmp_path: Path, *, use_repo_countries: bool = False) -> Settings:
    repo_root = Path(__file__).resolve().parents[3]
    countries_dir = (repo_root / "config" / "countries") if use_repo_countries else (tmp_path / "countries")
    countries_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        config_countries_dir=str(countries_dir),
    )


def _write_country(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def test_build_population_artifact_uses_country_geography_field_and_aliases(tmp_path: Path, monkeypatch) -> None:
    service = PersonaRelevanceService(_make_settings(tmp_path, use_repo_countries=True))

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
    service = PersonaRelevanceService(_make_settings(tmp_path, use_repo_countries=True))

    normalized = service._normalize_instruction_values("state", ["Washington", "wa"], country="usa")

    assert normalized == ["wa"]
    assert service._persona_geography_value({"state": "WA"}, "state", country="usa") == "Washington"


def test_build_population_artifact_applies_country_display_rules_to_slug_fields(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    _write_country(
        Path(settings.config_countries_dir) / "usa.yaml",
        """
        name: "United States"
        code: "usa"
        dataset:
          local_paths: ["backend/.cache/nemotron/data/train-*.parquet"]
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
        text_cleaning:
          categorical_fields:
            occupation:
              strategy: "slug_title"
            education_level:
              strategy: "slug_title"
              overrides:
                9th_12th_no_diploma: "9th-12th, No Diploma"
            marital_status:
              strategy: "slug_title"
              overrides:
                married_present: "Married"
        filterable_columns:
          - field: "state"
            type: "categorical"
        """,
    )
    service = PersonaRelevanceService(settings)

    scored_rows = [
        {
            "persona": {
                "state": "WA",
                "age": 32,
                "sex": "female",
                "occupation": "teacher_or_instructor",
                "education_level": "9th_12th_no_diploma",
                "marital_status": "married_present",
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
        personas=[{"state": "WA"}],
        knowledge_artifact={"entity_nodes": [], "relationship_edges": []},
        filters={},
        agent_count=1,
        sample_mode="population_baseline",
        seed=7,
        parsed_sampling_instructions={"source": "runtime"},
        live_mode=False,
        country="usa",
    )

    persona = artifact["sampled_personas"][0]["persona"]

    assert persona["planning_area"] == "Washington"
    assert persona["geography_value"] == "Washington"
    assert persona["occupation"] == "Teacher Or Instructor"
    assert persona["education_level"] == "9th-12th, No Diploma"
    assert persona["marital_status"] == "Married"
