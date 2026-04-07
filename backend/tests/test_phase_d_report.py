from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.persona_sampler import PersonaSampler
from mckainsey.services.report_service import ReportService

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

    monkeypatch.setattr(
        ReportService,
        "build_report",
        lambda self, simulation_id: {
            "simulation_id": simulation_id,
            "executive_summary": "Support improved after cohort-targeted messaging.",
            "approval_rates": {"stage3a": 0.4, "stage3b": 0.6, "delta": 0.2},
            "top_dissenting_demographics": [
                {"planning_area": "Woodlands", "approval_post": 0.42, "friction_index": 0.31},
            ],
            "friction_by_planning_area": [
                {"planning_area": "Woodlands", "friction_index": 0.31, "approval_post": 0.42},
            ],
            "income_cohorts": [
                {"income_bracket": "$2,000-$2,999", "approval_post": 0.41, "avg_post_opinion": 4.8, "cohort_size": 1},
            ],
            "influential_agents": [
                {"agent_id": "agent-1", "influence_score": 0.9, "planning_area": "Woodlands"},
            ],
            "key_arguments_for": [
                {"text": "Transport support improves affordability.", "agent_id": "agent-1", "round_no": 1, "strength": 0.5},
            ],
            "key_arguments_against": [
                {"text": "Coverage is still narrow for some households.", "agent_id": "agent-2", "round_no": 1, "strength": 0.4},
            ],
            "recommendations": [
                {"title": "Targeted outreach", "confidence": 0.7},
            ],
        },
    )
    monkeypatch.setattr(
        ReportService,
        "report_chat",
        lambda self, simulation_id, message: "Woodlands and Yishun remain the highest-friction cohorts.",
    )

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
