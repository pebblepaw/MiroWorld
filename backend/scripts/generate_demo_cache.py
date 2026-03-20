from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from mckainsey.config import get_settings
from mckainsey.main import app
from mckainsey.services.geo_service import PlanningAreaGeoService


SIMULATION_ID = "demo-budget-2026"
POLICY_SUMMARY = (
    "Singapore FY2026 Budget scenario: targeted cost-of-living support, transport affordability, "
    "retirement security, and household resilience measures."
)
DEFAULT_AGENT_COUNT = 50
DEFAULT_ROUNDS = 10


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _log(message: str) -> None:
    print(f"[{_now()}] {message}", flush=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _log(f"Wrote JSON artifact: {path}")


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _require_ok(step: str, response: Response) -> dict[str, Any]:
    if response.status_code >= 400:
        _log(f"{step} failed with status {response.status_code}")
        _log(f"{step} response body: {response.text}")
        raise RuntimeError(f"{step} failed with status {response.status_code}")
    payload = response.json()
    _log(f"{step} succeeded (status {response.status_code})")
    return payload


def _run_or_load(
    should_run: bool,
    scratch_path: Path,
    run_fn,
    stage_name: str,
) -> dict[str, Any]:
    if should_run:
        _log(f"Running stage: {stage_name}")
        payload = run_fn()
        _write_json(scratch_path, payload)
        return payload

    _log(f"Loading cached stage output: {stage_name}")
    payload = _load_json_if_exists(scratch_path)
    if payload is None:
        raise RuntimeError(f"Missing cached artifact for {stage_name}: {scratch_path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cached Budget 2026 demo artifacts.")
    parser.add_argument("--skip-knowledge", action="store_true", help="Skip Phase A knowledge processing step.")
    parser.add_argument(
        "--from-stage",
        choices=["all", "knowledge", "simulation", "memory", "report", "dashboard", "chat"],
        default="all",
        help="Start from stage and run to completion, loading prior stage artifacts from cache.",
    )
    parser.add_argument("--agent-count", type=int, default=DEFAULT_AGENT_COUNT)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    args = parser.parse_args()

    settings = get_settings()
    client = TestClient(app)

    skip_knowledge = args.skip_knowledge or (os.getenv("SKIP_KNOWLEDGE", "false").lower() == "true")

    ordered_stages = ["knowledge", "simulation", "memory", "report", "dashboard", "chat"]
    start_idx = 0 if args.from_stage == "all" else ordered_stages.index(args.from_stage)
    should_run = {stage: idx >= start_idx for idx, stage in enumerate(ordered_stages)}

    scratch_dir = Path("data/demo-run")
    scratch_dir.mkdir(parents=True, exist_ok=True)

    _log("Starting demo cache generation")
    _log(f"Simulation ID: {SIMULATION_ID}")
    _log(f"Simulation params: agent_count={args.agent_count}, rounds={args.rounds}")
    _log(
        "Runtime settings: "
        f"enable_real_oasis={settings.enable_real_oasis}, "
        f"oasis_python_bin={settings.oasis_python_bin}, "
        f"oasis_runner_script={settings.oasis_runner_script}"
    )

    def run_knowledge() -> dict[str, Any]:
        if skip_knowledge:
            return {
                "status": "skipped",
                "reason": "SKIP_KNOWLEDGE=true or --skip-knowledge",
                "document": "Sample_Inputs/fy2026_budget_statement.md",
            }
        response = client.post(
            "/api/v1/phase-a/knowledge/process",
            json={
                "simulation_id": SIMULATION_ID,
                "use_default_demo_document": True,
                "demographic_focus": "Singapore FY2026 budget impact by planning area and income cohorts",
            },
        )
        return _require_ok("phase-a/knowledge/process", response)

    def run_simulation() -> dict[str, Any]:
        response = client.post(
            "/api/v1/phase-b/simulations/run",
            json={
                "simulation_id": SIMULATION_ID,
                "policy_summary": POLICY_SUMMARY,
                "agent_count": args.agent_count,
                "rounds": args.rounds,
            },
        )
        return _require_ok("phase-b/simulations/run", response)

    def run_memory() -> dict[str, Any]:
        response = client.post(
            "/api/v1/phase-c/memory/sync",
            json={"simulation_id": SIMULATION_ID},
        )
        return _require_ok("phase-c/memory/sync", response)

    def run_report() -> dict[str, Any]:
        response = client.get(f"/api/v1/phase-d/report/{SIMULATION_ID}")
        return _require_ok("phase-d/report", response)

    def run_dashboard() -> dict[str, Any]:
        response = client.get(f"/api/v1/phase-e/dashboard/{SIMULATION_ID}")
        return _require_ok("phase-e/dashboard", response)

    knowledge_payload = _run_or_load(
        should_run["knowledge"] or skip_knowledge,
        scratch_dir / "01_knowledge.json",
        run_knowledge,
        "knowledge",
    )
    simulation_payload = _run_or_load(
        should_run["simulation"],
        scratch_dir / "02_simulation.json",
        run_simulation,
        "simulation",
    )
    memory_sync_payload = _run_or_load(
        should_run["memory"],
        scratch_dir / "03_memory_sync.json",
        run_memory,
        "memory",
    )
    report_payload = _run_or_load(
        should_run["report"],
        scratch_dir / "04_report.json",
        run_report,
        "report",
    )
    dashboard_payload = _run_or_load(
        should_run["dashboard"],
        scratch_dir / "05_dashboard.json",
        run_dashboard,
        "dashboard",
    )

    def run_chat() -> dict[str, Any]:
        influential = report_payload.get("influential_agents", [])
        top_agent = influential[0].get("agent_id") if influential else None

        report_chat = client.post(
            "/api/v1/phase-d/report/chat",
            json={
                "simulation_id": SIMULATION_ID,
                "message": "Summarize the strongest dissent clusters and one practical mitigation.",
            },
        )
        report_chat_payload = _require_ok("phase-d/report/chat", report_chat)

        agent_chat_payload: dict[str, Any] | None = None
        if top_agent:
            agent_chat = client.post(
                "/api/v1/phase-c/chat/agent",
                json={
                    "simulation_id": SIMULATION_ID,
                    "agent_id": top_agent,
                    "message": "What drove your final view on this FY2026 budget package?",
                },
            )
            agent_chat_payload = _require_ok("phase-c/chat/agent", agent_chat)

        return {
            "report_chat": report_chat_payload,
            "agent_chat": agent_chat_payload,
        }

    chat_payload = _run_or_load(
        should_run["chat"],
        scratch_dir / "06_chat.json",
        run_chat,
        "chat",
    )

    influential = report_payload.get("influential_agents", [])
    friction = report_payload.get("friction_by_planning_area", [])
    output = {
        "generated_at": _now(),
        "simulation_id": SIMULATION_ID,
        "session": {
            "session_id": SIMULATION_ID,
            "mode": "demo",
            "status": "created",
        },
        "knowledge": knowledge_payload,
        "population": {
            "session_id": SIMULATION_ID,
            "candidate_count": len(influential),
            "sample_count": len(influential),
            "coverage": {
                "planning_areas": sorted({str(agent.get("planning_area", "Unknown")) for agent in influential}),
                "age_buckets": {},
            },
            "sampled_personas": [
                {
                    "agent_id": agent.get("agent_id", f"agent-{idx+1:04d}"),
                    "persona": {
                        "planning_area": agent.get("planning_area", "Unknown"),
                        "income_bracket": agent.get("income_bracket", "Unknown"),
                        "occupation": agent.get("occupation", "Unknown"),
                    },
                    "selection_reason": {
                        "score": agent.get("influence_score", 0.6),
                        "semantic_relevance": 0.7,
                        "geographic_relevance": 0.8,
                        "socioeconomic_relevance": 0.6,
                        "digital_behavior_relevance": 0.5,
                        "filter_alignment": 1.0,
                    },
                }
                for idx, agent in enumerate(influential)
            ],
            "agent_graph": {
                "nodes": [
                    {
                        "id": agent.get("agent_id", f"agent-{idx+1:04d}"),
                        "label": agent.get("agent_id", f"agent-{idx+1:04d}"),
                        "planning_area": agent.get("planning_area", "Unknown"),
                        "score": agent.get("influence_score", 0.6),
                    }
                    for idx, agent in enumerate(influential)
                ],
                "links": [],
            },
            "representativeness": {"status": "cached-demo"},
        },
        "simulation": simulation_payload,
        "simulationState": {
            "session_id": SIMULATION_ID,
            "status": "completed",
            "event_count": len(dashboard_payload.get("simulation", {}).get("top_posts", [])),
            "last_round": args.rounds,
            "latest_metrics": {
                "approval_pre": simulation_payload.get("stage3a_approval_rate", 0),
                "approval_post": simulation_payload.get("stage3b_approval_rate", 0),
            },
            "recent_events": [
                {
                    "event_type": "post_created",
                    "session_id": SIMULATION_ID,
                    "round_no": 1,
                    "actor_agent_id": row.get("actor_agent_id"),
                    "content": row.get("content"),
                }
                for row in dashboard_payload.get("simulation", {}).get("top_posts", [])
            ],
        },
        "memory_sync": memory_sync_payload,
        "report": report_payload,
        "reportFull": {
            "session_id": SIMULATION_ID,
            "report": report_payload,
        },
        "reportOpinions": {
            "session_id": SIMULATION_ID,
            "feed": dashboard_payload.get("simulation", {}).get("top_posts", []),
            "influential_agents": influential,
        },
        "reportFriction": {
            "session_id": SIMULATION_ID,
            "map_metrics": friction,
            "anomaly_summary": f"Highest observed friction cluster: {friction[0]['planning_area']}" if friction else "No friction anomalies in cached run.",
        },
        "interactionHub": {
            "session_id": SIMULATION_ID,
            "report_agent": {
                "starter_prompt": chat_payload.get("report_chat", {}).get("response", ""),
            },
            "influential_agents": influential,
            "selected_agent": influential[0] if influential else None,
        },
        "dashboard": dashboard_payload,
        "report_chat": chat_payload.get("report_chat", {}),
        "agent_chat": chat_payload.get("agent_chat"),
        "brd_metric_snapshot": {
            "agent_count": args.agent_count,
            "rounds": args.rounds,
            "sankey_links": len(dashboard_payload.get("opinion_flow", {}).get("links", [])),
            "heatmap_cells": len(dashboard_payload.get("heatmap_matrix", [])),
            "zep_enabled": bool(memory_sync_payload.get("zep_enabled", False)),
        },
    }

    backend_path = Path("data/demo-output.json")
    frontend_path = Path("../frontend/public/demo-output.json")
    _write_json(backend_path, output)
    _write_json(frontend_path, output)

    _log("Refreshing planning-area GeoJSON cache from Data.gov")
    frontend_geojson_path = Path("../frontend/public/planning-area-boundaries.geojson")
    try:
        geojson = PlanningAreaGeoService(settings).get_geojson(force_refresh=True)
        _write_json(frontend_geojson_path, geojson)
    except Exception as exc:  # noqa: BLE001
        _log(f"GeoJSON refresh failed, attempting cached fallback: {exc}")
        try:
            geojson = PlanningAreaGeoService(settings).get_geojson(force_refresh=False)
            _write_json(frontend_geojson_path, geojson)
        except Exception as fallback_exc:  # noqa: BLE001
            if frontend_geojson_path.exists():
                _log(f"Using existing frontend GeoJSON file: {frontend_geojson_path}")
            else:
                raise RuntimeError(f"No GeoJSON available from API or cache: {fallback_exc}") from fallback_exc

    _log(
        "Demo generation completed: "
        + json.dumps(
            {
                "simulation_id": SIMULATION_ID,
                "backend_cache": str(backend_path),
                "frontend_cache": str(frontend_path),
                "frontend_geojson_cache": str(frontend_geojson_path),
                "zep_enabled": memory_sync_payload.get("zep_enabled", False),
                "interactions": dashboard_payload.get("simulation", {}).get("stats", {}).get("interactions", 0),
            }
        )
    )


if __name__ == "__main__":
    main()
