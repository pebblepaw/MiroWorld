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
