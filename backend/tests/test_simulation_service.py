import json

import pytest

from mckainsey.config import Settings
from mckainsey.services.simulation_service import SimulationService


def test_build_context_bundles_prioritizes_matched_facets_and_adjacent_nodes(tmp_path):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    knowledge_artifact = {
        "summary": "Sports voucher policy for active youths in Woodlands.",
        "entity_nodes": [
            {
                "id": "policy:sports-voucher",
                "label": "Sports Voucher",
                "type": "policy",
                "source_ids": ["chunk-1"],
                "file_paths": ["policy.md"],
            },
            {
                "id": "age:youth",
                "label": "Youth",
                "type": "demographic",
                "facet_kind": "age_cohort",
                "canonical_key": "age_cohort:youth",
                "source_ids": ["chunk-1"],
                "file_paths": ["policy.md"],
            },
            {
                "id": "area:woodlands",
                "label": "Woodlands",
                "type": "location",
                "facet_kind": "planning_area",
                "canonical_key": "planning_area:woodlands",
                "source_ids": ["chunk-2"],
                "file_paths": ["policy.md"],
            },
        ],
        "relationship_edges": [
            {
                "source": "policy:sports-voucher",
                "target": "age:youth",
                "label": "targets",
            },
            {
                "source": "policy:sports-voucher",
                "target": "area:woodlands",
                "label": "pilot area",
            },
        ],
    }
    sampled_personas = [
        {
            "agent_id": "agent-0001",
            "persona": {
                "planning_area": "Woodlands",
                "age": 23,
                "occupation": "Student",
            },
            "selection_reason": {
                "matched_facets": ["planning_area:woodlands", "age_cohort:youth"],
                "matched_document_entities": ["sports voucher"],
            },
        }
    ]

    bundles = service.build_context_bundles(
        simulation_id="session-1",
        policy_summary="Sports voucher for active youths.",
        knowledge_artifact=knowledge_artifact,
        sampled_personas=sampled_personas,
    )

    bundle = bundles["agent-0001"]
    assert bundle["matched_context_nodes"][:2] == ["planning_area:woodlands", "age_cohort:youth"]
    assert "policy:sports-voucher" in bundle["graph_node_ids"]
    assert bundle["provenance"]["source_ids"] == ["chunk-1", "chunk-2"]
    assert bundle["provenance"]["file_paths"] == ["policy.md"]
    assert "sports voucher" in bundle["brief"].lower()


def test_run_opinion_checkpoint_returns_structured_stance_records(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda prompt, system_prompt=None, response_format=None: (
            '[{"agent_id":"agent-0001","stance_score":0.81,"stance_class":"approve",'
            '"confidence":0.74,"primary_driver":"affordability","matched_context_nodes":["planning_area:woodlands"]}]'
        ),
    )

    checkpoints = service.run_opinion_checkpoint(
        simulation_id="session-1",
        checkpoint_kind="baseline",
        policy_summary="Subsidise sports access in Woodlands.",
        agent_context_bundles={
            "agent-0001": {
                "agent_id": "agent-0001",
                "brief": "Young Woodlands resident who benefits from sports subsidies.",
                "matched_context_nodes": ["planning_area:woodlands"],
            }
        },
    )

    assert checkpoints[0]["checkpoint_kind"] == "baseline"
    assert checkpoints[0]["agent_id"] == "agent-0001"
    assert checkpoints[0]["stance_class"] == "approve"
    assert checkpoints[0]["primary_driver"] == "affordability"
    assert checkpoints[0]["matched_context_nodes"] == ["planning_area:woodlands"]


def test_run_opinion_checkpoint_retries_when_model_omits_agents(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    responses = iter(
        [
            (
                '[{"agent_id":"agent-0001","stance_score":0.72,"stance_class":"approve",'
                '"confidence":0.66,"primary_driver":"cost_support","matched_context_nodes":["planning_area:woodlands"]}]'
            ),
            (
                '[{"agent_id":"agent-0002","stance_score":0.41,"stance_class":"neutral",'
                '"confidence":0.62,"primary_driver":"implementation_clarity","matched_context_nodes":["planning_area:yishun"]}]'
            ),
        ]
    )
    call_counter = {"count": 0}

    def fake_complete_required(prompt, system_prompt=None, response_format=None):
        del prompt, system_prompt, response_format
        call_counter["count"] += 1
        return next(responses)

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    checkpoints = service.run_opinion_checkpoint(
        simulation_id="session-2",
        checkpoint_kind="baseline",
        policy_summary="Targeted support for north-region households.",
        agent_context_bundles={
            "agent-0001": {
                "agent_id": "agent-0001",
                "brief": "Resident in Woodlands with transport cost concerns.",
                "matched_context_nodes": ["planning_area:woodlands"],
            },
            "agent-0002": {
                "agent_id": "agent-0002",
                "brief": "Resident in Yishun focused on implementation practicality.",
                "matched_context_nodes": ["planning_area:yishun"],
            },
        },
    )

    assert call_counter["count"] == 2
    assert [row["agent_id"] for row in checkpoints] == ["agent-0001", "agent-0002"]


def test_run_opinion_checkpoint_retries_transient_timeout_error(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    responses = iter(
        [
            RuntimeError("Request timed out while waiting for local model"),
            (
                '[{"agent_id":"agent-0001","stance_score":0.66,"stance_class":"approve",'
                '"confidence":0.71,"primary_driver":"transport_relief","matched_context_nodes":[]}]'
            ),
        ]
    )
    call_counter = {"count": 0}

    def fake_complete_required(prompt, system_prompt=None, response_format=None):
        del prompt, system_prompt, response_format
        call_counter["count"] += 1
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    checkpoints = service.run_opinion_checkpoint(
        simulation_id="session-3",
        checkpoint_kind="baseline",
        policy_summary="Bus fare support for lower-income commuters.",
        agent_context_bundles={
            "agent-0001": {
                "agent_id": "agent-0001",
                "brief": "Resident with daily transport costs.",
                "matched_context_nodes": [],
            }
        },
    )

    assert call_counter["count"] == 2
    assert checkpoints[0]["agent_id"] == "agent-0001"


def test_run_opinion_checkpoint_uses_smaller_batches_for_ollama(tmp_path, monkeypatch):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="ollama",
    )
    service = SimulationService(settings)

    call_counter = {"count": 0}

    def fake_complete_required(prompt, system_prompt=None, response_format=None):
        del system_prompt, response_format
        call_counter["count"] += 1
        payload = prompt.split("Agents:\n", 1)[1]
        agents = json.loads(payload)
        records = [
            {
                "agent_id": agent["agent_id"],
                "stance_score": 0.55,
                "stance_class": "neutral",
                "confidence": 0.65,
                "primary_driver": "general_sentiment",
                "matched_context_nodes": agent.get("matched_context_nodes") or [],
            }
            for agent in agents
        ]
        return json.dumps(records)

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)

    bundles = {
        f"agent-{idx:04d}": {
            "agent_id": f"agent-{idx:04d}",
            "brief": f"Persona {idx}",
            "matched_context_nodes": [],
        }
        for idx in range(1, 10)
    }

    checkpoints = service.run_opinion_checkpoint(
        simulation_id="session-4",
        checkpoint_kind="baseline",
        policy_summary="Support package",
        agent_context_bundles=bundles,
    )

    assert len(checkpoints) == 9
    assert call_counter["count"] == 3


def test_resolve_oasis_timeout_scales_for_ollama_workloads(tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="ollama",
        oasis_timeout_seconds=1800,
    )
    service = SimulationService(settings)

    timeout_seconds = service._resolve_oasis_timeout_seconds(rounds=3, persona_count=500)

    expected = max(
        settings.oasis_timeout_seconds,
        300 + (500 * 3 * settings.oasis_ollama_timeout_per_agent_round_seconds) + (120 * 3),
    )
    assert timeout_seconds == expected


def test_resolve_oasis_timeout_respects_configured_floor(tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="google",
        oasis_timeout_seconds=1800,
    )
    service = SimulationService(settings)

    timeout_seconds = service._resolve_oasis_timeout_seconds(rounds=2, persona_count=50)

    assert timeout_seconds == 1800


def test_run_with_personas_threads_controversy_boost_to_oasis_runtime(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    captured: dict[str, object] = {}

    def fake_run_oasis_with_inputs(
        self,
        *,
        simulation_id,
        policy_summary,
        rounds,
        personas,
        events_path,
        on_progress=None,
        elapsed_offset_seconds=0,
        tail_checkpoint_estimate_seconds=0,
        controversy_boost=0.0,
    ):
        del self, policy_summary, rounds, personas, events_path, on_progress, elapsed_offset_seconds, tail_checkpoint_estimate_seconds
        captured["simulation_id"] = simulation_id
        captured["controversy_boost"] = controversy_boost
        return {
            "agents": [{"agent_id": "agent-0001", "persona": {"planning_area": "Woodlands"}, "opinion_pre": 5.0, "opinion_post": 5.5}],
            "interactions": [],
            "stage3a_approval_rate": 0.4,
            "stage3b_approval_rate": 0.5,
            "net_opinion_shift": 0.1,
            "elapsed_seconds": 7,
            "counters": {"posts": 1, "comments": 0, "reactions": 0, "active_authors": 1},
        }

    monkeypatch.setattr(SimulationService, "_run_oasis_with_inputs", fake_run_oasis_with_inputs)

    result = service.run_with_personas(
        simulation_id="session-controversy",
        policy_summary="Policy summary",
        rounds=1,
        personas=[{"agent_id": "agent-0001", "planning_area": "Woodlands"}],
        force_live=True,
        controversy_boost=0.7,
    )

    assert result["runtime"] == "oasis"
    assert captured["simulation_id"] == "session-controversy"
    assert captured["controversy_boost"] == 0.7


def test_run_opinion_checkpoint_reports_estimated_token_usage(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    monkeypatch.setattr(
        service.llm,
        "complete_required",
        lambda prompt, system_prompt=None, response_format=None: (
            '[{"agent_id":"agent-0001","stance_score":0.81,"stance_class":"approve",'
            '"confidence":0.74,"primary_driver":"affordability","matched_context_nodes":[]}]'
        ),
    )

    usage_calls: list[tuple[int, int, int]] = []

    checkpoints = service.run_opinion_checkpoint(
        simulation_id="session-token",
        checkpoint_kind="baseline",
        policy_summary="Subsidise transport costs.",
        agent_context_bundles={
            "agent-0001": {
                "agent_id": "agent-0001",
                "brief": "Resident with daily commuting concerns.",
                "matched_context_nodes": [],
            }
        },
        on_token_usage=lambda input_tokens, output_tokens, cached_tokens: usage_calls.append(
            (input_tokens, output_tokens, cached_tokens)
        ),
    )

    assert checkpoints[0]["agent_id"] == "agent-0001"
    assert usage_calls
    assert usage_calls[0][0] > 0


def test_run_with_personas_live_mode_propagates_real_runtime_failure(tmp_path, monkeypatch):
    settings = Settings(simulation_db_path=str(tmp_path / "sim.db"))
    service = SimulationService(settings)

    monkeypatch.setattr(
        service,
        "_run_oasis_with_inputs",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Real OASIS runtime unavailable")),
    )

    with pytest.raises(RuntimeError, match="Real OASIS runtime unavailable"):
        service.run_with_personas(
            simulation_id="session-live",
            policy_summary="Support package",
            rounds=2,
            personas=[{"planning_area": "Woodlands", "age": 31, "occupation": "Teacher"}],
            force_live=True,
        )
