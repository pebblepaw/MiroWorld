from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.persona_sampler import PersonaSampler
from mckainsey.services.report_service import ReportService

client = TestClient(app)


def test_phase_e_dashboard_payload(monkeypatch):
    personas = [
        {"age": 27, "planning_area": "Yishun", "income_bracket": "$3,000-$5,999"},
        {"age": 51, "planning_area": "Woodlands", "income_bracket": "$4,000-$4,999"},
    ]
    monkeypatch.setattr(PersonaSampler, "sample", lambda self, req: personas)
    monkeypatch.setattr(
        ReportService,
        "build_report",
        lambda self, simulation_id: {
            "simulation_id": simulation_id,
            "approval_rates": {"stage3a": 0.5, "stage3b": 0.6, "delta": 0.1},
            "friction_by_planning_area": [
                {"planning_area": "Yishun", "friction_index": 0.24, "approval_post": 0.58},
                {"planning_area": "Woodlands", "friction_index": 0.27, "approval_post": 0.54},
            ],
            "recommendations": [
                {"title": "Increase local outreach", "confidence": 0.68},
            ],
        },
    )

    client.post(
        "/api/v1/phase-b/simulations/run",
        json={
            "simulation_id": "sim-dashboard",
            "policy_summary": "Targeted senior transport grants",
            "agent_count": 2,
            "rounds": 1,
        },
    )

    response = client.get("/api/v1/phase-e/dashboard/sim-dashboard")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["simulation"]["simulation_id"] == "sim-dashboard"
    assert "friction_map" in body
    assert "opinion_flow" in body
    assert "heatmap_matrix" in body


def test_phase_e_geojson_endpoint(monkeypatch):
    fake_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "WOODLANDS"},
                "geometry": {"type": "Polygon", "coordinates": []},
            }
        ],
    }

    from mckainsey.services.geo_service import PlanningAreaGeoService

    monkeypatch.setattr(PlanningAreaGeoService, "get_geojson", lambda self, force_refresh=False: fake_geojson)

    response = client.get("/api/v1/phase-e/geo/planning-areas")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["properties"]["name"] == "WOODLANDS"
