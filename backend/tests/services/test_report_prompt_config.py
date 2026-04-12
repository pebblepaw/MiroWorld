from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.report_service import ReportService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        llm_provider="google",
        llm_model="gemini-2.5-flash-lite",
    )


def test_answer_guiding_question_requests_detailed_evidence_rich_output(monkeypatch, tmp_path: Path) -> None:
    service = ReportService(_make_settings(tmp_path))
    captured: dict[str, str] = {}
    report_prompt_cfg = service.config.get_system_prompt_config("report_agent")
    defaults = (report_prompt_cfg.get("defaults") or {}) if isinstance(report_prompt_cfg, dict) else {}
    min_words = int(defaults.get("min_words_per_question") or 300)
    max_words = int(defaults.get("max_words_per_question") or 500)

    monkeypatch.setattr(
        service.store,
        "get_knowledge_artifact",
        lambda _simulation_id: {"summary": "Housing policy summary"},
    )

    def fake_complete_required(prompt: str, system_prompt: str) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        return "Agents expressed sustained concern about affordability and rollout clarity."

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

    assert response.startswith("Agents expressed")
    assert f"{min_words}-{max_words} words of detailed, evidence-rich analysis" in captured["prompt"]
    assert len(captured["prompt"]) > 10000
