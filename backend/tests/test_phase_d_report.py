from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.persona_sampler import PersonaSampler

client = TestClient(app)


def _seed_simulation(monkeypatch):
    personas = [
        {"age": 64, "planning_area": "Woodlands", "income_bracket": "$2,000-$2,999"},
        {"age": 45, "planning_area": "Yishun", "income_bracket": "$5,000-$5,999"},
        {"age": 31, "planning_area": "Bishan", "income_bracket": "$10,000-$11,999"},
    ]
    monkeypatch.setattr(PersonaSampler, "sample", lambda self, req: personas)
    client.post(
        "/api/v1/phase-b/simulations/run",
        json={
            "simulation_id": "sim-report",
            "policy_summary": "Expand childcare subsidies and carbon tax rebates",
            "agent_count": 3,
            "rounds": 2,
        },
    )


def test_phase_d_report_and_chat(monkeypatch):
    _seed_simulation(monkeypatch)

    report = client.get("/api/v1/phase-d/report/sim-report")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["simulation_id"] == "sim-report"
    assert "approval_rates" in body

    chat = client.post(
        "/api/v1/phase-d/report/chat",
        json={"simulation_id": "sim-report", "message": "Who are the most dissenting groups?"},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["simulation_id"] == "sim-report"
