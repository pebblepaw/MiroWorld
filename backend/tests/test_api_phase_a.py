from fastapi.testclient import TestClient

from mckainsey.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_knowledge_process_requires_text_or_default_flag():
    response = client.post(
        "/api/v1/phase-a/knowledge/process",
        json={"simulation_id": "sim-1"},
    )
    assert response.status_code == 422
    assert "use_default_demo_document" in response.json()["detail"]
