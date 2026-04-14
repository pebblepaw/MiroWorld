from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.report_service import ReportService
from miroworld.services.storage import SimulationStore


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        llm_provider="google",
        llm_model="gemini-2.5-flash-lite",
    )


def _seed_report_inputs(store: SimulationStore) -> str:
    session_id = "session-report"
    store.upsert_simulation(session_id, "Housing policy summary", rounds=5, agent_count=2)
    store.replace_agents(
        session_id,
        [
            {
                "agent_id": "agent-0001",
                "persona": {"name": "Alex Tan", "planning_area": "Bishan"},
                "opinion_pre": 4.0,
                "opinion_post": 7.0,
            },
            {
                "agent_id": "agent-0002",
                "persona": {"name": "Priya Nair", "planning_area": "Jurong West"},
                "opinion_pre": 6.0,
                "opinion_post": 8.0,
            },
        ],
    )
    store.replace_interactions(
        session_id,
        [
            {
                "round_no": 1,
                "actor_agent_id": "agent-0001",
                "target_agent_id": "agent-0002",
                "action_type": "create_post",
                "content": "Housing affordability is the main concern for working families.",
                "delta": -0.2,
            },
            {
                "round_no": 2,
                "actor_agent_id": "agent-0002",
                "target_agent_id": "agent-0001",
                "action_type": "comment",
                "content": "Clearer safeguards made the proposal feel more practical by the final round.",
                "delta": 0.4,
            },
        ],
    )
    store.replace_checkpoint_records(
        session_id,
        "baseline",
        [
            {
                "agent_id": "agent-0001",
                "checkpoint_kind": "baseline",
                "metric_answers": {"approval_rate": 4, "net_sentiment": 4},
            },
            {
                "agent_id": "agent-0002",
                "checkpoint_kind": "baseline",
                "metric_answers": {"approval_rate": 6, "net_sentiment": 6},
            },
        ],
    )
    store.replace_checkpoint_records(
        session_id,
        "final",
        [
            {
                "agent_id": "agent-0001",
                "checkpoint_kind": "final",
                "metric_answers": {"approval_rate": 7, "net_sentiment": 7},
            },
            {
                "agent_id": "agent-0002",
                "checkpoint_kind": "final",
                "metric_answers": {"approval_rate": 8, "net_sentiment": 8},
            },
        ],
    )
    return session_id


def test_answer_guiding_question_requests_structured_bullet_json(monkeypatch, tmp_path: Path) -> None:
    service = ReportService(_make_settings(tmp_path))
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        service.store,
        "get_knowledge_artifact",
        lambda _simulation_id: {"summary": "Housing policy summary"},
    )

    def fake_complete_required(prompt: str, system_prompt: str) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        return '{"bullets": ["Affordability remained the main concern across early rounds.", "Safeguards improved confidence by the final checkpoint."]}'

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    interactions = [{"content": "A" * 30000, "round_no": 1, "actor_agent_id": "agent-0001"}]
    agents = [{"agent_id": "agent-0001", "persona": {"planning_area": "Bishan"}}]

    response = service._answer_guiding_question(
        "session-report",
        "What is the main concern?",
        agents,
        interactions,
        use_case="public-policy-testing",
    )

    assert response == [
        "Affordability remained the main concern across early rounds.",
        "Safeguards improved confidence by the final checkpoint.",
    ]
    assert '"bullets"' in captured["prompt"]
    assert "Example output" in captured["prompt"]
    assert "Return valid JSON only" in captured["system_prompt"]


def test_build_v2_report_repairs_invalid_section_json_and_keeps_bullets(monkeypatch, tmp_path: Path) -> None:
    service = ReportService(_make_settings(tmp_path))
    session_id = _seed_report_inputs(service.store)
    prompts: list[str] = []
    responses = iter(
        [
            "not valid json",
            '{"bullets": ["Affordability pressure dominated the early discussion.", "Named safeguards improved support in later rounds."]}',
            '{"bullets": ["Lead with safeguards in public messaging.", "Address affordability explicitly in rollout FAQs."]}',
            "Approval strengthened once safeguards became more concrete.",
        ]
    )

    monkeypatch.setattr(
        service,
        "_resolve_analysis_questions",
        lambda **_: [
            {
                "question": "How strongly do you support this policy? Rate 1-10.",
                "type": "scale",
                "metric_name": "approval_rate",
                "metric_label": "Approval Rate",
                "metric_unit": "%",
                "threshold": 7,
                "report_title": "Policy Approval",
            }
        ],
    )
    monkeypatch.setattr(service, "_resolve_insight_blocks", lambda _use_case: [])
    monkeypatch.setattr(
        service,
        "_resolve_preset_sections",
        lambda _use_case: [
            {
                "title": "Recommendations",
                "prompt": "What should policymakers do next?",
            }
        ],
    )

    def fake_complete_required(prompt: str, system_prompt: str) -> str:
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    report = service.build_v2_report(session_id, use_case="public-policy-testing")

    assert report["sections"][0]["bullets"] == [
        "Affordability pressure dominated the early discussion.",
        "Named safeguards improved support in later rounds.",
    ]
    assert report["preset_sections"][0]["bullets"] == [
        "Lead with safeguards in public messaging.",
        "Address affordability explicitly in rollout FAQs.",
    ]
    assert any("Original invalid output" in prompt for prompt in prompts)
