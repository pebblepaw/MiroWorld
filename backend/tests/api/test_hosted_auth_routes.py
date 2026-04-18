from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from miroworld.api import routes_console
from miroworld.config import Settings, get_settings
from miroworld.main import app
from miroworld.services.storage import reset_store_user_context, set_store_user_context


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


class _RegisterResponse:
    status_code = 200

    def __init__(self, email: str = "new-user@example.com") -> None:
        self._email = email

    def json(self) -> dict[str, str]:
        return {"id": "supabase-user-1", "email": self._email}

    @property
    def text(self) -> str:
        return '{"id":"supabase-user-1"}'


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


def test_hosted_session_create_persists_authenticated_user_id(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(routes_console, "_verify_supabase_user", lambda *args, **kwargs: {"id": "user-hosted-123"})

    store = routes_console.SimulationStore(settings.simulation_db_path)

    class _ConsoleService:
        def __init__(self, _settings: Settings) -> None:
            pass

        def create_v2_session(self, **_: object) -> dict[str, str]:
            store.upsert_console_session(
                session_id="session-owned-route",
                mode="live",
                status="created",
            )
            return {"session_id": "session-owned-route"}

    monkeypatch.setattr(routes_console, "ConsoleService", _ConsoleService)

    client = TestClient(app)
    response = client.post(
        "/api/v2/session/create",
        headers={"Authorization": "Bearer hosted-session-owner-token"},
        json={
            "country": "usa",
            "use_case": "public-policy-testing",
            "provider": "gemini",
            "model": "gemini-2.5-flash-lite",
            "api_key": "test-gemini-key",
        },
    )

    assert response.status_code == 200
    session_id = response.json()["session_id"]

    token = set_store_user_context("user-hosted-123")
    try:
        session = store.get_console_session(session_id)
    finally:
        reset_store_user_context(token)

    assert session is not None
    assert session["user_id"] == "user-hosted-123"
    app.dependency_overrides.clear()


def test_hosted_register_route_creates_auto_confirmed_user(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings

    captured: dict[str, object] = {}

    def _fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _RegisterResponse(email=str(json["email"]))

    monkeypatch.setattr(routes_console.requests, "post", _fake_post)

    client = TestClient(app)
    response = client.post(
        "/api/v2/hosted/auth/register",
        json={"email": "new-user@example.com", "password": "CodexPass!2026"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == "supabase-user-1"
    assert captured["url"] == "https://example.supabase.co/auth/v1/admin/users"
    assert captured["headers"] == {
        "apikey": "service-role-key",
        "Authorization": "Bearer service-role-key",
        "Content-Type": "application/json",
    }
    assert captured["json"] == {
        "email": "new-user@example.com",
        "password": "CodexPass!2026",
        "email_confirm": True,
        "user_metadata": {
            "email_verified": True,
            "hosted_signup": True,
        },
    }
    assert captured["timeout"] == 15
    app.dependency_overrides.clear()


def test_hosted_knowledge_artifact_route_returns_saved_artifact(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(routes_console.requests, "get", lambda *args, **kwargs: _OkResponse())

    store = routes_console.SimulationStore(settings.simulation_db_path)
    token = set_store_user_context("user-hosted-123")
    try:
        store.upsert_console_session(
            session_id="session-knowledge-route",
            mode="live",
            status="knowledge_ready",
        )
        store.save_knowledge_artifact(
            "session-knowledge-route",
            {
                "session_id": "session-knowledge-route",
                "document": {"document_id": "doc-1", "paragraph_count": 1},
                "summary": "Hosted artifact summary",
                "entity_nodes": [],
                "relationship_edges": [],
                "entity_type_counts": {},
                "processing_logs": [],
            },
        )
    finally:
        reset_store_user_context(token)

    client = TestClient(app)
    response = client.get(
        "/api/v2/console/session/session-knowledge-route/knowledge",
        headers={"Authorization": "Bearer hosted-artifact-token"},
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "Hosted artifact summary"
    app.dependency_overrides.clear()


def test_hosted_knowledge_artifact_route_returns_no_content_when_not_ready(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(routes_console.requests, "get", lambda *args, **kwargs: _OkResponse())

    store = routes_console.SimulationStore(settings.simulation_db_path)
    token = set_store_user_context("user-hosted-123")
    try:
        store.upsert_console_session(
            session_id="session-knowledge-missing",
            mode="live",
            status="created",
        )
    finally:
        reset_store_user_context(token)

    client = TestClient(app)
    response = client.get(
        "/api/v2/console/session/session-knowledge-missing/knowledge",
        headers={"Authorization": "Bearer hosted-artifact-token"},
    )

    assert response.status_code == 204
    assert response.text == ""
    app.dependency_overrides.clear()


def test_hosted_population_artifact_route_returns_saved_artifact(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(routes_console.requests, "get", lambda *args, **kwargs: _OkResponse())

    store = routes_console.SimulationStore(settings.simulation_db_path)
    token = set_store_user_context("user-hosted-123")
    try:
        store.upsert_console_session(
            session_id="session-population-route",
            mode="live",
            status="knowledge_ready",
        )
        store.save_population_artifact(
            "session-population-route",
            {
                "session_id": "session-population-route",
                "candidate_count": 12,
                "sample_count": 10,
                "sample_mode": "affected_groups",
                "sample_seed": 17,
                "parsed_sampling_instructions": {"source": "gemini"},
                "coverage": {"states": ["Michigan"]},
                "sampled_personas": [],
                "agent_graph": {"nodes": [], "links": []},
                "representativeness": {},
                "selection_diagnostics": {},
            },
        )
    finally:
        reset_store_user_context(token)

    client = TestClient(app)
    response = client.get(
        "/api/v2/console/session/session-population-route/sampling",
        headers={"Authorization": "Bearer hosted-population-token"},
    )

    assert response.status_code == 200
    assert response.json()["sample_count"] == 10
    app.dependency_overrides.clear()


def test_hosted_population_artifact_route_returns_no_content_when_not_ready(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(routes_console.requests, "get", lambda *args, **kwargs: _OkResponse())

    store = routes_console.SimulationStore(settings.simulation_db_path)
    token = set_store_user_context("user-hosted-123")
    try:
        store.upsert_console_session(
            session_id="session-population-missing",
            mode="live",
            status="knowledge_ready",
        )
    finally:
        reset_store_user_context(token)

    client = TestClient(app)
    response = client.get(
        "/api/v2/console/session/session-population-missing/sampling",
        headers={"Authorization": "Bearer hosted-population-token"},
    )

    assert response.status_code == 204
    assert response.text == ""
    app.dependency_overrides.clear()
