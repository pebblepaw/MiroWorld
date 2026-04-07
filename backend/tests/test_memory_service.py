from mckainsey.config import Settings
from mckainsey.services.memory_service import MemoryService


def test_search_agent_context_falls_back_until_zep_returns_hits(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "simulation.db"))
    service = MemoryService(settings)

    queries: list[str] = []

    def fake_search(simulation_id: str, query: str, limit: int = 8, live_mode: bool = False):
        queries.append(query)
        del live_mode
        if query == "agent-0004":
            return {
                "episodes": [{"content": "actor=agent-0004 action=comment_created content=Support details matter."}],
                "synced_events": 3,
                "zep_context_used": True,
            }
        return {
            "episodes": [],
            "synced_events": 3,
            "zep_context_used": False,
        }

    monkeypatch.setattr(service, "search_simulation_context", fake_search)

    result = service.search_agent_context("session-a", "agent-0004", "Why did your position change?", limit=8)

    assert result["zep_context_used"] is True
    assert result["episodes"][0]["content"].startswith("actor=agent-0004")
    assert queries == [
        "actor=agent-0004 target=agent-0004 Why did your position change?",
        "agent-0004 Why did your position change?",
        "agent-0004",
    ]


def test_search_simulation_context_uses_local_fallback_when_zep_is_unavailable(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "simulation.db"), zep_api_key=None, zep_cloud=None)
    service = MemoryService(settings)

    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda simulation_id: [
            {
                "id": 12,
                "round_no": 2,
                "actor_agent_id": "agent-0007",
                "target_agent_id": "agent-0003",
                "action_type": "comment_created",
                "content": "Transport costs changed my position over time.",
                "delta": -0.6,
            },
            {
                "id": 13,
                "round_no": 3,
                "actor_agent_id": "agent-0005",
                "target_agent_id": "agent-0007",
                "action_type": "comment_created",
                "content": "I agree that costs remain the central concern.",
                "delta": -0.2,
            },
        ],
    )

    payload = service.search_simulation_context("session-a", "transport costs", limit=2)

    assert payload["zep_context_used"] is False
    assert payload["memory_backend"] == "local"
    assert len(payload["episodes"]) == 2
    assert "transport costs" in payload["episodes"][0]["content"].lower()


def test_agent_chat_realtime_falls_back_to_local_memory_without_graphiti_or_zep(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "simulation.db"), zep_api_key=None, zep_cloud=None)
    service = MemoryService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda simulation_id: [
            {
                "agent_id": "agent-0003",
                "persona": {"planning_area": "Woodlands", "occupation": "Driver"},
                "opinion_pre": 7,
                "opinion_post": 4,
            }
        ],
    )
    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda simulation_id: [
            {
                "id": 51,
                "round_no": 2,
                "actor_agent_id": "agent-0003",
                "target_agent_id": "agent-0001",
                "action_type": "comment_created",
                "content": "Fare increases make this policy harder to support.",
                "delta": -0.7,
            }
        ],
    )
    monkeypatch.setattr(service.llm, "is_enabled", lambda: True)
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda prompt, system_prompt=None: captured.update({"prompt": prompt, "system_prompt": system_prompt})
        or "My view shifted because transport affordability worsened in my area.",
    )

    payload = service.agent_chat_realtime("session-a", "agent-0003", "Why did your view change?")

    assert payload["agent_id"] == "agent-0003"
    assert payload["memory_used"] is True
    assert payload["zep_context_used"] is False
    assert payload["graphiti_context_used"] is False
    assert "You are persona agent agent-0003 from McKAInsey simulation session-a." in captured["prompt"]
    assert "Persona profile: {'planning_area': 'Woodlands', 'occupation': 'Driver'}" in captured["prompt"]
    assert "User question: Why did your view change?" in captured["prompt"]
    assert captured["system_prompt"] == "You are a simulated Singapore persona agent. Stay grounded in supplied memory."


def test_search_simulation_context_live_mode_errors_without_graph_backends(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "simulation.db"), zep_api_key=None, zep_cloud=None)
    service = MemoryService(settings)

    try:
        service.search_simulation_context("session-a", "transport costs", limit=2, live_mode=True)
    except RuntimeError as exc:
        assert "live" in str(exc).lower()
    else:
        raise AssertionError("Live memory search should not fall back to local context")


def test_agent_chat_realtime_live_mode_requires_llm(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "simulation.db"), zep_api_key=None, zep_cloud=None)
    service = MemoryService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda simulation_id: [
            {
                "agent_id": "agent-0003",
                "persona": {"planning_area": "Woodlands", "occupation": "Driver"},
                "opinion_pre": 7,
                "opinion_post": 4,
            }
        ],
    )
    monkeypatch.setattr(service.llm, "is_enabled", lambda: False)

    try:
        service.agent_chat_realtime("session-a", "agent-0003", "Why did your view change?", live_mode=True)
    except RuntimeError as exc:
        assert "live" in str(exc).lower()
    else:
        raise AssertionError("Live agent chat should not use the local fallback response")
