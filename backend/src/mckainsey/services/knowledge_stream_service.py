from __future__ import annotations

import json
import time
from typing import Any, Iterator

from mckainsey.config import Settings
from mckainsey.services.storage import SimulationStore


class KnowledgeStreamService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)

    def reset(self, session_id: str) -> None:
        self.store.clear_knowledge_events(session_id)
        self.store.clear_knowledge_state_snapshot(session_id)
        self.store.save_knowledge_state_snapshot(
            session_id,
            {
                "session_id": session_id,
                "status": "idle",
                "document_count": 0,
                "documents_completed": 0,
                "current_document_index": 0,
                "current_chunk": 0,
                "chunks_processed": 0,
                "total_chunks": 0,
                "total_nodes": 0,
                "total_edges": 0,
                "entity_nodes": [],
                "relationship_edges": [],
            },
        )

    def append_events(self, session_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return self.get_state(session_id)
        self.store.append_knowledge_events(session_id, events)
        all_events = self.store.list_knowledge_events(session_id)
        previous = self.store.get_knowledge_state_snapshot(session_id) or {}
        state = self._build_state(session_id, all_events, previous_state=previous)
        self.store.save_knowledge_state_snapshot(session_id, state)
        return state

    def get_state(self, session_id: str) -> dict[str, Any]:
        state = self.store.get_knowledge_state_snapshot(session_id)
        if state:
            return state
        events = self.store.list_knowledge_events(session_id)
        state = self._build_state(session_id, events, previous_state={})
        self.store.save_knowledge_state_snapshot(session_id, state)
        return state

    def sse_iter(self, session_id: str) -> Iterator[str]:
        events = self.store.list_knowledge_events(session_id)
        replay = events[-self.settings.simulation_stream_replay_limit :]
        for event in replay:
            yield self._format_sse(event.get("event_type", "event"), event)
        sent = len(events)
        idle_cycles = 0
        while idle_cycles < 240:
            current_events = self.store.list_knowledge_events(session_id)
            while sent < len(current_events):
                payload = current_events[sent]
                yield self._format_sse(payload.get("event_type", "event"), payload)
                sent += 1
                idle_cycles = 0
            latest_state = self.store.get_knowledge_state_snapshot(session_id) or {}
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
        state = {
            "session_id": session_id,
            "status": str(previous_state.get("status") or ("running" if events else "idle")),
            "document_count": int(previous_state.get("document_count", 0) or 0),
            "documents_completed": int(previous_state.get("documents_completed", 0) or 0),
            "current_document_index": int(previous_state.get("current_document_index", 0) or 0),
            "current_document_id": previous_state.get("current_document_id"),
            "current_chunk": int(previous_state.get("current_chunk", 0) or 0),
            "chunks_processed": int(previous_state.get("chunks_processed", 0) or 0),
            "total_chunks": int(previous_state.get("total_chunks", 0) or 0),
            "total_nodes": int(previous_state.get("total_nodes", 0) or 0),
            "total_edges": int(previous_state.get("total_edges", 0) or 0),
            "entity_nodes": list(previous_state.get("entity_nodes", [])),
            "relationship_edges": list(previous_state.get("relationship_edges", [])),
            "last_error": previous_state.get("last_error"),
        }

        node_map: dict[str, dict[str, Any]] = {
            str(node.get("id") or ""): dict(node)
            for node in state["entity_nodes"]
            if str(node.get("id") or "").strip()
        }
        edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
        for edge in state["relationship_edges"]:
            key = self._edge_key(edge)
            if key is not None:
                edge_map[key] = dict(edge)

        for event in events:
            event_type = str(event.get("event_type") or "").strip().lower()
            if event_type == "knowledge_started":
                state["status"] = "running"
                state["document_count"] = int(event.get("document_count", state["document_count"]) or state["document_count"])
            elif event_type == "knowledge_document_started":
                state["status"] = "running"
                state["current_document_index"] = int(
                    event.get("document_index", state["current_document_index"]) or state["current_document_index"]
                )
                state["document_count"] = int(event.get("document_count", state["document_count"]) or state["document_count"])
                state["current_document_id"] = event.get("document_id")
            elif event_type == "knowledge_chunk_started":
                state["status"] = "running"
                state["current_chunk"] = int(event.get("chunk_index", state["current_chunk"]) or state["current_chunk"])
                state["total_chunks"] = int(event.get("chunk_count", state["total_chunks"]) or state["total_chunks"])
            elif event_type == "knowledge_chunk_completed":
                state["status"] = "running"
                state["current_chunk"] = int(event.get("chunk_index", state["current_chunk"]) or state["current_chunk"])
                state["total_chunks"] = int(event.get("chunk_count", state["total_chunks"]) or state["total_chunks"])
                state["chunks_processed"] = max(
                    state["chunks_processed"],
                    int(event.get("chunk_index", state["chunks_processed"]) or state["chunks_processed"]),
                )
            elif event_type == "knowledge_partial":
                state["status"] = "running"
                state["current_chunk"] = int(event.get("chunk_index", state["current_chunk"]) or state["current_chunk"])
                state["total_chunks"] = int(event.get("chunk_count", state["total_chunks"]) or state["total_chunks"])
                state["chunks_processed"] = max(
                    state["chunks_processed"],
                    int(event.get("chunk_index", state["chunks_processed"]) or state["chunks_processed"]),
                )
                for node in event.get("entity_nodes", []):
                    node_id = str((node or {}).get("id") or "").strip()
                    if not node_id:
                        continue
                    node_map[node_id] = dict(node)
                for edge in event.get("relationship_edges", []):
                    key = self._edge_key(edge)
                    if key is None:
                        continue
                    edge_map[key] = dict(edge)
                state["total_nodes"] = int(event.get("total_nodes", len(node_map)) or len(node_map))
                state["total_edges"] = int(event.get("total_edges", len(edge_map)) or len(edge_map))
            elif event_type == "knowledge_completed":
                state["status"] = "completed"
                state["documents_completed"] = int(event.get("document_count", state["document_count"]) or state["document_count"])
                state["total_nodes"] = int(event.get("total_nodes", len(node_map)) or len(node_map))
                state["total_edges"] = int(event.get("total_edges", len(edge_map)) or len(edge_map))
            elif event_type == "knowledge_failed":
                state["status"] = "failed"
                state["last_error"] = event.get("detail") or event.get("error")

        state["entity_nodes"] = list(node_map.values())
        state["relationship_edges"] = list(edge_map.values())
        return state

    def _edge_key(self, edge: dict[str, Any] | None) -> tuple[str, str, str] | None:
        payload = edge or {}
        source = str(payload.get("source") or "").strip()
        target = str(payload.get("target") or "").strip()
        edge_type = str(payload.get("label") or payload.get("type") or "").strip()
        if not source or not target or not edge_type:
            return None
        return (source, target, edge_type)

    def _format_sse(self, event_name: str, payload: dict[str, Any]) -> str:
        return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
