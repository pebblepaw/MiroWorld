from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from mckainsey.config import get_settings
from mckainsey.main import app
from mckainsey.services.storage import SimulationStore


DEFAULT_URL = (
    "https://www.singaporebudget.gov.sg/budget-speech/budget-statement/"
    "c-harness-ai-as-a-strategic-advantage#Harness-AI-as-a-Strategic-Advantage"
)
DEFAULT_AGENT_COUNT = 50
DEFAULT_ROUNDS = 8
DEFAULT_CONTROVERSY_BOOST = 0.5
DEFAULT_COUNTRY = "singapore"
DEFAULT_PROVIDER = "google"
DEFAULT_USE_CASE = "public-policy-testing"
DEFAULT_MODEL = "gemini-2.5-flash-lite"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _log(message: str) -> None:
    print(f"[{_now()}] {message}", flush=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"Wrote JSON artifact: {path}")


def _require_ok(step: str, response: Response) -> dict[str, Any]:
    if response.status_code >= 400:
        _log(f"{step} failed with status {response.status_code}")
        _log(f"{step} response body: {response.text}")
        raise RuntimeError(f"{step} failed with status {response.status_code}")
    payload = response.json()
    _log(f"{step} succeeded (status {response.status_code})")
    return payload


def _extract_opinion_score(record: dict[str, Any]) -> float:
    raw = record.get("opinion_score")
    if isinstance(raw, (int, float)):
        return float(raw)

    raw = record.get("score")
    if isinstance(raw, (int, float)):
        return float(raw)

    raw = record.get("stance_score")
    if isinstance(raw, (int, float)):
        # Map 0..1 stance scores to the opinion 1..10 scale.
        return 1.0 + (float(raw) * 9.0)

    return 5.0


def _approval_rate(scores: list[float]) -> float:
    if not scores:
        return 0.0
    approvals = sum(1 for score in scores if score >= 6.0)
    return approvals / len(scores)


def _net_shift(baseline_scores: list[float], final_scores: list[float]) -> float:
    if not baseline_scores or not final_scores:
        return 0.0
    size = min(len(baseline_scores), len(final_scores))
    if size == 0:
        return 0.0
    baseline_avg = sum(baseline_scores[:size]) / size
    final_avg = sum(final_scores[:size]) / size
    return final_avg - baseline_avg


def _poll_simulation_state(
    client: TestClient,
    session_id: str,
    *,
    timeout_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(30, timeout_seconds)
    last_status: str | None = None
    last_round: int | None = None

    while time.monotonic() < deadline:
        state = _require_ok(
            "simulation/state",
            client.get(f"/api/v2/console/session/{session_id}/simulation/state"),
        )
        status = str(state.get("status") or "unknown")
        current_round = int(state.get("current_round") or 0)

        if status != last_status or current_round != last_round:
            elapsed = int(state.get("elapsed_seconds") or 0)
            remaining = int(state.get("estimated_remaining_seconds") or 0)
            _log(
                "Simulation progress: "
                f"status={status}, round={current_round}, elapsed={elapsed}s, remaining={remaining}s"
            )
            last_status = status
            last_round = current_round

        if status == "completed":
            return state

        if status == "failed":
            latest = state.get("latest_metrics") if isinstance(state.get("latest_metrics"), dict) else {}
            err = str((latest or {}).get("error") or "Simulation failed")
            raise RuntimeError(err)

        time.sleep(max(1, poll_seconds))

    raise TimeoutError(
        f"Simulation did not finish within {timeout_seconds} seconds for session {session_id}."
    )


def _resolve_api_key(provider: str) -> str | None:
    settings = get_settings()
    return settings.resolved_key_for_provider(provider)


def _build_demo_output(
    *,
    session_id: str,
    source_url: str,
    country: str,
    use_case: str,
    provider: str,
    model: str,
    agent_count: int,
    rounds: int,
    controversy_boost: float,
    knowledge: dict[str, Any],
    population: dict[str, Any],
    simulation_state: dict[str, Any],
    report: dict[str, Any],
    report_opinions: dict[str, Any],
    report_friction: dict[str, Any],
    interaction_hub: dict[str, Any],
    analytics_polarization: dict[str, Any],
    analytics_opinion_flow: dict[str, Any],
    analytics_influence: dict[str, Any],
    analytics_cascades: dict[str, Any],
    baseline_scores: list[float],
    final_scores: list[float],
) -> dict[str, Any]:
    stage3a = _approval_rate(baseline_scores)
    stage3b = _approval_rate(final_scores)

    simulation_summary = {
        "session_id": session_id,
        "simulation_id": session_id,
        "agent_count": int(population.get("sample_count") or agent_count),
        "rounds": rounds,
        "controversy_boost": controversy_boost,
        "stage3a_approval_rate": round(stage3a, 4),
        "stage3b_approval_rate": round(stage3b, 4),
        "net_opinion_shift": round(_net_shift(baseline_scores, final_scores), 4),
        "baseline_scores": baseline_scores,
        "final_scores": final_scores,
        "runtime": "oasis",
    }

    return {
        "generated_at": _now(),
        "session": {
            "session_id": session_id,
            "mode": "demo",
            "status": "simulation_completed",
        },
        "source_run": {
            "source_url": source_url,
            "country": country,
            "use_case": use_case,
            "provider": provider,
            "model": model,
            "agent_count": agent_count,
            "rounds": rounds,
            "controversy_boost": controversy_boost,
            "generated_at": _now(),
        },
        "knowledge": knowledge,
        "population": population,
        "simulation": simulation_summary,
        "simulationState": simulation_state,
        "report": report,
        "reportFull": report,
        "reportOpinions": report_opinions,
        "reportFriction": report_friction,
        "interactionHub": interaction_hub,
        "analytics": {
            "polarization": analytics_polarization,
            "opinion_flow": analytics_opinion_flow,
            "influence": analytics_influence,
            "cascades": analytics_cascades,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run V2 live simulation from URL and write demo cache artifacts.",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Source URL for Screen 1 scrape input.")
    parser.add_argument("--country", default=DEFAULT_COUNTRY)
    parser.add_argument("--use-case", default=DEFAULT_USE_CASE)
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", default=None, help="Optional provider API key override.")
    parser.add_argument("--agent-count", type=int, default=DEFAULT_AGENT_COUNT)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--controversy-boost", type=float, default=DEFAULT_CONTROVERSY_BOOST)
    parser.add_argument("--timeout-seconds", type=int, default=5400)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()

    if args.agent_count < 2:
        raise ValueError("--agent-count must be >= 2")
    if args.rounds < 1:
        raise ValueError("--rounds must be >= 1")
    if args.controversy_boost < 0.0 or args.controversy_boost > 1.0:
        raise ValueError("--controversy-boost must be in [0.0, 1.0]")

    settings = get_settings()
    store = SimulationStore(settings.simulation_db_path)
    client = TestClient(app)

    api_key = args.api_key or _resolve_api_key(args.provider)
    if not api_key and args.provider in {"google", "gemini", "openai", "openrouter"}:
        raise RuntimeError(
            f"No API key resolved for provider '{args.provider}'. Set it in .env or pass --api-key."
        )

    _log("Starting V2 live run for demo cache generation")
    _log(
        "Run params: "
        f"url={args.url}, agent_count={args.agent_count}, rounds={args.rounds}, "
        f"controversy_boost={args.controversy_boost}"
    )

    session_payload = {
        "country": args.country,
        "provider": args.provider,
        "model": args.model,
        "use_case": args.use_case,
        "mode": "live",
    }
    if api_key:
        session_payload["api_key"] = api_key

    session = _require_ok(
        "session/create",
        client.post("/api/v2/session/create", json=session_payload),
    )
    session_id = str(session["session_id"])
    _log(f"Created session: {session_id}")

    scraped = _require_ok(
        "session/scrape",
        client.post(
            f"/api/v2/console/session/{session_id}/scrape",
            json={"url": args.url},
        ),
    )

    documents = [
        {
            "document_text": str(scraped.get("text") or ""),
            "source_path": args.url,
        }
    ]
    knowledge = _require_ok(
        "knowledge/process",
        client.post(
            f"/api/v2/console/session/{session_id}/knowledge/process",
            json={
                "documents": documents,
                "demographic_focus": "Singapore residents by planning area, age, income, and occupation",
            },
        ),
    )

    population = _require_ok(
        "sampling/preview",
        client.post(
            f"/api/v2/console/session/{session_id}/sampling/preview",
            json={
                "agent_count": args.agent_count,
                "sample_mode": "affected_groups",
            },
        ),
    )

    _require_ok(
        "simulation/start",
        client.post(
            f"/api/v2/console/session/{session_id}/simulation/start",
            json={
                "policy_summary": str(knowledge.get("summary") or "").strip(),
                "rounds": args.rounds,
                "controversy_boost": args.controversy_boost,
                "mode": "live",
            },
        ),
    )

    simulation_state = _poll_simulation_state(
        client,
        session_id,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )

    _require_ok(
        "report/generate",
        client.post(f"/api/v2/console/session/{session_id}/report/generate"),
    )
    report = _require_ok(
        "report",
        client.get(f"/api/v2/console/session/{session_id}/report"),
    )
    report_opinions = _require_ok(
        "report/opinions",
        client.get(f"/api/v2/console/session/{session_id}/report/opinions"),
    )
    report_friction = _require_ok(
        "report/friction-map",
        client.get(f"/api/v2/console/session/{session_id}/report/friction-map"),
    )
    interaction_hub = _require_ok(
        "interaction-hub",
        client.get(f"/api/v2/console/session/{session_id}/interaction-hub"),
    )

    analytics_polarization = _require_ok(
        "analytics/polarization",
        client.get(f"/api/v2/console/session/{session_id}/analytics/polarization"),
    )
    analytics_opinion_flow = _require_ok(
        "analytics/opinion-flow",
        client.get(f"/api/v2/console/session/{session_id}/analytics/opinion-flow"),
    )
    analytics_influence = _require_ok(
        "analytics/influence",
        client.get(f"/api/v2/console/session/{session_id}/analytics/influence"),
    )
    analytics_cascades = _require_ok(
        "analytics/cascades",
        client.get(f"/api/v2/console/session/{session_id}/analytics/cascades"),
    )

    baseline_records = store.list_checkpoint_records(session_id, "baseline")
    final_records = store.list_checkpoint_records(session_id, "final")
    baseline_scores = [_extract_opinion_score(row) for row in baseline_records]
    final_scores = [_extract_opinion_score(row) for row in final_records]

    demo_output = _build_demo_output(
        session_id=session_id,
        source_url=args.url,
        country=args.country,
        use_case=args.use_case,
        provider=args.provider,
        model=args.model,
        agent_count=args.agent_count,
        rounds=args.rounds,
        controversy_boost=args.controversy_boost,
        knowledge=knowledge,
        population=population,
        simulation_state=simulation_state,
        report=report,
        report_opinions=report_opinions,
        report_friction=report_friction,
        interaction_hub=interaction_hub,
        analytics_polarization=analytics_polarization,
        analytics_opinion_flow=analytics_opinion_flow,
        analytics_influence=analytics_influence,
        analytics_cascades=analytics_cascades,
        baseline_scores=baseline_scores,
        final_scores=final_scores,
    )

    backend_path = Path(settings.console_demo_output_path)
    frontend_path = Path(settings.console_demo_frontend_output_path)
    _write_json(backend_path, demo_output)
    _write_json(frontend_path, demo_output)

    _log("Demo cache generation completed successfully")
    _log(
        "Summary: "
        f"session_id={session_id}, entities={len(knowledge.get('entity_nodes', []))}, "
        f"sample_count={population.get('sample_count')}, rounds={args.rounds}, "
        f"events={simulation_state.get('event_count', 0)}"
    )


if __name__ == "__main__":
    main()
