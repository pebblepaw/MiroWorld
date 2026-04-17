from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from miroworld.config import Settings
from miroworld.models.console import PopulationPreviewRequest
from miroworld.services.console_service import ConsoleService
from miroworld.services.knowledge_stream_service import KnowledgeStreamService
from miroworld.services.lightrag_service import LightRAGService
from miroworld.services.persona_relevance_service import PersonaRelevanceService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def _stub_country_dataset_ready(service: ConsoleService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_ensure_country_ready(country: str) -> str:
        code = str(country).strip().lower()
        if code == "singapore":
            code = "sg"
        return str(tmp_path / f"{code}_nemotron_cc.parquet")

    monkeypatch.setattr(service.country_datasets, "ensure_country_ready", fake_ensure_country_ready)


def _event_names(chunks: list[str]) -> list[str]:
    names: list[str] = []
    for chunk in chunks:
        for line in chunk.splitlines():
            if line.startswith("event: "):
                names.append(line.split(": ", 1)[1])
    return names


def test_knowledge_stream_service_replays_events_in_order(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    stream = KnowledgeStreamService(settings)
    session_id = "session-stream"

    stream.reset(session_id)
    stream.append_events(
        session_id,
        [
            {"event_type": "knowledge_started", "session_id": session_id, "document_count": 1},
            {
                "event_type": "knowledge_document_started",
                "session_id": session_id,
                "document_id": "doc-1",
                "document_index": 1,
                "document_count": 1,
            },
            {
                "event_type": "knowledge_chunk_started",
                "session_id": session_id,
                "document_id": "doc-1",
                "chunk_index": 1,
                "chunk_count": 2,
            },
            {
                "event_type": "knowledge_partial",
                "session_id": session_id,
                "document_id": "doc-1",
                "chunk_index": 1,
                "chunk_count": 2,
                "entity_nodes": [{"id": "node-1", "label": "Transport Subsidy", "type": "policy"}],
                "relationship_edges": [{"source": "node-1", "target": "node-2", "type": "affects"}],
                "total_nodes": 1,
                "total_edges": 1,
            },
            {
                "event_type": "knowledge_chunk_completed",
                "session_id": session_id,
                "document_id": "doc-1",
                "chunk_index": 1,
                "chunk_count": 2,
                "node_delta_count": 1,
                "edge_delta_count": 1,
            },
            {
                "event_type": "knowledge_completed",
                "session_id": session_id,
                "document_count": 1,
                "total_nodes": 1,
                "total_edges": 1,
            },
        ],
    )

    replay = list(stream.sse_iter(session_id))
    state = stream.get_state(session_id)

    assert _event_names(replay) == [
        "knowledge_started",
        "knowledge_document_started",
        "knowledge_chunk_started",
        "knowledge_partial",
        "knowledge_chunk_completed",
        "knowledge_completed",
    ]
    assert state["status"] == "completed"
    assert state["total_nodes"] == 1
    assert state["total_edges"] == 1


def test_knowledge_stream_service_tracks_failure_state(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    stream = KnowledgeStreamService(settings)
    session_id = "session-failed"

    stream.reset(session_id)
    stream.append_events(
        session_id,
        [
            {"event_type": "knowledge_started", "session_id": session_id, "document_count": 1},
            {"event_type": "knowledge_failed", "session_id": session_id, "detail": "model unavailable"},
        ],
    )

    state = stream.get_state(session_id)

    assert state["status"] == "failed"
    assert state["last_error"] == "model unavailable"


def test_console_process_knowledge_publishes_stream_events(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    session_id = "session-stream"
    service.create_session(
        requested_session_id=session_id,
        mode="live",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        api_key="test-key",
    )

    async def fake_process_document(
        self: LightRAGService,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, object]:
        assert simulation_id == session_id
        assert source_path == "policy.txt"
        assert document_id is not None
        assert event_callback is not None
        await event_callback(
            "knowledge_chunk_started",
            {
                "document_id": "doc-1",
                "chunk_index": 1,
                "chunk_count": 2,
            },
        )
        await event_callback(
            "knowledge_partial",
            {
                "document_id": "doc-1",
                "chunk_index": 1,
                "chunk_count": 2,
                "entity_nodes": [{"id": "node-1", "label": "Transport Subsidy", "type": "policy"}],
                "relationship_edges": [{"source": "node-1", "target": "node-2", "type": "affects"}],
                "total_nodes": 1,
                "total_edges": 1,
            },
        )
        await event_callback(
            "knowledge_chunk_completed",
            {
                "document_id": "doc-1",
                "chunk_index": 1,
                "chunk_count": 2,
                "node_delta_count": 1,
                "edge_delta_count": 1,
            },
        )
        return {
            "simulation_id": session_id,
            "document_id": "doc-1",
            "document": {
                "document_id": "doc-1",
                "source_path": "policy.txt",
                "file_name": "policy.txt",
                "file_type": "text/plain",
                "text_length": len(document_text),
                "paragraph_count": 2,
            },
            "summary": "Transport subsidy policy summary for commuters and low-income workers.",
            "guiding_prompt": guiding_prompt,
            "demographic_context": demographic_focus,
            "entity_nodes": [{"id": "node-1", "label": "Transport Subsidy", "type": "policy"}],
            "relationship_edges": [{"source": "node-1", "target": "node-2", "type": "affects"}],
            "entity_type_counts": {"policy": 1},
            "graph_origin": "lightrag_native",
            "processing_logs": ["chunk 1 complete"],
            "demographic_focus_summary": demographic_focus,
        }

    monkeypatch.setattr(LightRAGService, "process_document", fake_process_document)

    payload = asyncio.run(
        service.process_knowledge(
            session_id,
            document_text="Paragraph 1.\n\nParagraph 2.",
            source_path="policy.txt",
        )
    )

    stream = KnowledgeStreamService(settings)
    replay = list(stream.sse_iter(session_id))
    state = stream.get_state(session_id)
    stored_artifact = service.store.get_knowledge_artifact(session_id)

    assert payload["summary"] == "Transport subsidy policy summary for commuters and low-income workers."
    assert stored_artifact is not None
    assert stored_artifact["summary"] == "Transport subsidy policy summary for commuters and low-income workers."
    assert _event_names(replay) == [
        "knowledge_started",
        "knowledge_document_started",
        "knowledge_chunk_started",
        "knowledge_partial",
        "knowledge_chunk_completed",
        "knowledge_completed",
    ]
    assert state["status"] == "completed"
    assert state["current_chunk"] == 1
    assert state["total_chunks"] == 2
    assert state["total_nodes"] == 1
    assert state["total_edges"] == 1


def test_console_process_knowledge_rejects_unusable_policy_summary_on_screen1(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    session_id = "session-screen1-refusal"
    service.create_session(
        requested_session_id=session_id,
        mode="live",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        api_key="test-key",
    )
    service._upsert_session_config(
        session_id,
        {
            "country": "usa",
            "use_case": "public-policy-testing",
        },
    )

    async def fake_process_document(
        self: LightRAGService,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, object]:
        assert simulation_id == session_id
        assert use_case_id == "public-policy-testing"
        return {
            "simulation_id": session_id,
            "document_id": "doc-1",
            "document": {
                "document_id": "doc-1",
                "source_path": "briefing.txt",
                "text_length": len(document_text),
                "paragraph_count": 1,
            },
            "summary": "I am sorry, but I do not have enough information to answer your request.",
            "entity_nodes": [{"id": "node-1", "label": "Press Release", "type": "document"}],
            "relationship_edges": [],
            "entity_type_counts": {"document": 1},
            "processing_logs": ["chunk 1 complete"],
        }

    monkeypatch.setattr(LightRAGService, "process_document", fake_process_document)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            service.process_knowledge(
                session_id,
                document_text="A press release, not a policy proposal.",
                source_path="briefing.txt",
            )
        )

    assert exc_info.value.status_code == 422
    assert "concrete civic or political detail" in str(exc_info.value.detail)

    stream = KnowledgeStreamService(settings)
    replay = list(stream.sse_iter(session_id))
    state = stream.get_state(session_id)

    assert _event_names(replay) == [
        "knowledge_started",
        "knowledge_document_started",
        "knowledge_failed",
    ]
    assert state["status"] == "failed"
    assert "concrete civic or political detail" in str(state["last_error"])
    assert service.store.get_knowledge_artifact(session_id) is None


def test_console_process_knowledge_accepts_broad_political_comparison_summary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    session_id = "session-screen1-political"
    service.create_session(
        requested_session_id=session_id,
        mode="live",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        api_key="test-key",
    )
    service._upsert_session_config(
        session_id,
        {
            "country": "usa",
            "use_case": "public-policy-testing",
        },
    )

    async def fake_process_document(
        self: LightRAGService,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, object]:
        del self, document_text, source_path, document_id, guiding_prompt, demographic_focus, live_mode, event_callback
        assert simulation_id == session_id
        assert use_case_id == "public-policy-testing"
        return {
            "simulation_id": session_id,
            "document_id": "doc-1",
            "document": {
                "document_id": "doc-1",
                "source_path": "comparison.txt",
                "text_length": 120,
                "paragraph_count": 1,
            },
            "summary": (
                "The article compares Trump and Harris on immigration enforcement, border policy, "
                "healthcare costs, and tax priorities for Michigan voters."
            ),
            "entity_nodes": [{"id": "node-1", "label": "Immigration Policy", "type": "policy"}],
            "relationship_edges": [],
            "entity_type_counts": {"policy": 1},
            "processing_logs": ["chunk 1 complete"],
        }

    monkeypatch.setattr(LightRAGService, "process_document", fake_process_document)

    payload = asyncio.run(
        service.process_knowledge(
            session_id,
            document_text="Bridge Michigan comparison article.",
            source_path="comparison.txt",
        )
    )

    assert payload["summary"].startswith("The article compares Trump and Harris")
    assert service.store.get_knowledge_artifact(session_id)["summary"].startswith("The article compares")


def test_console_process_knowledge_accepts_product_news_summary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    session_id = "session-screen1-product"
    service.create_session(
        requested_session_id=session_id,
        mode="live",
        model_provider="google",
        model_name="gemini-2.5-flash-lite",
        api_key="test-key",
    )
    service._upsert_session_config(
        session_id,
        {
            "country": "usa",
            "use_case": "product-market-research",
        },
    )

    async def fake_process_document(
        self: LightRAGService,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, object]:
        del self, document_text, source_path, document_id, guiding_prompt, demographic_focus, live_mode, event_callback
        assert simulation_id == session_id
        assert use_case_id == "product-market-research"
        return {
            "simulation_id": session_id,
            "document_id": "doc-1",
            "document": {
                "document_id": "doc-1",
                "source_path": "electronics.txt",
                "text_length": 180,
                "paragraph_count": 1,
            },
            "summary": (
                "The launch article describes a consumer electronics product with a lower entry price, "
                "battery-life improvements, and new camera features for mobile creators."
            ),
            "entity_nodes": [{"id": "node-1", "label": "Camera Feature", "type": "feature"}],
            "relationship_edges": [],
            "entity_type_counts": {"feature": 1},
            "processing_logs": ["chunk 1 complete"],
        }

    monkeypatch.setattr(LightRAGService, "process_document", fake_process_document)

    payload = asyncio.run(
        service.process_knowledge(
            session_id,
            document_text="Electronics launch article.",
            source_path="electronics.txt",
        )
    )

    assert payload["summary"].startswith("The launch article describes")
    assert service.store.get_knowledge_artifact(session_id)["summary"].startswith("The launch article")


def test_console_process_knowledge_records_runtime_failure_detail(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    _stub_country_dataset_ready(service, monkeypatch, tmp_path)
    session_id = "session-usa-failure"
    service.create_v2_session(
        country="usa",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id=session_id,
    )

    async def fake_process_document(
        self: LightRAGService,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, object]:
        raise HTTPException(status_code=502, detail="USA LightRAG extraction failed: malformed graph payload")

    monkeypatch.setattr(LightRAGService, "process_document", fake_process_document)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            service.process_knowledge(
                session_id,
                document_text="USA policy text",
                source_path="usa-policy.txt",
            )
        )

    state = KnowledgeStreamService(settings).get_state(session_id)

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "USA LightRAG extraction failed: malformed graph payload"
    assert state["status"] == "failed"
    assert state["last_error"] == "USA LightRAG extraction failed: malformed graph payload"


def test_preview_population_surfaces_prior_knowledge_failure(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    _stub_country_dataset_ready(service, monkeypatch, tmp_path)
    session_id = "session-usa-preview"
    service.create_v2_session(
        country="usa",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id=session_id,
    )

    service.knowledge_streams.reset(session_id)
    service.knowledge_streams.append_events(
        session_id,
        [
            {"event_type": "knowledge_started", "session_id": session_id, "document_count": 1},
            {
                "event_type": "knowledge_failed",
                "session_id": session_id,
                "detail": "USA LightRAG extraction failed: malformed graph payload",
            },
        ],
    )

    request = PopulationPreviewRequest(agent_count=10, sample_mode="affected_groups")

    with pytest.raises(HTTPException) as exc_info:
        service.preview_population(session_id, request)

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "USA LightRAG extraction failed: malformed graph payload"


def test_process_uploaded_knowledge_persists_artifact_for_usa_session(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    _stub_country_dataset_ready(service, monkeypatch, tmp_path)
    session_id = "session-usa-upload"
    service.create_v2_session(
        country="usa",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id=session_id,
    )

    class _Upload:
        filename = "usa-policy.pdf"

        async def read(self) -> bytes:
            return b"%PDF-1.4 fake pdf payload"

    async def fake_process_document(
        self: LightRAGService,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, object]:
        assert simulation_id == session_id
        assert live_mode is True
        assert source_path is not None and source_path.endswith("usa-policy.pdf")
        return {
            "simulation_id": session_id,
            "document_id": "doc-usa-1",
            "document": {
                "document_id": "doc-usa-1",
                "source_path": source_path,
                "file_name": "usa-policy.pdf",
                "file_type": "application/pdf",
                "text_length": len(document_text),
                "paragraph_count": 1,
            },
            "summary": "USA policy summary",
            "guiding_prompt": guiding_prompt,
            "demographic_context": demographic_focus,
            "entity_nodes": [{"id": "node-usa-1", "label": "Housing Support", "type": "policy"}],
            "relationship_edges": [{"source": "node-usa-1", "target": "node-usa-2", "type": "affects"}],
            "entity_type_counts": {"policy": 1},
            "graph_origin": "lightrag_native",
            "processing_logs": ["ingested usa upload"],
            "demographic_focus_summary": demographic_focus,
        }

    monkeypatch.setattr("miroworld.services.console_service.extract_document_text", lambda *_: "USA housing policy text")
    monkeypatch.setattr(LightRAGService, "process_document", fake_process_document)

    payload = asyncio.run(
        service.process_uploaded_knowledge(
            session_id,
            upload=_Upload(),
        )
    )

    stored_artifact = service.store.get_knowledge_artifact(session_id)

    assert payload["summary"] == "USA policy summary"
    assert stored_artifact is not None
    assert stored_artifact["summary"] == "USA policy summary"
    assert stored_artifact["document"]["source_path"].endswith("usa-policy.pdf")


def test_process_knowledge_clears_prior_artifacts_and_stream_state(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    _stub_country_dataset_ready(service, monkeypatch, tmp_path)
    session_id = "session-reset"
    service.create_v2_session(
        country="usa",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id=session_id,
    )

    service.store.save_knowledge_artifact(session_id, {"session_id": session_id, "summary": "old summary"})
    service.store.save_population_artifact(session_id, {"session_id": session_id, "sample_count": 99})
    service.store.save_simulation_state_snapshot(session_id, {"session_id": session_id, "status": "running"})
    service.store.save_report_state(session_id, {"session_id": session_id, "status": "running"})
    service.store.replace_checkpoint_records(
        session_id,
        "baseline",
        [{"agent_id": "agent-old", "checkpoint_kind": "baseline"}],
    )
    service.store.append_interaction_transcript(session_id, "group_chat", "user", "stale transcript")
    service.store.save_memory_sync_state(session_id, 10, 5, last_checkpoint_id=3)
    service.knowledge_streams.append_events(
        session_id,
        [{"event_type": "knowledge_started", "session_id": session_id, "document_count": 1}],
    )

    async def fake_process_document(
        self: LightRAGService,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, object]:
        assert simulation_id == session_id
        assert live_mode is True
        assert source_path == "policy.txt"
        assert event_callback is not None
        await event_callback(
            "knowledge_partial",
            {
                "document_id": "doc-new",
                "chunk_index": 1,
                "chunk_count": 1,
                "entity_nodes": [{"id": "node-new", "label": "Policy Change", "type": "policy"}],
                "relationship_edges": [],
                "total_nodes": 1,
                "total_edges": 0,
            },
        )
        return {
            "simulation_id": session_id,
            "document_id": "doc-new",
            "document": {
                "document_id": "doc-new",
                "source_path": source_path,
                "file_name": "policy.txt",
                "file_type": "text/plain",
                "text_length": len(document_text),
                "paragraph_count": 1,
            },
            "summary": "Fresh policy summary covering a new housing subsidy for Michigan renters.",
            "guiding_prompt": guiding_prompt,
            "demographic_context": demographic_focus,
            "entity_nodes": [{"id": "node-new", "label": "Policy Change", "type": "policy"}],
            "relationship_edges": [],
            "entity_type_counts": {"policy": 1},
            "graph_origin": "lightrag_native",
            "processing_logs": ["rebuilt knowledge"],
            "demographic_focus_summary": demographic_focus,
        }

    monkeypatch.setattr(LightRAGService, "process_document", fake_process_document)

    payload = asyncio.run(
        service.process_knowledge(
            session_id,
            document_text="Updated policy text.",
            source_path="policy.txt",
        )
    )

    assert payload["summary"] == "Fresh policy summary covering a new housing subsidy for Michigan renters."
    assert (
        service.store.get_knowledge_artifact(session_id)["summary"]
        == "Fresh policy summary covering a new housing subsidy for Michigan renters."
    )
    assert service.store.get_population_artifact(session_id) is None
    assert service.store.get_simulation_state_snapshot(session_id) is None
    assert service.store.get_report_state(session_id) is None
    assert service.store.list_checkpoint_records(session_id) == []
    assert service.store.get_interaction_transcripts(session_id) == []
    assert service.store.get_memory_sync_state(session_id) is None

    state = service.knowledge_streams.get_state(session_id)
    assert state["status"] == "completed"
    assert state["document_count"] == 1
    assert state["total_nodes"] == 1
    assert state["total_edges"] == 0


def test_preview_population_uses_country_dataset_path_and_clears_downstream_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    _stub_country_dataset_ready(service, monkeypatch, tmp_path)
    session_id = "session-preview"
    service.create_v2_session(
        country="usa",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id=session_id,
    )

    service.store.save_knowledge_artifact(
        session_id,
        {
            "session_id": session_id,
            "summary": "USA policy summary",
            "entity_nodes": [],
            "relationship_edges": [],
        },
    )
    service.store.save_population_artifact(session_id, {"session_id": session_id, "sample_count": 8})
    service.store.save_simulation_state_snapshot(session_id, {"session_id": session_id, "status": "running"})
    service.store.save_report_state(session_id, {"session_id": session_id, "status": "running"})
    service.store.replace_checkpoint_records(
        session_id,
        "baseline",
        [{"agent_id": "agent-old", "checkpoint_kind": "baseline"}],
    )
    service.store.append_interaction_transcript(session_id, "group_chat", "user", "stale transcript")
    service.store.save_memory_sync_state(session_id, 15, 7, last_checkpoint_id=4)

    captured: dict[str, object] = {}

    def fake_query_candidates(*, dataset_path: str | None = None, **_kwargs) -> list[dict[str, object]]:
        captured["dataset_path"] = dataset_path
        return [
            {
                "state": "California",
                "age": 32,
                "sex": "female",
                "occupation": "Teacher",
                "industry": "Education",
            }
        ]

    def fake_build_population_artifact(
        self: PersonaRelevanceService,
        session_id_arg: str,
        *,
        personas: list[dict[str, object]],
        knowledge_artifact: dict[str, object],
        filters: dict[str, object],
        agent_count: int,
        sample_mode: str = "affected_groups",
        seed: int | None = None,
        parsed_sampling_instructions: dict[str, object] | None = None,
        live_mode: bool = False,
        country: str | None = None,
    ) -> dict[str, object]:
        captured["country"] = country
        captured["personas"] = personas
        return {
            "session_id": session_id_arg,
            "candidate_count": len(personas),
            "sample_count": 1,
            "sample_mode": sample_mode,
            "sample_seed": seed or 0,
            "geography_field": "state",
            "parsed_sampling_instructions": parsed_sampling_instructions or {},
            "coverage": {
                "planning_areas": ["California"],
                "geographies": ["California"],
                "geography_field": "state",
                "age_buckets": {"30-39": 1},
                "sex_distribution": {"female": 1},
            },
            "sampled_personas": [
                {
                    "agent_id": "agent-0001",
                    "display_name": "Teacher (California)",
                    "persona": {
                        "state": "California",
                        "planning_area": "California",
                        "geography_field": "state",
                        "geography_value": "California",
                    },
                    "selection_reason": {"score": 0.9},
                }
            ],
            "agent_graph": {
                "nodes": [
                    {
                        "id": "agent-0001",
                        "label": "Teacher (California)",
                        "subtitle": "California · Teacher",
                        "planning_area": "California",
                        "geography_field": "state",
                        "geography_value": "California",
                    }
                ],
                "links": [],
            },
            "representativeness": {
                "status": "balanced",
                "planning_area_distribution": {"California": 1},
                "geography_distribution": {"California": 1},
                "state_distribution": {"California": 1},
                "sex_distribution": {"female": 1},
                "geography_field": "state",
            },
            "selection_diagnostics": {"candidate_count": len(personas)},
        }

    monkeypatch.setattr(service.sampler, "query_candidates", fake_query_candidates)
    monkeypatch.setattr(PersonaRelevanceService, "build_population_artifact", fake_build_population_artifact)

    artifact = service.preview_population(
        session_id,
        PopulationPreviewRequest(agent_count=10, sample_mode="affected_groups", seed=42),
    )

    selected_dataset = str(captured["dataset_path"])
    assert selected_dataset.endswith("usa_nemotron_cc.parquet") or "/backend/.cache/nemotron/data/train-" in selected_dataset
    assert captured["country"] == "usa"
    assert artifact["coverage"]["planning_areas"] == ["California"]
    assert artifact["representativeness"]["state_distribution"] == {"California": 1}
    assert service.store.get_population_artifact(session_id) == artifact
    assert service.store.get_simulation_state_snapshot(session_id) is None
    assert service.store.get_report_state(session_id) is None
    assert service.store.list_checkpoint_records(session_id) == []
    assert service.store.get_interaction_transcripts(session_id) == []
    assert service.store.get_memory_sync_state(session_id) is None


def test_update_v2_session_config_clears_derived_artifacts_when_country_changes(tmp_path: Path, monkeypatch) -> None:
    settings = _make_settings(tmp_path)
    service = ConsoleService(settings)
    _stub_country_dataset_ready(service, monkeypatch, tmp_path)
    session_id = "session-config-reset"
    service.create_v2_session(
        country="singapore",
        use_case="public-policy-testing",
        provider="google",
        model="gemini-2.5-flash-lite",
        api_key="test-key",
        mode="live",
        session_id=session_id,
    )

    service.store.save_knowledge_artifact(session_id, {"session_id": session_id, "summary": "old summary"})
    service.store.save_population_artifact(session_id, {"session_id": session_id, "sample_count": 5})
    service.store.save_simulation_state_snapshot(session_id, {"session_id": session_id, "status": "running"})
    service.store.save_report_state(session_id, {"session_id": session_id, "status": "running"})
    service.store.replace_checkpoint_records(
        session_id,
        "baseline",
        [{"agent_id": "agent-old", "checkpoint_kind": "baseline"}],
    )
    service.store.append_interaction_transcript(session_id, "group_chat", "user", "stale transcript")
    service.store.save_memory_sync_state(session_id, 6, 4, last_checkpoint_id=2)

    service.update_v2_session_config(session_id, country="usa", use_case="public-policy-testing")

    assert service.store.get_knowledge_artifact(session_id) is None
    assert service.store.get_population_artifact(session_id) is None
    assert service.store.get_simulation_state_snapshot(session_id) is None
    assert service.store.get_report_state(session_id) is None
    assert service.store.list_checkpoint_records(session_id) == []
    assert service.store.get_interaction_transcripts(session_id) == []
    assert service.store.get_memory_sync_state(session_id) is None
    assert service.knowledge_streams.get_state(session_id)["status"] == "idle"
