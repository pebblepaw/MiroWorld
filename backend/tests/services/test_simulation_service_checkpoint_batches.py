from __future__ import annotations

import logging
from pathlib import Path

from miroworld.config import Settings
from miroworld.services.simulation_service import SimulationService


def test_non_ollama_checkpoint_batches_default_to_ten(tmp_path: Path) -> None:
    service = SimulationService(Settings(simulation_db_path=str(tmp_path / "simulation.db"), llm_provider="google"))

    assert service._resolve_checkpoint_batch_size(total_agents=50) == 10


def test_ollama_checkpoint_batches_stay_small(tmp_path: Path) -> None:
    service = SimulationService(Settings(simulation_db_path=str(tmp_path / "simulation.db"), llm_provider="ollama"))

    assert service._resolve_checkpoint_batch_size(total_agents=50) == 3


def test_google_checkpoint_repairs_invalid_json_with_structured_output_and_logs(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    service = SimulationService(
        Settings(
            simulation_db_path=str(tmp_path / "simulation.db"),
            llm_provider="google",
            llm_model="gemini-2.5-flash-lite",
            llm_api_key="test-google-key",
            llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    )
    calls: list[dict[str, object]] = []
    responses = iter(
        [
            "I am sorry, but I cannot classify this as a policy.",
            (
                '{"records":[{"agent_id":"agent-0001","stance_score":0.82,'
                '"stance_class":"approve","confidence":0.91,"primary_driver":"usefulness",'
                '"confirmed_name":"Alex Tan","metric_answers":{"product_interest":8,'
                '"pain_points":"Pricing clarity"},"matched_context_nodes":["pricing"]}]}'
            ),
        ]
    )

    def fake_complete_required(
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict[str, object] | None = None,
    ) -> str:
        calls.append(
            {
                "prompt": prompt,
                "system_prompt": system_prompt or "",
                "response_format": response_format,
            }
        )
        return next(responses)

    monkeypatch.setattr(service.llm, "complete_required", fake_complete_required)
    caplog.set_level(logging.WARNING)

    records = service.run_opinion_checkpoint(
        simulation_id="session-product",
        checkpoint_kind="baseline",
        subject_summary="Users saw the tool as promising but expensive.",
        agent_context_bundles={
            "agent-0001": {
                "agent_id": "agent-0001",
                "brief": "Persona highlights: {\"planning_area\": \"Bishan\", \"occupation\": \"Founder\"}.",
                "knowledge_digest": "The uploaded document describes a collaboration product for startup teams.",
                "matched_context_nodes": ["pricing"],
            }
        },
        checkpoint_questions=[
            {
                "question": "How interested are you in this product? Rate 1-10.",
                "type": "scale",
                "metric_name": "product_interest",
            },
            {
                "question": "What are the main pain points or problems you see with this product?",
                "type": "open-ended",
                "metric_name": "pain_points",
            },
        ],
        use_case_id="product-market-research",
    )

    assert records[0]["metric_answers"]["product_interest"] == 8.0
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "Product summary:" in str(calls[0]["prompt"])
    assert "product or service concept" in str(calls[0]["prompt"])
    assert "Policy summary:" not in str(calls[0]["prompt"])
    assert "Original invalid output" in str(calls[1]["prompt"])
    assert "Checkpoint attempt failed" in caplog.text
    assert "raw_preview=" in caplog.text


def test_build_context_bundles_use_clean_display_text_in_brief(tmp_path: Path) -> None:
    service = SimulationService(
        Settings(
            simulation_db_path=str(tmp_path / "simulation.db"),
            llm_provider="google",
            llm_model="gemini-2.5-flash-lite",
        )
    )

    bundles = service.build_context_bundles(
        simulation_id="session-product",
        subject_summary="Teachers in Washington want simpler product onboarding.",
        knowledge_artifact={
            "summary": "Teachers in Washington want simpler product onboarding.",
            "entity_nodes": [],
            "relationship_edges": [],
        },
        sampled_personas=[
            {
                "agent_id": "agent-0001",
                "persona": {
                    "display_name": "John Lewis",
                    "planning_area": "Washington",
                    "occupation": "Teacher Or Instructor",
                    "age": 32,
                    "education_level": "9th-12th, No Diploma",
                    "marital_status": "Married",
                },
                "selection_reason": {
                    "matched_facets": ["pricing"],
                    "matched_document_entities": [],
                    "semantic_summary": "The persona cares about clear pricing.",
                },
            }
        ],
    )

    brief = bundles["agent-0001"]["brief"]
    assert "Teacher Or Instructor" in brief
    assert "9th-12th, No Diploma" in brief
    assert "Married" in brief
    assert '{"planning_area"' not in brief
    assert "teacher_or_instructor" not in brief
