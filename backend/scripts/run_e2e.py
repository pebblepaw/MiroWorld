from __future__ import annotations

import time

from fastapi.testclient import TestClient

from miroworld.main import app


def main() -> None:
    client = TestClient(app)
    simulation_id = "e2e-demo"

    t0 = time.perf_counter()
    run_resp = client.post(
        "/api/v1/phase-b/simulations/run",
        json={
            "simulation_id": simulation_id,
            "policy_summary": "Pilot congestion pricing with low-income transport rebates",
            "agent_count": 50,
            "rounds": 10,
        },
    )
    run_resp.raise_for_status()

    sync_resp = client.post("/api/v1/phase-c/memory/sync", json={"simulation_id": simulation_id})
    sync_resp.raise_for_status()

    report_resp = client.get(f"/api/v1/phase-d/report/{simulation_id}")
    report_resp.raise_for_status()

    dashboard_resp = client.get(f"/api/v1/phase-e/dashboard/{simulation_id}")
    dashboard_resp.raise_for_status()

    elapsed = time.perf_counter() - t0
    print({
        "simulation_id": simulation_id,
        "elapsed_seconds": round(elapsed, 3),
        "approval_pre": run_resp.json()["stage3a_approval_rate"],
        "approval_post": run_resp.json()["stage3b_approval_rate"],
        "memory_events": sync_resp.json()["synced_events"],
        "report_keys": list(report_resp.json().keys()),
        "dashboard_keys": list(dashboard_resp.json().keys()),
    })


if __name__ == "__main__":
    main()
