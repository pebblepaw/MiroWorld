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
