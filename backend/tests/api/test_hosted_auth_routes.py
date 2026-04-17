from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from miroworld.api import routes_console
from miroworld.config import Settings, get_settings
from miroworld.main import app


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        app_state_backend="sqlite",
        hosted_auth_required=True,
        supabase_url="https://example.supabase.co",
        supabase_publishable_key="publishable-key",
        supabase_service_role_key="service-role-key",
    )


class _OkResponse:
    status_code = 200

    def json(self) -> dict[str, str]:
        return {"id": "user-hosted-123"}


def test_hosted_route_requires_supabase_bearer_token(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)

    response = client.post(
        "/api/v2/session/create",
        json={
            "country": "usa",
            "use_case": "public-policy-testing",
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
        },
    )

    assert response.status_code == 401
    assert "Supabase bearer token" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_hosted_routes_accept_cookie_after_authenticated_call(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings

    class _ConsoleService:
        def __init__(self, _settings: Settings) -> None:
            pass

        def create_v2_session(self, **_: object) -> dict[str, str]:
            return {"session_id": "session-cookie-auth"}

        def get_session_analysis_questions(self, session_id: str) -> dict[str, object]:
            return {"session_id": session_id, "use_case": "public-policy-testing", "questions": []}

    monkeypatch.setattr(routes_console, "ConsoleService", _ConsoleService)
    monkeypatch.setattr(routes_console.requests, "get", lambda *args, **kwargs: _OkResponse())

    client = TestClient(app)
    create_response = client.post(
        "/api/v2/session/create",
        headers={"Authorization": "Bearer test-access-token"},
        json={
            "country": "usa",
            "use_case": "public-policy-testing",
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
        },
    )

    assert create_response.status_code == 200
    assert routes_console.HOSTED_AUTH_COOKIE in create_response.cookies

    followup = client.get("/api/v2/session/session-cookie-auth/analysis-questions")

    assert followup.status_code == 200
    assert followup.json()["session_id"] == "session-cookie-auth"
    app.dependency_overrides.clear()
