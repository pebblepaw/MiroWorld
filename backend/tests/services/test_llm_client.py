from __future__ import annotations

from types import SimpleNamespace

import httpx
from openai import RateLimitError

import miroworld.services.llm_client as llm_client_module
from miroworld.config import Settings
from miroworld.services.llm_client import GeminiEmbeddingClient


def _rate_limit_error(message: str = "rate limit exceeded") -> RateLimitError:
    request = httpx.Request(
        "POST",
        "https://generativelanguage.googleapis.com/v1beta/openai/embeddings",
    )
    response = httpx.Response(429, request=request)
    return RateLimitError(message, response=response, body={"error": {"message": message}})


def test_gemini_embedding_client_falls_back_to_secondary_google_model_on_rate_limit(monkeypatch) -> None:
    attempted_models: list[str] = []

    class _FakeEmbeddingsApi:
        def create(self, *, model: str, input: list[str], timeout: int):  # noqa: A002
            attempted_models.append(model)
            if model == "gemini-embedding-001":
                raise _rate_limit_error()
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.11, 0.22, 0.33]) for _ in input]
            )

    class _FakeOpenAIClient:
        def __init__(self) -> None:
            self.embeddings = _FakeEmbeddingsApi()

    monkeypatch.setattr(
        llm_client_module,
        "OpenAI",
        lambda api_key, base_url: _FakeOpenAIClient(),
    )

    settings = Settings(
        llm_provider="google",
        llm_model="gemini-2.5-flash-lite",
        llm_embed_model="gemini-embedding-001",
        llm_api_key="test-google-key",
        llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        google_fallback_embed_models="gemini-embedding-2-preview",
    )

    client = GeminiEmbeddingClient(settings)

    embeddings = client.embed_texts(["policy summary"])

    assert attempted_models == ["gemini-embedding-001", "gemini-embedding-2-preview"]
    assert embeddings == [[0.11, 0.22, 0.33]]
