import json

from mckainsey.config import Settings
from mckainsey.services.simulation_stream_service import SimulationStreamService
from mckainsey.services.storage import SimulationStore


def test_simulation_stream_service_ingests_events_and_updates_state(tmp_path):
    db_path = tmp_path / "simulation.db"
    settings = Settings(simulation_db_path=str(db_path))
    service = SimulationStreamService(settings)
    store = SimulationStore(str(db_path))

    session_id = "session-stream"
    store.upsert_console_session(session_id=session_id, mode="live", status="running")

    events_path = tmp_path / "events.ndjson"
    events = [
        {"event_type": "run_started", "session_id": session_id, "round_no": 0},
        {"event_type": "post_created", "session_id": session_id, "round_no": 1, "actor_agent_id": "agent-0001", "content": "Post body"},
        {"event_type": "comment_created", "session_id": session_id, "round_no": 1, "actor_agent_id": "agent-0002", "content": "Comment body"},
        {"event_type": "metrics_updated", "session_id": session_id, "round_no": 1, "metrics": {"approval": 0.48}},
    ]
    events_path.write_text("\n".join(json.dumps(row) for row in events), encoding="utf-8")

    ingested = service.ingest_events_file(session_id, events_path)
    assert ingested == 4

    persisted = store.list_simulation_events(session_id)
    assert len(persisted) == 4

    state = store.get_simulation_state_snapshot(session_id)
    assert state["session_id"] == session_id
    assert state["event_count"] == 4
    assert state["latest_metrics"]["approval"] == 0.48


def test_simulation_stream_service_ingests_incremental_events_and_tracks_live_progress(tmp_path):
    db_path = tmp_path / "simulation.db"
    settings = Settings(simulation_db_path=str(db_path))
    service = SimulationStreamService(settings)
    store = SimulationStore(str(db_path))

    session_id = "session-live"
    store.upsert_console_session(session_id=session_id, mode="live", status="running")

    events_path = tmp_path / "live-events.ndjson"
    initial_events = [
        {
            "event_type": "run_started",
            "session_id": session_id,
            "platform": "reddit",
            "planned_rounds": 4,
            "timestamp": "2026-03-21T00:00:00Z",
        },
        {
            "event_type": "checkpoint_started",
            "session_id": session_id,
            "checkpoint_kind": "baseline",
            "total_agents": 3,
            "timestamp": "2026-03-21T00:00:01Z",
        },
    ]
    events_path.write_text("\n".join(json.dumps(row) for row in initial_events) + "\n", encoding="utf-8")

    ingested_first = service.ingest_events_incremental(session_id, events_path)
    assert ingested_first == 2

    intermediate = service.get_state(session_id)
    assert intermediate["status"] == "running"
    assert intermediate["platform"] == "reddit"
    assert intermediate["planned_rounds"] == 4
    assert intermediate["current_round"] == 0
    assert intermediate["checkpoint_status"]["baseline"]["status"] == "running"

    later_events = [
        {
            "event_type": "checkpoint_completed",
            "session_id": session_id,
            "checkpoint_kind": "baseline",
            "completed_agents": 3,
            "total_agents": 3,
            "timestamp": "2026-03-21T00:00:05Z",
        },
        {
            "event_type": "round_started",
            "session_id": session_id,
            "round_no": 1,
            "timestamp": "2026-03-21T00:00:06Z",
        },
        {
            "event_type": "post_created",
            "session_id": session_id,
            "round_no": 1,
            "actor_agent_id": "agent-0001",
            "post_id": 1,
            "content": "We need stronger sports grants.",
            "timestamp": "2026-03-21T00:00:07Z",
        },
        {
            "event_type": "comment_created",
            "session_id": session_id,
            "round_no": 1,
            "actor_agent_id": "agent-0002",
            "post_id": 1,
            "comment_id": 9,
            "content": "Only if access is equitable.",
            "timestamp": "2026-03-21T00:00:08Z",
        },
        {
            "event_type": "reaction_added",
            "session_id": session_id,
            "round_no": 1,
            "actor_agent_id": "agent-0003",
            "post_id": 1,
            "reaction": "like",
            "timestamp": "2026-03-21T00:00:09Z",
        },
        {
            "event_type": "metrics_updated",
            "session_id": session_id,
            "round_no": 1,
            "elapsed_seconds": 15,
            "estimated_total_seconds": 60,
            "estimated_remaining_seconds": 45,
            "counters": {"posts": 1, "comments": 1, "reactions": 1, "active_authors": 2},
            "discussion_momentum": {"approval_delta": 0.12, "dominant_stance": "support"},
            "top_threads": [{"post_id": 1, "title": "Sports Grants", "engagement": 3}],
            "timestamp": "2026-03-21T00:00:10Z",
        },
        {
            "event_type": "round_completed",
            "session_id": session_id,
            "round_no": 1,
            "timestamp": "2026-03-21T00:00:11Z",
        },
        {
            "event_type": "run_completed",
            "session_id": session_id,
            "round_no": 1,
            "elapsed_seconds": 16,
            "timestamp": "2026-03-21T00:00:12Z",
        },
    ]
    with events_path.open("a", encoding="utf-8") as handle:
        for row in later_events:
            handle.write(json.dumps(row) + "\n")

    ingested_second = service.ingest_events_incremental(session_id, events_path)
    assert ingested_second == len(later_events)

    final_state = service.get_state(session_id)
    assert final_state["status"] == "completed"
    assert final_state["event_count"] == len(initial_events) + len(later_events)
    assert final_state["current_round"] == 1
    assert final_state["elapsed_seconds"] == 16
    assert final_state["estimated_total_seconds"] == 60
    assert final_state["estimated_remaining_seconds"] == 45
    assert final_state["counters"]["posts"] == 1
    assert final_state["counters"]["comments"] == 1
    assert final_state["counters"]["reactions"] == 1
    assert final_state["discussion_momentum"]["dominant_stance"] == "support"
    assert final_state["top_threads"][0]["post_id"] == 1
