from mckainsey.config import Settings
from mckainsey.services.report_service import ReportService


def test_generate_structured_report_returns_fixed_schema(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ReportService(settings)

    monkeypatch.setattr(service.store, "get_agents", lambda simulation_id: [{"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 0.45, "opinion_post": 0.72}])
    monkeypatch.setattr(service.store, "get_interactions", lambda simulation_id: [{"id": 1, "round_no": 1, "actor_agent_id": "agent-0001", "target_agent_id": None, "action_type": "create_post", "content": "Support if rollout is targeted.", "delta": 0.2}])
    monkeypatch.setattr(service.store, "get_cached_report", lambda simulation_id: None)
    monkeypatch.setattr(service.store, "cache_report", lambda simulation_id, report: None)
    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda session_id: {"summary": "Sports voucher policy."})
    monkeypatch.setattr(service.store, "get_population_artifact", lambda session_id: {"sampled_personas": [{"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}}]})
    monkeypatch.setattr(service.store, "list_simulation_events", lambda simulation_id, limit=None: [{"event_type": "post_created", "actor_agent_id": "agent-0001"}])
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [{"agent_id": "agent-0001", "checkpoint_kind": "baseline", "stance_class": "approve", "stance_score": 0.72, "primary_driver": "affordability"}])
    monkeypatch.setattr(service.memory, "search_simulation_context", lambda simulation_id, query, limit=6: {"episodes": [], "zep_context_used": False})
    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda prompt, system_prompt=None: (
            '{"generated_at":"2026-03-21T08:00:00Z","executive_summary":"Support strengthened after peer discussion.",'
            '"insight_cards":[{"title":"Support concentrated in Woodlands","summary":"Approval rose after targeted cost framing.","severity":"high"}],'
            '"support_themes":[{"theme":"access","summary":"Agents support cheaper participation.","evidence":["Support if rollout is targeted."]}],'
            '"dissent_themes":[{"theme":"equity","summary":"Some worry rollout may miss quieter cohorts.","evidence":["Need broader access."]}],'
            '"demographic_breakdown":[{"segment":"Woodlands youth","approval_rate":0.72,"dissent_rate":0.18,"sample_size":1}],'
            '"influential_content":[{"content_type":"post","author_agent_id":"agent-0001","summary":"Targeted rollout drove approval.","engagement_score":3}],'
            '"recommendations":[{"title":"Lead with targeted affordability messaging","rationale":"This was the strongest support driver.","priority":"high"}],'
            '"risks":[{"title":"Overfocus on active users","summary":"Less vocal cohorts may still feel excluded.","severity":"medium"}]}'
        ),
    )

    payload = service.generate_structured_report("session-1")

    assert payload["status"] == "completed"
    assert payload["executive_summary"] == "Support strengthened after peer discussion."
    assert payload["insight_cards"][0]["title"] == "Support concentrated in Woodlands"
    assert payload["demographic_breakdown"][0]["segment"] == "Woodlands youth"
    assert payload["recommendations"][0]["priority"] == "high"


def test_generate_structured_report_raises_on_invalid_llm_output(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ReportService(settings)

    monkeypatch.setattr(service.store, "get_agents", lambda simulation_id: [{"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 0.45, "opinion_post": 0.72}])
    monkeypatch.setattr(service.store, "get_interactions", lambda simulation_id: [])
    monkeypatch.setattr(service.store, "get_cached_report", lambda simulation_id: None)
    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda session_id: {"summary": "Sports voucher policy."})
    monkeypatch.setattr(service.store, "get_population_artifact", lambda session_id: {"sampled_personas": []})
    monkeypatch.setattr(service.store, "list_simulation_events", lambda simulation_id, limit=None: [])
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [])
    monkeypatch.setattr(service.llm, "complete_required", lambda prompt, system_prompt=None: "not json")

    try:
        service.generate_structured_report("session-1")
    except RuntimeError as exc:
        assert "valid structured report JSON" in str(exc)
    else:
        raise AssertionError("Expected invalid structured report output to raise RuntimeError")
