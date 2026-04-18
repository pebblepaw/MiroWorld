from __future__ import annotations

import uuid
from pathlib import Path

from miroworld.config import Settings, get_settings
from miroworld.services import console_service as console_service_module
from miroworld.services.console_service import ConsoleService
from miroworld.services.memory_service import MemoryService
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


def test_hosted_memory_uses_zep_when_zep_cloud_env_is_present(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEP_CLOUD", "zep_test_api_key")
    settings = Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        app_state_backend="postgres",
    )

    service = MemoryService(settings)

    assert settings.zep_cloud == "zep_test_api_key"
    assert service.zep.enabled is True
    assert service.memory_backend == "zep-cloud"


def test_zep_user_ids_are_stable_per_authenticated_user(tmp_path: Path) -> None:
    service = MemoryService(
        Settings(
            simulation_db_path=str(tmp_path / "simulation.db"),
            app_state_backend="postgres",
            zep_api_key="zep-test-key",
        )
    )
    service.store.get_console_session = lambda _session_id: {"user_id": "user-123"}  # type: ignore[method-assign]

    owner_id, zep_user_id, thread_id = service._zep_ids_for_session("session-456")

    assert owner_id == "user-123"
    assert zep_user_id == "miroworld::user-123"
    assert thread_id == "session::session-456"


def test_zep_sync_ensures_user_and_thread_only_once_per_process(tmp_path: Path) -> None:
    service = MemoryService(
        Settings(
            simulation_db_path=str(tmp_path / "simulation.db"),
            app_state_backend="postgres",
            zep_api_key="zep-test-key",
        )
    )
    sync_state: dict[str, int] = {"last_interaction_id": 0, "last_checkpoint_id": 0, "synced_events": 0}
    ensure_user_calls: list[dict[str, object]] = []
    ensure_thread_calls: list[dict[str, object]] = []
    add_messages_calls: list[dict[str, object]] = []

    service.store.get_console_session = lambda _session_id: {"user_id": "user-123"}  # type: ignore[method-assign]
    service.store.get_memory_sync_state = lambda _session_id: dict(sync_state)  # type: ignore[method-assign]
    service.store.get_knowledge_artifact = lambda _session_id: {"summary": "A new tax proposal was announced."}  # type: ignore[method-assign]
    service.store.get_interactions_after_id = lambda _session_id, _last_id: []  # type: ignore[method-assign]
    service.store.list_checkpoint_records_after_id = lambda _session_id, _last_id: []  # type: ignore[method-assign]
    service.store.get_agents = lambda _session_id: []  # type: ignore[method-assign]

    def _save_memory_sync_state(
        _session_id: str,
        *,
        last_interaction_id: int,
        synced_events: int,
        last_checkpoint_id: int,
    ) -> None:
        sync_state.update(
            {
                "last_interaction_id": last_interaction_id,
                "synced_events": synced_events,
                "last_checkpoint_id": last_checkpoint_id,
            }
        )

    service.store.save_memory_sync_state = _save_memory_sync_state  # type: ignore[method-assign]
    service.zep.ensure_user = lambda **kwargs: ensure_user_calls.append(kwargs)  # type: ignore[method-assign]
    service.zep.ensure_thread = lambda **kwargs: ensure_thread_calls.append(kwargs)  # type: ignore[method-assign]
    service.zep.add_messages = lambda **kwargs: add_messages_calls.append(kwargs) or {}  # type: ignore[method-assign]

    first = service._ensure_zep_synced("session-456")
    second = service._ensure_zep_synced("session-456")

    assert first["synced_events"] == 1
    assert second["synced_events"] == 1
    assert ensure_user_calls == [{"user_id": "miroworld::user-123", "metadata": {"app_user_id": "user-123"}}]
    assert ensure_thread_calls == [{"user_id": "miroworld::user-123", "thread_id": "session::session-456"}]
    assert len(add_messages_calls) == 1


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


def test_simulation_background_rebinds_session_owner_context(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        app_state_backend="sqlite",
    )
    service = ConsoleService(settings)

    owner_id = f"user-{uuid.uuid4().hex[:8]}"
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    observed_user_ids: list[str | None] = []

    class _StopBackground(RuntimeError):
        pass

    class _FakeSimulationService:
        def __init__(self, _settings: Settings) -> None:
            pass

        def build_context_bundles(self, **_: object) -> dict[str, object]:
            return {}

        def run_opinion_checkpoint(self, **_: object) -> list[dict[str, object]]:
            return [{"agent_id": "agent-1", "metric_answers": {}}]

    class _FakeMetricsService:
        def __init__(self, _config_service: object) -> None:
            pass

        def compute_dynamic_metrics(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            return {}

    monkeypatch.setattr(console_service_module, "SimulationService", _FakeSimulationService)
    monkeypatch.setattr(console_service_module, "MetricsService", _FakeMetricsService)
    monkeypatch.setattr(service, "_runtime_settings_for_session", lambda _session_id: settings)
    monkeypatch.setattr(service, "_session_use_case", lambda _session_id: "public-policy-testing")
    monkeypatch.setattr(service, "get_session_analysis_questions", lambda _session_id: {"questions": []})
    monkeypatch.setattr(service, "_checkpoint_questions_for_use_case", lambda *_args, **_kwargs: [{"question": "Q"}])
    monkeypatch.setattr(service, "_personality_modifiers_for_use_case", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_session_country_config", lambda _session_id: ("usa", {"name": "United States"}, None))
    monkeypatch.setattr(service, "_flatten_dynamic_metrics_payload", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_agents_for_dynamic_metrics", lambda records: records)
    monkeypatch.setattr(service.streams, "append_events", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.streams, "ingest_events_incremental", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.store, "get_console_session", lambda _session_id: {"session_id": session_id, "user_id": owner_id})
    monkeypatch.setattr(service.store, "get_knowledge_artifact", lambda _session_id: {})
    monkeypatch.setattr(
        service.store,
        "replace_checkpoint_records",
        lambda *_args, **_kwargs: (observed_user_ids.append(service.store._current_user_id()), (_ for _ in ()).throw(_StopBackground())),
    )

    service._run_simulation_background(
        session_id,
        owner_id,
        "Subject summary",
        3,
        [{"agent_id": "agent-1"}],
        [{"agent_id": "agent-1"}],
        tmp_path / "events.jsonl",
        "live",
    )

    assert observed_user_ids == [owner_id]
    assert service.store._current_user_id() is None


def test_postgres_replace_agents_handles_null_user_scope_without_typed_null_sql(monkeypatch, tmp_path: Path) -> None:
    store = SimulationStore(str(tmp_path / "simulation.db"))
    observed: list[tuple[str, tuple[object, ...] | None]] = []

    class _Conn:
        def __enter__(self) -> "_Conn":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
            observed.append((sql, params))

    monkeypatch.setattr(type(store), "is_postgres", property(lambda self: True))
    monkeypatch.setattr(store, "_connect", lambda: _Conn())

    store.replace_agents(
        "sim-null-user",
        [
            {
                "agent_id": "agent-1",
                "persona": {"display_name": "Agent One"},
                "opinion_pre": None,
                "opinion_post": None,
            }
        ],
    )

    assert observed[0] == ("DELETE FROM agents WHERE simulation_id = %s", ("sim-null-user",))
    assert observed[1] == ("DELETE FROM report_cache WHERE simulation_id = %s", ("sim-null-user",))


def test_postgres_replace_interactions_handles_null_user_scope_without_typed_null_sql(monkeypatch, tmp_path: Path) -> None:
    store = SimulationStore(str(tmp_path / "simulation.db"))
    observed: list[tuple[str, tuple[object, ...] | None]] = []

    class _Conn:
        def __enter__(self) -> "_Conn":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
            observed.append((sql, params))

    monkeypatch.setattr(type(store), "is_postgres", property(lambda self: True))
    monkeypatch.setattr(store, "_connect", lambda: _Conn())

    store.replace_interactions(
        "sim-null-user",
        [
            {
                "round_no": 1,
                "actor_agent_id": "agent-1",
                "target_agent_id": None,
                "action_type": "create_post",
                "title": "Seeded post",
                "content": "content",
                "delta": 0.0,
            }
        ],
    )

    assert observed[0] == ("DELETE FROM interactions WHERE simulation_id = %s", ("sim-null-user",))
    assert observed[1] == ("DELETE FROM report_cache WHERE simulation_id = %s", ("sim-null-user",))
    assert observed[2] == ("DELETE FROM memory_sync_state WHERE simulation_id = %s", ("sim-null-user",))
