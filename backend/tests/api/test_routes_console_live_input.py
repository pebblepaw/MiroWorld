from __future__ import annotations

import asyncio
from pathlib import Path

from miroworld.config import Settings
from miroworld.models.console import ConsoleKnowledgeProcessRequest
from miroworld.api import routes_console


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(simulation_db_path=str(tmp_path / "simulation.db"))


def test_process_knowledge_uses_demo_cache_even_when_explicit_document_is_provided(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)

    class _DemoService:
        def is_demo_available(self) -> bool:
            return True

        def get_knowledge_artifact(self, session_id: str) -> dict[str, object]:
            return {"session_id": session_id, "summary": "Demo artifact", "document": {}, "entity_nodes": [], "relationship_edges": [], "entity_type_counts": {}, "processing_logs": []}

    class _ConsoleService:
        def __init__(self, _settings: Settings) -> None:
            raise AssertionError("Live knowledge processing should not run in demo mode")

    monkeypatch.setattr(routes_console, "_is_demo_session", lambda *_: True)
    monkeypatch.setattr(routes_console, "_get_demo_service", lambda *_: _DemoService())
    monkeypatch.setattr(routes_console, "ConsoleService", _ConsoleService)

    req = ConsoleKnowledgeProcessRequest(document_text="Fresh scraped policy text", source_path="airbnb-policy.pdf")

    payload = asyncio.run(routes_console.process_knowledge("session-live", req, settings))

    assert payload.summary == "Demo artifact"


def test_upload_knowledge_uses_demo_cache_when_file_is_uploaded(monkeypatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)

    class _DemoService:
        def is_demo_available(self) -> bool:
            return True

        def get_knowledge_artifact(self, session_id: str) -> dict[str, object]:
            return {"session_id": session_id, "summary": "Demo artifact", "document": {}, "entity_nodes": [], "relationship_edges": [], "entity_type_counts": {}, "processing_logs": []}

    class _ConsoleService:
        def __init__(self, _settings: Settings) -> None:
            raise AssertionError("Live upload processing should not run in demo mode")

    class _Upload:
        filename = "airbnb-policy.pdf"

        async def read(self) -> bytes:
            return b"fake"

    monkeypatch.setattr(routes_console, "_is_demo_session", lambda *_: True)
    monkeypatch.setattr(routes_console, "_get_demo_service", lambda *_: _DemoService())
    monkeypatch.setattr(routes_console, "ConsoleService", _ConsoleService)

    payload = asyncio.run(routes_console.upload_knowledge("session-live", _Upload(), None, None, settings))

    assert payload.summary == "Demo artifact"
