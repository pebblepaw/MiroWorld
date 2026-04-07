from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace


def test_graphiti_service_imports_without_optional_graphiti_packages():
    module = importlib.import_module("mckainsey.services.graphiti_service")
    assert hasattr(module, "GraphitiService")
    assert isinstance(module.GraphitiService.is_available(), bool)


def test_graphiti_service_initializes_provider_specific_client_and_wraps_calls(monkeypatch):
    module = importlib.import_module("mckainsey.services.graphiti_service")

    captured = {}

    class FakeLLMConfig:
        def __init__(self, **kwargs):
            captured["llm_config"] = kwargs

    class FakeGeminiClient:
        def __init__(self, config):
            captured["provider"] = "gemini"
            captured["client_config"] = config

    class FakeGraphiti:
        def __init__(self, url, graph_name, password, llm_client):
            captured["graphiti_init"] = (url, graph_name, password, llm_client)
            self.calls = []

        async def build_indices_and_constraints(self):
            self.calls.append("build")

        async def add_episode(self, **kwargs):
            self.calls.append(("add_episode", kwargs))

        async def search(self, **kwargs):
            self.calls.append(("search", kwargs))
            return [SimpleNamespace(fact="agent memory", valid_at="2026-04-06T00:00:00Z", score=0.9)]

        async def close(self):
            self.calls.append("close")

    monkeypatch.setattr(module, "LLMConfig", FakeLLMConfig)
    monkeypatch.setattr(module, "GeminiClient", FakeGeminiClient)
    monkeypatch.setattr(module, "OpenAIClient", FakeGeminiClient)
    monkeypatch.setattr(module, "Graphiti", FakeGraphiti)

    service = module.GraphitiService(
        {
            "session_id": "session-1",
            "provider": "gemini",
            "api_key": "test-key",
            "model": "gemini-2.0-flash",
        }
    )

    asyncio.run(service.initialize())
    asyncio.run(service.add_agent_memory("agent-1", "hello world", 2, "2026-04-06T00:00:00Z"))
    asyncio.run(service.add_opinion_checkpoint("agent-1", 7.5, 2, "2026-04-06T00:00:00Z"))
    result = asyncio.run(service.search_agent_context("agent-1", "hello", limit=1))
    asyncio.run(service.cleanup())

    assert captured["graphiti_init"][0] == "bolt://localhost:6379"
    assert captured["graphiti_init"][1] == "default"
    assert captured["llm_config"]["api_key"] == "test-key"
    assert captured["llm_config"]["model"] == "gemini-2.0-flash"
    assert result == [{"content": "agent memory", "timestamp": "2026-04-06T00:00:00Z", "confidence": 0.9}]


def test_graphiti_service_uses_openai_compatible_client_for_ollama(monkeypatch):
    module = importlib.import_module("mckainsey.services.graphiti_service")

    seen = {}

    class FakeLLMConfig:
        def __init__(self, **kwargs):
            seen["llm_config"] = kwargs

    class FakeOpenAIClient:
        def __init__(self, config):
            seen["client"] = config

    class FakeGraphiti:
        def __init__(self, *args, **kwargs):
            seen["graphiti_kwargs"] = kwargs

        async def build_indices_and_constraints(self):
            return None

    monkeypatch.setattr(module, "LLMConfig", FakeLLMConfig)
    monkeypatch.setattr(module, "OpenAIClient", FakeOpenAIClient)
    monkeypatch.setattr(module, "Graphiti", FakeGraphiti)

    service = module.GraphitiService({"session_id": "s-2", "provider": "ollama", "api_key": "", "model": "llama3.2"})

    asyncio.run(service.initialize())

    assert seen["llm_config"]["api_key"] == "ollama"
    assert seen["llm_config"]["base_url"] == "http://host.docker.internal:11434/v1"


def test_graphiti_service_search_without_initialize_raises_clear_error():
    module = importlib.import_module("mckainsey.services.graphiti_service")
    service = module.GraphitiService({"session_id": "s-3", "provider": "gemini", "api_key": "key", "model": "gemini-2.0-flash"})

    async def _run():
        await service.search_agent_context("agent-1", "hello", limit=2)

    try:
        asyncio.run(_run())
    except RuntimeError as exc:
        assert "initialize" in str(exc).lower()
    else:
        raise AssertionError("Expected search without initialize to fail")
