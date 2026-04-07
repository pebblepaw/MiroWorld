from types import SimpleNamespace

from mckainsey.config import Settings
from mckainsey.services.llm_client import GeminiChatClient, GeminiEmbeddingClient


def test_gemini_chat_client_uses_configured_timeout(tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="google",
        llm_api_key="test-key",
        llm_timeout_seconds=13,
    )
    client = GeminiChatClient(settings)

    recorded: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            recorded.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
            )

    client._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    response = client.complete_required("parse this", system_prompt="json only")

    assert response == '{"ok": true}'
    assert recorded["timeout"] == 13


def test_gemini_embedding_client_uses_configured_timeout(tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="google",
        llm_api_key="test-key",
        llm_timeout_seconds=17,
    )
    client = GeminiEmbeddingClient(settings)

    recorded: dict[str, object] = {}

    class FakeEmbeddings:
        def create(self, **kwargs):
            recorded.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2]) for _ in kwargs["input"]])

    client._client = SimpleNamespace(embeddings=FakeEmbeddings())

    vectors = client.embed_texts(["hello"])

    assert vectors == [[0.1, 0.2]]
    assert recorded["timeout"] == 17


def test_ollama_chat_client_uses_ollama_specific_timeout(tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "sim.db"),
        llm_provider="ollama",
        llm_timeout_seconds=20,
        ollama_llm_timeout_seconds=95,
    )
    client = GeminiChatClient(settings)

    recorded: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs):
            recorded.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
            )

    client._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    response = client.complete_required("parse this", system_prompt="json only")

    assert response == '{"ok": true}'
    assert recorded["timeout"] == 95
