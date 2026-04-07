from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.console_service import ConsoleService


client = TestClient(app)


def test_v2_analytics_polarization_route(monkeypatch):
    def fake_polarization(self, session_id: str):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "series": [
                {"round": "R1", "polarization_index": 0.12, "severity": "low"},
                {"round": "R2", "polarization_index": 0.33, "severity": "moderate"},
            ],
        }

    monkeypatch.setattr(ConsoleService, "get_analytics_polarization", fake_polarization)

    response = client.get("/api/v2/console/session/session-a/analytics/polarization")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["series"][1]["severity"] == "moderate"


def test_v2_analytics_opinion_flow_route(monkeypatch):
    def fake_opinion_flow(self, session_id: str):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "initial": {"supporter": 122, "neutral": 44, "dissenter": 54},
            "final": {"supporter": 87, "neutral": 19, "dissenter": 114},
            "flows": [
                {"from": "supporter", "to": "dissenter", "count": 31},
                {"from": "neutral", "to": "dissenter", "count": 20},
            ],
        }

    monkeypatch.setattr(ConsoleService, "get_analytics_opinion_flow", fake_opinion_flow)

    response = client.get("/api/v2/console/session/session-a/analytics/opinion-flow")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["final"]["dissenter"] == 114
    assert body["flows"][0]["from"] == "supporter"


def test_v2_analytics_influence_route(monkeypatch):
    def fake_influence(self, session_id: str):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "top_influencers": [
                {
                    "agent_id": "agent-09",
                    "agent_name": "Agent Nine",
                    "stance": "supporter",
                    "score": 1.82,
                    "influence_score": 1.82,
                    "top_view": "Keep going with the rollout.",
                    "top_post": {"content": "Keep going with the rollout."},
                }
            ],
            "leaders": [
                {
                    "agent_id": "agent-09",
                    "agent_name": "Agent Nine",
                    "stance": "supporter",
                    "influence_score": 1.82,
                    "top_post": {"content": "Keep going with the rollout."},
                }
            ],
            "items": [{"agent_id": "agent-09", "influence_score": 1.82}],
            "nodes": [{"id": "agent-09", "influence_score": 1.82}],
            "edges": [{"source": "agent-09", "target": "agent-77", "weight": 0.51}],
            "total_nodes": 38,
            "total_edges": 116,
        }

    monkeypatch.setattr(ConsoleService, "get_analytics_influence", fake_influence)

    response = client.get("/api/v2/console/session/session-a/analytics/influence")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["top_influencers"][0]["agent_id"] == "agent-09"
    assert body["leaders"][0]["top_post"]["content"] == "Keep going with the rollout."
    assert body["items"][0]["agent_id"] == "agent-09"
    assert body["total_edges"] == 116


def test_v2_analytics_cascades_route(monkeypatch):
    def fake_cascades(self, session_id: str):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "viral_posts": [
                {
                    "post_id": "post-111",
                    "author": "agent-01",
                    "author_name": "Agent One",
                    "stance": "supporter",
                    "title": "Rollout update",
                    "content": "The rollout is moving ahead with safeguards.",
                    "likes": 12,
                    "dislikes": 2,
                    "comments": [
                        {
                            "author": "agent-04",
                            "stance": "neutral",
                            "content": "Need more detail on timing.",
                            "likes": 2,
                            "dislikes": 1,
                        }
                    ],
                }
            ],
            "cascades": [
                {
                    "post_id": "post-111",
                    "comments": [
                        {
                            "author": "agent-04",
                            "stance": "neutral",
                            "content": "Need more detail on timing.",
                            "likes": 2,
                            "dislikes": 1,
                        }
                    ],
                }
            ],
            "posts": [{"post_id": "post-111", "content": "The rollout is moving ahead with safeguards."}],
            "post_id": "post-111",
            "tree_size": 18,
            "total_engagement": 203,
            "mean_opinion_delta": -1.7,
            "engaged_agents": ["agent-01", "agent-04", "agent-09"],
        }

    monkeypatch.setattr(ConsoleService, "get_analytics_cascades", fake_cascades)

    response = client.get("/api/v2/console/session/session-a/analytics/cascades")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["viral_posts"][0]["post_id"] == "post-111"
    assert body["viral_posts"][0]["comments"][0]["author"] == "agent-04"
    assert body["posts"][0]["content"] == "The rollout is moving ahead with safeguards."
