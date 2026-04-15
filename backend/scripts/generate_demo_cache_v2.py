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

REPO_ROOT = Path(__file__).resolve().parents[2]

# ── Config ────────────────────────────────────────────────────────────
SOURCE_URL = (
    "https://www.singaporebudget.gov.sg/budget-speech/budget-statement/"
    "c-harness-ai-as-a-strategic-advantage#Harness-AI-as-a-Strategic-Advantage"
)
COUNTRY = "singapore"
USE_CASE = "public-policy-testing"
PROVIDER = "google"
AGENT_COUNT = 50
ROUNDS = 10

# Models to try in order (fallback on rate-limit)
# Each entry: (provider, model_name, api_key_env_var)
MODEL_CANDIDATES = [
    ("google", "gemini-2.5-flash-lite", "GEMINI_API"),
    ("google", "gemini-2.5-flash", "GEMINI_API"),
    ("google", "gemini-2.0-flash-lite", "GEMINI_API"),
    ("openai", "gpt-4.1-mini", "OPENAI_API"),
    ("openai", "gpt-4.1-nano", "OPENAI_API"),
    ("ollama", "qwen3:4b-instruct-2507-q4_K_M", None),
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


def _provider_key_env(provider: str) -> str | None:
    normalized = str(provider).strip().lower()
    if normalized == "google":
        return "GEMINI_API"
    if normalized == "openai":
        return "OPENAI_API"
    if normalized == "openrouter":
        return "OPENROUTER_API_KEY"
    return None


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
    parser.add_argument("--embed-model", default=None, help="Override embedding model name")
    parser.add_argument("--source-url", default=SOURCE_URL, help="Source URL to scrape for the demo cache")
    parser.add_argument("--country", default=COUNTRY, help="Country code for the demo session")
    parser.add_argument("--use-case", default=USE_CASE, help="Use case code for the demo session")
    parser.add_argument("--extra-question", default=EXTRA_QUESTION["question"], help="Extra analysis question to append to the demo config")
    parser.add_argument("--agents", type=int, default=None, help="Override agent count")
    parser.add_argument("--rounds", type=int, default=None, help="Override round count")
    parser.add_argument("--skip-knowledge", action="store_true")
    parser.add_argument("--skip-simulation", action="store_true")
    parser.add_argument("--session-id", default=None, help="Resume from existing session")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    api = f"{base}/api/v2/console"
    compat_api = f"{base}/api/v2"

    agent_count = args.agents or AGENT_COUNT
    rounds = args.rounds or ROUNDS
    source_url = str(args.source_url).strip() or SOURCE_URL
    country = str(args.country).strip().lower() or COUNTRY
    use_case = str(args.use_case).strip().lower() or USE_CASE
    extra_question = {
        **EXTRA_QUESTION,
        "question": str(args.extra_question).strip() or EXTRA_QUESTION["question"],
    }

    if args.model and args.provider:
        candidates = [(args.provider, args.model, _provider_key_env(args.provider))]
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
            api_key = args.api_key or (os.getenv(key_env, "") if key_env else "")
            if key_env and not api_key:
                _log(f"  No {key_env} env var for {provider}/{model}; relying on backend-configured credentials if available")
            _log(f"Creating session with provider={provider} model={model}")
            try:
                session_body: dict[str, Any] = {
                    "country": country,
                    "use_case": use_case,
                    "provider": "gemini" if provider == "google" else provider,
                    "model": model,
                    "mode": "live",
                }
                if api_key:
                    session_body["api_key"] = api_key
                resp = requests.post(f"{compat_api}/session/create", json=session_body, timeout=30)
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
    active_api_key = args.api_key or (os.getenv(_provider_key_env(provider_used), "") if _provider_key_env(provider_used) else "")

    # ── 2. Store config with extra question ───────────────────────────
    _log("Updating session config with extra question...")
    # First get default analysis questions
    try:
        aq_resp = requests.get(f"{compat_api}/session/{session_id}/analysis-questions", timeout=15)
        default_questions = aq_resp.json().get("questions", []) if aq_resp.status_code < 400 else []
    except Exception:
        default_questions = []

    all_questions = default_questions + [extra_question]
    _log(f"  Total analysis questions: {len(all_questions)}")

    config_patch: dict[str, Any] = {
        "country": country,
        "use_case": use_case,
        "provider": "gemini" if provider_used == "google" else provider_used,
        "model": model_used,
        "analysis_questions": all_questions,
    }
    if active_api_key:
        config_patch["api_key"] = active_api_key
    resp = requests.patch(f"{api}/session/{session_id}/config", json=config_patch, timeout=15)
    _ok("config/update", resp)

    scratch = REPO_ROOT / "backend/data/demo-run"
    scratch.mkdir(parents=True, exist_ok=True)

    # ── 3. Knowledge extraction ───────────────────────────────────────
    knowledge = None
    if not args.skip_knowledge:
        _log("Scraping URL...")
        resp = requests.post(f"{api}/session/{session_id}/scrape",
                             json={"url": source_url}, timeout=120)
        scrape = _ok("scrape", resp)
        _log(f"  Scraped {scrape.get('length', 0)} chars: {scrape.get('title', '')[:80]}")

        _log("Processing knowledge graph...")
        resp = requests.post(f"{api}/session/{session_id}/knowledge/process", json={
            "document_text": scrape.get("text", ""),
            "source_path": source_url,
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
            _log(f"  Loaded {len(knowledge.get('entity_nodes', []))} entities, "
                 f"{len(knowledge.get('relationship_edges', []))} edges from cache")
        else:
            _log("  No cached knowledge found, fetching from session...")
            resp = requests.get(f"{api}/session/{session_id}/knowledge", timeout=30)
            knowledge = _ok("knowledge/get", resp)
        # Inject cached knowledge into the new session's DB
        _log("  Injecting cached knowledge into session...")
        resp = requests.put(f"{api}/session/{session_id}/knowledge",
                            json=knowledge, timeout=30)
        _ok("knowledge/inject", resp)

    # ── 4. Population sampling ────────────────────────────────────────
    _log(f"Sampling {agent_count} agents...")
    resp = requests.post(f"{api}/session/{session_id}/sampling/preview", json={
        "agent_count": agent_count,
        "sample_mode": "affected_groups",
        "seed": 42,
    }, timeout=120)
    population = _ok("sampling/preview", resp)
    _write_json(scratch / "02_population.json", population)
    _log(f"  Sampled: {population.get('sample_count', 0)} agents")

    # ── 5. Run simulation ─────────────────────────────────────────────
    simulation_state = None
    if not args.skip_simulation:
        # Resolve subject_summary from knowledge artifact or scraped content
        subject_summary = ""
        if knowledge:
            subject_summary = str(knowledge.get("summary") or "").strip()
        if not subject_summary and knowledge:
            # Fallback: use the scraped document text (first 2000 chars)
            doc = knowledge.get("document") or {}
            subject_summary = str(doc.get("text") or doc.get("content") or "").strip()[:2000]
        if not subject_summary:
            subject_summary = f"Analysis summary from {source_url}"
        _log(f"Starting simulation ({rounds} rounds, {agent_count} agents)...")
        resp = requests.post(f"{api}/session/{session_id}/simulate", json={
            "rounds": rounds,
            "controversy_boost": 0.0,
            "mode": "live",
            "subject_summary": subject_summary,
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
            _log(f"  Poll {i}: status={status}, round={rnd}/{rounds}, "
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

    # ── 7. Fetch analytics ────────────────────────────────────────────
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

    # ── 8. Assemble demo-output.json ──────────────────────────────────
    _log("Assembling demo-output.json...")
    output = {
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
            "provider": provider_used,
            "model": model_used,
            "agent_count": agent_count,
            "rounds": rounds,
            "controversy_boost": 0.0,
            "analysis_questions": all_questions,
            "generated_at": _now(),
        },
        "analysis_questions": all_questions,
        "knowledge": knowledge,
        "population": population,
        "simulation": simulation_state,
        "simulationState": simulation_state,
        "report": report,
        "analytics": analytics,
    }

    backend_path = REPO_ROOT / "backend/data/demo-output.json"
    frontend_path = REPO_ROOT / "frontend/public/demo-output.json"
    _write_json(backend_path, output)
    _write_json(frontend_path, output)

    _log(f"Demo cache generation complete!")
    _log(f"  Session: {session_id}")
    _log(f"  Model: {model_used}")
    _log(f"  Agents: {agent_count}, Rounds: {rounds}")
    _log(f"  Files: {backend_path}, {frontend_path}")


if __name__ == "__main__":
    main()
