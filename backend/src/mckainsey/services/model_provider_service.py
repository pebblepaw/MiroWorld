from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse, urlunparse
from urllib.request import Request, urlopen

from openai import OpenAI

from mckainsey.config import Settings


SUPPORTED_PROVIDERS = ("google", "openrouter", "openai", "ollama")


@dataclass
class ResolvedModelSelection:
    provider: str
    model_name: str
    embed_model_name: str
    api_key: str | None
    base_url: str
    timeout_seconds: int

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key)


def normalize_provider(provider: str | None) -> str:
    normalized = str(provider or "ollama").strip().lower()
    if normalized in {"gemini", "google-gemini"}:
        return "google"
    if normalized not in SUPPORTED_PROVIDERS:
        return "ollama"
    return normalized


def normalize_base_url(base_url: str) -> str:
    cleaned = base_url.strip()
    if not cleaned.endswith("/"):
        cleaned = f"{cleaned}/"
    return cleaned


def mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def resolve_model_selection(
    settings: Settings,
    *,
    provider: str | None = None,
    model_name: str | None = None,
    embed_model_name: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModelSelection:
    resolved_provider = normalize_provider(provider or settings.llm_provider)
    resolved_model = (model_name or settings.default_model_for_provider(resolved_provider)).strip()
    resolved_embed_model = (embed_model_name or settings.default_embed_model_for_provider(resolved_provider)).strip()
    resolved_base_url = normalize_base_url(base_url or settings.default_base_url_for_provider(resolved_provider))
    resolved_api_key = (api_key or settings.resolved_key_for_provider(resolved_provider) or None)

    if resolved_provider == "ollama" and not resolved_api_key:
        resolved_api_key = "ollama"

    timeout_seconds = _resolve_timeout_seconds(settings, provider=resolved_provider)

    return ResolvedModelSelection(
        provider=resolved_provider,
        model_name=resolved_model,
        embed_model_name=resolved_embed_model,
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        timeout_seconds=timeout_seconds,
    )


def _resolve_timeout_seconds(settings: Settings, *, provider: str) -> int:
    if provider == "ollama":
        return max(5, int(settings.ollama_llm_timeout_seconds))
    return max(5, int(settings.llm_timeout_seconds))


def selection_to_settings_update(selection: ResolvedModelSelection) -> dict[str, Any]:
    return {
        "llm_provider": selection.provider,
        "llm_model": selection.model_name,
        "llm_embed_model": selection.embed_model_name,
        "llm_base_url": selection.base_url,
        "llm_timeout_seconds": selection.timeout_seconds,
        "gemini_model": selection.model_name,
        "gemini_embed_model": selection.embed_model_name,
        "gemini_openai_base_url": selection.base_url,
        "gemini_timeout_seconds": selection.timeout_seconds,
        "gemini_api_key": selection.api_key,
        "gemini_api": None,
    }


def provider_catalog(settings: Settings) -> list[dict[str, Any]]:
    providers = []
    for provider in SUPPORTED_PROVIDERS:
        providers.append(
            {
                "id": provider,
                "label": {
                    "google": "Google",
                    "openrouter": "OpenRouter",
                    "openai": "OpenAI",
                    "ollama": "Ollama",
                }[provider],
                "default_model": settings.default_model_for_provider(provider),
                "default_embed_model": settings.default_embed_model_for_provider(provider),
                "default_base_url": settings.default_base_url_for_provider(provider),
                "requires_api_key": provider in {"google", "openai", "openrouter"},
            }
        )
    return providers


def list_models_for_provider(
    settings: Settings,
    *,
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> list[dict[str, Any]]:
    resolved = resolve_model_selection(
        settings,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
    )

    if resolved.provider == "google":
        return _list_google_models(resolved)
    if resolved.provider == "ollama":
        return _list_ollama_models(resolved)
    return _list_openai_compatible_models(resolved)


def ensure_ollama_models_available(settings: Settings, selection: ResolvedModelSelection) -> None:
    if selection.provider != "ollama":
        return

    available = {_canonical_ollama_model_name(model["id"]) for model in _list_ollama_models(selection)}
    required = [selection.model_name, selection.embed_model_name]
    for model_name in required:
        if _canonical_ollama_model_name(model_name) in available:
            continue
        if not settings.llm_auto_pull_ollama_models:
            raise RuntimeError(
                f"Required Ollama model '{model_name}' is not installed. Run: ollama pull {model_name}"
            )
        _pull_ollama_model(selection, model_name)

    refreshed = {_canonical_ollama_model_name(model["id"]) for model in _list_ollama_models(selection)}
    missing = [
        model_name
        for model_name in required
        if _canonical_ollama_model_name(model_name) not in refreshed
    ]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(f"Ollama model pull did not complete for: {missing_text}")


def _list_openai_compatible_models(selection: ResolvedModelSelection) -> list[dict[str, Any]]:
    if not selection.api_key:
        raise RuntimeError(f"API key is required for provider '{selection.provider}'.")

    try:
        client = OpenAI(api_key=selection.api_key, base_url=selection.base_url)
        result = client.models.list()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Unable to list models for provider '{selection.provider}': {exc}") from exc

    models: list[dict[str, Any]] = []
    for item in result.data:
        model_id = str(item.id)
        if not _is_chat_model_candidate(model_id):
            continue
        models.append({"id": model_id, "label": model_id})

    models.sort(key=lambda row: row["id"])
    return models


def _list_google_models(selection: ResolvedModelSelection) -> list[dict[str, Any]]:
    if not selection.api_key:
        raise RuntimeError("API key is required for provider 'google'.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={quote(selection.api_key)}"
    request = Request(url=url, method="GET")

    try:
        with urlopen(request, timeout=selection.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Google model listing failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Google model listing failed: {exc}") from exc

    models: list[dict[str, Any]] = []
    for item in payload.get("models", []):
        methods = set(item.get("supportedGenerationMethods", []))
        if "generateContent" not in methods and "generateText" not in methods:
            continue
        raw_name = str(item.get("name", ""))
        model_id = raw_name.split("/", 1)[-1]
        if not _is_chat_model_candidate(model_id):
            continue
        models.append({"id": model_id, "label": model_id})

    models.sort(key=lambda row: row["id"])
    return models


def _list_ollama_models(selection: ResolvedModelSelection) -> list[dict[str, Any]]:
    api_root = _ollama_api_root(selection.base_url)
    request = Request(url=f"{api_root}/api/tags", method="GET")

    try:
        with urlopen(request, timeout=selection.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Ollama model listing failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Ollama model listing failed: {exc}") from exc

    models: list[dict[str, Any]] = []
    for item in payload.get("models", []):
        model_id = str(item.get("name") or item.get("model") or "").strip()
        if not model_id:
            continue
        models.append({"id": model_id, "label": model_id})

    models.sort(key=lambda row: row["id"])
    return models


def _pull_ollama_model(selection: ResolvedModelSelection, model_name: str) -> None:
    api_root = _ollama_api_root(selection.base_url)
    payload = json.dumps({"model": model_name, "stream": False}).encode("utf-8")
    request = Request(
        url=f"{api_root}/api/pull",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=payload,
    )

    try:
        with urlopen(request, timeout=selection.timeout_seconds * 30) as response:
            _ = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Ollama pull failed for '{model_name}' ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Ollama pull failed for '{model_name}': {exc}") from exc


def _is_chat_model_candidate(model_id: str) -> bool:
    lowered = model_id.lower()
    blocked_tokens = ("embedding", "whisper", "tts", "audio", "moderation", "image", "dall")
    return not any(token in lowered for token in blocked_tokens)


def _ollama_api_root(base_url: str) -> str:
    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[: -len("/v1")]
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")).rstrip("/")


def _canonical_ollama_model_name(model_name: str) -> str:
    cleaned = model_name.strip()
    if ":" not in cleaned:
        return cleaned
    repository, tag = cleaned.rsplit(":", 1)
    if tag == "latest":
        return repository
    return cleaned
