from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator

from miroworld.config import Settings
from miroworld.services.storage import SimulationStore


class SimulationStreamService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)

    def append_events(self, session_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return self.get_state(session_id)
        self.store.append_simulation_events(session_id, events)
        all_events = self.store.list_simulation_events(session_id)
        previous = self.store.get_simulation_state_snapshot(session_id) or {}
        state = self._build_state(session_id, all_events, previous_state=previous)
        self.store.save_simulation_state_snapshot(session_id, state)
        return state

    def ingest_events_file(self, session_id: str, path: Path) -> int:
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            event = json.loads(stripped)
            event.setdefault("session_id", session_id)
            events.append(event)
        previous = self.store.get_simulation_state_snapshot(session_id) or {}
        self.store.append_simulation_events(session_id, events)
        all_events = self.store.list_simulation_events(session_id)
        state = self._build_state(session_id, all_events, previous_state=previous)
        state["events_path"] = str(path)
        state["stream_offset_bytes"] = path.stat().st_size if path.exists() else 0
        self.store.save_simulation_state_snapshot(session_id, state)
        return len(events)

    def ingest_events_incremental(self, session_id: str, path: Path) -> int:
        previous = self.store.get_simulation_state_snapshot(session_id) or {}
        offset = int(previous.get("stream_offset_bytes", 0) or 0)
        if not path.exists():
            return 0

        with path.open("r", encoding="utf-8") as handle:
            handle.seek(offset)
            payload = handle.read()
            new_offset = handle.tell()

        lines = [line.strip() for line in payload.splitlines() if line.strip()]
        if not lines:
            previous["events_path"] = str(path)
            previous["stream_offset_bytes"] = new_offset
            self.store.save_simulation_state_snapshot(session_id, previous)
            return 0

        events: list[dict[str, Any]] = []
        for line in lines:
            event = json.loads(line)
            event.setdefault("session_id", session_id)
            events.append(event)

        self.store.append_simulation_events(session_id, events)
        all_events = self.store.list_simulation_events(session_id)
        state = self._build_state(session_id, all_events, previous_state=previous)
        state["events_path"] = str(path)
        state["stream_offset_bytes"] = new_offset
        self.store.save_simulation_state_snapshot(session_id, state)
        return len(events)

    def get_state(self, session_id: str) -> dict[str, Any]:
        state = self.store.get_simulation_state_snapshot(session_id)
        if state:
            return state
        events = self.store.list_simulation_events(session_id)
        state = self._build_state(session_id, events, previous_state={})
        self.store.save_simulation_state_snapshot(session_id, state)
        return state

    def sse_iter(self, session_id: str) -> Iterator[str]:
        events = self.store.list_simulation_events(session_id)
        replay = events[-self.settings.simulation_stream_replay_limit :]
        for event in replay:
            yield self._format_sse("event", event)
        sent = len(events)
        idle_cycles = 0
        while idle_cycles < 240:
            current_events = self.store.list_simulation_events(session_id)
            while sent < len(current_events):
                payload = current_events[sent]
                yield self._format_sse(payload.get("event_type", "event"), payload)
                sent += 1
                idle_cycles = 0
            latest_state = self.store.get_simulation_state_snapshot(session_id) or {}
            if latest_state.get("status") in {"completed", "failed"} and sent >= len(current_events):
                break
            yield self._format_sse("heartbeat", {"session_id": session_id})
            idle_cycles += 1
            time.sleep(self.settings.simulation_stream_heartbeat_seconds)

    def _build_state(
        self,
        session_id: str,
        events: list[dict[str, Any]],
        *,
        previous_state: dict[str, Any],
    ) -> dict[str, Any]:
        latest_metrics: dict[str, Any] = {}
        last_round = 0
        platform = previous_state.get("platform")
        planned_rounds = int(previous_state.get("planned_rounds", 0) or 0)
        elapsed_seconds = int(previous_state.get("elapsed_seconds", 0) or 0)
        estimated_total_seconds = previous_state.get("estimated_total_seconds")
        estimated_remaining_seconds = previous_state.get("estimated_remaining_seconds")
        counters = dict(previous_state.get("counters", {}))
        discussion_momentum = dict(previous_state.get("discussion_momentum", {}))
        top_threads = list(previous_state.get("top_threads", []))
        round_progress = dict(previous_state.get("round_progress", {}))
        checkpoint_status = {
            "baseline": {"status": "pending", "completed_agents": 0, "total_agents": 0},
            "final": {"status": "pending", "completed_agents": 0, "total_agents": 0},
        }
        checkpoint_status.update(previous_state.get("checkpoint_status", {}))
        active_authors: set[str] = set()
        status = "running" if events else "idle"

        for event in events:
            last_round = max(last_round, int(event.get("round_no", 0) or 0))
            event_type = str(event.get("event_type", ""))
            if event_type == "run_started":
                platform = event.get("platform") or platform or self.settings.simulation_platform
                planned_rounds = int(event.get("planned_rounds", 0) or planned_rounds)
                status = "running"
            elif event_type == "checkpoint_started":
                kind = str(event.get("checkpoint_kind") or "baseline")
                checkpoint_status.setdefault(kind, {"status": "pending", "completed_agents": 0, "total_agents": 0})
                checkpoint_status[kind]["status"] = "running"
                checkpoint_status[kind]["total_agents"] = int(event.get("total_agents", checkpoint_status[kind].get("total_agents", 0)) or 0)
            elif event_type == "checkpoint_completed":
                kind = str(event.get("checkpoint_kind") or "baseline")
                checkpoint_status.setdefault(kind, {"status": "pending", "completed_agents": 0, "total_agents": 0})
                checkpoint_status[kind]["status"] = "completed"
                checkpoint_status[kind]["completed_agents"] = int(event.get("completed_agents", 0) or 0)
                checkpoint_status[kind]["total_agents"] = int(event.get("total_agents", checkpoint_status[kind].get("total_agents", 0)) or 0)
            elif event_type in {"post_created", "comment_created"}:
                actor = str(event.get("actor_agent_id", "")).strip()
                if actor:
                    active_authors.add(actor)
                if event_type == "post_created":
                    counters["posts"] = int(counters.get("posts", 0) or 0) + 1
                else:
                    counters["comments"] = int(counters.get("comments", 0) or 0) + 1
            elif event_type == "reaction_added":
                counters["reactions"] = int(counters.get("reactions", 0) or 0) + 1
                if str(event.get("reaction", "")).strip().lower() == "dislike":
                    counters["post_dislikes"] = int(counters.get("post_dislikes", 0) or 0) + 1
            elif event_type == "round_batch_flushed":
                batch_index = int(event.get("batch_index", event.get("batch", 0)) or 0)
                batch_count = int(event.get("batch_count", event.get("total_batches", 0)) or 0)
                round_no = int(event.get("round_no", event.get("round", 0)) or 0)
                percentage = float(event.get("percentage", 0.0) or 0.0)
                if batch_count > 0 and percentage <= 0:
                    percentage = round((batch_index / max(1, batch_count)) * 100, 1)
                label = str(event.get("label") or f"Round {round_no} ({percentage:.0f}%)")
                round_progress = {
                    "round": int(event.get("round", round_no) or round_no),
                    "batch": int(event.get("batch", batch_index) or batch_index),
                    "total_batches": int(event.get("total_batches", batch_count) or batch_count),
                    "percentage": round(percentage, 1),
                    "label": label,
                }
            elif event_type == "metrics_updated":
                metrics_payload = event.get("metrics", {})
                latest_metrics = dict(metrics_payload) if isinstance(metrics_payload, dict) else {}
                event_counters = dict(event.get("counters", {}))
                counters.update(event_counters)
                counters["active_authors"] = int(event_counters.get("active_authors", counters.get("active_authors", len(active_authors))) or len(active_authors))
                event_round_progress = event.get("round_progress")
                if isinstance(event_round_progress, dict):
                    round_progress = dict(event_round_progress)
                if round_progress:
                    latest_metrics["round_progress"] = round_progress
                    latest_metrics["round_progress_label"] = str(round_progress.get("label") or "")
                for key, value in event.items():
                    if key in {
                        "event_type",
                        "session_id",
                        "timestamp",
                        "round_no",
                        "metrics",
                        "counters",
                        "discussion_momentum",
                        "top_threads",
                        "elapsed_seconds",
                        "estimated_total_seconds",
                        "estimated_remaining_seconds",
                        "id",
                    }:
                        continue
                    latest_metrics[key] = value
                discussion_momentum = dict(event.get("discussion_momentum", discussion_momentum))
                top_threads = list(event.get("top_threads", top_threads))
                elapsed_seconds = int(event.get("elapsed_seconds", elapsed_seconds) or elapsed_seconds)
                estimated_total_seconds = event.get("estimated_total_seconds", estimated_total_seconds)
                estimated_remaining_seconds = event.get("estimated_remaining_seconds", estimated_remaining_seconds)
            elif event_type == "run_completed":
                status = "completed"
                elapsed_seconds = int(event.get("elapsed_seconds", elapsed_seconds) or elapsed_seconds)
            elif event_type == "run_failed":
                status = "failed"
            elif event_type == "round_started":
                status = "running"

        if active_authors and "active_authors" not in counters:
            counters["active_authors"] = len(active_authors)

        return {
            "session_id": session_id,
            "status": status,
            "platform": platform or self.settings.simulation_platform,
            "planned_rounds": planned_rounds,
            "event_count": len(events),
            "last_round": last_round,
            "current_round": last_round,
            "elapsed_seconds": elapsed_seconds,
            "estimated_total_seconds": estimated_total_seconds,
            "estimated_remaining_seconds": estimated_remaining_seconds,
            "counters": counters or {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
            "checkpoint_status": checkpoint_status,
            "top_threads": top_threads,
            "discussion_momentum": discussion_momentum,
            "latest_metrics": latest_metrics,
            "round_progress": round_progress,
            "recent_events": events[-10:],
            "events_path": previous_state.get("events_path"),
            "stream_offset_bytes": int(previous_state.get("stream_offset_bytes", 0) or 0),
        }

    def _format_sse(self, event_name: str, payload: dict[str, Any]) -> str:
        return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
