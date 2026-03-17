from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.persona_sampler import PersonaSampler

client = TestClient(app)


def test_phase_c_memory_sync_and_fetch(monkeypatch):
    personas = [
        {"age": 30, "planning_area": "Woodlands", "income_bracket": "$3,000-$5,999"},
        {"age": 44, "planning_area": "Sembawang", "income_bracket": "$6,000-$8,999"},
    ]
    monkeypatch.setattr(PersonaSampler, "sample", lambda self, req: personas)

    client.post(
        "/api/v1/phase-b/simulations/run",
        json={
            "simulation_id": "sim-memory",
            "policy_summary": "Public transport fare stabilization",
            "agent_count": 2,
            "rounds": 1,
        },
    )

    sync = client.post("/api/v1/phase-c/memory/sync", json={"simulation_id": "sim-memory"})
    assert sync.status_code == 200, sync.text
    assert sync.json()["synced_events"] > 0

    memory = client.get("/api/v1/phase-c/memory/sim-memory/agent-0001")
    assert memory.status_code == 200, memory.text
    assert memory.json()["agent_id"] == "agent-0001"
