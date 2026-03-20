from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator

from mckainsey.config import Settings
from mckainsey.services.storage import SimulationStore


class SimulationStreamService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)

    def ingest_events_file(self, session_id: str, path: Path) -> int:
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            event = json.loads(stripped)
            event.setdefault("session_id", session_id)
            events.append(event)
        self.store.append_simulation_events(session_id, events)
        self.store.save_simulation_state_snapshot(session_id, self._build_state(session_id, events))
        return len(events)

    def get_state(self, session_id: str) -> dict[str, Any]:
        state = self.store.get_simulation_state_snapshot(session_id)
        if state:
            return state
        events = self.store.list_simulation_events(session_id)
        state = self._build_state(session_id, events)
        self.store.save_simulation_state_snapshot(session_id, state)
        return state

    def sse_iter(self, session_id: str) -> Iterator[str]:
        events = self.store.list_simulation_events(session_id, limit=self.settings.simulation_stream_replay_limit)
        for event in events:
            yield self._format_sse("event", event)
        state = self.store.get_simulation_state_snapshot(session_id) or {}
        events_path = state.get("events_path")
        if not events_path:
            yield self._format_sse("heartbeat", {"session_id": session_id})
            return

        path = Path(events_path)
        sent = 0
        idle_cycles = 0
        while idle_cycles < 120:
            if path.exists():
                lines = path.read_text(encoding="utf-8").splitlines()
                while sent < len(lines):
                    payload = json.loads(lines[sent])
                    yield self._format_sse(payload.get("event_type", "event"), payload)
                    sent += 1
                    idle_cycles = 0
            latest_state = self.store.get_simulation_state_snapshot(session_id) or {}
            if latest_state.get("status") in {"completed", "failed"} and sent >= len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else True:
                break
            idle_cycles += 1
            yield self._format_sse("heartbeat", {"session_id": session_id})
            time.sleep(self.settings.simulation_stream_heartbeat_seconds)

    def _build_state(self, session_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        latest_metrics: dict[str, Any] = {}
        last_round = 0
        for event in events:
            last_round = max(last_round, int(event.get("round_no", 0) or 0))
            if event.get("event_type") == "metrics_updated":
                latest_metrics = dict(event.get("metrics", {}))
        return {
            "session_id": session_id,
            "status": "running" if events else "idle",
            "event_count": len(events),
            "last_round": last_round,
            "latest_metrics": latest_metrics,
            "recent_events": events[-10:],
        }

    def _format_sse(self, event_name: str, payload: dict[str, Any]) -> str:
        return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
