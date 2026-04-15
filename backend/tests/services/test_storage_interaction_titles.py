from __future__ import annotations

from pathlib import Path

from miroworld.services.storage import SimulationStore


def test_replace_interactions_persists_titles(tmp_path: Path) -> None:
    store = SimulationStore(str(tmp_path / "simulation.db"))
    simulation_id = "sim-seed-title"
    store.upsert_simulation(simulation_id, "Policy summary", rounds=2, agent_count=1)

    store.replace_interactions(
        simulation_id,
        [
            {
                "round_no": 1,
                "actor_agent_id": "agent-1",
                "target_agent_id": None,
                "action_type": "create_post",
                "title": "[Will this keep transport affordable?] (Seeded post)",
                "content": "As a teacher in Woodlands, fare support matters for daily travel.",
                "delta": 0.0,
            }
        ],
    )

    interactions = store.get_interactions(simulation_id)

    assert len(interactions) == 1
    assert interactions[0]["title"] == "[Will this keep transport affordable?] (Seeded post)"
