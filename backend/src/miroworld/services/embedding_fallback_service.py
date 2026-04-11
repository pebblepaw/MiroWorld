from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from openai import APIStatusError, RateLimitError
from tenacity import RetryError

from miroworld.config import Settings
from miroworld.services.model_provider_service import normalize_provider


T = TypeVar("T")


def is_rate_limited_error(exc: BaseException) -> bool:
    for candidate in _iter_exception_chain(exc):
        if isinstance(candidate, RateLimitError):
            return True
        if isinstance(candidate, APIStatusError) and getattr(candidate, "status_code", None) == 429:
            return True
        status_code = getattr(getattr(candidate, "response", None), "status_code", None)
        if status_code == 429:
            return True
        message = str(candidate).strip().lower()
        if any(
            token in message
            for token in (
                "429",
                "insufficient_quota",
                "quota exceeded",
                "rate limit",
                "resource exhausted",
                "too many requests",
            )
        ):
            return True
    return False


def run_with_embedding_model_fallback(
    settings: Settings,
    *,
    provider: str,
    preferred_model: str | None,
    runner: Callable[[str], T],
) -> tuple[str, T]:
    candidates = settings.provider_embed_model_candidates(provider, preferred_model=preferred_model)
    last_exc: Exception | None = None
    for index, model_name in enumerate(candidates):
        try:
            return model_name, runner(model_name)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if normalize_provider(provider) != "google":
                raise
            is_retryable = is_rate_limited_error(exc)
            has_more_candidates = index + 1 < len(candidates)
            if not is_retryable or not has_more_candidates:
                raise
    assert last_exc is not None
    raise last_exc


async def arun_with_embedding_model_fallback(
    settings: Settings,
    *,
    provider: str,
    preferred_model: str | None,
    runner: Callable[[str], Awaitable[T]],
) -> tuple[str, T]:
    candidates = settings.provider_embed_model_candidates(provider, preferred_model=preferred_model)
    last_exc: Exception | None = None
    for index, model_name in enumerate(candidates):
        try:
            return model_name, await runner(model_name)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if normalize_provider(provider) != "google":
                raise
            is_retryable = is_rate_limited_error(exc)
            has_more_candidates = index + 1 < len(candidates)
            if not is_retryable or not has_more_candidates:
                raise
    assert last_exc is not None
    raise last_exc


def _iter_exception_chain(exc: BaseException):
    stack: list[BaseException] = [exc]
    seen: set[int] = set()

    while stack:
        candidate = stack.pop()
        marker = id(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        yield candidate

        if isinstance(candidate, RetryError):
            last_attempt = getattr(candidate, "last_attempt", None)
            if last_attempt is not None:
                attempt_exc = last_attempt.exception()
                if attempt_exc is not None:
                    stack.append(attempt_exc)

        cause = getattr(candidate, "__cause__", None)
        if isinstance(cause, BaseException):
            stack.append(cause)

        context = getattr(candidate, "__context__", None)
        if isinstance(context, BaseException):
            stack.append(context)
