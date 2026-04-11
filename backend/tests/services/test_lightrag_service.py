from __future__ import annotations

from pathlib import Path

import miroworld.services.lightrag_service as lightrag_module
from miroworld.config import Settings
from miroworld.services.lightrag_service import LightRAGService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


class _DummyRag:
    async def ainsert(self, *_args, **_kwargs) -> None:
        return None

    async def aquery(self, prompt: str, param=None) -> str:  # noqa: ANN001
        del param
        return f"summary for: {prompt}"


def test_process_document_falls_back_in_live_mode_when_native_graph_is_empty(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _make_settings(tmp_path)
    settings.llm_provider = "google"
    service = LightRAGService(settings)
    service._rag = _DummyRag()

    async def fake_ensure_ready() -> None:
        return None

    async def fake_load_document_native_graph(_rag, _document_id):  # noqa: ANN001
        return None

    async def fake_build_graph_from_text(**_kwargs):  # noqa: ANN002
        return (
            [{"id": "node-1", "label": "Housing Support", "type": "policy"}],
            [{"source": "node-1", "target": "node-2", "type": "affects"}],
        )

    monkeypatch.setattr(service, "ensure_ready", fake_ensure_ready)
    monkeypatch.setattr(lightrag_module, "_load_document_native_graph", fake_load_document_native_graph)
    monkeypatch.setattr(lightrag_module, "_build_graph_from_text", fake_build_graph_from_text)
    monkeypatch.setattr(
        service._config,
        "get_system_prompt_value",
        lambda *args, **kwargs: "Summarize the document.",
    )

    import asyncio

    payload = asyncio.run(
        service.process_document(
            simulation_id="session-1",
            document_text="Paragraph one.\n\nParagraph two.",
            source_path="usa-policy.pdf",
            document_id="doc-1",
            live_mode=True,
        )
    )

    assert payload["graph_origin"] == "fallback_model_extract"
    assert payload["entity_nodes"] == [{"id": "node-1", "label": "Housing Support", "type": "policy"}]
    assert payload["relationship_edges"] == [{"source": "node-1", "target": "node-2", "type": "affects"}]
    assert any("fallback extraction" in log for log in payload["processing_logs"])
    assert any("Live mode accepted fallback graph extraction" in log for log in payload["processing_logs"])
