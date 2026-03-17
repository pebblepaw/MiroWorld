from __future__ import annotations

from zep_cloud import Zep


class ZepEventLogger:
    def __init__(self, api_key: str | None):
        self._api_key = api_key
        self._client = Zep(api_key=api_key) if api_key else None

    def is_enabled(self) -> bool:
        return self._client is not None

    def log_phase_a_event(self, simulation_id: str, payload: str, source: str) -> None:
        if not self._client:
            return

        self._client.graph.add(
            user_id=simulation_id,
            data=payload,
            type="text",
            source_description=source,
        )
