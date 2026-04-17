from __future__ import annotations

import logging
from typing import Any

import requests

from miroworld.config import Settings

logger = logging.getLogger(__name__)


class ZepService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._api_key = self._resolve_api_key(settings)
        self._base_url = self._resolve_base_url(settings)
        self._session = requests.Session()

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def ensure_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError("Zep Cloud is not configured. Set ZEP_CLOUD or ZEP_API_KEY.")

    def ensure_user(
        self,
        *,
        user_id: str,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"user_id": user_id}
        if email:
            payload["email"] = email
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if metadata:
            payload["metadata"] = metadata
        self._post("/api/v2/users", payload, allow_conflict=True)

    def ensure_thread(self, *, user_id: str, thread_id: str) -> None:
        self._post(
            "/api/v2/threads",
            {"user_id": user_id, "thread_id": thread_id},
            allow_conflict=True,
        )

    def add_messages(
        self,
        *,
        thread_id: str,
        messages: list[dict[str, Any]],
        return_context: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "messages": messages,
            "return_context": return_context,
        }
        return self._post(f"/api/v2/threads/{thread_id}/messages", payload)

    def graph_search(
        self,
        *,
        user_id: str,
        query: str,
        scope: str,
        limit: int = 10,
        reranker: str = "rrf",
        search_filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "user_id": user_id,
            "query": query,
            "scope": scope,
            "limit": max(1, min(int(limit), 50)),
            "reranker": reranker,
        }
        if search_filters:
            payload["search_filters"] = search_filters
        return self._post("/api/v2/graph/search", payload)

    def delete_user(self, *, user_id: str) -> None:
        self.ensure_enabled()
        response = self._session.delete(
            f"{self._base_url}/api/v2/users/{user_id}",
            headers=self._headers(),
            timeout=30,
        )
        if response.status_code in {200, 202, 204, 404}:
            return
        response.raise_for_status()

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        allow_conflict: bool = False,
    ) -> dict[str, Any]:
        self.ensure_enabled()
        response = self._session.post(
            f"{self._base_url}{path}",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        if allow_conflict and response.status_code in {400, 409}:
            logger.debug("Zep conflict tolerated for %s: %s", path, response.text[:300])
            return {}
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Api-Key {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _resolve_api_key(settings: Settings) -> str | None:
        for candidate in (
            getattr(settings, "zep_api_key", None),
            getattr(settings, "zep_cloud", None),
        ):
            value = str(candidate or "").strip()
            if value and not value.startswith("http://") and not value.startswith("https://"):
                return value
        return None

    @staticmethod
    def _resolve_base_url(settings: Settings) -> str:
        explicit = str(getattr(settings, "zep_api_url", "") or "").strip()
        if explicit:
            return explicit.rstrip("/")
        cloud_value = str(getattr(settings, "zep_cloud", "") or "").strip()
        if cloud_value.startswith("http://") or cloud_value.startswith("https://"):
            return cloud_value.rstrip("/")
        return "https://api.getzep.com"
