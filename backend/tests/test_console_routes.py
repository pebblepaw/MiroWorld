import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.config import Settings, get_settings
from mckainsey.services.console_service import ConsoleService
from mckainsey.services.demo_service import DemoService
from mckainsey.services.persona_relevance_service import PersonaRelevanceService


client = TestClient(app)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_console_session_creation_and_knowledge_processing(monkeypatch, tmp_path):
    def fake_create_session(self, requested_session_id=None, mode="demo", **_kwargs):
        return {
            "session_id": requested_session_id or "session-test",
            "mode": mode,
            "status": "created",
            "model_provider": "ollama",
            "model_name": "qwen3:4b-instruct-2507-q4_K_M",
            "embed_model_name": "nomic-embed-text",
            "base_url": "http://127.0.0.1:11434/v1/",
            "api_key_configured": True,
            "api_key_masked": "ol...ama",
        }

    async def fake_process_knowledge(
        self,
        session_id,
        *,
        document_text=None,
        source_path=None,
        documents=None,
        guiding_prompt,
        demographic_focus=None,
        use_default_demo_document=False,
    ):
        assert guiding_prompt == "focus on budget tradeoffs and transport"
        return {
            "session_id": session_id,
            "document": {
                "document_id": "doc-1",
                "source_path": source_path,
                "text_length": len(document_text or ""),
            },
            "summary": "Budget support touches transport and seniors.",
            "entity_nodes": [
                {
                    "id": "policy:transport",
                    "label": "Transport Support",
                    "type": "policy",
                    "description": "Support for transport affordability.",
                    "weight": 0.9,
                },
                {
                    "id": "group:seniors",
                    "label": "Seniors",
                    "type": "demographic",
                    "description": "Older residents targeted by support.",
                },
            ],
            "relationship_edges": [
                {
                    "source": "policy:transport",
                    "target": "group:seniors",
                    "type": "targets",
                    "label": "Targets seniors",
                },
            ],
            "entity_type_counts": {"policy": 1, "demographic": 1},
            "processing_logs": ["Parsed document", "Built graph"],
            "demographic_focus_summary": demographic_focus,
            "guiding_prompt": guiding_prompt,
        }

    monkeypatch.setattr(ConsoleService, "create_session", fake_create_session)
    monkeypatch.setattr(ConsoleService, "process_knowledge", fake_process_knowledge)

    created = client.post("/api/v2/console/session", json={"session_id": "session-a", "mode": "demo"})
    assert created.status_code == 200, created.text
    assert created.json()["session_id"] == "session-a"
    assert created.json()["model_provider"] == "ollama"

    knowledge = client.post(
        "/api/v2/console/session/session-a/knowledge/process",
        json={
            "document_text": "Singapore budget support for transport and seniors.",
            "demographic_focus": "seniors in Woodlands",
            "guiding_prompt": "focus on budget tradeoffs and transport",
        },
    )
    assert knowledge.status_code == 200, knowledge.text
    body = knowledge.json()
    assert body["session_id"] == "session-a"
    assert body["entity_type_counts"]["policy"] == 1
    assert body["relationship_edges"][0]["type"] == "targets"
    assert body["entity_nodes"][0]["description"] == "Support for transport affordability."
    assert body["guiding_prompt"] == "focus on budget tradeoffs and transport"


def test_console_population_preview_route(monkeypatch):
    def fake_preview_population(self, session_id, request):
        assert request.sample_mode == "affected_groups"
        assert request.seed == 17
        assert request.sampling_instructions == "Bias toward younger teachers and parents in the north-east"
        return {
            "session_id": session_id,
            "candidate_count": 12,
            "sample_count": 4,
            "sample_mode": "affected_groups",
            "sample_seed": 17,
            "parsed_sampling_instructions": {
                "hard_filters": {"occupation": ["teacher"]},
                "soft_boosts": {"age_cohort": ["youth"], "planning_area": ["Sengkang", "Punggol"]},
                "exclusions": {},
                "distribution_targets": {},
                "notes_for_ui": ["Bias toward younger teachers and parents in the north-east"],
            },
            "coverage": {
                "planning_areas": ["Woodlands", "Yishun"],
                "age_buckets": {"25-34": 2, "35-44": 2},
            },
            "sampled_personas": [
                {
                    "agent_id": "agent-0001",
                    "persona": {"planning_area": "Woodlands", "income_bracket": "$3,000-$5,999", "age": 32},
                    "selection_reason": {
                        "score": 0.78,
                        "matched_facets": ["planning_area:woodlands"],
                        "matched_document_entities": ["transport affordability"],
                        "instruction_matches": ["teacher"],
                        "bm25_terms": ["teacher", "young", "north-east"],
                        "semantic_summary": "Matched education and parent-facing policy concerns.",
                        "semantic_relevance": 0.8,
                        "geographic_relevance": 0.9,
                        "socioeconomic_relevance": 0.7,
                        "digital_behavior_relevance": 0.5,
                        "filter_alignment": 1.0,
                    },
                }
            ],
            "agent_graph": {
                "nodes": [{"id": "agent-0001", "label": "agent-0001", "planning_area": "Woodlands", "node_type": "planning_area_cluster"}],
                "links": [],
            },
            "representativeness": {"status": "balanced"},
            "selection_diagnostics": {
                "shortlist_count": 8,
                "structured_filter_count": 6,
                "bm25_shortlist_count": 4,
                "semantic_rerank_count": 3,
            },
        }

    monkeypatch.setattr(ConsoleService, "preview_population", fake_preview_population)

    response = client.post(
        "/api/v2/console/session/session-a/sampling/preview",
        json={
            "agent_count": 4,
            "planning_areas": ["Woodlands", "Yishun"],
            "sample_mode": "affected_groups",
            "seed": 17,
            "sampling_instructions": "Bias toward younger teachers and parents in the north-east",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["candidate_count"] == 12
    assert body["sample_mode"] == "affected_groups"
    assert body["sample_seed"] == 17
    assert body["parsed_sampling_instructions"]["hard_filters"]["occupation"] == ["teacher"]
    assert body["sampled_personas"][0]["selection_reason"]["score"] == 0.78
    assert body["sampled_personas"][0]["selection_reason"]["bm25_terms"] == ["teacher", "young", "north-east"]
    assert body["selection_diagnostics"]["bm25_shortlist_count"] == 4
    assert body["representativeness"]["status"] == "balanced"


def test_console_population_preview_route_rejects_unknown_fields():
    response = client.post(
        "/api/v2/console/session/session-a/sampling/preview",
        json={
            "agent_count": 4,
            "sample_mode": "affected_groups",
            "income_brackets": ["$3,000-$5,999"],
        },
    )

    assert response.status_code == 422, response.text


def test_console_knowledge_upload_route_parses_pdf(monkeypatch):
    async def fake_process_knowledge(
        self,
        session_id,
        *,
        document_text=None,
        source_path=None,
        documents=None,
        guiding_prompt,
        demographic_focus=None,
        use_default_demo_document=False,
    ):
        assert guiding_prompt == "map policies to transport affordability"
        assert "transport" in (document_text or "").lower()
        assert source_path and source_path.endswith(".pdf")
        return {
            "session_id": session_id,
            "document": {
                "document_id": "doc-upload",
                "source_path": source_path,
                "text_length": len(document_text or ""),
            },
            "summary": "Parsed uploaded PDF.",
            "entity_nodes": [
                {"id": "policy:transport", "label": "Transport", "type": "policy", "weight": 0.8}
            ],
            "relationship_edges": [
                {
                    "source": "policy:transport",
                    "target": "group:seniors",
                    "type": "funds",
                    "label": "Funds transport support for seniors",
                }
            ],
            "entity_type_counts": {},
            "processing_logs": ["Uploaded file parsed"],
            "demographic_focus_summary": demographic_focus,
            "guiding_prompt": guiding_prompt,
        }

    monkeypatch.setattr(ConsoleService, "process_knowledge", fake_process_knowledge)

    sample_pdf = Path(__file__).resolve().parents[2] / "Sample_Inputs" / "fy2026_budget_statement.pdf"
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/v2/console/session/session-a/knowledge/upload",
            data={
                "demographic_focus": "seniors in Woodlands",
                "guiding_prompt": "map policies to transport affordability",
            },
            files={"file": (sample_pdf.name, handle, "application/pdf")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-a"
    assert body["document"]["source_path"].endswith(".pdf")
    assert body["summary"] == "Parsed uploaded PDF."
    assert body["relationship_edges"][0]["label"] == "Funds transport support for seniors"


def test_console_interaction_hub_chat_routes(monkeypatch):
    def fake_report_chat(self, session_id, message):
        assert session_id == "session-a"
        assert "friction" in message.lower()
        return {
            "session_id": session_id,
            "response": "Woodlands shows the highest friction because affordability concerns concentrated there.",
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "gemini_model": "gemini-2.0-flash",
            "zep_context_used": True,
        }

    def fake_agent_chat(self, session_id, agent_id, message):
        assert session_id == "session-a"
        assert agent_id == "agent-001"
        assert "position" in message.lower()
        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "response": "My concerns increased after repeated comments about transport costs and weak household buffers.",
            "memory_used": True,
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "gemini_model": "gemini-2.0-flash",
            "zep_context_used": True,
        }

    monkeypatch.setattr(ConsoleService, "report_chat", fake_report_chat)
    monkeypatch.setattr(ConsoleService, "agent_chat", fake_agent_chat)

    report_response = client.post(
        "/api/v2/console/session/session-a/interaction-hub/report-chat",
        json={"message": "What is the highest friction area?"},
    )
    assert report_response.status_code == 200, report_response.text
    report_body = report_response.json()
    assert report_body["zep_context_used"] is True
    assert report_body["gemini_model"] == "gemini-2.0-flash"
    assert report_body["model_provider"] == "google"

    agent_response = client.post(
        "/api/v2/console/session/session-a/interaction-hub/agent-chat",
        json={"agent_id": "agent-001", "message": "What changed your position?"},
    )
    assert agent_response.status_code == 200, agent_response.text
    agent_body = agent_response.json()
    assert agent_body["memory_used"] is True
    assert agent_body["zep_context_used"] is True
    assert agent_body["agent_id"] == "agent-001"


def test_console_simulation_start_route_returns_extended_live_state(monkeypatch):
    def fake_start_simulation(self, session_id, *, policy_summary, rounds, mode=None, controversy_boost=0.0):
        assert session_id == "session-a"
        assert rounds == 4
        assert mode == "live"
        assert controversy_boost == 0.5
        return {
            "session_id": session_id,
            "status": "running",
            "event_count": 2,
            "last_round": 0,
            "platform": "reddit",
            "planned_rounds": 4,
            "current_round": 0,
            "elapsed_seconds": 5,
            "estimated_total_seconds": 55,
            "estimated_remaining_seconds": 50,
            "counters": {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
            "checkpoint_status": {"baseline": {"status": "running", "completed_agents": 0, "total_agents": 100}},
            "top_threads": [],
            "discussion_momentum": {"approval_delta": 0.0, "dominant_stance": "mixed"},
            "latest_metrics": {},
            "recent_events": [],
        }

    monkeypatch.setattr(ConsoleService, "start_simulation", fake_start_simulation)

    response = client.post(
        "/api/v2/console/session/session-a/simulation/start",
        json={
            "policy_summary": "Sports grants for active youths.",
            "rounds": 4,
            "controversy_boost": 0.5,
            "mode": "live",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["platform"] == "reddit"
    assert body["planned_rounds"] == 4
    assert body["elapsed_seconds"] == 5
    assert body["estimated_remaining_seconds"] == 50
    assert body["checkpoint_status"]["baseline"]["status"] == "running"
    assert body["discussion_momentum"]["dominant_stance"] == "mixed"


def test_console_simulate_route_returns_extended_live_state(monkeypatch):
    def fake_start_simulation(self, session_id, *, policy_summary, rounds, mode=None, controversy_boost=0.0):
        assert session_id == "session-a"
        assert rounds == 4
        assert mode == "live"
        assert controversy_boost == 0.5
        return {
            "session_id": session_id,
            "status": "running",
            "event_count": 2,
            "last_round": 0,
            "platform": "reddit",
            "planned_rounds": 4,
            "current_round": 0,
            "elapsed_seconds": 5,
            "estimated_total_seconds": 55,
            "estimated_remaining_seconds": 50,
            "counters": {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
            "checkpoint_status": {"baseline": {"status": "running", "completed_agents": 0, "total_agents": 100}},
            "top_threads": [],
            "discussion_momentum": {"approval_delta": 0.0, "dominant_stance": "mixed"},
            "latest_metrics": {},
            "recent_events": [],
        }

    monkeypatch.setattr(ConsoleService, "start_simulation", fake_start_simulation)

    response = client.post(
        "/api/v2/console/session/session-a/simulate",
        json={
            "policy_summary": "Sports grants for active youths.",
            "rounds": 4,
            "controversy_boost": 0.5,
            "mode": "live",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["platform"] == "reddit"
    assert body["planned_rounds"] == 4
    assert body["elapsed_seconds"] == 5
    assert body["estimated_remaining_seconds"] == 50
    assert body["checkpoint_status"]["baseline"]["status"] == "running"
    assert body["discussion_momentum"]["dominant_stance"] == "mixed"


def test_console_simulate_route_uses_demo_state_without_policy_summary(monkeypatch):
    from mckainsey.api import routes_console as routes_module

    class FakeDemoService:
        def is_demo_available(self):
            return True

        def get_simulation_state(self, session_id):
            assert session_id == "demo-session-fy2026-budget"
            return {
                "session_id": session_id,
                "status": "completed",
                "event_count": 3,
                "last_round": 1,
                "platform": "reddit",
                "planned_rounds": 3,
                "current_round": 1,
                "elapsed_seconds": 12,
                "estimated_total_seconds": 42,
                "estimated_remaining_seconds": 30,
                "counters": {"posts": 1, "comments": 2, "reactions": 3, "active_authors": 4},
                "checkpoint_status": {"baseline": {"status": "completed", "completed_agents": 3, "total_agents": 3}},
                "top_threads": [],
                "discussion_momentum": {"approval_delta": 0.1, "dominant_stance": "support"},
                "latest_metrics": {},
                "recent_events": [],
            }

    def fail_start_simulation(*_args, **_kwargs):
        raise AssertionError("demo /simulate should not start a live simulation")

    monkeypatch.setattr(routes_module, "_is_demo_session", lambda _session_id, _settings: True)
    monkeypatch.setattr(routes_module, "_get_demo_service", lambda _settings: FakeDemoService())
    monkeypatch.setattr(ConsoleService, "start_simulation", fail_start_simulation)

    response = client.post(
        "/api/v2/console/session/demo-session-fy2026-budget/simulate",
        json={
            "rounds": 3,
            "controversy_boost": 0.5,
            "mode": "demo",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "demo-session-fy2026-budget"
    assert body["status"] == "completed"
    assert body["planned_rounds"] == 3
    assert body["discussion_momentum"]["dominant_stance"] == "support"


def test_console_simulation_metrics_route_returns_current_state(monkeypatch):
    def fake_get_simulation_state(self, session_id):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "status": "running",
            "event_count": 9,
            "last_round": 2,
            "platform": "reddit",
            "planned_rounds": 5,
            "current_round": 2,
            "elapsed_seconds": 31,
            "estimated_total_seconds": 60,
            "estimated_remaining_seconds": 29,
            "counters": {"posts": 3, "comments": 7, "reactions": 12, "active_authors": 4},
            "checkpoint_status": {"baseline": {"status": "completed", "completed_agents": 3, "total_agents": 3}},
            "top_threads": [{"post_id": 1, "title": "Thread title", "engagement": 8}],
            "discussion_momentum": {"approval_delta": 0.14, "dominant_stance": "support"},
            "latest_metrics": {"approval_rate": 73.4, "net_sentiment": 6.8},
            "recent_events": [{"event_type": "metrics_updated"}],
        }

    monkeypatch.setattr(ConsoleService, "get_simulation_state", fake_get_simulation_state)

    response = client.get("/api/v2/console/session/session-a/simulation/metrics")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-a"
    assert body["latest_metrics"]["approval_rate"] == 73.4
    assert body["counters"]["posts"] == 3
    assert body["top_threads"][0]["title"] == "Thread title"


def test_console_service_run_background_records_runtime_tokens(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)
    session_id = "session-token-runtime"

    service.store.upsert_console_session(
        session_id=session_id,
        mode="live",
        status="simulation_running",
        model_provider="ollama",
        model_name="qwen3:4b-instruct-2507-q4_K_M",
        embed_model_name="nomic-embed-text",
        api_key="ollama",
        base_url="http://127.0.0.1:11434/v1/",
    )

    class FakeSimulationService:
        def __init__(self, runtime_settings):
            del runtime_settings

        def build_context_bundles(self, **kwargs):
            del kwargs
            return {"agent-0001": {"agent_id": "agent-0001", "brief": "brief", "matched_context_nodes": []}}

        def run_opinion_checkpoint(self, **kwargs):
            on_token_usage = kwargs.get("on_token_usage")
            if callable(on_token_usage):
                on_token_usage(120, 40, 0)
            return [
                {
                    "agent_id": "agent-0001",
                    "checkpoint_kind": kwargs.get("checkpoint_kind", "baseline"),
                    "stance_score": 0.6,
                    "stance_class": "neutral",
                    "confidence": 0.7,
                    "primary_driver": "affordability",
                    "matched_context_nodes": [],
                }
            ]

        def run_with_personas(self, **kwargs):
            del kwargs
            return {
                "elapsed_seconds": 12,
                "counters": {"posts": 2, "comments": 1, "reactions": 1, "active_authors": 1},
                "token_usage": {"input_tokens": 240, "output_tokens": 80, "cached_tokens": 0},
            }

    monkeypatch.setattr("mckainsey.services.console_service.SimulationService", FakeSimulationService)
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)
    monkeypatch.setattr(service.streams, "ingest_events_incremental", lambda _session_id, _path: 0)

    recorded: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        service,
        "record_runtime_token_usage",
        lambda _session_id, *, input_tokens, output_tokens, cached_tokens=0: recorded.append(
            (input_tokens, output_tokens, cached_tokens)
        ),
    )

    sampled_rows = [
        {
            "agent_id": "agent-0001",
            "persona": {"planning_area": "Woodlands"},
            "selection_reason": {"score": 0.75},
        }
    ]
    personas = [{"agent_id": "agent-0001", "planning_area": "Woodlands"}]
    events_path = tmp_path / "events.ndjson"

    service._run_simulation_background(
        session_id=session_id,
        policy_summary="Policy summary",
        rounds=1,
        sampled_rows=sampled_rows,
        personas=personas,
        events_path=events_path,
        mode="live",
        controversy_boost=0.4,
    )

    assert recorded
    assert any(item[0] == 240 and item[1] == 80 for item in recorded)


def test_console_report_generation_routes(monkeypatch):
    def fake_generate_v2_report(self, session_id):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "generated_at": "2026-04-06T09:00:00Z",
            "executive_summary": "Support strengthened after discussion.",
            "metric_deltas": [],
            "quick_stats": {"agent_count": 120, "round_count": 4, "model": "gemini-2.5-flash-lite", "provider": "google"},
            "sections": [{"question": "Do you approve?", "report_title": "Approval", "type": "scale", "answer": "Mixed response.", "evidence": []}],
            "insight_blocks": [],
            "preset_sections": [{"title": "Recommendations", "answer": "Clarify rollout timeline."}],
        }

    def fake_get_v2_report(self, session_id):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "generated_at": "2026-03-21T09:00:00Z",
            "executive_summary": "Support strengthened after discussion.",
            "metric_deltas": [{"metric_name": "approval_rate", "metric_label": "Approval Rate", "metric_unit": "%", "initial_value": 61.0, "final_value": 73.0, "delta": 12.0, "direction": "up", "report_title": "Approval"}],
            "quick_stats": {"agent_count": 180, "round_count": 5, "model": "gemini-2.5-flash-lite", "provider": "google"},
            "sections": [{"question": "Do you approve?", "report_title": "Approval", "type": "scale", "answer": "Support increased in later rounds.", "evidence": []}],
            "insight_blocks": [{"type": "polarization_index", "title": "Polarization Over Time", "description": "Trend", "data": {"status": "ok"}}],
            "preset_sections": [{"title": "Recommendations", "answer": "Lead with affordability"}],
        }

    monkeypatch.setattr(ConsoleService, "generate_v2_report", fake_generate_v2_report)
    monkeypatch.setattr(ConsoleService, "get_v2_report", fake_get_v2_report)

    generate = client.post("/api/v2/console/session/session-a/report/generate")
    assert generate.status_code == 200, generate.text
    assert generate.json()["quick_stats"]["agent_count"] == 120

    report = client.get("/api/v2/console/session/session-a/report/full")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["executive_summary"] == "Support strengthened after discussion."
    assert body["metric_deltas"][0]["metric_name"] == "approval_rate"
    assert body["insight_blocks"][0]["type"] == "polarization_index"


def test_console_service_caps_stage2_candidate_pool_for_live_preview(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda session_id: {"summary": "Education support", "entity_nodes": [], "relationship_edges": []})
    monkeypatch.setattr(
        PersonaRelevanceService,
        "parse_sampling_instructions",
        lambda self, instructions, knowledge_artifact=None, live_mode=False: {"hard_filters": {}, "soft_boosts": {}, "exclusions": {}, "distribution_targets": {}, "notes_for_ui": [], "source": "test"},
    )

    captured: dict[str, object] = {}

    def fake_query_candidates(**kwargs):
        captured.update(kwargs)
        return [{"planning_area": "Sengkang", "industry": "Education", "age": 28, "occupation": "Teacher"}]

    monkeypatch.setattr(service.sampler, "query_candidates", fake_query_candidates)
    monkeypatch.setattr(
        PersonaRelevanceService,
        "build_population_artifact",
        lambda self, *args, **kwargs: {"session_id": "session-a", "candidate_count": 1, "sample_count": 1, "sample_mode": "affected_groups", "sample_seed": kwargs["seed"], "parsed_sampling_instructions": kwargs["parsed_sampling_instructions"], "coverage": {}, "sampled_personas": [], "agent_graph": {"nodes": [], "links": []}, "representativeness": {"status": "narrow"}, "selection_diagnostics": {}},
    )

    class Req:
        agent_count = 500
        sample_mode = "affected_groups"
        sampling_instructions = "Bias toward younger teachers."
        seed = 17
        min_age = None
        max_age = None
        planning_areas = []
        income_brackets = []

        def model_dump(self):
            return {
                "agent_count": self.agent_count,
                "sample_mode": self.sample_mode,
                "sampling_instructions": self.sampling_instructions,
                "seed": self.seed,
                "min_age": self.min_age,
                "max_age": self.max_age,
                "planning_areas": self.planning_areas,
                "income_brackets": self.income_brackets,
            }

    service.preview_population("session-a", Req())

    assert captured["limit"] == 1000


def test_console_service_process_knowledge_wraps_runtime_errors_with_provider_context(monkeypatch, tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="openai",
        llm_model="gpt-5-mini",
        openai_api_key="test-key",
    )
    service = ConsoleService(settings)

    async def fake_process_document(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG001
        raise RuntimeError("RateLimitError: insufficient_quota")

    monkeypatch.setattr("mckainsey.services.console_service.LightRAGService.process_document", fake_process_document)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            service.process_knowledge(
                "session-a",
                document_text="Policy text for transport affordability.",
            )
        )

    assert exc_info.value.status_code == 502
    detail = str(exc_info.value.detail)
    assert "provider 'openai'" in detail
    assert "model 'gpt-5-mini'" in detail
    assert "insufficient_quota" in detail


def test_console_service_process_knowledge_rejects_retired_google_models_before_extraction(monkeypatch, tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="google",
        llm_model="gemini-2.0-flash-lite",
        llm_api_key="test-key",
        gemini_api_key="test-key",
    )
    service = ConsoleService(settings)
    service.create_session(
        requested_session_id="session-retired-google",
        mode="live",
        model_provider="google",
        model_name="gemini-2.0-flash-lite",
        api_key="test-key",
    )

    async def fail_if_called(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG001
        raise AssertionError("LightRAG extraction should not start for retired Google models")

    monkeypatch.setattr("mckainsey.services.console_service.LightRAGService.process_document", fail_if_called)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            service.process_knowledge(
                "session-retired-google",
                document_text="Policy text for family support and childcare affordability.",
            )
        )

    assert exc_info.value.status_code == 502
    detail = str(exc_info.value.detail)
    assert "provider 'google'" in detail
    assert "model 'gemini-2.0-flash-lite'" in detail
    assert "no longer available" in detail


def test_console_service_summarizes_simulation_runtime_failures_without_run_log_noise(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    raw_error = RuntimeError(
        "Real OASIS simulation failed. "
        "run_log=/tmp/oasis.log tail=Traceback ... ModuleNotFoundError: No module named 'camel'"
    )

    detail = service._summarize_simulation_failure(raw_error)

    assert "run_log=" not in detail
    assert "Traceback" not in detail
    assert "missing required packages" in detail


def test_console_service_get_dynamic_filters_live_mode_errors_when_dataset_missing(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)
    service.store.upsert_console_session(
        session_id="session-live",
        mode="live",
        status="created",
    )

    monkeypatch.setattr(
        "mckainsey.services.console_service.ConfigService.get_country",
        lambda self, country: {"dataset_path": str(tmp_path / "missing.parquet"), "filter_fields": [{"field": "planning_area", "type": "select"}]},
    )
    monkeypatch.setattr(
        service.sampler,
        "infer_filter_schema",
        lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError("dataset missing")),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.get_dynamic_filters("session-live")

    assert exc_info.value.status_code == 502
    assert "dataset path not found" in str(exc_info.value.detail).lower()


def test_console_service_applies_age_range_hard_filters_from_instruction_parser(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda session_id: {"summary": "Age-targeted policy", "entity_nodes": [], "relationship_edges": []})
    monkeypatch.setattr(
        PersonaRelevanceService,
        "parse_sampling_instructions",
        lambda self, instructions, knowledge_artifact=None, live_mode=False: {
            "hard_filters": {"age_cohort": ["0_10", "11_20", "21_30", "31_40"]},
            "soft_boosts": {},
            "soft_penalties": {},
            "exclusions": {},
            "distribution_targets": {},
            "notes_for_ui": ["Strictly no one over the age of 40."],
            "source": "test",
        },
    )

    captured: dict[str, object] = {}

    def fake_query_candidates(**kwargs):
        captured.update(kwargs)
        return [{"planning_area": "Sengkang", "industry": "Education", "age": 35, "occupation": "Teacher"}]

    monkeypatch.setattr(service.sampler, "query_candidates", fake_query_candidates)
    monkeypatch.setattr(
        PersonaRelevanceService,
        "build_population_artifact",
        lambda self, *args, **kwargs: {
            "session_id": "session-a",
            "candidate_count": 1,
            "sample_count": 1,
            "sample_mode": "affected_groups",
            "sample_seed": kwargs["seed"],
            "parsed_sampling_instructions": kwargs["parsed_sampling_instructions"],
            "coverage": {},
            "sampled_personas": [],
            "agent_graph": {"nodes": [], "links": []},
            "representativeness": {"status": "narrow"},
            "selection_diagnostics": {},
        },
    )

    class Req:
        agent_count = 100
        sample_mode = "affected_groups"
        sampling_instructions = "Strictly no one over the age of 40."
        seed = 19
        min_age = None
        max_age = None
        planning_areas = []

        def model_dump(self):
            return {
                "agent_count": self.agent_count,
                "sample_mode": self.sample_mode,
                "sampling_instructions": self.sampling_instructions,
                "seed": self.seed,
                "min_age": self.min_age,
                "max_age": self.max_age,
                "planning_areas": self.planning_areas,
            }

    service.preview_population("session-a", Req())

    assert captured["min_age"] == 0
    assert captured["max_age"] == 40


def test_console_service_allows_live_start_without_enable_real_oasis(monkeypatch, tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        enable_real_oasis=False,
    )
    service = ConsoleService(settings)
    session_id = "session-live"

    service.store.upsert_console_session(
        session_id=session_id,
        mode="live",
        status="population_ready",
        model_provider="ollama",
        model_name="qwen3:4b-instruct-2507-q4_K_M",
        embed_model_name="nomic-embed-text",
        api_key="ollama",
        base_url="http://127.0.0.1:11434/v1/",
    )
    service.store.save_population_artifact(
        session_id,
        {
            "sampled_personas": [
                {
                    "agent_id": "agent-0001",
                    "persona": {
                        "age": 32,
                        "planning_area": "Woodlands",
                        "occupation": "Teacher",
                    },
                    "selection_reason": {
                        "score": 0.88,
                    },
                }
            ]
        },
    )

    captured: dict[str, object] = {}

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("mckainsey.services.console_service.threading.Thread", FakeThread)

    state = service.start_simulation(
        session_id,
        policy_summary="Public transport fare support for shift workers.",
        rounds=1,
        mode="live",
    )

    assert state["status"] == "running"
    assert captured["started"] is True
    assert captured["args"][-2] == "live"
    assert captured["args"][-1] == 0.0


def test_console_service_create_session_live_mode_wraps_ollama_validation_failure(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(
        "mckainsey.services.console_service.ensure_ollama_models_available",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Ollama runtime unavailable")),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_session(
            requested_session_id="session-live",
            mode="live",
            model_provider="ollama",
            model_name="qwen3:4b-instruct-2507-q4_K_M",
            embed_model_name="nomic-embed-text",
            base_url="http://127.0.0.1:11434/v1/",
        )

    assert exc_info.value.status_code == 502
    assert "Session creation failed" in str(exc_info.value.detail)
    assert "Ollama runtime unavailable" in str(exc_info.value.detail)


def test_v2_compat_countries_route_returns_yaml_backed_catalog(tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"
    _write_text(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "/tmp/sg.parquet"
available: true
filter_fields: []
geo_json_path: "/tmp/sg.geo.json"
map_center: [1.35, 103.81]
map_zoom: 11
max_agents: 500
default_agents: 250
name_regex: "^[A-Z].*$"
""".strip(),
    )
    _write_text(
        prompts_dir / "policy-review.yaml",
        """
name: "Policy Review"
code: "policy-review"
description: "Policy reviews"
guiding_prompt: "Prompt"
agent_personality_modifiers: []
checkpoint_questions: []
report_sections: []
""".strip(),
    )

    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = client.get("/api/v2/countries")
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Singapore"
    assert body[0]["code"] == "sg"
    assert body[0]["available"] is True


def test_console_service_live_dynamic_filters_resolve_local_dataset_shards(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(repo_root / "config" / "countries"),
    )
    service = ConsoleService(settings)
    session_id = "session-live-filters"

    service.store.upsert_console_session(session_id=session_id, mode="live", status="created")
    service._upsert_session_config(
        session_id,
        {
            "country": "singapore",
            "use_case": "policy-review",
        },
    )

    response = service.get_dynamic_filters(session_id)
    fields = {row["field"]: row for row in response["filters"]}

    assert response["country"] == "singapore"
    assert fields["age"]["min"] <= fields["age"]["max"]
    assert fields["planning_area"]["options"]
    assert fields["occupation"]["options"]
    assert fields["gender"]["options"] == ["Female", "Male"]


def test_console_service_live_dynamic_filters_skip_missing_usa_fields(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(repo_root / "config" / "countries"),
    )
    service = ConsoleService(settings)
    session_id = "session-live-filters-usa"

    service.store.upsert_console_session(session_id=session_id, mode="live", status="created")
    service._upsert_session_config(
        session_id,
        {
            "country": "usa",
            "use_case": "policy-review",
        },
    )

    response = service.get_dynamic_filters(session_id)
    fields = {row["field"]: row for row in response["filters"]}

    assert response["country"] == "usa"
    assert fields["age"]["min"] <= fields["age"]["max"]
    assert fields["occupation"]["options"]
    assert fields["gender"]["options"] == ["Female", "Male"]
    assert "state" not in fields
    assert "ethnicity" not in fields


def test_v2_compat_providers_route_maps_gemini_and_falls_back_to_default_models(monkeypatch):
    def fake_model_provider_catalog(self):
        return {
            "providers": [
                {
                    "id": "google",
                    "label": "Google",
                    "default_model": "gemini-2.5-flash-lite",
                    "default_embed_model": "gemini-embedding-001",
                    "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "requires_api_key": True,
                },
                {
                    "id": "openai",
                    "label": "OpenAI",
                    "default_model": "gpt-5-mini",
                    "default_embed_model": "text-embedding-3-small",
                    "default_base_url": "https://api.openai.com/v1/",
                    "requires_api_key": True,
                },
                {
                    "id": "ollama",
                    "label": "Ollama",
                    "default_model": "qwen3:4b-instruct-2507-q4_K_M",
                    "default_embed_model": "nomic-embed-text",
                    "default_base_url": "http://127.0.0.1:11434/v1/",
                    "requires_api_key": False,
                },
            ]
        }

    def fake_list_provider_models(self, provider, *, api_key=None, base_url=None):  # noqa: ANN001, ANN202, ARG001
        if provider == "google":
            return {
                "provider": "google",
                "models": [
                    {"id": "gemini-2.0-flash-lite", "label": "gemini-2.0-flash-lite"},
                    {"id": "gemini-2.5-flash", "label": "gemini-2.5-flash"},
                    {"id": "gemini-2.5-flash-lite", "label": "gemini-2.5-flash-lite"},
                ],
            }
        if provider == "ollama":
            return {"provider": "ollama", "models": [{"id": "qwen3:4b", "label": "qwen3:4b"}]}
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(ConsoleService, "model_provider_catalog", fake_model_provider_catalog)
    monkeypatch.setattr(ConsoleService, "list_provider_models", fake_list_provider_models)

    response = client.get("/api/v2/providers")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["name"] for row in body] == ["gemini", "openai", "ollama"]
    assert body[0]["models"] == ["gemini-2.5-flash-lite", "gemini-2.5-flash"]
    assert body[1]["models"] == ["gpt-5-mini"]
    assert body[2]["models"] == ["qwen3:4b"]
    assert body[0]["requires_api_key"] is True
    assert body[2]["requires_api_key"] is False


def test_v2_compat_session_create_route_normalizes_provider_and_use_case(monkeypatch, tmp_path):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"
    _write_text(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "/tmp/sg.parquet"
available: true
filter_fields: []
geo_json_path: "/tmp/sg.geo.json"
map_center: [1.35, 103.81]
map_zoom: 11
max_agents: 500
default_agents: 250
name_regex: "^[A-Z].*$"
""".strip(),
    )
    _write_text(
        prompts_dir / "product-market-research.yaml",
        """
name: "Product & Market Research"
code: "product-market-research"
description: "Product research"
guiding_prompt: "Prompt"
agent_personality_modifiers: []
analysis_questions: []
preset_sections: []
""".strip(),
    )

    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
    )
    app.dependency_overrides[get_settings] = lambda: settings

    captured: dict[str, str | None] = {}

    def fake_create_session(
        self,
        requested_session_id: str | None = None,
        mode: str = "demo",
        *,
        model_provider: str | None = None,
        model_name: str | None = None,
        embed_model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        captured["requested_session_id"] = requested_session_id
        captured["mode"] = mode
        captured["model_provider"] = model_provider
        captured["model_name"] = model_name
        captured["embed_model_name"] = embed_model_name
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        return {
            "session_id": "session-compat-1",
            "mode": mode,
            "status": "created",
            "model_provider": model_provider or "google",
            "model_name": model_name or "gemini-2.5-flash-lite",
            "embed_model_name": embed_model_name or "gemini-embedding-001",
            "base_url": base_url or "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key_configured": bool(api_key),
            "api_key_masked": None,
        }

    monkeypatch.setattr(ConsoleService, "create_session", fake_create_session)
    try:
        response = client.post(
            "/api/v2/session/create",
            json={
                "country": "singapore",
                "provider": "gemini",
                "model": "gemini-2.0-flash",
                "api_key": "test-key",
                "use_case": "reviews",
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200, response.text
    assert response.json() == {"session_id": "session-compat-1"}
    assert captured["mode"] == "live"
    assert captured["model_provider"] == "google"
    assert captured["model_name"] == "gemini-2.0-flash"
    assert captured["api_key"] == "test-key"


def test_v2_session_config_patch_route_persists_session_config(monkeypatch):
    captured: dict[str, object] = {}

    def fake_update_v2_session_config(
        self,
        session_id: str,
        *,
        country: str | None = None,
        use_case: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        guiding_prompt: str | None = None,
        analysis_questions: list[dict[str, object]] | None = None,
    ):
        captured["session_id"] = session_id
        captured["country"] = country
        captured["use_case"] = use_case
        captured["provider"] = provider
        captured["model"] = model
        captured["api_key"] = api_key
        captured["guiding_prompt"] = guiding_prompt
        captured["analysis_questions"] = analysis_questions
        return {
            "session_id": session_id,
            "country": country or "singapore",
            "use_case": use_case or "public-policy-testing",
            "provider": provider or "google",
            "model": model or "gemini-2.5-flash-lite",
            "api_key_configured": bool(api_key),
            "guiding_prompt": guiding_prompt,
            "analysis_questions": analysis_questions or [],
        }

    monkeypatch.setattr(ConsoleService, "update_v2_session_config", fake_update_v2_session_config)

    response = client.patch(
        "/api/v2/session/session-config-1/config",
        json={
            "country": "singapore",
            "use_case": "public-policy-testing",
            "provider": "gemini",
            "model": "gemini-2.0-flash",
            "api_key": "test-key",
            "guiding_prompt": "Focus on transport affordability for seniors.",
            "analysis_questions": [
                {
                    "question": "Do you approve of this policy? Rate 1-10.",
                    "type": "scale",
                    "metric_name": "approval_rate",
                    "metric_label": "Approval Rate",
                    "metric_unit": "%",
                    "threshold": 7,
                    "threshold_direction": "gte",
                    "report_title": "Policy Approval",
                    "tooltip": "Share of respondents at or above 7/10.",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-config-1"
    assert body["country"] == "singapore"
    assert body["use_case"] == "public-policy-testing"
    assert body["provider"] == "gemini"
    assert body["model"] == "gemini-2.0-flash"
    assert body["api_key_configured"] is True
    assert "transport affordability" in body["guiding_prompt"]
    assert body["analysis_questions"][0]["metric_name"] == "approval_rate"
    assert captured["country"] == "singapore"
    assert captured["use_case"] == "public-policy-testing"
    assert captured["provider"] == "gemini"
    assert captured["analysis_questions"][0]["report_title"] == "Policy Approval"


def test_v2_console_prefix_session_config_patch_route_persists_session_config(monkeypatch):
    captured: dict[str, object] = {}

    def fake_update_v2_session_config(
        self,
        session_id: str,
        *,
        country: str | None = None,
        use_case: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        guiding_prompt: str | None = None,
        analysis_questions: list[dict[str, object]] | None = None,
    ):
        captured["session_id"] = session_id
        captured["country"] = country
        captured["use_case"] = use_case
        captured["provider"] = provider
        captured["model"] = model
        captured["api_key"] = api_key
        captured["guiding_prompt"] = guiding_prompt
        captured["analysis_questions"] = analysis_questions
        return {
            "session_id": session_id,
            "country": country or "singapore",
            "use_case": use_case or "public-policy-testing",
            "provider": provider or "google",
            "model": model or "gemini-2.5-flash-lite",
            "api_key_configured": bool(api_key),
            "guiding_prompt": guiding_prompt,
            "analysis_questions": analysis_questions or [],
        }

    monkeypatch.setattr(ConsoleService, "update_v2_session_config", fake_update_v2_session_config)

    response = client.patch(
        "/api/v2/console/session/session-config-2/config",
        json={
            "country": "singapore",
            "use_case": "public-policy-testing",
            "provider": "gemini",
            "model": "gemini-2.0-flash",
            "api_key": "test-key",
            "analysis_questions": [
                {
                    "question": "How useful would the $500 credits be for your household?",
                    "type": "scale",
                    "metric_name": "household_usefulness",
                    "report_title": "Household Usefulness",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "session-config-2"
    assert body["provider"] == "gemini"
    assert body["analysis_questions"][0]["metric_name"] == "household_usefulness"
    assert captured["session_id"] == "session-config-2"
    assert captured["analysis_questions"][0]["report_title"] == "Household Usefulness"


def test_v2_generate_question_metadata_route_uses_sync_service_method(monkeypatch):
    calls: dict[str, object] = {}

    def fake_generate_metric_metadata_sync(self, question_text: str):
        calls["question"] = question_text
        return {
            "question": question_text,
            "type": "scale",
            "metric_name": "approval_rate",
            "metric_label": "Approval Rate",
            "metric_unit": "%",
            "threshold": 7,
            "threshold_direction": "gte",
            "report_title": "Policy Approval",
            "tooltip": "Percentage rating at least 7/10.",
        }

    monkeypatch.setattr(
        "mckainsey.services.question_metadata_service.QuestionMetadataService.generate_metric_metadata_sync",
        fake_generate_metric_metadata_sync,
    )

    response = client.post(
        "/api/v2/questions/generate-metadata",
        json={"question": "Do you approve of this policy? Rate 1-10."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert calls["question"] == "Do you approve of this policy? Rate 1-10."
    assert body["metric_name"] == "approval_rate"
    assert body["report_title"] == "Policy Approval"


def test_v2_analysis_questions_route_returns_session_scoped_questions(monkeypatch):
    def fake_get_session_analysis_questions(self, session_id: str):
        assert session_id == "session-a"
        return {
            "session_id": session_id,
            "use_case": "campaign-content-testing",
            "questions": [
                {
                    "question": "Would you try this campaign? (yes/no)",
                    "type": "yes-no",
                    "metric_name": "conversion_intent",
                    "metric_label": "Conversion Intent",
                    "metric_unit": "%",
                    "report_title": "Conversion Analysis",
                    "tooltip": "Share of yes responses.",
                }
            ],
        }

    monkeypatch.setattr(ConsoleService, "get_session_analysis_questions", fake_get_session_analysis_questions)

    response = client.get("/api/v2/session/session-a/analysis-questions")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["use_case"] == "campaign-content-testing"
    assert body["questions"][0]["metric_name"] == "conversion_intent"


def test_console_service_v2_session_config_persists_analysis_questions(tmp_path, monkeypatch):
    countries_dir = tmp_path / "countries"
    prompts_dir = tmp_path / "prompts"
    _write_text(
        countries_dir / "singapore.yaml",
        """
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "/tmp/sg.parquet"
available: true
filter_fields: []
""".strip(),
    )
    _write_text(
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
    tooltip: "Share of respondents rating >= 7."
""".strip(),
    )

    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        config_countries_dir=str(countries_dir),
        config_prompts_dir=str(prompts_dir),
    )
    service = ConsoleService(settings)

    def fake_create_session(
        self,
        requested_session_id: str | None = None,
        mode: str = "demo",
        *,
        model_provider: str | None = None,
        model_name: str | None = None,
        embed_model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        del embed_model_name, base_url
        session_id = requested_session_id or "session-v2-1"
        self.store.upsert_console_session(
            session_id=session_id,
            mode=mode,
            status="created",
            model_provider=model_provider or "google",
            model_name=model_name or "gemini-2.5-flash-lite",
            embed_model_name="gemini-embedding-001",
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        return {
            "session_id": session_id,
            "mode": mode,
            "status": "created",
            "model_provider": model_provider or "google",
            "model_name": model_name or "gemini-2.5-flash-lite",
            "embed_model_name": "gemini-embedding-001",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key_configured": bool(api_key),
            "api_key_masked": None,
        }

    monkeypatch.setattr(ConsoleService, "create_session", fake_create_session)

    created = service.create_v2_session(
        country="singapore",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        session_id="session-v2-1",
    )
    assert created["session_id"] == "session-v2-1"

    session_questions = service.get_session_analysis_questions("session-v2-1")
    assert session_questions["use_case"] == "public-policy-testing"
    assert session_questions["questions"][0]["metric_name"] == "approval_rate"

    updated = service.update_v2_session_config(
        "session-v2-1",
        analysis_questions=[
            {
                "question": "What specific aspects do you support or oppose?",
                "type": "open-ended",
                "metric_name": "policy_viewpoints",
                "report_title": "Key Viewpoints",
                "tooltip": "Qualitative summary.",
            }
        ],
    )
    assert updated["analysis_questions"][0]["metric_name"] == "policy_viewpoints"
    assert service.get_session_analysis_questions("session-v2-1")["questions"][0]["report_title"] == "Key Viewpoints"


def test_console_service_defaults_to_canonical_v2_use_case(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    assert service._session_use_case("missing-session") == "public-policy-testing"


def test_console_service_group_chat_selects_top_n_from_requested_segment(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda session_id: [
            {"agent_id": "agent-001", "opinion_post": 3, "persona": {"planning_area": "Woodlands"}},
            {"agent_id": "agent-002", "opinion_post": 4, "persona": {"planning_area": "Yishun"}},
            {"agent_id": "agent-003", "opinion_post": 8, "persona": {"planning_area": "Punggol"}},
        ],
    )
    monkeypatch.setattr(
        service.store,
        "get_interactions",
        lambda session_id: [
            {"actor_agent_id": "agent-001", "target_agent_id": "agent-002", "type": "comment", "likes": 20, "dislikes": 2},
            {"actor_agent_id": "agent-001", "target_agent_id": "agent-003", "type": "comment", "likes": 16, "dislikes": 1},
            {"actor_agent_id": "agent-002", "target_agent_id": "agent-001", "type": "post", "likes": 7, "dislikes": 1},
            {"actor_agent_id": "agent-003", "target_agent_id": "agent-001", "type": "post", "likes": 30, "dislikes": 2},
        ],
    )
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)

    calls: list[str] = []

    def fake_agent_chat_realtime(self, simulation_id: str, agent_id: str, message: str, live_mode: bool = False):
        assert simulation_id == "session-a"
        assert "position" in message.lower()
        assert live_mode is False
        calls.append(agent_id)
        return {
            "session_id": simulation_id,
            "agent_id": agent_id,
            "response": f"{agent_id} reply",
            "memory_used": True,
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "zep_context_used": False,
            "graphiti_context_used": False,
        }

    monkeypatch.setattr("mckainsey.services.console_service.MemoryService.agent_chat_realtime", fake_agent_chat_realtime)

    payload = service.group_chat("session-a", "dissenter", "What changed your position?", top_n=2)

    assert payload["segment"] == "dissenter"
    assert [item["agent_id"] for item in payload["responses"]] == ["agent-001", "agent-002"]
    assert calls == ["agent-001", "agent-002"]


def test_console_service_group_chat_accepts_plural_segment_aliases(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(
        service.store,
        "get_agents",
        lambda session_id: [
            {"agent_id": "agent-001", "opinion_post": 3, "persona": {"planning_area": "Woodlands"}},
            {"agent_id": "agent-002", "opinion_post": 4, "persona": {"planning_area": "Yishun"}},
        ],
    )
    monkeypatch.setattr(service.store, "get_interactions", lambda session_id: [])
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)

    captured: list[str] = []

    def fake_agent_chat_realtime(self, simulation_id: str, agent_id: str, message: str, live_mode: bool = False):
        captured.append(agent_id)
        return {
            "session_id": simulation_id,
            "agent_id": agent_id,
            "response": f"{agent_id} reply",
            "memory_used": True,
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "zep_context_used": False,
            "graphiti_context_used": False,
        }

    monkeypatch.setattr("mckainsey.services.console_service.MemoryService.agent_chat_realtime", fake_agent_chat_realtime)

    payload = service.group_chat("session-a", "dissenters", "What changed your position?", top_n=1)

    assert payload["segment"] == "dissenter"
    assert captured == ["agent-001"]


def test_console_service_group_chat_returns_system_notice_when_segment_is_empty(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(
        service,
        "_agents_for_metrics",
        lambda _session_id: [{"agent_id": "agent-001", "opinion_post": 8, "persona": {"planning_area": "Woodlands"}}],
    )
    monkeypatch.setattr(service.store, "get_interactions", lambda _session_id: [])
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)
    monkeypatch.setattr(service.store, "append_interaction_transcript", lambda *args, **kwargs: None)

    payload = service.group_chat("session-a", "dissenters", "Why do you oppose this policy?", top_n=2)

    assert payload["segment"] == "dissenter"
    assert payload["responses"][0]["agent_id"] == "system"
    assert "No agents were classified as dissenter" in payload["responses"][0]["response"]


def test_console_service_group_chat_passes_live_mode_to_memory_service(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    service.store.upsert_console_session(
        session_id="session-live",
        mode="live",
        status="created",
    )
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)
    monkeypatch.setattr(service, "_is_demo_session", lambda _session_id: False)
    monkeypatch.setattr(
        service,
        "_agents_for_metrics",
        lambda _session_id: [{"agent_id": "agent-001", "opinion_post": 4, "persona": {"planning_area": "Woodlands"}}],
    )
    monkeypatch.setattr(service.store, "get_interactions", lambda _session_id: [])
    monkeypatch.setattr(service.store, "append_interaction_transcript", lambda *args, **kwargs: None)

    captured: dict[str, object] = {}

    def fake_agent_chat_realtime(self, simulation_id: str, agent_id: str, message: str, live_mode: bool = False):
        captured.update(
            {
                "simulation_id": simulation_id,
                "agent_id": agent_id,
                "message": message,
                "live_mode": live_mode,
            }
        )
        return {
            "session_id": simulation_id,
            "agent_id": agent_id,
            "response": "live response",
            "memory_used": True,
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "zep_context_used": False,
            "graphiti_context_used": False,
            "memory_backend": "zep",
        }

    monkeypatch.setattr("mckainsey.services.console_service.MemoryService.agent_chat_realtime", fake_agent_chat_realtime)

    payload = service.group_chat("session-live", "dissenter", "What changed your position?", top_n=1)

    assert payload["responses"][0]["response"] == "live response"
    assert captured["live_mode"] is True


def test_console_service_agent_chat_v2_passes_live_mode_to_memory_service(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    service.store.upsert_console_session(
        session_id="session-live",
        mode="live",
        status="created",
    )
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)
    monkeypatch.setattr(
        service.store,
        "get_console_session",
        lambda session_id: {"session_id": session_id, "mode": "live", "status": "created"},
    )
    monkeypatch.setattr(service.store, "append_interaction_transcript", lambda *args, **kwargs: None)

    captured: dict[str, object] = {}

    def fake_agent_chat_realtime(self, simulation_id: str, agent_id: str, message: str, live_mode: bool = False):
        captured.update(
            {
                "simulation_id": simulation_id,
                "agent_id": agent_id,
                "message": message,
                "live_mode": live_mode,
            }
        )
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "response": "live response",
            "memory_used": True,
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "gemini_model": "gemini-2.0-flash",
            "zep_context_used": False,
            "graphiti_context_used": False,
            "memory_backend": "zep",
        }

    monkeypatch.setattr("mckainsey.services.console_service.MemoryService.agent_chat_realtime", fake_agent_chat_realtime)

    payload = service.agent_chat_v2("session-live", "agent-001", "What changed your mind?")

    assert payload["response"] == "live response"
    assert captured["live_mode"] is True


def test_console_service_agent_chat_v2_includes_document_context_in_message(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    service.store.upsert_console_session(
        session_id="session-live",
        mode="live",
        status="created",
    )
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)
    monkeypatch.setattr(
        service.store,
        "get_console_session",
        lambda session_id: {"session_id": session_id, "mode": "live", "status": "created"},
    )
    monkeypatch.setattr(
        service.store,
        "get_knowledge_artifact",
        lambda session_id: {
            "summary": "Sports voucher policy for families.",
            "document": {"source_path": "/tmp/policy.pdf", "text_length": 4321},
        },
    )
    monkeypatch.setattr(service.store, "append_interaction_transcript", lambda *args, **kwargs: None)

    captured: dict[str, object] = {}

    def fake_agent_chat_realtime(self, simulation_id: str, agent_id: str, message: str, live_mode: bool = False):
        captured.update(
            {
                "simulation_id": simulation_id,
                "agent_id": agent_id,
                "message": message,
                "live_mode": live_mode,
            }
        )
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "response": "live response",
            "memory_used": True,
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
            "gemini_model": "gemini-2.0-flash",
            "zep_context_used": False,
            "graphiti_context_used": False,
            "memory_backend": "zep",
        }

    monkeypatch.setattr("mckainsey.services.console_service.MemoryService.agent_chat_realtime", fake_agent_chat_realtime)

    payload = service.agent_chat_v2("session-live", "agent-001", "What changed your mind?")

    assert payload["response"] == "live response"
    assert captured["live_mode"] is True
    assert "Sports voucher policy for families." in str(captured["message"])
    assert "/tmp/policy.pdf" in str(captured["message"])


def test_console_service_group_chat_uses_demo_fallback_when_demo_session(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(ConsoleService, "_is_demo_session", lambda self, session_id: True)
    monkeypatch.setattr(DemoService, "is_demo_available", lambda self: True)
    monkeypatch.setattr(
        DemoService,
        "get_interaction_hub",
        lambda self, session_id, agent_id=None: {
            "session_id": session_id,
            "influential_agents": [
                {"agent_id": "agent-001", "influence_score": 0.94},
                {"agent_id": "agent-002", "influence_score": 0.88},
            ],
            "selected_agent": None,
        },
    )
    monkeypatch.setattr(
        DemoService,
        "generate_demo_agent_chat",
        lambda self, session_id, agent_id, message: {
            "response": f"Demo response from {agent_id}: {message}",
            "zep_context_used": False,
            "demo_mode": True,
        },
    )
    monkeypatch.setattr(service, "_agents_for_metrics", lambda _session_id: [])
    monkeypatch.setattr(service.store, "get_interactions", lambda _session_id: [])

    payload = service.group_chat("demo-session", "dissenter", "What concerns matter most?", top_n=2)

    assert payload["segment"] == "dissenter"
    assert [item["agent_id"] for item in payload["responses"]] == ["agent-001", "agent-002"]
    assert payload["responses"][0]["memory_backend"] == "demo"
    assert payload["responses"][0]["response"].startswith("Demo response from agent-001")


def test_console_service_agent_chat_v2_uses_demo_fallback_when_demo_session(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    monkeypatch.setattr(ConsoleService, "_is_demo_session", lambda self, session_id: True)
    monkeypatch.setattr(DemoService, "is_demo_available", lambda self: True)
    monkeypatch.setattr(
        DemoService,
        "generate_demo_agent_chat",
        lambda self, session_id, agent_id, message: {
            "response": f"Demo response from {agent_id}: {message}",
            "zep_context_used": False,
            "demo_mode": True,
        },
    )
    monkeypatch.setattr(
        service,
        "_session_model_payload",
        lambda _session_id: {
            "model_provider": "google",
            "model_name": "gemini-2.0-flash",
        },
    )

    payload = service.agent_chat_v2("demo-session", "agent-001", "What changed your mind?")

    assert payload["agent_id"] == "agent-001"
    assert payload["response"].startswith("Demo response from agent-001")
    assert payload["memory_backend"] == "demo"


def test_console_service_uses_config_service_prompt_helpers(monkeypatch, tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = ConsoleService(settings)

    question_calls: list[str] = []
    modifier_calls: list[str] = []

    def fake_checkpoint_questions(self, use_case):
        question_calls.append(use_case)
        return [{"question": "Do you approve?", "type": "scale", "metric_name": "approval_rate"}]

    def fake_modifiers(self, use_case):
        modifier_calls.append(use_case)
        return ["Speak about affordability"]

    monkeypatch.setattr("mckainsey.services.config_service.ConfigService.get_checkpoint_questions", fake_checkpoint_questions)
    monkeypatch.setattr("mckainsey.services.config_service.ConfigService.get_agent_personality_modifiers", fake_modifiers)

    from mckainsey.services.config_service import ConfigService

    cfg = ConfigService(settings)
    questions = service._checkpoint_questions_for_use_case(cfg, "policy-review")
    modifiers = service._personality_modifiers_for_use_case(cfg, "policy-review")

    assert question_calls == ["policy-review"]
    assert modifier_calls == ["policy-review"]
    assert questions == [{"question": "Do you approve?", "type": "scale", "metric_name": "approval_rate"}]
    assert modifiers == ["Speak about affordability"]
