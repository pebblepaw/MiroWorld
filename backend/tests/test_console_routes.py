from pathlib import Path

from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.console_service import ConsoleService


client = TestClient(app)


def test_console_session_creation_and_knowledge_processing(monkeypatch, tmp_path):
    def fake_create_session(self, requested_session_id=None, mode="demo"):
        return {
            "session_id": requested_session_id or "session-test",
            "mode": mode,
            "status": "created",
        }

    async def fake_process_knowledge(self, session_id, *, document_text=None, source_path=None, demographic_focus=None, use_default_demo_document=False):
        return {
            "session_id": session_id,
            "document": {
                "document_id": "doc-1",
                "source_path": source_path,
                "text_length": len(document_text or ""),
            },
            "summary": "Budget support touches transport and seniors.",
            "entity_nodes": [
                {"id": "policy:transport", "label": "Transport Support", "type": "policy"},
                {"id": "group:seniors", "label": "Seniors", "type": "demographic"},
            ],
            "relationship_edges": [
                {"source": "policy:transport", "target": "group:seniors", "type": "affects"},
            ],
            "entity_type_counts": {"policy": 1, "demographic": 1},
            "processing_logs": ["Parsed document", "Built graph"],
            "demographic_focus_summary": demographic_focus,
        }

    monkeypatch.setattr(ConsoleService, "create_session", fake_create_session)
    monkeypatch.setattr(ConsoleService, "process_knowledge", fake_process_knowledge)

    created = client.post("/api/v2/console/session", json={"session_id": "session-a", "mode": "demo"})
    assert created.status_code == 200, created.text
    assert created.json()["session_id"] == "session-a"

    knowledge = client.post(
        "/api/v2/console/session/session-a/knowledge/process",
        json={
            "document_text": "Singapore budget support for transport and seniors.",
            "demographic_focus": "seniors in Woodlands",
        },
    )
    assert knowledge.status_code == 200, knowledge.text
    body = knowledge.json()
    assert body["session_id"] == "session-a"
    assert body["entity_type_counts"]["policy"] == 1
    assert body["relationship_edges"][0]["type"] == "affects"


def test_console_population_preview_route(monkeypatch):
    def fake_preview_population(self, session_id, request):
        return {
            "session_id": session_id,
            "candidate_count": 12,
            "sample_count": 4,
            "coverage": {
                "planning_areas": ["Woodlands", "Yishun"],
                "age_buckets": {"25-34": 2, "35-44": 2},
            },
            "sampled_personas": [
                {
                    "agent_id": "agent-0001",
                    "persona": {"planning_area": "Woodlands", "income_bracket": "$3,000-$5,999", "age": 32},
                    "selection_reason": {
                        "score": 0.78,
                        "semantic_relevance": 0.8,
                        "geographic_relevance": 0.9,
                        "socioeconomic_relevance": 0.7,
                        "digital_behavior_relevance": 0.5,
                        "filter_alignment": 1.0,
                    },
                }
            ],
            "agent_graph": {
                "nodes": [{"id": "agent-0001", "label": "agent-0001", "planning_area": "Woodlands"}],
                "links": [],
            },
            "representativeness": {"status": "balanced"},
        }

    monkeypatch.setattr(ConsoleService, "preview_population", fake_preview_population)

    response = client.post(
        "/api/v2/console/session/session-a/sampling/preview",
        json={"agent_count": 4, "planning_areas": ["Woodlands", "Yishun"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate_count"] == 12
    assert body["sampled_personas"][0]["selection_reason"]["score"] == 0.78
    assert body["representativeness"]["status"] == "balanced"


def test_console_knowledge_upload_route_parses_pdf(monkeypatch):
    async def fake_process_knowledge(self, session_id, *, document_text=None, source_path=None, demographic_focus=None, use_default_demo_document=False):
        assert "transport" in (document_text or "").lower()
        assert source_path and source_path.endswith(".pdf")
        return {
            "session_id": session_id,
            "document": {
                "document_id": "doc-upload",
                "source_path": source_path,
                "text_length": len(document_text or ""),
            },
            "summary": "Parsed uploaded PDF.",
            "entity_nodes": [],
            "relationship_edges": [],
            "entity_type_counts": {},
            "processing_logs": ["Uploaded file parsed"],
            "demographic_focus_summary": demographic_focus,
        }

    monkeypatch.setattr(ConsoleService, "process_knowledge", fake_process_knowledge)

    sample_pdf = Path(__file__).resolve().parents[2] / "Sample_Inputs" / "fy2026_budget_statement.pdf"
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/v2/console/session/session-a/knowledge/upload",
            data={"demographic_focus": "seniors in Woodlands"},
            files={"file": (sample_pdf.name, handle, "application/pdf")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-a"
    assert body["document"]["source_path"].endswith(".pdf")
    assert body["summary"] == "Parsed uploaded PDF."


def test_console_interaction_hub_chat_routes(monkeypatch):
    def fake_report_chat(self, session_id, message):
        assert session_id == "session-a"
        assert "friction" in message.lower()
        return {
            "session_id": session_id,
            "response": "Woodlands shows the highest friction because affordability concerns concentrated there.",
            "gemini_model": "gemini-2.0-flash",
            "zep_context_used": True,
        }

    def fake_agent_chat(self, session_id, agent_id, message):
        assert session_id == "session-a"
        assert agent_id == "agent-001"
        assert "position" in message.lower()
        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "response": "My concerns increased after repeated comments about transport costs and weak household buffers.",
            "memory_used": True,
            "gemini_model": "gemini-2.0-flash",
            "zep_context_used": True,
        }

    monkeypatch.setattr(ConsoleService, "report_chat", fake_report_chat)
    monkeypatch.setattr(ConsoleService, "agent_chat", fake_agent_chat)

    report_response = client.post(
        "/api/v2/console/session/session-a/interaction-hub/report-chat",
        json={"message": "What is the highest friction area?"},
    )
    assert report_response.status_code == 200, report_response.text
    report_body = report_response.json()
    assert report_body["zep_context_used"] is True
    assert report_body["gemini_model"] == "gemini-2.0-flash"

    agent_response = client.post(
        "/api/v2/console/session/session-a/interaction-hub/agent-chat",
        json={"agent_id": "agent-001", "message": "What changed your position?"},
    )
    assert agent_response.status_code == 200, agent_response.text
    agent_body = agent_response.json()
    assert agent_body["memory_used"] is True
    assert agent_body["zep_context_used"] is True
    assert agent_body["agent_id"] == "agent-001"
