from __future__ import annotations

from mckainsey.config import Settings
from mckainsey.services.model_provider_service import resolve_model_selection, selection_to_settings_update


def test_resolve_model_selection_uses_active_runtime_settings_when_no_overrides() -> None:
    settings = Settings(
        llm_provider="openrouter",
        llm_model="openai/gpt-oss-20b:free",
        llm_embed_model="openai/text-embedding-3-small",
        llm_base_url="https://openrouter.ai/api/v1/",
        llm_api_key="runtime-session-key",
    )

    selection = resolve_model_selection(settings)

    assert selection.provider == "openrouter"
    assert selection.model_name == "openai/gpt-oss-20b:free"
    assert selection.embed_model_name == "openai/text-embedding-3-small"
    assert selection.base_url == "https://openrouter.ai/api/v1/"
    assert selection.api_key == "runtime-session-key"


def test_selection_to_settings_update_preserves_openrouter_session_override() -> None:
    settings = Settings()
    selection = resolve_model_selection(
        settings,
        provider="openrouter",
        model_name="openai/gpt-oss-20b:free",
        embed_model_name="openai/text-embedding-3-small",
        api_key="session-openrouter-key",
        base_url="https://openrouter.ai/api/v1/",
    )

    runtime_settings = settings.model_copy(update=selection_to_settings_update(selection))
    runtime_selection = resolve_model_selection(runtime_settings)

    assert runtime_selection.provider == "openrouter"
    assert runtime_selection.model_name == "openai/gpt-oss-20b:free"
    assert runtime_selection.embed_model_name == "openai/text-embedding-3-small"
    assert runtime_selection.base_url == "https://openrouter.ai/api/v1/"
    assert runtime_selection.api_key == "session-openrouter-key"


def test_resolve_model_selection_uses_provider_defaults_when_switching_provider() -> None:
    settings = Settings(
        llm_provider="google",
        llm_model="gemini-2.5-flash-lite",
        llm_embed_model="gemini-embedding-001",
        llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    selection = resolve_model_selection(settings, provider="openrouter")

    assert selection.provider == "openrouter"
    assert selection.model_name == settings.openrouter_default_model
    assert selection.embed_model_name == settings.openrouter_default_embed_model
    assert selection.base_url == settings.openrouter_default_base_url