"""
Prepare Demo Cache from Existing Snapshot

This script converts the existing demo-snapshot.json into the format
needed for the demo service and frontend.

Usage:
    cd backend && python scripts/prepare_demo_cache.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


def main() -> None:
    print("Preparing demo cache from existing snapshot...")
    
    # Load existing snapshot
    snapshot_path = Path("data/demo-snapshot.json")
    if not snapshot_path.exists():
        print(f"Error: {snapshot_path} not found")
        return
    
    with open(snapshot_path) as f:
        snapshot = json.load(f)
    
    session_id = snapshot.get("session", {}).get("session_id", "demo-session-fy2026-budget")
    
    print(f"Session ID: {session_id}")
    print(f"Knowledge entities: {len(snapshot.get('knowledge', {}).get('entity_nodes', []))}")
    print(f"Population agents: {len(snapshot.get('population', {}).get('sampled_personas', []))}")
    print(f"Interactions: {len(snapshot.get('interactions', []))}")
    
    # Build unified output
    knowledge = snapshot.get("knowledge", {})
    population = snapshot.get("population", {})
    agents = snapshot.get("agents", [])
    interactions = snapshot.get("interactions", [])
    checkpoints = snapshot.get("checkpoints", {})
    report_state = snapshot.get("report_state", {})
    
    # Calculate metrics from checkpoints (list format)
    baseline = [c for c in checkpoints if c.get("checkpoint_kind") == "baseline"]
    final = [c for c in checkpoints if c.get("checkpoint_kind") == "final"]
    
    # Map stance_score (0-1) to opinion_score (1-10)
    def _stance_to_opinion(stance_score):
        return 1 + stance_score * 9 if stance_score is not None else 5.0
    
    baseline_scores = [_stance_to_opinion(r.get("stance_score")) for r in baseline]
    final_scores = [_stance_to_opinion(r.get("stance_score")) for r in final]
    
    stage3a_approval = sum(1 for s in baseline_scores if s >= 6) / len(baseline_scores) if baseline_scores else 0
    stage3b_approval = sum(1 for s in final_scores if s >= 6) / len(final_scores) if final_scores else 0
    
    shifts = [f - b for b, f in zip(baseline_scores, final_scores)]
    net_shift = sum(shifts) / len(shifts) if shifts else 0
    
    # Build friction data
    by_area: dict[str, dict[str, list]] = {}
    for agent in agents:
        area = agent.get("persona", {}).get("planning_area", "Unknown")
        if area not in by_area:
            by_area[area] = {"pre": [], "post": []}
        if agent.get("opinion_pre"):
            by_area[area]["pre"].append(float(agent["opinion_pre"]))
        if agent.get("opinion_post"):
            by_area[area]["post"].append(float(agent["opinion_post"]))
    
    friction = []
    for area, scores in by_area.items():
        if scores["pre"] and scores["post"]:
            avg_pre = sum(scores["pre"]) / len(scores["pre"])
            avg_post = sum(scores["post"]) / len(scores["post"])
            friction.append({
                "planning_area": area,
                "avg_pre_opinion": round(avg_pre, 2),
                "avg_post_opinion": round(avg_post, 2),
                "approval_post": round(sum(1 for s in scores["post"] if s >= 6) / len(scores["post"]), 2),
                "mean_shift": round(avg_post - avg_pre, 2),
                "friction_index": round(abs(avg_post - 5) / 5, 2),
                "cohort_size": len(scores["post"]),
            })
    
    friction.sort(key=lambda x: x["friction_index"], reverse=True)
    
    # Build feed from interactions
    # Map action_type to event_type that frontend expects
    def _map_event_type(action_type):
        mapping = {
            "post": "post_created",
            "create_post": "post_created",
            "comment": "comment_created",
            "like": "reaction_added",
            "dislike": "reaction_added",
        }
        return mapping.get(action_type, action_type)
    
    # Build agent lookup for persona data
    agent_lookup = {a.get("agent_id"): a for a in agents}
    
    def _extract_name_from_persona(persona: dict) -> str:
        """Extract name from professional_persona text (format: 'Name, a XX-year-old...')"""
        prof = persona.get("professional_persona", "")
        if prof:
            # Extract name before first comma
            match = prof.split(",")[0] if "," in prof else prof.split(" ")[0]
            return match.strip() if match else None
        return None
    
    def _extract_age_from_persona(persona: dict) -> int:
        """Extract age from professional_persona text"""
        import re
        prof = persona.get("professional_persona", "")
        if prof:
            # Look for patterns like "20-year-old" or "52 year old"
            match = re.search(r'(\d+)[\s\-]?year[\s\-]?old', prof, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 35  # default
    
    def _extract_occupation_from_persona(persona: dict) -> str:
        """Extract occupation from professional_persona text"""
        prof = persona.get("professional_persona", "")
        occupations = ["Teacher", "Engineer", "Manager", "Nurse", "Doctor", "Lawyer", 
                      "Accountant", "Sales", "Clerical", "Service", "Professional",
                      "Homemaker", "Student", "Retired", "Unemployed", "Consultant",
                      "Analyst", "Developer", "Designer", "Researcher"]
        if prof:
            prof_lower = prof.lower()
            for occ in occupations:
                if occ.lower() in prof_lower:
                    return occ
        return "Professional"  # default
    
    # Build feed from last 50 interactions with persona data
    feed = []
    for i in interactions[-50:]:
        actor_id = i.get("actor_agent_id")
        agent = agent_lookup.get(actor_id, {})
        persona = agent.get("persona", {})
        
        # Extract name, age, occupation from persona text
        name = _extract_name_from_persona(persona) or actor_id
        age = _extract_age_from_persona(persona)
        occupation = _extract_occupation_from_persona(persona)
        
        feed.append({
            "event_type": _map_event_type(i.get("action_type", "post")),
            "session_id": session_id,
            "round_no": i.get("round_no", 1),
            "actor_agent_id": actor_id,
            "actor_name": name,
            "actor_occupation": occupation,
            "actor_age": age,
            "content": i.get("content", ""),
            "post_id": i.get("target_agent_id") or actor_id,
        })
    
    # Add run_completed event at the end
    feed.append({
        "event_type": "run_completed",
        "session_id": session_id,
        "round_no": 6,
        "status": "completed",
    })
    
    # Count by mapped event types for counters
    posts_count = len([i for i in interactions if i.get("action_type") in ("post", "create_post")])
    comments_count = len([i for i in interactions if i.get("action_type") in ("comment",)])
    reactions_count = len([i for i in interactions if i.get("action_type") in ("like", "dislike", "reaction")])
    
    # Build influential agents
    # Calculate influence from interactions
    influence_scores: dict[str, float] = {}
    for i in interactions:
        actor = i.get("actor_agent_id")
        if actor:
            delta = abs(float(i.get("delta", 0)))
            influence_scores[actor] = influence_scores.get(actor, 0) + delta
    
    influential = sorted(
        [
            {
                "agent_id": agent_id,
                "influence_score": round(score, 3),
                "planning_area": next(
                    (a.get("persona", {}).get("planning_area", "Unknown") for a in agents if a.get("agent_id") == agent_id),
                    "Unknown"
                ),
            }
            for agent_id, score in influence_scores.items()
        ],
        key=lambda x: x["influence_score"],
        reverse=True,
    )[:20]  # Top 20
    
    # Build report
    report = {
        "session_id": session_id,
        "status": "completed",
        "generated_at": _now(),
        "executive_summary": (report_state or {}).get("executive_summary", 
            f"Demo simulation with {len(agents)} agents. Approval shifted from {stage3a_approval:.1%} to {stage3b_approval:.1%}."
        ),
        "insight_cards": (report_state or {}).get("insight_cards", [
            {"title": "Demo Insight", "content": "Sample insight from demo data", "confidence": "medium"}
        ]),
        "support_themes": (report_state or {}).get("support_themes", []),
        "dissent_themes": (report_state or {}).get("dissent_themes", []),
        "demographic_breakdown": [
            {"cohort": f["planning_area"], "pre_approval": f["avg_pre_opinion"], "post_approval": f["avg_post_opinion"], "shift": f["mean_shift"]}
            for f in friction[:5]
        ],
        "influential_content": (report_state or {}).get("influential_content", []),
        "recommendations": (report_state or {}).get("recommendations", [
            {"title": "Demo Recommendation", "description": "Sample recommendation", "target": "general"}
        ]),
        "risks": (report_state or {}).get("risks", []),
        "friction_by_planning_area": friction,
        "influential_agents": influential,
        "approval_rates": {
            "stage3a": round(stage3a_approval, 4),
            "stage3b": round(stage3b_approval, 4),
            "delta": round(stage3b_approval - stage3a_approval, 4),
        },
    }
    
    # Build unified output
    output = {
        "generated_at": _now(),
        "simulation_id": session_id,
        "session": {
            "session_id": session_id,
            "mode": "demo",
            "status": "simulation_completed",
            "created_at": snapshot.get("session", {}).get("created_at", _now()),
            "updated_at": _now(),
        },
        "knowledge": knowledge,
        "population": population,
        "simulation": {
            "session_id": session_id,
            "simulation_id": session_id,
            "platform": "reddit",
            "agent_count": len(agents),
            "rounds": 6,
            "stage3a_approval_rate": round(stage3a_approval, 4),
            "stage3b_approval_rate": round(stage3b_approval, 4),
            "net_opinion_shift": round(net_shift, 4),
            "baseline_scores": baseline_scores,
            "final_scores": final_scores,
            "runtime": "heuristic",
            "demo_mode": True,
            "generated_at": _now(),
        },
        "simulationState": {
            "session_id": session_id,
            "status": "completed",
            "event_count": len(interactions),
            "last_round": 6,
            "platform": "reddit",
            "planned_rounds": 6,
            "current_round": 6,
            "elapsed_seconds": 180,
            "estimated_total_seconds": 180,
            "estimated_remaining_seconds": 0,
            "latest_metrics": {
                "approval_pre": round(stage3a_approval, 4),
                "approval_post": round(stage3b_approval, 4),
                "net_shift": round(net_shift, 4),
            },
            "recent_events": feed,
            "counters": {
                "posts": posts_count,
                "comments": comments_count,
                "reactions": reactions_count,
                "active_authors": len(set(i.get("actor_agent_id") for i in interactions)),
            },
            "checkpoint_status": {
                "baseline": {"status": "completed", "completed_agents": len(agents), "total_agents": len(agents)},
                "final": {"status": "completed", "completed_agents": len(agents), "total_agents": len(agents)},
            },
            "top_threads": [],
            "discussion_momentum": {"approval_delta": round(stage3b_approval - stage3a_approval, 4), "dominant_stance": "mixed"},
        },
        "memory_sync": {
            "session_id": session_id,
            "simulation_id": session_id,
            "synced_events": len(interactions),
            "zep_enabled": True,
            "demo_mode": True,
        },
        "report": report,
        "reportFull": {
            "session_id": session_id,
            "status": "completed",
            "generated_at": _now(),
            **report,
        },
        "reportOpinions": {
            "session_id": session_id,
            "feed": feed,
            "influential_agents": influential,
        },
        "reportFriction": {
            "session_id": session_id,
            "map_metrics": friction,
            "anomaly_summary": f"Highest friction: {friction[0]['planning_area']}" if friction else "No friction data",
        },
        "interactionHub": {
            "session_id": session_id,
            "report_agent": {
                "starter_prompt": "Ask about dissent clusters, mitigation options, or demographic shifts.",
            },
            "influential_agents": influential,
            "selected_agent": influential[0] if influential else None,
        },
        "demo_metadata": {
            "agent_count": len(agents),
            "rounds": 6,
            "document": "Sample_Inputs/fy2026_budget_statement.md",
            "zep_enabled": True,
            "cached_at": _now(),
            "source": "demo-snapshot-conversion",
        },
    }
    
    # Write output files
    backend_path = Path("data/demo-output.json")
    frontend_path = Path("../frontend/public/demo-output.json")
    
    with open(backend_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote: {backend_path}")
    
    frontend_path.parent.mkdir(parents=True, exist_ok=True)
    with open(frontend_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote: {frontend_path}")
    
    print("\nDemo cache preparation complete!")
    print(f"  - Agents: {len(agents)}")
    print(f"  - Interactions: {len(interactions)}")
    print(f"  - Approval: {stage3a_approval:.1%} -> {stage3b_approval:.1%}")
    print(f"  - Net shift: {net_shift:+.3f}")


if __name__ == "__main__":
    main()
