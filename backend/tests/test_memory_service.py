from mckainsey.config import Settings
from mckainsey.services.memory_service import MemoryService


def test_search_agent_context_falls_back_until_zep_returns_hits(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "simulation.db"))
    service = MemoryService(settings)

    queries: list[str] = []

    def fake_search(simulation_id: str, query: str, limit: int = 8):
        queries.append(query)
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
