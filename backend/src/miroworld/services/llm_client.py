from __future__ import annotations

from typing import Any

from openai import OpenAI

from miroworld.config import Settings
from miroworld.services.embedding_fallback_service import run_with_embedding_model_fallback
from miroworld.services.model_provider_service import ResolvedModelSelection, resolve_model_selection


class GeminiChatClient:
    def __init__(self, settings: Settings, model_overrides: dict[str, Any] | None = None):
        self._settings = settings
        self._selection: ResolvedModelSelection = resolve_model_selection(settings, **(model_overrides or {}))
        api_key = self._selection.api_key
        self._client = None
        if api_key:
            self._client = OpenAI(
                api_key=api_key,
                base_url=self._selection.base_url,
            )

    def is_enabled(self) -> bool:
        return self._client is not None

    @property
    def provider(self) -> str:
        return self._selection.provider

    @property
    def model_name(self) -> str:
        return self._selection.model_name

    @property
    def embed_model_name(self) -> str:
        return self._selection.embed_model_name

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        return self.complete_required(prompt, system_prompt=system_prompt)

    def _build_messages(self, prompt: str, system_prompt: str | None = None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _require_client(self) -> OpenAI:
        if not self._client:
            raise RuntimeError(
                f"LLM provider '{self._selection.provider}' requires an API key configuration before this action can run."
            )
        return self._client

    def complete_with_metadata(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = self._require_client()
        messages = self._build_messages(prompt, system_prompt=system_prompt)
        request: dict[str, Any] = {
            "model": self._selection.model_name,
            "messages": messages,
            "temperature": 0.3,
            "timeout": self._selection.timeout_seconds,
        }
        if response_format is not None:
            request["response_format"] = response_format
        try:
            response = client.chat.completions.create(**request)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "LLM request failed for "
                f"provider '{self._selection.provider}' "
                f"model '{self._selection.model_name}' "
                f"base_url '{self._selection.base_url}' "
                f"timeout_seconds={self._selection.timeout_seconds}: {exc}"
            ) from exc

        content = response.choices[0].message.content or ""
        if not content.strip():
            raise RuntimeError(
                f"LLM provider '{self._selection.provider}' model '{self._selection.model_name}' returned an empty response."
            )

        return {
            "provider": self._selection.provider,
            "model_name": self._selection.model_name,
            "content": content,
        }

    def complete_required(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload = self.complete_with_metadata(
            prompt,
            system_prompt=system_prompt,
            response_format=response_format,
        )
        return str(payload["content"])


class GeminiEmbeddingClient:
    def __init__(self, settings: Settings, model_overrides: dict[str, Any] | None = None):
        self._settings = settings
        self._selection: ResolvedModelSelection = resolve_model_selection(settings, **(model_overrides or {}))
        api_key = self._selection.api_key
        self._client = None
        if api_key:
            self._client = OpenAI(
                api_key=api_key,
                base_url=self._selection.base_url,
            )

    def is_enabled(self) -> bool:
        return self._client is not None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self._client:
            raise RuntimeError(
                f"Embeddings require an API key for provider '{self._selection.provider}'."
            )
        if not texts:
            return []

        current_model = self._selection.embed_model_name
        try:
            resolved_model_name, response = run_with_embedding_model_fallback(
                self._settings,
                provider=self._selection.provider,
                preferred_model=current_model,
                runner=lambda model_name: self._client.embeddings.create(
                    model=model_name,
                    input=texts,
                    timeout=self._selection.timeout_seconds,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Embedding request failed for "
                f"provider '{self._selection.provider}' "
                f"model '{current_model}' "
                f"base_url '{self._selection.base_url}' "
                f"timeout_seconds={self._selection.timeout_seconds}: {exc}"
            ) from exc

        self._selection.embed_model_name = resolved_model_name
        return [list(item.embedding) for item in response.data]
