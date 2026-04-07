from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.console_service import ConsoleService


client = TestClient(app)


def test_v2_report_route_returns_structured_payload(monkeypatch):
    def fake_get_v2_report(self, session_id: str):
        raise AssertionError("legacy V2 report builder should not be used for /report")

    def fake_get_report_full(self, session_id: str):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "status": "completed",
            "generated_at": "2026-04-06T09:00:00Z",
            "executive_summary": "Approval softened among lower-income cohorts after rounds 3-5.",
            "insight_cards": [{"title": "Affordability became the dominant fault line", "summary": "Later rounds concentrated on cost pressure.", "severity": "high"}],
            "support_themes": [{"theme": "targeting", "summary": "Targeted aid stayed credible among families.", "evidence": ["Targeted aid remains useful for families with children."]}],
            "dissent_themes": [{"theme": "rent", "summary": "Housing costs kept surfacing as the main objection.", "evidence": ["Rent pressure offsets most benefits in mature estates."]}],
            "demographic_breakdown": [{"segment": "Woodlands, lower-income", "approval_rate": 0.43, "dissent_rate": 0.38, "sample_size": 31}],
            "influential_content": [{"content_type": "post", "author_agent_id": "agent-0002", "summary": "A cost-of-living post shaped the late-round shift.", "engagement_score": 18}],
            "recommendations": [{"title": "Front-load affordability safeguards", "rationale": "Cost pressure is the clearest driver of dissent.", "priority": "high"}],
            "risks": [{"title": "Lower-income backlash", "summary": "Affected cohorts may harden if implementation details lag.", "severity": "high"}],
        }

    monkeypatch.setattr(ConsoleService, "get_v2_report", fake_get_v2_report)
    monkeypatch.setattr(ConsoleService, "get_report_full", fake_get_report_full)

    response = client.get("/api/v2/console/session/session-a/report")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-a"
    assert body["status"] == "completed"
    assert body["executive_summary"] == "Approval softened among lower-income cohorts after rounds 3-5."
    assert body["insight_cards"][0]["title"] == "Affordability became the dominant fault line"
    assert body["recommendations"][0]["priority"] == "high"


def test_v2_report_export_route_streams_docx(monkeypatch):
    def fake_export(self, session_id: str):
        assert session_id == "session-a"
        return ("mckainsey-session-a-report.docx", b"PK\x03\x04fake-docx-binary")

    monkeypatch.setattr(ConsoleService, "export_v2_report_docx", fake_export)

    response = client.get("/api/v2/console/session/session-a/report/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "mckainsey-session-a-report.docx" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"PK\x03\x04")


def test_v2_group_chat_route_returns_segment_responses(monkeypatch):
    def fake_group_chat(self, session_id: str, segment: str, message: str, top_n: int = 5):
        assert session_id == "session-a"
        assert segment == "dissenter"
        assert top_n == 3
        assert "position" in message.lower()
        return {
            "session_id": session_id,
            "segment": segment,
            "responses": [
                {"agent_id": "agent-001", "response": "Costs in my area rose faster than support.", "influence_score": 0.94},
                {"agent_id": "agent-004", "response": "I shifted after repeated posts from renters.", "influence_score": 0.87},
            ],
        }

    monkeypatch.setattr(ConsoleService, "group_chat", fake_group_chat)

    response = client.post(
        "/api/v2/console/session/session-a/chat/group",
        json={"segment": "dissenter", "message": "What changed your position?", "top_n": 3},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["segment"] == "dissenter"
    assert len(body["responses"]) == 2
    assert body["responses"][0]["agent_id"] == "agent-001"


def test_v2_group_chat_route_accepts_plural_segment_aliases(monkeypatch):
    def fake_group_chat(self, session_id: str, segment: str, message: str, top_n: int = 5):
        assert session_id == "session-a"
        assert segment == "supporter"
        assert top_n == 2
        assert "why" in message.lower()
        return {
            "session_id": session_id,
            "segment": segment,
            "responses": [
                {"agent_id": "agent-101", "response": "The policy still looks beneficial overall.", "influence_score": 0.91},
            ],
        }

    monkeypatch.setattr(ConsoleService, "group_chat", fake_group_chat)

    response = client.post(
        "/api/v2/console/session/session-a/chat/group",
        json={"segment": "supporters", "message": "Why do you support it?", "top_n": 2},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["segment"] == "supporter"
    assert body["responses"][0]["agent_id"] == "agent-101"


def test_v2_agent_chat_route_returns_persona_response(monkeypatch):
    def fake_agent_chat(self, session_id: str, agent_id: str, message: str):
        assert session_id == "session-a"
        assert agent_id == "agent-002"
        assert "concern" in message.lower()
        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "response": "My concern is whether support reaches renters early enough.",
            "memory_used": True,
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "zep_context_used": False,
            "graphiti_context_used": True,
        }

    monkeypatch.setattr(ConsoleService, "agent_chat_v2", fake_agent_chat)

    response = client.post(
        "/api/v2/console/session/session-a/chat/agent/agent-002",
        json={"message": "What is your biggest concern now?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agent_id"] == "agent-002"
    assert body["graphiti_context_used"] is True
