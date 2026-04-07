from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.persona_sampler import PersonaSampler

client = TestClient(app)


def test_phase_b_run_and_snapshot(monkeypatch):
    personas = [
        {"age": 35, "planning_area": "Woodlands", "income_bracket": "$3,000-$5,999"},
        {"age": 41, "planning_area": "Yishun", "income_bracket": "$6,000-$8,999"},
        {"age": 28, "planning_area": "Tampines", "income_bracket": "$9,000-$11,999"},
    ]

    monkeypatch.setattr(PersonaSampler, "sample", lambda self, req: personas)

    run = client.post(
        "/api/v1/phase-b/simulations/run",
        json={
            "simulation_id": "sim-test-b",
            "policy_summary": "Introduce congestion pricing with targeted rebates",
            "agent_count": 3,
            "rounds": 2,
        },
    )
    assert run.status_code == 200, run.text
    payload = run.json()
    assert payload["agent_count"] == 3

    snap = client.get("/api/v1/phase-b/simulations/sim-test-b")
    assert snap.status_code == 200, snap.text
    snapshot = snap.json()
    assert snapshot["stats"]["agent_count"] == 3
    assert len(snapshot["stage3a_scores"]) == 3
