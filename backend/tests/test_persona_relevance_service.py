import pytest

from mckainsey.config import Settings
from mckainsey.services.persona_relevance_service import PersonaRelevanceService


def test_persona_relevance_service_scores_document_relevant_personas_higher(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    knowledge = {
        "summary": "Transport affordability support for seniors in Woodlands.",
        "entity_nodes": [
            {"id": "area:woodlands", "label": "Woodlands", "type": "planning_area"},
            {"id": "group:seniors", "label": "Seniors", "type": "demographic"},
            {"id": "policy:transport", "label": "Transport affordability", "type": "policy"},
        ],
        "demographic_focus_summary": "seniors in Woodlands",
    }

    personas = [
        {
            "planning_area": "Woodlands",
            "income_bracket": "$3,000-$5,999",
            "age": 67,
            "occupation": "Retired",
            "digital_literacy": "medium",
        },
        {
            "planning_area": "Bukit Timah",
            "income_bracket": "$12,000 and above",
            "age": 28,
            "occupation": "Trader",
            "digital_literacy": "high",
        },
    ]

    scored = service.score_personas(
        personas,
        knowledge_artifact=knowledge,
        filters={"planning_areas": ["Woodlands", "Bukit Timah"]},
    )

    assert scored[0]["score"] > scored[1]["score"]
    assert scored[0]["component_scores"]["geographic_relevance"] > scored[1]["component_scores"]["geographic_relevance"]


def test_persona_relevance_service_balanced_sampling_keeps_multiple_strata(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    scored = [
        {
            "persona": {"planning_area": "Woodlands", "income_bracket": "$3,000-$5,999", "age": 31},
            "score": 0.90,
            "component_scores": {},
        },
        {
            "persona": {"planning_area": "Woodlands", "income_bracket": "$3,000-$5,999", "age": 33},
            "score": 0.88,
            "component_scores": {},
        },
        {
            "persona": {"planning_area": "Yishun", "income_bracket": "$6,000-$8,999", "age": 42},
            "score": 0.60,
            "component_scores": {},
        },
        {
            "persona": {"planning_area": "Yishun", "income_bracket": "$6,000-$8,999", "age": 44},
            "score": 0.59,
            "component_scores": {},
        },
    ]

    sampled = service.sample_balanced(scored, agent_count=3)
    planning_areas = {row["persona"]["planning_area"] for row in sampled}
    assert "Woodlands" in planning_areas
    assert "Yishun" in planning_areas


def test_persona_relevance_service_balanced_sampling_handles_more_strata_than_agents(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    scored = [
        {
            "persona": {"planning_area": f"Area-{index}", "income_bracket": f"Bracket-{index}", "age": 20 + index},
            "score": 1.0 - (index * 0.01),
            "component_scores": {},
        }
        for index in range(8)
    ]

    sampled = service.sample_balanced(scored, agent_count=3)

    assert len(sampled) == 3
    assert sampled[0]["score"] >= sampled[-1]["score"]


def test_persona_relevance_service_uses_graph_facet_metadata_for_matching(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    knowledge = {
        "summary": "",
        "entity_nodes": [
            {
                "id": "facet:woodlands",
                "label": "Northern neighborhood focus",
                "type": "location",
                "families": ["facet"],
                "facet_kind": "planning_area",
                "canonical_key": "planning_area:woodlands",
            },
            {
                "id": "facet:gardening",
                "label": "Outdoor lifestyle cluster",
                "type": "concept",
                "families": ["facet"],
                "facet_kind": "hobby",
                "canonical_key": "hobby:gardening",
            },
        ],
        "demographic_focus_summary": "",
    }

    personas = [
        {
            "planning_area": "Woodlands",
            "age": 62,
            "occupation": "Retired",
            "hobbies_and_interests_list": "['Gardening', 'Photography']",
            "skills_and_expertise_list": "['Community volunteering']",
        },
        {
            "planning_area": "Bukit Timah",
            "age": 29,
            "occupation": "Trader",
            "hobbies_and_interests_list": "['Photography', 'Travel planning']",
            "skills_and_expertise_list": "['Data analysis']",
        },
    ]

    scored = service.score_personas(
        personas,
        knowledge_artifact=knowledge,
        filters={"planning_areas": ["Woodlands", "Bukit Timah"]},
    )

    assert scored[0]["persona"]["planning_area"] == "Woodlands"
    assert scored[0]["score"] > scored[1]["score"]


def test_persona_relevance_service_sampling_is_repeatable_for_same_seed(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    scored = [
        {
            "persona": {"planning_area": "Woodlands", "industry": "Education", "age": 28, "occupation": "Teacher"},
            "score": 0.93,
            "component_scores": {},
        },
        {
            "persona": {"planning_area": "Sengkang", "industry": "Education", "age": 31, "occupation": "Teacher"},
            "score": 0.89,
            "component_scores": {},
        },
        {
            "persona": {"planning_area": "Punggol", "industry": "Education", "age": 34, "occupation": "Teacher"},
            "score": 0.88,
            "component_scores": {},
        },
        {
            "persona": {"planning_area": "Bedok", "industry": "Technology", "age": 54, "occupation": "Engineer"},
            "score": 0.61,
            "component_scores": {},
        },
    ]

    first = service.sample_balanced(scored, agent_count=3, seed=41)
    second = service.sample_balanced(scored, agent_count=3, seed=41)
    third = service.sample_balanced(scored, agent_count=3, seed=99)

    assert [row["persona"]["planning_area"] for row in first] == [row["persona"]["planning_area"] for row in second]
    assert [row["persona"]["planning_area"] for row in first] != [row["persona"]["planning_area"] for row in third]


def test_persona_relevance_service_build_population_artifact_includes_screen2_metadata(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    knowledge = {
        "summary": "Education grants for younger teachers and parents in north-east Singapore.",
        "entity_nodes": [
            {"id": "area:sengkang", "label": "Sengkang", "type": "location", "facet_kind": "planning_area", "canonical_key": "planning_area:sengkang"},
            {"id": "industry:education", "label": "Education", "type": "industry", "facet_kind": "industry", "canonical_key": "industry:education"},
            {"id": "group:young_adults", "label": "Young Adults", "type": "demographic", "facet_kind": "age_cohort", "canonical_key": "age_cohort:youth"},
        ],
        "relationship_edges": [],
        "demographic_focus_summary": "younger teachers and parents",
    }

    personas = [
        {
            "planning_area": "Sengkang",
            "industry": "Education",
            "age": 28,
            "occupation": "Teacher",
            "persona": "Primary school teacher balancing early-career progression with childcare concerns.",
            "skills_and_expertise_list": "['Teaching', 'Curriculum planning']",
            "hobbies_and_interests_list": "['Parenting communities']",
        },
        {
            "planning_area": "Punggol",
            "industry": "Education",
            "age": 32,
            "occupation": "Teacher",
            "persona": "Secondary school teacher concerned about student support and transport affordability.",
            "skills_and_expertise_list": "['Teaching', 'Student counselling']",
            "hobbies_and_interests_list": "['Family outings']",
        },
        {
            "planning_area": "Bukit Timah",
            "industry": "Finance",
            "age": 46,
            "occupation": "Trader",
            "persona": "Finance professional less exposed to school policy changes.",
            "skills_and_expertise_list": "['Trading', 'Risk analysis']",
            "hobbies_and_interests_list": "['Golf']",
        },
    ]

    artifact = service.build_population_artifact(
        "session-screen2",
        personas=personas,
        knowledge_artifact=knowledge,
        filters={},
        agent_count=2,
        sample_mode="affected_groups",
        seed=7,
        parsed_sampling_instructions={
            "hard_filters": {},
            "soft_boosts": {"occupation": ["teacher"]},
            "exclusions": {},
            "distribution_targets": {},
            "notes_for_ui": ["Bias toward younger teachers and parents in the north-east"],
        },
    )

    assert artifact["sample_mode"] == "affected_groups"
    assert artifact["sample_seed"] == 7
    assert artifact["parsed_sampling_instructions"]["soft_boosts"]["occupation"] == ["teacher"]
    assert artifact["selection_diagnostics"]["semantic_rerank_count"] >= 1
    assert artifact["sampled_personas"][0]["selection_reason"]["matched_facets"]
    assert artifact["sampled_personas"][0]["selection_reason"]["semantic_summary"]


def test_population_artifact_caps_semantic_rerank_pool_for_large_screen2_samples(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    knowledge = {
        "summary": "Education policy for younger families and teachers in Singapore.",
        "entity_nodes": [
            {"id": "area:sengkang", "label": "Sengkang", "type": "location", "facet_kind": "planning_area", "canonical_key": "planning_area:sengkang"},
            {"id": "industry:education", "label": "Education", "type": "industry", "facet_kind": "industry", "canonical_key": "industry:education"},
        ],
        "relationship_edges": [],
        "demographic_focus_summary": "younger adults, families, teachers",
    }

    personas = [
        {
            "planning_area": "Sengkang" if index % 2 == 0 else "Punggol",
            "industry": "Education" if index % 3 else "Healthcare",
            "age": 24 + (index % 35),
            "occupation": "Teacher" if index % 2 == 0 else "Nurse",
            "persona": f"Persona {index} focused on education, childcare, and neighbourhood services.",
            "professional_persona": f"Professional persona {index}",
            "cultural_background": "Singaporean",
            "skills_and_expertise": "Teaching, curriculum planning, student support",
            "skills_and_expertise_list": "['Teaching', 'Curriculum planning']",
            "hobbies_and_interests_list": "['Parenting communities', 'Reading']",
            "career_goals_and_ambitions": "Support families and build better public services.",
            "sex": "Female" if index % 2 == 0 else "Male",
            "education_level": "Bachelor's degree",
            "marital_status": "Married" if index % 4 == 0 else "Single",
        }
        for index in range(1000)
    ]

    captured_counts: list[int] = []

    monkeypatch.setattr(service.embeddings, "is_enabled", lambda: True)

    def fake_embed_texts(texts):
        captured_counts.append(len(texts))
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(service.embeddings, "embed_texts", fake_embed_texts)

    artifact = service.build_population_artifact(
        "session-screen2-large",
        personas=personas,
        knowledge_artifact=knowledge,
        filters={},
        agent_count=500,
        sample_mode="affected_groups",
        seed=11,
        parsed_sampling_instructions={
            "hard_filters": {},
            "soft_boosts": {"occupation": ["teacher"]},
            "exclusions": {},
            "distribution_targets": {},
            "notes_for_ui": ["Bias toward younger teachers and families."],
        },
    )

    assert captured_counts
    assert captured_counts[0] <= 49
    assert artifact["selection_diagnostics"]["semantic_rerank_count"] <= 48


def test_normalize_parsed_instructions_discards_unsupported_fields(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    normalized = service._normalize_parsed_instructions(
        {
            "hard_filters": {
                "occupation": ["teacher"],
                "notes": ["should-not-appear"],
            },
            "soft_boosts": {
                "age_cohort": ["youth"],
                "free_text": ["ignore-me"],
            },
            "notes_for_ui": ["Bias toward teachers and younger adults."],
        },
        source="gemini",
    )

    assert normalized["hard_filters"] == {"occupation": ["teacher"]}
    assert normalized["soft_boosts"] == {"age_cohort": ["youth"]}
    assert normalized["notes_for_ui"] == ["Bias toward teachers and younger adults."]


def test_issue_profile_ignores_hidden_screen1_noise_nodes(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    issue_profile = service._build_issue_profile(
        {
            "summary": "Education affordability concerns for younger Singaporeans.",
            "entity_nodes": [
                {
                    "id": "hidden:google",
                    "label": "Google",
                    "type": "organization",
                    "ui_default_hidden": True,
                    "generic_placeholder": True,
                },
                {
                    "id": "hidden:japan",
                    "label": "Japan",
                    "type": "location",
                    "ui_default_hidden": True,
                    "low_value_orphan": True,
                },
                {
                    "id": "facet:education",
                    "label": "Education",
                    "type": "industry",
                    "facet_kind": "industry",
                    "canonical_key": "industry:education",
                },
                {
                    "id": "facet:young-adults",
                    "label": "Young Adults",
                    "type": "demographic",
                    "facet_kind": "age_cohort",
                    "canonical_key": "age_cohort:youth",
                },
                {
                    "id": "doc:teachers",
                    "label": "Teachers",
                    "type": "persons",
                    "ui_default_hidden": False,
                },
                {
                    "id": "doc:singapore",
                    "label": "Singapore",
                    "type": "location",
                    "display_bucket": "location",
                    "ui_default_hidden": False,
                },
            ],
            "relationship_edges": [],
            "demographic_focus_summary": "",
        },
        {"hard_filters": {}, "soft_boosts": {}, "soft_penalties": {}, "exclusions": {}, "distribution_targets": {}, "notes_for_ui": []},
    )

    assert "google" not in issue_profile["document_entities"]
    assert "japan" not in issue_profile["document_entities"]
    assert "singapore" not in issue_profile["document_entities"]
    assert "teachers" in issue_profile["document_entities"]
    assert issue_profile["facets"]["industry"] == {"education"}
    assert issue_profile["facets"]["age_cohort"] == {"youth"}


def test_parse_sampling_instructions_extracts_numeric_age_constraints(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    monkeypatch.setattr(service.llm, "is_enabled", lambda: True)
    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda *args, **kwargs: (
            '{"hard_filters": {}, "soft_boosts": {}, "soft_penalties": {}, '
            '"exclusions": {}, "distribution_targets": {}, '
            '"notes_for_ui": ["Operator asked for strict age limits."]}'
        ),
    )

    parsed = service.parse_sampling_instructions(
        "Strictly no one over the age of 40.",
        knowledge_artifact={"summary": "Birth-rate and childcare pressure in Singapore.", "entity_nodes": []},
    )

    assert parsed["hard_filters"]["max_age"] == ["40"]
    assert any("age <= 40" in note.lower() for note in parsed["notes_for_ui"])


def test_parse_sampling_instructions_allows_notes_only_without_runtime_error(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    monkeypatch.setattr(service.llm, "is_enabled", lambda: True)
    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda *args, **kwargs: (
            '{"hard_filters": {}, "soft_boosts": {}, "soft_penalties": {}, '
            '"exclusions": {}, "distribution_targets": {}, '
            '"notes_for_ui": ["Focus on digitally engaged residents."]}'
        ),
    )

    parsed = service.parse_sampling_instructions(
        "Focus on digitally engaged residents.",
        knowledge_artifact={"summary": "Digital adoption trends.", "entity_nodes": []},
    )

    assert parsed["hard_filters"] == {}
    assert parsed["soft_boosts"] == {}
    assert parsed["notes_for_ui"]


def test_parse_sampling_instructions_live_mode_requires_llm(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    monkeypatch.setattr(service.llm, "is_enabled", lambda: False)

    with pytest.raises(RuntimeError, match="Live"):
        service.parse_sampling_instructions(
            "Focus on digitally engaged residents.",
            knowledge_artifact={"summary": "Digital adoption trends.", "entity_nodes": []},
            live_mode=True,
        )


def test_persona_relevance_service_applies_exclusions_penalties_and_distribution_targets(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    knowledge = {
        "summary": "Education affordability and childcare pressure for younger households.",
        "entity_nodes": [
            {"id": "facet:education", "label": "Education", "type": "industry", "facet_kind": "industry", "canonical_key": "industry:public_administration_education_services"},
            {"id": "facet:young", "label": "Young Adults", "type": "demographic", "facet_kind": "age_cohort", "canonical_key": "age_cohort:youth"},
        ],
        "relationship_edges": [],
        "demographic_focus_summary": "",
    }

    personas = [
        {
            "planning_area": "Sengkang",
            "industry": "Public Administration & Education Services",
            "age": 25,
            "occupation": "Professional",
            "marital_status": "Married",
            "persona": "Education worker with childcare concerns.",
            "professional_persona": "Supports school programmes.",
            "skills_and_expertise_list": "['Teaching support']",
            "hobbies_and_interests_list": "['Parenting communities']",
        },
        {
            "planning_area": "Bedok",
            "industry": "Public Administration & Education Services",
            "age": 24,
            "occupation": "Professional",
            "marital_status": "Single",
            "persona": "Education worker focused on career growth.",
            "professional_persona": "Supports student services.",
            "skills_and_expertise_list": "['Teaching support']",
            "hobbies_and_interests_list": "['Reading']",
        },
        {
            "planning_area": "Bedok",
            "industry": "Financial & Insurance Services",
            "age": 27,
            "occupation": "Professional",
            "marital_status": "Married",
            "persona": "Finance worker with little exposure to school policy.",
            "professional_persona": "Works in banking.",
            "skills_and_expertise_list": "['Financial analysis']",
            "hobbies_and_interests_list": "['Investing']",
        },
    ]

    artifact = service.build_population_artifact(
        "session-screen2-instructions",
        personas=personas,
        knowledge_artifact=knowledge,
        filters={},
        agent_count=1,
        sample_mode="affected_groups",
        seed=19,
        parsed_sampling_instructions={
            "hard_filters": {},
            "soft_boosts": {"industry": ["public_administration_education_services"]},
            "soft_penalties": {"marital_status": ["single"]},
            "exclusions": {"industry": ["financial_insurance_services"]},
            "distribution_targets": {"planning_area": ["sengkang"]},
            "notes_for_ui": [],
            "source": "test",
        },
    )

    industries = [row["persona"]["industry"] for row in artifact["sampled_personas"]]
    planning_areas = [row["persona"]["planning_area"] for row in artifact["sampled_personas"]]
    assert "Financial & Insurance Services" not in industries
    assert "Sengkang" in planning_areas
    assert artifact["sampled_personas"][0]["persona"]["marital_status"] == "Married"


def test_persona_relevance_service_matches_hobby_and_skill_fields(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    knowledge = {
        "summary": "Community-facing outreach.",
        "entity_nodes": [
            {"id": "facet:gardening", "label": "Gardening", "type": "concept", "facet_kind": "hobby", "canonical_key": "hobby:gardening"},
            {"id": "facet:public-speaking", "label": "Public Speaking", "type": "skill", "facet_kind": "skill", "canonical_key": "skill:public_speaking"},
        ],
        "relationship_edges": [],
        "demographic_focus_summary": "",
    }

    personas = [
        {
            "planning_area": "Woodlands",
            "age": 34,
            "occupation": "Professional",
            "industry": "Professional Services",
            "persona": "Community volunteer with strong outreach experience.",
            "professional_persona": "Leads neighborhood workshops.",
            "skills_and_expertise_list": "['Public speaking', 'Event coordination']",
            "hobbies_and_interests_list": "['Gardening', 'Photography']",
        },
        {
            "planning_area": "Bedok",
            "age": 34,
            "occupation": "Professional",
            "industry": "Professional Services",
            "persona": "Office worker focused on spreadsheets.",
            "professional_persona": "Back-office operations.",
            "skills_and_expertise_list": "['Data analysis']",
            "hobbies_and_interests_list": "['Reading']",
        },
    ]

    scored, _ = service.rank_personas(
        personas,
        knowledge_artifact=knowledge,
        filters={},
        parsed_sampling_instructions={
            "hard_filters": {},
            "soft_boosts": {"hobby": ["gardening"], "skill": ["public_speaking"]},
            "soft_penalties": {},
            "exclusions": {},
            "distribution_targets": {},
            "notes_for_ui": [],
            "source": "test",
        },
    )

    assert scored[0]["persona"]["planning_area"] == "Woodlands"
    assert "hobby" in scored[0]["instruction_matches"]
    assert "skill" in scored[0]["instruction_matches"]
    assert "hobby:gardening" in scored[0]["matched_facets"]
    assert "skill:public_speaking" in scored[0]["matched_facets"]


def test_persona_relevance_service_falls_back_when_embeddings_unavailable(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    knowledge = {
        "summary": "Transport affordability support for seniors in Woodlands.",
        "entity_nodes": [
            {"id": "area:woodlands", "label": "Woodlands", "type": "planning_area"},
            {"id": "group:seniors", "label": "Seniors", "type": "demographic"},
            {"id": "policy:transport", "label": "Transport affordability", "type": "policy"},
        ],
        "demographic_focus_summary": "seniors in Woodlands",
    }

    personas = [
        {
            "planning_area": "Woodlands",
            "income_bracket": "$3,000-$5,999",
            "age": 67,
            "occupation": "Retired",
            "digital_literacy": "medium",
        },
        {
            "planning_area": "Bukit Timah",
            "income_bracket": "$12,000 and above",
            "age": 28,
            "occupation": "Trader",
            "digital_literacy": "high",
        },
    ]

    monkeypatch.setattr(service.embeddings, "is_enabled", lambda: True)
    monkeypatch.setattr(service.embeddings, "embed_texts", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    scored = service.score_personas(
        personas,
        knowledge_artifact=knowledge,
        filters={"planning_areas": ["Woodlands", "Bukit Timah"]},
    )

    assert scored[0]["persona"]["planning_area"] == "Woodlands"
    assert scored[0]["component_scores"]["semantic_relevance"] >= scored[1]["component_scores"]["semantic_relevance"]


def test_score_personas_live_mode_requires_embeddings(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = PersonaRelevanceService(settings)

    monkeypatch.setattr(service.embeddings, "is_enabled", lambda: False)

    with pytest.raises(RuntimeError, match="Live"):
        service.score_personas(
            [
                {
                    "planning_area": "Woodlands",
                    "income_bracket": "$3,000-$5,999",
                    "age": 67,
                    "occupation": "Retired",
                    "digital_literacy": "medium",
                }
            ],
            knowledge_artifact={
                "summary": "Transport affordability support for seniors in Woodlands.",
                "entity_nodes": [
                    {"id": "area:woodlands", "label": "Woodlands", "type": "planning_area"},
                ],
                "demographic_focus_summary": "seniors in Woodlands",
            },
            filters={"planning_areas": ["Woodlands"]},
            live_mode=True,
        )
