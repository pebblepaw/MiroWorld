from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response

from miroworld.config import get_settings
from miroworld.main import app
from miroworld.services.storage import SimulationStore


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
DEFAULT_EXTRA_QUESTION = "Are you worried about AI replacing your job? Yes/No"


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


def _normalize_discourse_text(value: Any) -> str:
    text = str(value or "").replace("**", " ")
    return " ".join(text.split()).strip().lower()


def _agent_id_from_oasis_alias(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith("agent-"):
        return text
    if text.startswith("sg_agent_"):
        raw_number = text.removeprefix("sg_agent_").strip()
        if raw_number.isdigit():
            return f"agent-{int(raw_number):04d}"
    generic_match = re.match(r".*_(\d+)$", text)
    if generic_match:
        return f"agent-{int(generic_match.group(1)):04d}"
    return None


def _display_name_lookup(population: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in population.get("sampled_personas") or []:
        if not isinstance(row, dict):
            continue
        agent_id = str(row.get("agent_id") or "").strip()
        persona = row.get("persona") if isinstance(row.get("persona"), dict) else {}
        display_name = str(
            row.get("display_name")
            or persona.get("display_name")
            or persona.get("confirmed_name")
            or persona.get("name")
            or ""
        ).strip()
        if agent_id and display_name:
            lookup[agent_id] = display_name
    return lookup


def _enrich_cascades_from_oasis(
    *,
    session_id: str,
    population: dict[str, Any],
    cascades_payload: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    enriched = json.loads(json.dumps(cascades_payload))

    oasis_db_root = Path(settings.oasis_db_dir)
    if not oasis_db_root.is_absolute():
        oasis_db_root = Path(__file__).resolve().parents[1] / oasis_db_root
    oasis_db_path = oasis_db_root / f"{session_id}.db"
    if not oasis_db_path.exists():
        return enriched

    display_name_by_agent = _display_name_lookup(population)

    with sqlite3.connect(oasis_db_path) as conn:
        conn.row_factory = sqlite3.Row
        user_rows = conn.execute("SELECT user_id, agent_id, name FROM user").fetchall()
        user_id_to_agent: dict[int, str] = {}
        for row in user_rows:
            mapped = _agent_id_from_oasis_alias(row["name"])
            if not mapped and row["agent_id"] is not None:
                mapped = f"agent-{int(row['agent_id']) + 1:04d}"
            if mapped:
                user_id_to_agent[int(row["user_id"])] = mapped

        post_like_counts = {
            int(row["post_id"]): int(row["count"] or 0)
            for row in conn.execute("SELECT post_id, COUNT(*) AS count FROM like GROUP BY post_id")
        }
        post_dislike_counts = {
            int(row["post_id"]): int(row["count"] or 0)
            for row in conn.execute("SELECT post_id, COUNT(*) AS count FROM dislike GROUP BY post_id")
        }
        comment_like_counts = {
            int(row["comment_id"]): int(row["count"] or 0)
            for row in conn.execute("SELECT comment_id, COUNT(*) AS count FROM comment_like GROUP BY comment_id")
        }
        comment_dislike_counts = {
            int(row["comment_id"]): int(row["count"] or 0)
            for row in conn.execute("SELECT comment_id, COUNT(*) AS count FROM comment_dislike GROUP BY comment_id")
        }

        post_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in conn.execute("SELECT post_id, user_id, content, num_likes, num_dislikes FROM post ORDER BY post_id"):
            agent_id = user_id_to_agent.get(int(row["user_id"]))
            if not agent_id:
                continue
            post_id = int(row["post_id"])
            key = (agent_id, _normalize_discourse_text(row["content"]))
            post_index.setdefault(key, []).append(
                {
                    "post_id": post_id,
                    "likes": max(int(row["num_likes"] or 0), post_like_counts.get(post_id, 0)),
                    "dislikes": max(int(row["num_dislikes"] or 0), post_dislike_counts.get(post_id, 0)),
                }
            )

        comment_index: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in conn.execute(
            "SELECT comment_id, post_id, user_id, content, num_likes, num_dislikes FROM comment ORDER BY comment_id"
        ):
            agent_id = user_id_to_agent.get(int(row["user_id"]))
            if not agent_id:
                continue
            comment_id = int(row["comment_id"])
            key = (agent_id, _normalize_discourse_text(row["content"]))
            comment_index.setdefault(key, []).append(
                {
                    "comment_id": comment_id,
                    "post_id": int(row["post_id"]),
                    "likes": max(int(row["num_likes"] or 0), comment_like_counts.get(comment_id, 0)),
                    "dislikes": max(int(row["num_dislikes"] or 0), comment_dislike_counts.get(comment_id, 0)),
                }
            )

    viral_posts = enriched.get("viral_posts")
    if not isinstance(viral_posts, list):
        return enriched

    total_engagement = 0
    for post in viral_posts:
        if not isinstance(post, dict):
            continue
        author_id = str(post.get("author") or post.get("author_agent_id") or "").strip()
        if author_id:
            post["author_name"] = display_name_by_agent.get(author_id, str(post.get("author_name") or author_id))

        post_match_key = (author_id, _normalize_discourse_text(post.get("content") or post.get("body") or ""))
        post_match = None
        if post_match_key in post_index and post_index[post_match_key]:
            post_match = post_index[post_match_key].pop(0)
        if post_match:
            post["likes"] = int(post_match["likes"])
            post["upvotes"] = int(post_match["likes"])
            post["dislikes"] = int(post_match["dislikes"])
            post["downvotes"] = int(post_match["dislikes"])

        comments = post.get("comments")
        if isinstance(comments, list):
            for comment in comments:
                if not isinstance(comment, dict):
                    continue
                comment_author_id = str(comment.get("author") or comment.get("author_agent_id") or "").strip()
                if comment_author_id:
                    comment["author_name"] = display_name_by_agent.get(
                        comment_author_id,
                        str(comment.get("author_name") or comment_author_id),
                    )
                comment_match_key = (
                    comment_author_id,
                    _normalize_discourse_text(comment.get("content") or comment.get("body") or ""),
                )
                comment_match = None
                if comment_match_key in comment_index and comment_index[comment_match_key]:
                    comment_match = comment_index[comment_match_key].pop(0)
                if comment_match:
                    comment["likes"] = int(comment_match["likes"])
                    comment["upvotes"] = int(comment_match["likes"])
                    comment["dislikes"] = int(comment_match["dislikes"])
                    comment["downvotes"] = int(comment_match["dislikes"])
                total_engagement += int(comment.get("likes") or comment.get("upvotes") or 0)
                total_engagement += int(comment.get("dislikes") or comment.get("downvotes") or 0)

        total_engagement += int(post.get("likes") or post.get("upvotes") or 0)
        total_engagement += int(post.get("dislikes") or post.get("downvotes") or 0)

    enriched["total_engagement"] = total_engagement
    return enriched


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
    analysis_questions: list[dict[str, Any]],
    agent_count: int,
    rounds: int,
    controversy_boost: float,
    knowledge: dict[str, Any],
    population: dict[str, Any],
    simulation_state: dict[str, Any],
    report: dict[str, Any],
    analytics_polarization: dict[str, Any],
    analytics_opinion_flow: dict[str, Any],
    analytics_influence: dict[str, Any],
    analytics_cascades: dict[str, Any],
    analytics_agent_stances: dict[str, Any],
    analytics_by_metric: dict[str, Any],
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
            "analysis_questions": analysis_questions,
            "agent_count": agent_count,
            "rounds": rounds,
            "controversy_boost": controversy_boost,
            "generated_at": _now(),
        },
        "analysis_questions": analysis_questions,
        "knowledge": knowledge,
        "population": population,
        "simulation": simulation_summary,
        "simulationState": simulation_state,
        "report": report,
        "analytics": {
            "polarization": analytics_polarization,
            "opinion_flow": analytics_opinion_flow,
            "influence": analytics_influence,
            "cascades": analytics_cascades,
            "agent_stances": analytics_agent_stances,
            "by_metric": analytics_by_metric,
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
    parser.add_argument("--extra-question", default=DEFAULT_EXTRA_QUESTION, help="Optional extra analysis question to append.")
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

    default_questions_payload = _require_ok(
        "analysis-questions",
        client.get(f"/api/v2/session/{session_id}/analysis-questions"),
    )
    analysis_questions = [
        dict(item)
        for item in (default_questions_payload.get("questions") or [])
        if isinstance(item, dict)
    ]
    extra_question_text = str(args.extra_question or "").strip()
    if extra_question_text:
        analysis_questions.append(
            {
                "question": extra_question_text,
                "type": "yes-no",
                "metric_name": "ai_job_worry",
                "metric_label": "AI Job Replacement Concern",
                "report_title": "AI Job Displacement Concerns",
            }
        )
        _require_ok(
            "session/config",
            client.patch(
                f"/api/v2/console/session/{session_id}/config",
                json={
                    "country": args.country,
                    "use_case": args.use_case,
                    "provider": args.provider,
                    "model": args.model,
                    "analysis_questions": analysis_questions,
                    **({"api_key": api_key} if api_key else {}),
                },
            ),
        )

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
                "subject_summary": str(knowledge.get("summary") or "").strip(),
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
    analytics_agent_stances = _require_ok(
        "analytics/agent-stances",
        client.get(f"/api/v2/console/session/{session_id}/analytics/agent-stances"),
    )

    analytics_cascades = _enrich_cascades_from_oasis(
        session_id=session_id,
        population=population,
        cascades_payload=analytics_cascades,
        settings=settings,
    )

    metric_names = sorted(
        {
            str(item.get("metric_name") or "").strip()
            for item in analysis_questions
            if isinstance(item, dict) and str(item.get("type") or "").strip() in {"scale", "yes-no"}
        }
        - {""}
    )
    analytics_by_metric: dict[str, Any] = {}
    for metric_name in metric_names:
        analytics_by_metric[metric_name] = {
            "polarization": _require_ok(
                f"analytics/polarization[{metric_name}]",
                client.get(
                    f"/api/v2/console/session/{session_id}/analytics/polarization",
                    params={"metric_name": metric_name},
                ),
            ),
            "opinion_flow": _require_ok(
                f"analytics/opinion-flow[{metric_name}]",
                client.get(
                    f"/api/v2/console/session/{session_id}/analytics/opinion-flow",
                    params={"metric_name": metric_name},
                ),
            ),
            "agent_stances": _require_ok(
                f"analytics/agent-stances[{metric_name}]",
                client.get(
                    f"/api/v2/console/session/{session_id}/analytics/agent-stances",
                    params={"metric_name": metric_name},
                ),
            ),
        }

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
        analysis_questions=analysis_questions,
        agent_count=args.agent_count,
        rounds=args.rounds,
        controversy_boost=args.controversy_boost,
        knowledge=knowledge,
        population=population,
        simulation_state=simulation_state,
        report=report,
        analytics_polarization=analytics_polarization,
        analytics_opinion_flow=analytics_opinion_flow,
        analytics_influence=analytics_influence,
        analytics_cascades=analytics_cascades,
        analytics_agent_stances=analytics_agent_stances,
        analytics_by_metric=analytics_by_metric,
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
