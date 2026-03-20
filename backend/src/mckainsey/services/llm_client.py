from __future__ import annotations

from openai import OpenAI

from mckainsey.config import Settings


class GeminiChatClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        api_key = settings.resolved_gemini_key
        self._client = None
        if api_key:
            self._client = OpenAI(
                api_key=api_key,
                base_url=settings.gemini_openai_base_url,
            )

    def is_enabled(self) -> bool:
        return self._client is not None

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self._client:
            return "LLM unavailable. Returning deterministic fallback response."

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self._settings.gemini_model,
                messages=messages,
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception:  # noqa: BLE001
            return "LLM quota/availability fallback: deterministic response path used."

    def complete_required(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self._client:
            raise RuntimeError("Gemini is required for this action but no GEMINI_API_KEY/GEMINI_API is configured.")

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self._settings.gemini_model,
                messages=messages,
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        content = response.choices[0].message.content or ""
        if not content.strip():
            raise RuntimeError("Gemini returned an empty response.")
        return content
