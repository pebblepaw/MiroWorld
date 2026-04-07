from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.console_service import ConsoleService


client = TestClient(app)


def test_v2_report_route_returns_structured_payload(monkeypatch):
    def fake_get_v2_report(self, session_id: str):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "generated_at": "2026-04-06T09:00:00Z",
            "executive_summary": "Approval softened among lower-income cohorts after rounds 3-5.",
            "metric_deltas": [
                {
                    "metric_name": "approval_rate",
                    "metric_label": "Approval Rate",
                    "metric_unit": "%",
                    "initial_value": 43.0,
                    "final_value": 55.0,
                    "delta": 12.0,
                    "direction": "up",
                    "report_title": "Policy Approval",
                }
            ],
            "quick_stats": {"agent_count": 220, "round_count": 5, "model": "gemini-2.5-flash-lite", "provider": "google"},
            "sections": [
                {
                    "question": "Do you approve of this policy? Rate 1-10.",
                    "report_title": "Policy Approval",
                    "type": "scale",
                    "answer": "Approval rose once implementation details were clarified.",
                    "evidence": [{"agent_id": "agent-002", "post_id": "post-22", "quote": "Details made it more acceptable."}],
                    "metric": {
                        "metric_name": "approval_rate",
                        "metric_label": "Approval Rate",
                        "metric_unit": "%",
                        "initial_value": 43.0,
                        "final_value": 55.0,
                        "delta": 12.0,
                        "direction": "up",
                        "report_title": "Policy Approval",
                    },
                }
            ],
            "insight_blocks": [{"type": "polarization_index", "title": "Polarization Over Time", "description": "How divided opinions became.", "data": {"status": "ok"}}],
            "preset_sections": [{"title": "Recommendations", "answer": "Prioritize affordability safeguards."}],
        }

    def fake_get_report_full(self, session_id: str):
        raise AssertionError("legacy ReportFullResponse path should not be used for /report")

    monkeypatch.setattr(ConsoleService, "get_v2_report", fake_get_v2_report)
    monkeypatch.setattr(ConsoleService, "get_report_full", fake_get_report_full)

    response = client.get("/api/v2/console/session/session-a/report")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-a"
    assert body["executive_summary"] == "Approval softened among lower-income cohorts after rounds 3-5."
    assert body["metric_deltas"][0]["metric_name"] == "approval_rate"
    assert body["sections"][0]["report_title"] == "Policy Approval"
    assert body["insight_blocks"][0]["type"] == "polarization_index"


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
