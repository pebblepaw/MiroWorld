from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from miroworld.services.token_tracker import TokenTracker


GenerateFn = Callable[[dict[str, Any]], dict[str, Any] | str]


class CachingLLMClient:
    """Provider-aware wrapper that tracks token usage with optional context cache metadata."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        generate_fn: GenerateFn | None = None,
    ) -> None:
        self.provider = str(provider or "").strip().lower()
        self.model = str(model or "").strip() or "gemini-2.0-flash"
        self._generate_fn = generate_fn
        self._token_tracker = TokenTracker(model=self.model)
        self._cache_id: str | None = None
        self._cached_context: str | None = None
        self._cache_expires_at: float | None = None

    def _supports_context_cache(self) -> bool:
        return self.provider in {"google", "gemini"}

    def create_simulation_cache(
        self,
        system_prompt: str,
        policy_doc: str,
        guiding_prompts: list[str],
        *,
        ttl_seconds: int = 7200,
    ) -> str:
        guiding_lines = "\n".join(f"- {str(item).strip()}" for item in guiding_prompts if str(item).strip())
        self._cached_context = "\n\n".join(
            [
                str(system_prompt or "").strip(),
                f"## Policy Document\n{str(policy_doc or '').strip()}",
                f"## Guiding Prompts\n{guiding_lines}".strip(),
            ]
        ).strip()
        self._cache_id = f"cache-{uuid.uuid4().hex[:12]}" if self._supports_context_cache() else None
        self._cache_expires_at = time.time() + max(0, int(ttl_seconds)) if self._cache_id else None
        return self._cache_id or f"cache-disabled-{uuid.uuid4().hex[:8]}"

    def generate_with_cache(self, agent_prompt: str) -> str:
        self._expire_cache_if_needed()
        payload = {
            "provider": self.provider,
            "model": self.model,
            "agent_prompt": str(agent_prompt or ""),
            "cache_id": self._cache_id if self._supports_context_cache() else None,
            "cached_context": self._cached_context if self._supports_context_cache() else None,
        }

        if self._generate_fn is None:
            raw_response: dict[str, Any] | str = {"text": "", "usage": {}}
        else:
            raw_response = self._generate_fn(payload)

        text, usage = self._normalize_response(raw_response)
        cached_tokens = usage["cached_tokens"] if self._supports_context_cache() and self._cache_id else 0
        self._token_tracker.record(
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            cached_tokens=cached_tokens,
        )
        return text

    def get_token_usage(self) -> dict[str, float | int | str]:
        return self._token_tracker.get_summary()

    def delete_cache(self) -> None:
        self._cache_id = None
        self._cached_context = None
        self._cache_expires_at = None

    def estimate_usage(
        self,
        *,
        agent_count: int,
        rounds: int,
        avg_input_tokens: int = 3000,
        avg_output_tokens: int = 500,
        cached_ratio: float = 0.6,
    ) -> dict[str, float | str]:
        return self._token_tracker.estimate_cost(
            agent_count=agent_count,
            rounds=rounds,
            avg_input_tokens=avg_input_tokens,
            avg_output_tokens=avg_output_tokens,
            cached_ratio=cached_ratio,
        )

    def _expire_cache_if_needed(self) -> None:
        if self._cache_id is None or self._cache_expires_at is None:
            return
        if time.time() >= self._cache_expires_at:
            self.delete_cache()

    def _normalize_response(self, raw_response: dict[str, Any] | str) -> tuple[str, dict[str, int]]:
        if isinstance(raw_response, str):
            return raw_response, {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}

        text = str(raw_response.get("text") or raw_response.get("content") or "")
        usage_payload = raw_response.get("usage") or {}
        usage = {
            "input_tokens": _safe_int(usage_payload.get("input_tokens")),
            "output_tokens": _safe_int(usage_payload.get("output_tokens")),
            "cached_tokens": _safe_int(usage_payload.get("cached_tokens")),
        }
        return text, usage


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except Exception:  # noqa: BLE001
        return 0
