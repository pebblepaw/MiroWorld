from __future__ import annotations

import asyncio
from pathlib import Path

from miroworld.config import Settings
from miroworld.services.console_service import ConsoleService
from miroworld.services.knowledge_stream_service import KnowledgeStreamService
from miroworld.services.lightrag_service import LightRAGService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


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
            "summary": "Transport subsidy summary",
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

    assert payload["summary"] == "Transport subsidy summary"
    assert stored_artifact is not None
    assert stored_artifact["summary"] == "Transport subsidy summary"
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
