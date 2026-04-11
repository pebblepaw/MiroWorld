from __future__ import annotations

import asyncio
from pathlib import Path

import miroworld.services.lightrag_service as lightrag_module
import numpy as np
import httpx
from openai import RateLimitError
from tenacity import Future, RetryError

from miroworld.config import Settings
from miroworld.services.lightrag_service import LightRAGService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def _rate_limit_error(message: str = "rate limit exceeded") -> RateLimitError:
    request = httpx.Request(
        "POST",
        "https://generativelanguage.googleapis.com/v1beta/openai/embeddings",
    )
    response = httpx.Response(429, request=request)
    return RateLimitError(message, response=response, body={"error": {"message": message}})


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


def test_ensure_ready_falls_back_to_secondary_google_embedding_model_on_rate_limit(
    tmp_path: Path, monkeypatch
) -> None:
    settings = Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        llm_provider="google",
        llm_model="gemini-2.5-flash-lite",
        llm_embed_model="gemini-embedding-001",
        llm_api_key="test-google-key",
        llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        google_fallback_embed_models="gemini-embedding-2-preview",
    )
    service = LightRAGService(settings)
    attempted_models: list[str] = []

    async def fake_embed(
        texts: list[str],
        *,
        model: str,
        api_key: str,
        base_url: str,
    ) -> np.ndarray:
        del texts, api_key, base_url
        attempted_models.append(model)
        if model == "gemini-embedding-001":
            last_attempt = Future(1)
            last_attempt.set_exception(_rate_limit_error())
            raise RetryError(last_attempt)
        return np.zeros((1, 3))

    class _FakeLightRAG:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def initialize_storages(self) -> None:
            return None

    async def fake_initialize_pipeline_status() -> None:
        return None

    monkeypatch.setattr(lightrag_module.openai_embed, "func", fake_embed)
    monkeypatch.setattr(lightrag_module, "LightRAG", _FakeLightRAG)
    monkeypatch.setattr(lightrag_module, "initialize_pipeline_status", fake_initialize_pipeline_status)

    asyncio.run(service.ensure_ready())

    assert attempted_models == ["gemini-embedding-001", "gemini-embedding-2-preview"]
    assert service._rag is not None
