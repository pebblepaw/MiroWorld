from __future__ import annotations

from pathlib import Path

from miroworld.config import Settings
from miroworld.services.memory_service import MemoryService
from miroworld.services.report_service import ReportService
from miroworld.services.storage import SimulationStore


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def _seed_memory_store(store: SimulationStore) -> str:
    session_id = "sim-001"
    store.upsert_simulation(session_id, "Policy summary", rounds=4, agent_count=2)
    store.replace_agents(
        session_id,
        [
            {
                "agent_id": "agent-a",
                "persona": {"name": "Agent A", "planning_area": "Central"},
                "opinion_pre": 4.0,
                "opinion_post": 6.0,
            },
            {
                "agent_id": "agent-b",
                "persona": {"name": "Agent B", "planning_area": "North"},
                "opinion_pre": 5.0,
                "opinion_post": 7.0,
            },
        ],
    )
    store.replace_interactions(
        session_id,
        [
            {
                "round_no": 1,
                "actor_agent_id": "agent-a",
                "target_agent_id": "agent-b",
                "action_type": "comment",
                "content": "Public transport access is the main issue for this proposal.",
                "delta": 0.4,
            },
            {
                "round_no": 2,
                "actor_agent_id": "agent-b",
                "target_agent_id": "agent-a",
                "action_type": "reply",
                "content": "Housing affordability will matter more than speed.",
                "delta": -0.2,
            },
        ],
    )
    store.append_interaction_transcript(
        session_id,
        "group_chat",
        "user",
        "We should keep the transport discussion focused on affordability.",
    )
    store.append_interaction_transcript(
        session_id,
        "group_chat",
        "assistant",
        "Transport remains the priority from my perspective.",
        agent_id="agent-a",
    )
    store.replace_checkpoint_records(
        session_id,
        "baseline",
        [
            {
                "agent_id": "agent-a",
                "checkpoint_kind": "baseline",
                "stance_score": 0.3,
                "stance_class": "dissent",
                "confidence": 0.8,
                "primary_driver": "transport bottlenecks",
                "metric_answers": {"approval": 4},
            }
        ],
    )
    store.replace_checkpoint_records(
        session_id,
        "final",
        [
            {
                "agent_id": "agent-a",
                "checkpoint_kind": "final",
                "stance_score": 0.7,
                "stance_class": "support",
                "confidence": 0.9,
                "primary_driver": "affordability safeguards",
                "metric_answers": {"approval": 6},
            }
        ],
    )
    return session_id


def test_search_simulation_context_returns_activity_and_checkpoint_sections(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    service = MemoryService(settings)
    result = service.search_simulation_context(session_id, "transport affordability", limit=6)

    assert result["memory_backend"] == "sqlite"
    assert result["zep_context_used"] is False
    assert result["graphiti_context_used"] is False
    assert [episode["source_kind"] for episode in result["episodes"]] == [
        "transcript",
        "interaction",
        "transcript",
        "interaction",
    ]
    assert all("checkpoint_kind" not in episode for episode in result["episodes"])

    checkpoint_kinds = [item["checkpoint_kind"] for item in result["checkpoint_records"]]
    assert checkpoint_kinds == ["final", "baseline"]
    assert all(item["source_kind"] == "checkpoint" for item in result["checkpoint_records"])


def test_search_simulation_context_splits_punctuation_for_fts_queries(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    service = MemoryService(settings)
    result = service.search_simulation_context(session_id, "transport-affordability", limit=4)

    assert result["memory_backend"] == "sqlite"
    assert result["episodes"][0]["source_kind"] == "transcript"
    assert "transport discussion focused on affordability" in result["episodes"][0]["content"]


def test_search_agent_context_is_scoped_to_agent_activity(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    service = MemoryService(settings)
    result = service.search_agent_context(session_id, "agent-a", "transport affordability", limit=6, live_mode=True)

    assert result["memory_backend"] == "sqlite"
    assert [episode["source_kind"] for episode in result["episodes"]] == [
        "interaction",
        "transcript",
        "interaction",
    ]
    assert all(
        str(episode.get("agent_id") or "") == "agent-a"
        or str(episode.get("actor_agent_id") or "") == "agent-a"
        or str(episode.get("target_agent_id") or "") == "agent-a"
        for episode in result["episodes"]
    )
    assert [item["checkpoint_kind"] for item in result["checkpoint_records"]] == ["final", "baseline"]


def test_search_simulation_context_falls_back_to_local_when_zep_lookup_fails(tmp_path: Path) -> None:
    settings = Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        app_state_backend="postgres",
        zep_api_key="zep-test-key",
    )
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    service = MemoryService(settings)
    service._search_zep_context = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("rate limited"))  # type: ignore[method-assign]

    result = service.search_simulation_context(session_id, "transport affordability", limit=4)

    assert result["zep_context_used"] is False
    assert result["episodes"]
    assert result["episodes"][0]["source_kind"] == "transcript"


def test_format_checkpoint_records_preserves_baseline_and_final_sections_under_limit(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    service = MemoryService(settings)

    checkpoint_records = [
        {
            "agent_id": f"agent-final-{index}",
            "checkpoint_kind": "final",
            "stance_score": 0.7,
            "stance_class": "support",
            "confidence": 0.9,
            "primary_driver": f"final-driver-{index}",
            "metric_answers": {"approval": 6 + index},
        }
        for index in range(4)
    ]
    checkpoint_records.append(
        {
            "agent_id": "agent-baseline",
            "checkpoint_kind": "baseline",
            "stance_score": 0.2,
            "stance_class": "dissent",
            "confidence": 0.8,
            "primary_driver": "baseline-driver",
            "metric_answers": {"approval": 3},
        }
    )

    formatted = service.format_checkpoint_records(checkpoint_records, limit=4)

    assert "Final:" in formatted
    assert "Baseline:" in formatted
    assert "baseline-driver" in formatted


def test_agent_chat_realtime_uses_sqlite_memory_in_live_mode(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    service = MemoryService(settings)
    service.llm.is_enabled = lambda: True  # type: ignore[method-assign]

    captured: dict[str, str] = {}

    def fake_complete_required(
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        captured["prompt"] = prompt
        return "Live agent answer"

    service.llm.complete_required = fake_complete_required  # type: ignore[method-assign]

    payload = service.agent_chat_realtime(
        session_id,
        "agent-a",
        "What matters most about transport?",
        live_mode=True,
    )

    assert payload["memory_backend"] == "sqlite"
    assert payload["zep_context_used"] is False
    assert payload["graphiti_context_used"] is False
    assert "## Your Checkpoint Responses" in captured["prompt"]
    assert "## Your Social Media Activity (Most Recent First)" in captured["prompt"]
    assert "## Key Discussions You Participated In (sqlite)" in captured["prompt"]
    assert "Baseline:" in captured["prompt"]
    assert "Final:" in captured["prompt"]
    assert "transport bottlenecks" in captured["prompt"]


def test_agent_chat_fallback_uses_checkpoint_evidence_when_llm_is_disabled(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    service = MemoryService(settings)
    service.llm.is_enabled = lambda: False  # type: ignore[method-assign]

    payload = service.agent_chat_realtime(
        session_id,
        "agent-a",
        "What matters most about transport?",
        live_mode=True,
    )

    assert payload["memory_backend"] == "sqlite"
    assert "transport bottlenecks" in payload["response"] or "affordability safeguards" in payload["response"]
    assert "approval=" in payload["response"]


def test_report_chat_payload_uses_neutral_memory_label_and_checkpoint_context(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    service = ReportService(settings)
    service.llm.complete = lambda *args, **kwargs: "Executive summary"  # type: ignore[method-assign]

    captured: dict[str, str] = {}

    def fake_complete_required(
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        if prompt.startswith("Generate 5 concrete policy communication/mitigation recommendations in JSON."):
            return (
                "[{"
                '"title": "Improve transport messaging", '
                '"rationale": "Transport is the main concern in the local evidence.", '
                '"target_demographic": "All cohorts", '
                '"expected_impact": "Medium", '
                '"execution_plan": ["Clarify transport mitigations", "Share affordability offsets", "Track sentiment shifts"], '
                '"confidence": 0.74'
                "}]"
            )
        captured["prompt"] = prompt
        return "Report answer"

    service.llm.complete_required = fake_complete_required  # type: ignore[method-assign]

    payload = service.report_chat_payload(session_id, "What is the main concern?")

    assert payload["zep_context_used"] is False
    assert payload["memory_backend"] == "sqlite"
    assert "Relevant Zep Cloud memory search results" not in captured["prompt"]
    assert "Relevant memory search results" in captured["prompt"]
    assert "Checkpoint evidence" in captured["prompt"]
    assert "transport bottlenecks" in captured["prompt"]


def test_memory_sync_is_sqlite_noop(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    store = SimulationStore(settings.simulation_db_path)
    session_id = _seed_memory_store(store)

    payload = MemoryService(settings).sync_simulation(session_id)

    assert payload["zep_enabled"] is False
    assert payload["external_sync_enabled"] is False
    assert payload["memory_backend"] == "sqlite"
    assert payload["synced_events"] == 0
