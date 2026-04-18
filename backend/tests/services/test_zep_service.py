from __future__ import annotations

from pathlib import Path

import requests

from miroworld.config import Settings
from miroworld.services import zep_service as zep_service_module
from miroworld.services.zep_service import ZepService


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text
        self.content = b"" if payload is None else b"{}"

    def json(self) -> dict[str, object]:
        return dict(self._payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def test_post_retries_rate_limit_and_returns_success(monkeypatch, tmp_path: Path) -> None:
    service = ZepService(
        Settings(
            simulation_db_path=str(tmp_path / "simulation.db"),
            zep_api_key="zep-test-key",
        )
    )
    responses = iter(
        [
            _FakeResponse(status_code=429, headers={"Retry-After": "0"}, text="Too Many Requests"),
            _FakeResponse(status_code=200, payload={"ok": True}),
        ]
    )
    sleeps: list[float] = []

    monkeypatch.setattr(service._session, "post", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(zep_service_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    payload = service._post("/api/v2/users", {"user_id": "user-1"})

    assert payload == {"ok": True}
    assert sleeps == [0.0]
