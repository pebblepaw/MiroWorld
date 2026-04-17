from __future__ import annotations

import uuid
from pathlib import Path

from miroworld.config import Settings, get_settings
from miroworld.services.console_service import ConsoleService
from miroworld.services.storage import SimulationStore, reset_store_user_context, set_store_user_context
import pytest


def test_google_sessions_can_fall_back_to_shared_gemini_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_STATE_BACKEND", "sqlite")
    get_settings.cache_clear()
    service = ConsoleService(
        Settings(
            simulation_db_path=str(tmp_path / "simulation.db"),
            app_state_backend="sqlite",
            gemini_api_key="shared-gemini-key",
        )
    )

    assert service._resolve_session_api_key(None, provider="google", api_key=None) == "shared-gemini-key"
    get_settings.cache_clear()


def test_postgres_store_scopes_session_state_by_authenticated_user(monkeypatch, tmp_path: Path) -> None:
    if not Settings().supabase_postgres_url:
        pytest.skip("Supabase session-pooler URL is not configured.")
    monkeypatch.setenv("APP_STATE_BACKEND", "postgres")
    get_settings.cache_clear()

    store = SimulationStore(str(tmp_path / "ignored.db"))
    session_id = f"session-{uuid.uuid4().hex[:12]}"
    owner_user_id = f"user-{uuid.uuid4().hex[:8]}"

    token = set_store_user_context(owner_user_id)
    try:
        store.upsert_console_session(
            session_id=session_id,
            mode="live",
            status="created",
            model_provider="google",
            model_name="gemini-2.5-flash-lite",
            api_key="shared-gemini-key",
        )
        store.upsert_session_config(
            session_id,
            {
                "country": "usa",
                "use_case": "public-policy-testing",
                "analysis_questions": [{"question": "Do you support it?"}],
                "config_json": {"country": "usa", "use_case": "public-policy-testing"},
            },
        )
        store.save_knowledge_artifact(session_id, {"session_id": session_id, "summary": "Michigan tax policy update"})
    finally:
        reset_store_user_context(token)

    token = set_store_user_context(owner_user_id)
    try:
        assert store.get_console_session(session_id)["user_id"] == owner_user_id
        assert store.get_session_config(session_id)["use_case"] == "public-policy-testing"
        assert store.get_knowledge_artifact(session_id)["summary"] == "Michigan tax policy update"
    finally:
        reset_store_user_context(token)

    token = set_store_user_context(f"user-{uuid.uuid4().hex[:8]}")
    try:
        assert store.get_console_session(session_id) is None
        assert store.get_session_config(session_id) == {}
        assert store.get_knowledge_artifact(session_id) is None
    finally:
        reset_store_user_context(token)

    get_settings.cache_clear()
