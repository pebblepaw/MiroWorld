from mckainsey.config import Settings
from mckainsey.services.simulation_service import SimulationService


def test_build_context_bundles_prioritizes_matched_facets_and_adjacent_nodes(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    knowledge_artifact = {
        "summary": "Sports voucher policy for active youths in Woodlands.",
        "entity_nodes": [
            {
                "id": "policy:sports-voucher",
                "label": "Sports Voucher",
                "type": "policy",
                "source_ids": ["chunk-1"],
                "file_paths": ["policy.md"],
            },
            {
                "id": "age:youth",
                "label": "Youth",
                "type": "demographic",
                "facet_kind": "age_cohort",
                "canonical_key": "age_cohort:youth",
                "source_ids": ["chunk-1"],
                "file_paths": ["policy.md"],
            },
            {
                "id": "area:woodlands",
                "label": "Woodlands",
                "type": "location",
                "facet_kind": "planning_area",
                "canonical_key": "planning_area:woodlands",
                "source_ids": ["chunk-2"],
                "file_paths": ["policy.md"],
            },
        ],
        "relationship_edges": [
            {
                "source": "policy:sports-voucher",
                "target": "age:youth",
                "label": "targets",
            },
            {
                "source": "policy:sports-voucher",
                "target": "area:woodlands",
                "label": "pilot area",
            },
        ],
    }
    sampled_personas = [
        {
            "agent_id": "agent-0001",
            "persona": {
                "planning_area": "Woodlands",
                "age": 23,
                "occupation": "Student",
            },
            "selection_reason": {
                "matched_facets": ["planning_area:woodlands", "age_cohort:youth"],
                "matched_document_entities": ["sports voucher"],
            },
        }
    ]

    bundles = service.build_context_bundles(
        simulation_id="session-1",
        policy_summary="Sports voucher for active youths.",
        knowledge_artifact=knowledge_artifact,
        sampled_personas=sampled_personas,
    )

    bundle = bundles["agent-0001"]
    assert bundle["matched_context_nodes"][:2] == ["planning_area:woodlands", "age_cohort:youth"]
    assert "policy:sports-voucher" in bundle["graph_node_ids"]
    assert bundle["provenance"]["source_ids"] == ["chunk-1", "chunk-2"]
    assert bundle["provenance"]["file_paths"] == ["policy.md"]
    assert "Sports voucher" in bundle["brief"]


def test_run_opinion_checkpoint_returns_structured_stance_records(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda prompt, system_prompt=None: (
            '[{"agent_id":"agent-0001","stance_score":0.81,"stance_class":"approve",'
            '"confidence":0.74,"primary_driver":"affordability","matched_context_nodes":["planning_area:woodlands"]}]'
        ),
    )

    checkpoints = service.run_opinion_checkpoint(
        simulation_id="session-1",
        checkpoint_kind="baseline",
        policy_summary="Subsidise sports access in Woodlands.",
        agent_context_bundles={
            "agent-0001": {
                "agent_id": "agent-0001",
                "brief": "Young Woodlands resident who benefits from sports subsidies.",
                "matched_context_nodes": ["planning_area:woodlands"],
            }
        },
    )

    assert checkpoints[0]["checkpoint_kind"] == "baseline"
    assert checkpoints[0]["agent_id"] == "agent-0001"
    assert checkpoints[0]["stance_class"] == "approve"
    assert checkpoints[0]["primary_driver"] == "affordability"
    assert checkpoints[0]["matched_context_nodes"] == ["planning_area:woodlands"]
