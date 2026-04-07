import io
from pathlib import Path
import zipfile

from mckainsey.config import Settings
from mckainsey.services.report_service import ReportService


def test_generate_structured_report_returns_fixed_schema(tmp_path, monkeypatch):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="google",
    )
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

    payload = service.generate_structured_report("session-1", use_case="policy-review")

    assert payload["status"] == "completed"
    assert payload["executive_summary"] == "Support strengthened after peer discussion."
    assert payload["insight_cards"][0]["title"] == "Support concentrated in Woodlands"
    assert payload["demographic_breakdown"][0]["segment"] == "Woodlands youth"
    assert payload["recommendations"][0]["priority"] == "high"


def test_generate_structured_report_uses_use_case_prompt_material(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "policy-review.yaml",
        """
name: "Policy Review"
code: "policy-review"
description: "Policy reviews"
guiding_prompt: |
  Focus on approval, disapproval, and concrete reasons for each stance.
agent_personality_modifiers: []
checkpoint_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    display_label: "Approval Rate"
report_sections:
  - title: "Overall Approval"
    prompt: "Summarize the approval trend over time."
  - title: "Recommendations"
    prompt: "Provide actionable recommendations for policy owners."
""".strip(),
    )
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_prompts_dir=str(prompts_dir),
        llm_provider="google",
    )
    service = ReportService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda simulation_id: [{"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 0.45, "opinion_post": 0.72}],
    )
    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda simulation_id: [{"id": 1, "round_no": 1, "actor_agent_id": "agent-0001", "target_agent_id": None, "action_type": "create_post", "content": "Targeted subsidies are still worth it.", "delta": 0.2}],
    )
    monkeypatch.setattr(service.store, "get_cached_report", lambda simulation_id: None)
    monkeypatch.setattr(service.store, "cache_report", lambda simulation_id, report: None)
    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda session_id: {"summary": "Sports voucher policy."})
    monkeypatch.setattr(service.store, "get_population_artifact", lambda session_id: {"sampled_personas": [{"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}}]})
    monkeypatch.setattr(service.store, "list_simulation_events", lambda simulation_id, limit=None: [{"event_type": "post_created", "actor_agent_id": "agent-0001"}])
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [{"agent_id": "agent-0001", "checkpoint_kind": "baseline", "stance_class": "approve", "stance_score": 0.72, "primary_driver": "affordability"}])
    monkeypatch.setattr(service.memory, "search_simulation_context", lambda simulation_id, query, limit=6: {"episodes": [], "zep_context_used": False})

    captured: dict[str, str] = {}

    def fake_complete_required(prompt, system_prompt=None):
        captured["prompt"] = prompt
        return (
            '{"generated_at":"2026-03-21T08:00:00Z","executive_summary":"Support strengthened after peer discussion.",'
            '"insight_cards":[{"title":"Support concentrated in Woodlands","summary":"Approval rose after targeted cost framing.","severity":"high"}],'
            '"support_themes":[{"theme":"access","summary":"Agents support cheaper participation.","evidence":["Targeted subsidies are still worth it."]}],'
            '"dissent_themes":[{"theme":"equity","summary":"Some worry rollout may miss quieter cohorts.","evidence":["Need broader access."]}],'
            '"demographic_breakdown":[{"segment":"Woodlands youth","approval_rate":0.72,"dissent_rate":0.18,"sample_size":1}],'
            '"influential_content":[{"content_type":"post","author_agent_id":"agent-0001","summary":"Targeted rollout drove approval.","engagement_score":3}],'
            '"recommendations":[{"title":"Lead with targeted affordability messaging","rationale":"This was the strongest support driver.","priority":"high"}],'
            '"risks":[{"title":"Overfocus on active users","summary":"Less vocal cohorts may still feel excluded.","severity":"medium"}]}'
        )

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    payload = service.generate_structured_report("session-1", use_case="policy-review")

    assert "Focus on approval, disapproval, and concrete reasons for each stance." in captured["prompt"]
    assert "Overall Approval" in captured["prompt"]
    assert "Provide actionable recommendations for policy owners." in captured["prompt"]
    assert payload["executive_summary"] == "Support strengthened after peer discussion."


def test_generate_structured_report_enriches_sparse_model_output(tmp_path, monkeypatch):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="google",
    )
    service = ReportService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda simulation_id: [
            {"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 0.45, "opinion_post": 0.72},
            {"agent_id": "agent-0002", "persona": {"planning_area": "Yishun"}, "opinion_pre": 0.52, "opinion_post": 0.31},
        ],
    )
    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda simulation_id: [
            {"id": 1, "round_no": 2, "actor_agent_id": "agent-0001", "target_agent_id": None, "action_type": "create_post", "content": "Targeted aid is still worthwhile.", "delta": 0.4},
            {"id": 2, "round_no": 3, "actor_agent_id": "agent-0002", "target_agent_id": None, "action_type": "create_post", "content": "The rent pressure is too high for this to work.", "delta": -0.6},
        ],
    )
    monkeypatch.setattr(service.store, "get_cached_report", lambda simulation_id: None)
    monkeypatch.setattr(service.store, "cache_report", lambda simulation_id, report: None)
    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda session_id: {"summary": "Sports voucher policy."})
    monkeypatch.setattr(service.store, "get_population_artifact", lambda session_id: {"sampled_personas": []})
    monkeypatch.setattr(service.store, "list_simulation_events", lambda simulation_id, limit=None: [{"event_type": "post_created", "actor_agent_id": "agent-0001"}])
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [])
    monkeypatch.setattr(service.memory, "search_simulation_context", lambda simulation_id, query, limit=6: {"episodes": [], "zep_context_used": False})
    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda prompt, system_prompt=None: '{"generated_at":"2026-03-21T08:00:00Z","executive_summary":"Sparse summary.","insight_cards":[],"support_themes":[],"dissent_themes":[],"demographic_breakdown":[],"influential_content":[],"recommendations":[],"risks":[]}',
    )

    payload = service.generate_structured_report("session-1")

    assert payload["insight_cards"], "expected deterministic insight cards to be synthesized"
    assert payload["support_themes"], "expected support themes to be synthesized"
    assert payload["dissent_themes"], "expected dissent themes to be synthesized"
    assert payload["influential_content"], "expected influential content to be synthesized"
    assert payload["recommendations"], "expected recommendations to be synthesized"
    assert payload["risks"], "expected risks to be synthesized"
    assert any("Woodlands" in str(item.get("summary", "")) for item in payload["insight_cards"])


def test_generate_structured_report_falls_back_on_invalid_llm_output(tmp_path, monkeypatch):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="google",
    )
    service = ReportService(settings)

    monkeypatch.setattr(service.store, "get_agents", lambda simulation_id: [{"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 0.45, "opinion_post": 0.72}])
    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda simulation_id: [
            {
                "id": 1,
                "round_no": 1,
                "actor_agent_id": "agent-0001",
                "target_agent_id": None,
                "action_type": "create_post",
                "content": "Targeted aid should remain part of the rollout.",
                "delta": 0.2,
            }
        ],
    )
    monkeypatch.setattr(service.store, "get_cached_report", lambda simulation_id: None)
    monkeypatch.setattr(service.store, "cache_report", lambda simulation_id, report: None)
    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda session_id: {"summary": "Sports voucher policy."})
    monkeypatch.setattr(service.store, "get_population_artifact", lambda session_id: {"sampled_personas": []})
    monkeypatch.setattr(service.store, "list_simulation_events", lambda simulation_id, limit=None: [])
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [])
    monkeypatch.setattr(service.llm, "complete_required", lambda prompt, system_prompt=None: "not json")

    payload = service.generate_structured_report("session-1")

    assert payload["status"] == "completed"
    assert payload["executive_summary"]
    assert payload["insight_cards"], "expected fallback insight cards from real simulation evidence"
    assert payload["support_themes"], "expected fallback support themes from real simulation evidence"
    assert payload["recommendations"], "expected fallback recommendations from real simulation evidence"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_v2_report_maps_sections_to_guiding_questions(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "policy-review.yaml",
        """
name: "Policy Review"
code: "policy-review"
description: "Policy reviews"
guiding_prompt: "Use policy lens."
agent_personality_modifiers: []
checkpoint_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    display_label: "Approval Rate"
  - question: "What is your overall sentiment? Rate 1-10."
    type: "scale"
    metric_name: "net_sentiment"
    display_label: "Net Sentiment"
report_sections: []
""".strip(),
    )
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_prompts_dir=str(prompts_dir),
    )
    service = ReportService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda simulation_id: [
            {"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 8, "opinion_post": 5},
            {"agent_id": "agent-0002", "persona": {"planning_area": "Yishun"}, "opinion_pre": 7, "opinion_post": 4},
        ],
    )
    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda simulation_id: [
            {
                "id": 10,
                "round_no": 3,
                "actor_agent_id": "agent-0002",
                "target_agent_id": "agent-0001",
                "action_type": "comment_created",
                "type": "comment",
                "content": "Rent and food inflation wiped out the policy benefit.",
                "likes": 21,
                "dislikes": 2,
                "delta": -0.8,
            }
        ],
    )
    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda prompt, system_prompt=None: "Narrative answer grounded in evidence.",
    )

    payload = service.build_v2_report("session-1", use_case="policy-review")

    questions = [section["question"] for section in payload["sections"]]
    assert questions == [
        "Do you approve of this policy? Rate 1-10.",
        "What is your overall sentiment? Rate 1-10.",
    ]
    assert payload["sections"][0]["answer"] == "Narrative answer grounded in evidence."


def test_export_v2_report_docx_generates_valid_docx_with_sections(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ReportService(settings)

    monkeypatch.setattr(
        service,
        "build_v2_report",
        lambda simulation_id, use_case=None: {
            "session_id": simulation_id,
            "generated_at": "2026-04-06T09:00:00Z",
            "executive_summary": "Sentiment polarized after affordability arguments intensified.",
            "quick_stats": {
                "initial_metric_value": 66.0,
                "final_metric_value": 41.0,
                "metric_label": "Approval Rate",
                "agent_count": 220,
                "round_count": 5,
            },
            "sections": [
                {
                    "question": "Do you approve of this policy? Rate 1-10.",
                    "answer": "Approval dropped over later rounds.",
                    "evidence": [{"agent_id": "agent-0002", "post_id": "post-22", "quote": "Rent pressure rose."}],
                }
            ],
            "supporting_views": ["Some agents still support long-term outcomes."],
            "dissenting_views": ["Household cost pressure dominates dissent."],
            "demographic_breakdown": [{"segment": "Woodlands lower-income", "supporter": 12, "neutral": 4, "dissenter": 19}],
            "key_recommendations": ["Phase safeguards by district."],
            "methodology": {"agents": 220, "rounds": 5, "model": "gemini-2.0-flash", "controversy_boost": 0.4},
        },
    )

    docx_bytes = service.export_v2_report_docx("session-1")

    assert docx_bytes.startswith(b"PK\x03\x04")
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        assert "word/document.xml" in archive.namelist()
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Sentiment polarized after affordability arguments intensified." in document_xml
    assert "Do you approve of this policy? Rate 1-10." in document_xml


def test_build_v2_report_uses_report_sections_when_checkpoint_questions_are_missing(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "policy-review.yaml",
        """
name: "Policy Review"
code: "policy-review"
description: "Policy reviews"
guiding_prompt: "Use policy lens."
agent_personality_modifiers: []
checkpoint_questions: []
report_sections:
  - title: "Approval"
    prompt: "Summarize approval trends."
  - title: "Recommendation"
    prompt: "List concrete actions."
""".strip(),
    )
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_prompts_dir=str(prompts_dir),
    )
    service = ReportService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda simulation_id: [
            {"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 8, "opinion_post": 5},
        ],
    )
    monkeypatch.setattr(service.store, "get_interactions", lambda simulation_id: [])
    monkeypatch.setattr(service.llm, "complete_required", lambda prompt, system_prompt=None: "Narrative answer grounded in evidence.")

    payload = service.build_v2_report("session-1", use_case="policy-review")

    assert [section["question"] for section in payload["sections"]] == [
        "Summarize approval trends.",
        "List concrete actions.",
    ]
