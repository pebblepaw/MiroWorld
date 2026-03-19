from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from mckainsey.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug Phase B simulation endpoint.")
    parser.add_argument("--simulation-id", default="debug-phase-b")
    parser.add_argument("--agent-count", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--policy", default="Debug policy summary")
    parser.add_argument("--out", default="data/demo-run/debug_phase_b_response.json")
    args = parser.parse_args()

    client = TestClient(app)
    payload = {
        "simulation_id": args.simulation_id,
        "policy_summary": args.policy,
        "agent_count": args.agent_count,
        "rounds": args.rounds,
    }

    print("[debug-phase-b] request payload:")
    print(json.dumps(payload, indent=2))

    response = client.post("/api/v1/phase-b/simulations/run", json=payload)

    body: dict | str
    try:
        body = response.json()
    except Exception:
        body = response.text

    output = {
        "status_code": response.status_code,
        "body": body,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"[debug-phase-b] status: {response.status_code}")
    print("[debug-phase-b] response body:")
    print(json.dumps(body, indent=2) if isinstance(body, dict) else str(body))
    print(f"[debug-phase-b] wrote: {out_path}")


if __name__ == "__main__":
    main()
