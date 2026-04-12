"""Generate demo cache using V2 API endpoints against a running backend.

Usage:
    python backend/scripts/generate_demo_cache_v2.py [--base-url http://localhost:8000]

Requires:
    - Backend running at the specified base URL
    - GEMINI_API env var set (or pass --api-key)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

# ── Config ────────────────────────────────────────────────────────────
SOURCE_URL = (
    "https://www.singaporebudget.gov.sg/budget-speech/budget-statement/"
    "c-harness-ai-as-a-strategic-advantage#Harness-AI-as-a-Strategic-Advantage"
)
COUNTRY = "singapore"
USE_CASE = "public-policy-testing"
PROVIDER = "google"
AGENT_COUNT = 100
ROUNDS = 10

# Models to try in order (fallback on rate-limit)
# Each entry: (provider, model_name, api_key_env_var)
MODEL_CANDIDATES = [
    ("google", "gemini-2.5-flash-lite", "GEMINI_API"),
    ("google", "gemini-2.5-flash", "GEMINI_API"),
    ("google", "gemini-2.0-flash-lite", "GEMINI_API"),
    ("openai", "gpt-4.1-mini", "OPENAI_API"),
    ("openai", "gpt-4.1-nano", "OPENAI_API"),
]

EXTRA_QUESTION = {
    "question": "Are you worried about AI replacing your job? Yes/No",
    "type": "yes-no",
    "metric_name": "ai_job_worry",
    "metric_label": "AI Job Replacement Concern",
    "report_title": "AI Job Displacement Concerns",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _log(msg: str) -> None:
    print(f"[{_now()}] {msg}", flush=True)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    _log(f"  Wrote {path} ({path.stat().st_size / 1024:.0f} KB)")


def _ok(label: str, resp: requests.Response) -> dict:
    if resp.status_code >= 400:
        _log(f"  FAILED {label}: {resp.status_code}")
        _log(f"  Body: {resp.text[:2000]}")
        raise RuntimeError(f"{label} failed: {resp.status_code}")
    data = resp.json()
    _log(f"  OK {label} ({resp.status_code})")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--model", default=None, help="Override model (skip fallback)")
    parser.add_argument("--provider", default=None, help="Override provider")
    parser.add_argument("--skip-knowledge", action="store_true")
    parser.add_argument("--skip-simulation", action="store_true")
    parser.add_argument("--session-id", default=None, help="Resume from existing session")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    api = f"{base}/api/v2/console"

    if args.model and args.provider:
        candidates = [(args.provider, args.model, "GEMINI_API" if args.provider == "google" else "OPENAI_API")]
    elif args.model:
        candidates = [("google", args.model, "GEMINI_API")]
    else:
        candidates = MODEL_CANDIDATES

    # ── 1. Create session ─────────────────────────────────────────────
    session_id = args.session_id
    model_used = candidates[0][1]
    provider_used = candidates[0][0]

    if not session_id:
        for provider, model, key_env in candidates:
            api_key = args.api_key or os.getenv(key_env, "")
            if not api_key:
                _log(f"  Skipping {provider}/{model}: no {key_env} env var")
                continue
            _log(f"Creating session with provider={provider} model={model}")
            try:
                resp = requests.post(f"{api}/session", json={
                    "mode": "live",
                    "model_provider": provider,
                    "model_name": model,
                    "api_key": api_key,
                }, timeout=30)
                data = _ok("session", resp)
                session_id = data["session_id"]
                model_used = model
                provider_used = provider
                _log(f"Session created: {session_id} (provider={provider}, model={model})")
                break
            except Exception as exc:
                _log(f"  Provider {provider} model {model} failed: {exc}")
                continue

        if not session_id:
            _log("ERROR: Could not create session with any model/provider")
            sys.exit(1)
    else:
        provider_used = args.provider or "google"
        _log(f"Resuming session: {session_id}")

    # Resolve the api_key for the winning provider
    active_api_key = args.api_key or os.getenv(
        "GEMINI_API" if provider_used == "google" else "OPENAI_API", ""
    )

    # ── 2. Store config with extra question ───────────────────────────
    _log("Updating session config with extra question...")
    # First get default analysis questions
    try:
        aq_resp = requests.get(f"{api}/session/{session_id}/analysis-questions", timeout=15)
        default_questions = aq_resp.json().get("questions", []) if aq_resp.status_code < 400 else []
    except Exception:
        default_questions = []

    all_questions = default_questions + [EXTRA_QUESTION]
    _log(f"  Total analysis questions: {len(all_questions)}")

    resp = requests.patch(f"{api}/session/{session_id}/config", json={
        "country": COUNTRY,
        "use_case": USE_CASE,
        "provider": provider_used,
        "model": model_used,
        "api_key": active_api_key,
        "analysis_questions": all_questions,
    }, timeout=15)
    _ok("config/update", resp)

    scratch = Path("backend/data/demo-run")
    scratch.mkdir(parents=True, exist_ok=True)

    # ── 3. Knowledge extraction ───────────────────────────────────────
    knowledge = None
    if not args.skip_knowledge:
        _log("Scraping URL...")
        resp = requests.post(f"{api}/session/{session_id}/scrape",
                             json={"url": SOURCE_URL}, timeout=120)
        scrape = _ok("scrape", resp)
        _log(f"  Scraped {scrape.get('length', 0)} chars: {scrape.get('title', '')[:80]}")

        _log("Processing knowledge graph...")
        resp = requests.post(f"{api}/session/{session_id}/knowledge/process", json={
            "document_text": scrape.get("text", ""),
            "source_path": SOURCE_URL,
        }, timeout=300)
        knowledge = _ok("knowledge/process", resp)
        _write_json(scratch / "01_knowledge.json", knowledge)
        _log(f"  Entities: {len(knowledge.get('entity_nodes', []))}, "
             f"Edges: {len(knowledge.get('relationship_edges', []))}")
    else:
        _log("Skipping knowledge (loading from cache)...")
        cache_path = scratch / "01_knowledge.json"
        if cache_path.exists():
            knowledge = json.loads(cache_path.read_text())
        else:
            _log("  No cached knowledge found, fetching from session...")
            resp = requests.get(f"{api}/session/{session_id}/knowledge", timeout=30)
            knowledge = _ok("knowledge/get", resp)

    # ── 4. Population sampling ────────────────────────────────────────
    _log(f"Sampling {AGENT_COUNT} agents...")
    resp = requests.post(f"{api}/session/{session_id}/sampling/preview", json={
        "agent_count": AGENT_COUNT,
        "sample_mode": "affected_groups",
        "seed": 42,
    }, timeout=120)
    population = _ok("sampling/preview", resp)
    _write_json(scratch / "02_population.json", population)
    _log(f"  Sampled: {population.get('sample_count', 0)} agents")

    # ── 5. Run simulation ─────────────────────────────────────────────
    simulation_state = None
    if not args.skip_simulation:
        _log(f"Starting simulation ({ROUNDS} rounds, {AGENT_COUNT} agents)...")
        resp = requests.post(f"{api}/session/{session_id}/simulate", json={
            "rounds": ROUNDS,
            "controversy_boost": 0.0,
            "mode": "live",
        }, timeout=60)
        sim_start = _ok("simulate", resp)
        _log(f"  Simulation started, status={sim_start.get('status')}")

        # Poll until done
        max_polls = 600  # 10 min max
        poll_interval = 3
        for i in range(max_polls):
            time.sleep(poll_interval)
            resp = requests.get(f"{api}/session/{session_id}/simulation/state", timeout=15)
            if resp.status_code >= 400:
                _log(f"  Poll {i}: status check failed ({resp.status_code})")
                continue
            state = resp.json()
            status = state.get("status", "unknown")
            rnd = state.get("current_round", "?")
            posts = state.get("counters", {}).get("posts", 0)
            comments = state.get("counters", {}).get("comments", 0)
            _log(f"  Poll {i}: status={status}, round={rnd}/{ROUNDS}, "
                 f"posts={posts}, comments={comments}")
            if status in ("completed", "error", "failed"):
                simulation_state = state
                break
        else:
            _log("ERROR: Simulation timed out after 10 minutes")
            resp = requests.get(f"{api}/session/{session_id}/simulation/state", timeout=15)
            simulation_state = resp.json() if resp.status_code < 400 else {}

        _write_json(scratch / "03_simulation_state.json", simulation_state or {})
    else:
        _log("Skipping simulation (loading from cache)...")
        cache_path = scratch / "03_simulation_state.json"
        if cache_path.exists():
            simulation_state = json.loads(cache_path.read_text())
        else:
            resp = requests.get(f"{api}/session/{session_id}/simulation/state", timeout=15)
            simulation_state = resp.json() if resp.status_code < 400 else {}

    if not simulation_state or simulation_state.get("status") == "error":
        _log(f"WARNING: Simulation ended with status={simulation_state.get('status')}")

    # ── 6. Generate report ────────────────────────────────────────────
    _log("Generating report...")
    resp = requests.post(f"{api}/session/{session_id}/report/generate", timeout=300)
    report_gen = _ok("report/generate", resp)

    _log("Fetching full report...")
    resp = requests.get(f"{api}/session/{session_id}/report", timeout=30)
    report = _ok("report/get", resp)
    _write_json(scratch / "04_report.json", report)

    # ── 7. Fetch report sub-views ─────────────────────────────────────
    _log("Fetching report opinions feed...")
    try:
        resp = requests.get(f"{api}/session/{session_id}/report/opinions", timeout=30)
        report_opinions = _ok("report/opinions", resp)
    except Exception as exc:
        _log(f"  Report opinions failed: {exc}")
        report_opinions = {"session_id": session_id, "feed": [], "influential_agents": []}

    _log("Fetching friction map...")
    try:
        resp = requests.get(f"{api}/session/{session_id}/report/friction-map", timeout=30)
        report_friction = _ok("report/friction-map", resp)
    except Exception as exc:
        _log(f"  Friction map failed: {exc}")
        report_friction = {"session_id": session_id, "map_metrics": [], "anomaly_summary": ""}

    _log("Fetching interaction hub...")
    try:
        resp = requests.get(f"{api}/session/{session_id}/interaction-hub", timeout=30)
        interaction_hub = _ok("interaction-hub", resp)
    except Exception as exc:
        _log(f"  Interaction hub failed: {exc}")
        interaction_hub = {"session_id": session_id, "influential_agents": []}

    # ── 8. Fetch analytics ────────────────────────────────────────────
    _log("Fetching analytics...")
    analytics = {}
    for endpoint in ["polarization", "opinion-flow", "influence", "cascades"]:
        try:
            resp = requests.get(f"{api}/session/{session_id}/analytics/{endpoint}", timeout=30)
            analytics[endpoint.replace("-", "_")] = resp.json() if resp.status_code < 400 else {}
            _log(f"  analytics/{endpoint}: OK")
        except Exception as exc:
            _log(f"  analytics/{endpoint}: {exc}")
            analytics[endpoint.replace("-", "_")] = {}

    _write_json(scratch / "05_analytics.json", analytics)

    # ── 9. Assemble demo-output.json ──────────────────────────────────
    _log("Assembling demo-output.json...")
    output = {
        "generated_at": _now(),
        "session": {
            "session_id": session_id,
            "mode": "demo",
            "status": "simulation_completed",
        },
        "source_run": {
            "source_url": SOURCE_URL,
            "country": COUNTRY,
            "use_case": USE_CASE,
            "provider": provider_used,
            "model": model_used,
            "agent_count": AGENT_COUNT,
            "rounds": ROUNDS,
            "controversy_boost": 0.0,
            "generated_at": _now(),
        },
        "knowledge": knowledge,
        "population": population,
        "simulation": simulation_state,
        "simulationState": simulation_state,
        "report": report,
        "reportFull": {
            "session_id": session_id,
            "report": report,
        },
        "reportOpinions": report_opinions,
        "reportFriction": report_friction,
        "interactionHub": interaction_hub,
        "analytics": analytics,
    }

    backend_path = Path("backend/data/demo-output.json")
    frontend_path = Path("frontend/public/demo-output.json")
    _write_json(backend_path, output)
    _write_json(frontend_path, output)

    _log(f"Demo cache generation complete!")
    _log(f"  Session: {session_id}")
    _log(f"  Model: {model_used}")
    _log(f"  Agents: {AGENT_COUNT}, Rounds: {ROUNDS}")
    _log(f"  Files: {backend_path}, {frontend_path}")


if __name__ == "__main__":
    main()
