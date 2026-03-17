from __future__ import annotations

import statistics
import time

from fastapi.testclient import TestClient

from mckainsey.main import app
from mckainsey.services.persona_sampler import PersonaSampler


def _mock_personas(count: int) -> list[dict]:
    areas = ["Woodlands", "Yishun", "Tampines", "Bishan", "Sengkang"]
    return [
        {
            "age": 22 + (i % 50),
            "planning_area": areas[i % len(areas)],
            "income_bracket": "$3,000-$5,999" if i % 2 == 0 else "$6,000-$8,999",
        }
        for i in range(count)
    ]


def run_case(client: TestClient, agents: int, rounds: int, runs: int = 3) -> dict:
    timings = []
    for idx in range(runs):
        simulation_id = f"bench-{agents}-{rounds}-{idx}"
        t0 = time.perf_counter()
        response = client.post(
            "/api/v1/phase-b/simulations/run",
            json={
                "simulation_id": simulation_id,
                "policy_summary": "Benchmark policy scenario",
                "agent_count": agents,
                "rounds": rounds,
            },
        )
        response.raise_for_status()
        timings.append(time.perf_counter() - t0)

    return {
        "agents": agents,
        "rounds": rounds,
        "runs": runs,
        "mean_seconds": round(statistics.mean(timings), 3),
        "p95_seconds": round(sorted(timings)[max(0, int(0.95 * len(timings)) - 1)], 3),
    }


def main() -> None:
    # Keep benchmark stable and offline by replacing live dataset fetches.
    PersonaSampler.sample = lambda self, req: _mock_personas(req.limit)  # type: ignore[method-assign]

    client = TestClient(app)
    results = [
        run_case(client, agents=50, rounds=10),
        run_case(client, agents=100, rounds=10),
        run_case(client, agents=200, rounds=20),
    ]
    print(results)


if __name__ == "__main__":
    main()
