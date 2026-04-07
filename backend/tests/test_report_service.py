import io
from pathlib import Path
import zipfile

from mckainsey.config import Settings
from mckainsey.services.report_service import ReportService
from mckainsey.services.console_service import ConsoleService


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


def test_build_v2_report_prefers_session_scoped_analysis_questions(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "public-policy-testing.yaml",
        """
name: "Public Policy Testing"
code: "public-policy-testing"
description: "Policy testing"
analysis_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    report_title: "Policy Approval"
  - question: "What specific aspects of this policy do you support or oppose, and why?"
    type: "open-ended"
    metric_name: "policy_viewpoints"
    report_title: "Key Viewpoints"
preset_sections: []
insight_blocks: []
""".strip(),
    )
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_prompts_dir=str(prompts_dir),
    )
    service = ReportService(settings)
    console_service = ConsoleService(settings)
    console_service._upsert_session_config(
        "session-1",
        {
            "use_case": "public-policy-testing",
            "analysis_questions": [
                {
                    "question": "Do you approve of this policy? Rate 1-10.",
                    "type": "scale",
                    "metric_name": "approval_rate",
                    "report_title": "Policy Approval",
                },
                {
                    "question": "What specific aspects of this policy do you support or oppose, and why?",
                    "type": "open-ended",
                    "metric_name": "policy_viewpoints",
                    "report_title": "Key Viewpoints",
                },
                {
                    "question": "How clear and practical are the eligibility rules, payout timing, and spending rules for the $500 Child LifeSG Credits? Rate 1-10.",
                    "type": "scale",
                    "metric_name": "child_life_sg_credits_clarity_practicality",
                    "report_title": "Child LifeSG Credits Clarity and Practicality",
                },
            ],
        },
    )

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda simulation_id: [
            {"agent_id": "agent-0001", "persona": {"planning_area": "Ang Mo Kio"}, "opinion_pre": 7, "opinion_post": 6},
        ],
    )
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
                "content": "Families need clearer rules on eligibility, payout timing, and how the credits can be spent.",
                "delta": -0.1,
            }
        ],
    )
    monkeypatch.setattr(service.store, "get_simulation", lambda simulation_id: {"rounds": 3})
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [])
    monkeypatch.setattr(service, "_answer_guiding_question", lambda simulation_id, question, agents, interactions: f"Answer for {question}")

    payload = service.build_v2_report("session-1", use_case="public-policy-testing")

    assert [section["question"] for section in payload["sections"]] == [
        "Do you approve of this policy? Rate 1-10.",
        "What specific aspects of this policy do you support or oppose, and why?",
        "How clear and practical are the eligibility rules, payout timing, and spending rules for the $500 Child LifeSG Credits? Rate 1-10.",
    ]
    assert payload["sections"][2]["report_title"] == "Child LifeSG Credits Clarity and Practicality"


def test_build_v2_report_enriches_evidence_with_agent_names_and_strips_markdown(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "public-policy-testing.yaml",
        """
name: "Public Policy Testing"
code: "public-policy-testing"
analysis_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    metric_label: "Approval Rate"
    report_title: "Policy Approval"
  - question: "What specific aspects of this policy do you support or oppose, and why?"
    type: "open-ended"
    metric_name: "policy_viewpoints"
    report_title: "Key Viewpoints"
preset_sections: []
insight_blocks: []
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
            {
                "agent_id": "agent-0001",
                "name": "Agent One",
                "persona": {"planning_area": "Ang Mo Kio"},
                "opinion_pre": 7,
                "opinion_post": 6,
            }
        ],
    )
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
                "content": "Families need clearer rules on eligibility and payout timing.",
                "delta": -0.1,
            }
        ],
    )
    monkeypatch.setattr(service.store, "get_simulation", lambda simulation_id: {"rounds": 3})
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [])
    monkeypatch.setattr(
        service.store,
        "get_knowledge_artifact",
        lambda session_id: {"summary": "Sports voucher policy.", "document": {"source_path": "/tmp/policy.pdf", "text_length": 1234}},
    )
    monkeypatch.setattr(service, "_answer_guiding_question", lambda simulation_id, question, agents, interactions: "**Bold narrative** with markdown markers.")

    payload = service.build_v2_report("session-1", use_case="public-policy-testing")

    assert [section["question"] for section in payload["sections"]] == [
        "Do you approve of this policy? Rate 1-10.",
        "What specific aspects of this policy do you support or oppose, and why?",
    ]
    assert payload["sections"][0]["evidence"][0]["agent_name"] == "Agent One"
    assert "**" not in payload["sections"][0]["answer"]


def test_build_v2_report_formats_yes_no_metrics_as_percentages_with_delta_display(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "public-policy-testing.yaml",
        """
name: "Public Policy Testing"
code: "public-policy-testing"
analysis_questions:
  - question: "Would you support this policy? (yes/no)"
    type: "yes-no"
    metric_name: "policy_support"
    metric_label: "Policy Support"
    metric_unit: "Text"
    report_title: "Policy Support"
preset_sections: []
insight_blocks: []
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
            {"agent_id": "agent-0001", "persona": {"planning_area": "Ang Mo Kio"}, "opinion_pre": 7, "opinion_post": 8},
            {"agent_id": "agent-0002", "persona": {"planning_area": "Yishun"}, "opinion_pre": 6, "opinion_post": 7},
        ],
    )
    monkeypatch.setattr(service.store, "get_interactions", lambda simulation_id: [])
    monkeypatch.setattr(service.store, "get_simulation", lambda simulation_id: {"rounds": 3})
    monkeypatch.setattr(
        service.store,
        "list_checkpoint_records",
        lambda simulation_id, checkpoint_kind=None: (
            [
                {"agent_id": "agent-0001", "metric_answers": {"policy_support": "yes"}},
                {"agent_id": "agent-0002", "metric_answers": {"policy_support": "no"}},
            ]
            if checkpoint_kind == "baseline"
            else [
                {"agent_id": "agent-0001", "metric_answers": {"policy_support": "yes"}},
                {"agent_id": "agent-0002", "metric_answers": {"policy_support": "yes"}},
            ]
        ),
    )
    monkeypatch.setattr(service, "_answer_guiding_question", lambda simulation_id, question, agents, interactions: "Narrative answer.")

    payload = service.build_v2_report("session-1", use_case="public-policy-testing")

    metric = payload["metric_deltas"][0]
    assert metric["metric_unit"] == "%"
    assert metric["initial_value"] == 50.0
    assert metric["final_value"] == 100.0
    assert metric["delta_display"] == "50.0% -> 100.0%"


def test_build_v2_report_includes_document_context_in_section_prompts(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "public-policy-testing.yaml",
        """
name: "Public Policy Testing"
code: "public-policy-testing"
analysis_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    metric_label: "Approval Rate"
    report_title: "Policy Approval"
preset_sections: []
insight_blocks: []
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
        lambda simulation_id: [{"agent_id": "agent-0001", "persona": {"planning_area": "Ang Mo Kio"}, "opinion_pre": 7, "opinion_post": 8}],
    )
    monkeypatch.setattr(service.store, "get_interactions", lambda simulation_id: [])
    monkeypatch.setattr(service.store, "get_simulation", lambda simulation_id: {"rounds": 3})
    monkeypatch.setattr(service.store, "list_checkpoint_records", lambda simulation_id, checkpoint_kind=None: [])
    monkeypatch.setattr(
        service.store,
        "get_knowledge_artifact",
        lambda session_id: {
            "summary": "Sports voucher policy for families.",
            "document": {"source_path": "/tmp/policy.pdf", "text_length": 4321},
        },
    )

    captured_prompts: list[str] = []

    def fake_complete_required(prompt, system_prompt=None):
        captured_prompts.append(prompt)
        return "Narrative answer."

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    service.build_v2_report("session-1", use_case="public-policy-testing")

    assert captured_prompts
    assert "Sports voucher policy for families." in captured_prompts[0]
    assert "/tmp/policy.pdf" in captured_prompts[0]


def test_report_chat_payload_includes_document_context(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ReportService(settings)

    monkeypatch.setattr(service, "build_report", lambda simulation_id: {"simulation_id": simulation_id, "executive_summary": "Summary"})
    monkeypatch.setattr(
        service.store,
        "get_knowledge_artifact",
        lambda session_id: {
            "summary": "Sports voucher policy for families.",
            "document": {"source_path": "/tmp/policy.pdf", "text_length": 4321},
        },
    )
    monkeypatch.setattr(service.memory, "search_simulation_context", lambda simulation_id, query, limit=8: {"episodes": [], "zep_context_used": False})

    captured: dict[str, str] = {}

    def fake_complete_required(prompt, system_prompt=None):
        captured["prompt"] = prompt
        return "Chat response."

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    payload = service.report_chat_payload("session-1", "What does the document say?")

    assert payload["response"] == "Chat response."
    assert "Sports voucher policy for families." in captured["prompt"]
    assert "/tmp/policy.pdf" in captured["prompt"]
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
                    "report_title": "Policy Approval",
                    "answer": "Approval dropped over later rounds.",
                    "evidence": [{"agent_id": "agent-0002", "post_id": "post-22", "quote": "Rent pressure rose."}],
                }
            ],
            "insight_blocks": [{"type": "polarization_index", "title": "Polarization Over Time", "description": "How divided views changed.", "data": {"status": "ok"}}],
            "preset_sections": [{"title": "Recommendations", "answer": "Phase safeguards by district."}],
        },
    )

    docx_bytes = service.export_v2_report_docx("session-1")

    assert docx_bytes.startswith(b"PK\x03\x04")
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
        assert "word/document.xml" in archive.namelist()
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "Sentiment polarized after affordability arguments intensified." in document_xml
    assert "Policy Approval" in document_xml
    assert "Recommendations" in document_xml
    assert "Supporting Views" not in document_xml
    assert "Dissenting Views" not in document_xml
    assert "Demographic Breakdown" not in document_xml
    assert "Methodology: Simulated agents=220, rounds=5" in document_xml


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


def test_build_v2_report_metric_deltas_use_checkpoint_metric_answers(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "public-policy-testing.yaml",
        """
name: "Public Policy Testing"
code: "public-policy-testing"
analysis_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    metric_label: "Approval Rate"
    metric_unit: "%"
    threshold: 7
    threshold_direction: "gte"
    report_title: "Policy Approval"
preset_sections: []
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
            {"agent_id": "agent-1", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 8, "opinion_post": 4},
            {"agent_id": "agent-2", "persona": {"planning_area": "Yishun"}, "opinion_pre": 7, "opinion_post": 3},
        ],
    )
    monkeypatch.setattr(service.store, "get_interactions", lambda simulation_id: [])
    monkeypatch.setattr(
        service.store,
        "list_checkpoint_records",
        lambda simulation_id, checkpoint_kind=None: (
            [
                {"agent_id": "agent-1", "metric_answers": {"approval_rate": 8}},
                {"agent_id": "agent-2", "metric_answers": {"approval_rate": 7}},
            ]
            if checkpoint_kind == "baseline"
            else [
                {"agent_id": "agent-1", "metric_answers": {"approval_rate": 4}},
                {"agent_id": "agent-2", "metric_answers": {"approval_rate": 3}},
            ]
        ),
    )
    monkeypatch.setattr(service.llm, "complete_required", lambda prompt, system_prompt=None: "Narrative answer.")

    payload = service.build_v2_report("session-1", use_case="public-policy-testing")

    assert payload["metric_deltas"][0]["initial_value"] == 100.0
    assert payload["metric_deltas"][0]["final_value"] == 0.0
    assert payload["metric_deltas"][0]["delta"] == -100.0


def test_build_v2_report_uses_stored_simulation_rounds_when_interactions_stop_early(tmp_path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    _write(
        prompts_dir / "public-policy-testing.yaml",
        """
name: "Public Policy Testing"
code: "public-policy-testing"
analysis_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    display_label: "Approval Rate"
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
            {"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 9, "opinion_post": 8},
        ],
    )
    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda simulation_id: [
            {
                "id": 1,
                "round_no": 2,
                "actor_agent_id": "agent-0001",
                "target_agent_id": None,
                "action_type": "create_post",
                "content": "Approval stayed strong.",
                "delta": 0.1,
            }
        ],
    )
    monkeypatch.setattr(service.store, "get_simulation", lambda simulation_id: {"simulation_id": simulation_id, "rounds": 5})
    monkeypatch.setattr(service.llm, "complete_required", lambda prompt, system_prompt=None: "Narrative answer grounded in evidence.")

    payload = service.build_v2_report("session-1", use_case="public-policy-testing")

    assert payload["quick_stats"]["round_count"] == 5
