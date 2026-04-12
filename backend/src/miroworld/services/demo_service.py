"""
Demo Service for MiroWorld

This service provides cached demo data for all screens when running in demo mode.
It ensures no Gemini API calls are made during demo operation.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from miroworld.config import Settings
from miroworld.services.storage import SimulationStore


DEMO_SESSION_ID = "demo-session-fy2026-budget"


class DemoService:
    """Service for serving cached demo data without API calls."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self._demo_cache: dict[str, Any] | None = None
        self._session_id: str | None = None
    
    def _load_demo_cache(self) -> dict[str, Any] | None:
        """Load the demo cache from file."""
        if self._demo_cache is not None:
            return self._demo_cache
        
        # Try backend path first
        cache_path = Path(self.settings.console_demo_output_path)
        if not cache_path.exists():
            # Try frontend path
            cache_path = Path(self.settings.console_demo_frontend_output_path)
        
        if cache_path.exists():
            try:
                self._demo_cache = json.loads(cache_path.read_text(encoding="utf-8"))
                return self._demo_cache
            except Exception:
                pass
        
        return None
    
    def is_demo_available(self) -> bool:
        """Check if demo cache is available."""
        return self._load_demo_cache() is not None
    
    def get_demo_session_id(self) -> str:
        """Get or create the demo session ID."""
        if self._session_id is None:
            cache = self._load_demo_cache()
            if cache and "session" in cache:
                self._session_id = cache["session"].get("session_id", DEMO_SESSION_ID)
            else:
                self._session_id = DEMO_SESSION_ID
        return self._session_id or DEMO_SESSION_ID
    
    def create_demo_session(self, requested_session_id: str | None = None) -> dict[str, Any]:
        """Create a demo session."""
        session_id = requested_session_id or f"demo-{uuid.uuid4().hex[:8]}"
        self._session_id = session_id
        
        # Initialize session in database
        self.store.upsert_console_session(session_id=session_id, mode="demo", status="created")
        
        # Load and cache demo data for this session
        cache = self._load_demo_cache()
        if cache:
            # Save knowledge artifact
            if "knowledge" in cache:
                knowledge = dict(cache["knowledge"])
                knowledge["session_id"] = session_id
                self.store.save_knowledge_artifact(session_id, knowledge)
            
            # Save population artifact
            if "population" in cache:
                population = dict(cache["population"])
                population["session_id"] = session_id
                self.store.save_population_artifact(session_id, population)
                
                # Save agents
                agents_to_save = []
                for row in population.get("sampled_personas", []):
                    agent_id = row.get("agent_id")
                    persona = row.get("persona", {})
                    agents_to_save.append({
                        "agent_id": agent_id,
                        "persona": persona,
                        "opinion_pre": 5.0,
                        "opinion_post": 5.0,
                    })
                if agents_to_save:
                    self.store.replace_agents(session_id, agents_to_save)
            
            # Save simulation state
            if "simulationState" in cache:
                state = dict(cache["simulationState"])
                state["session_id"] = session_id
                self.store.save_simulation_state_snapshot(session_id, state)
            
            # Save checkpoints if available
            if "simulation" in cache:
                sim = cache["simulation"]
                if "baseline_scores" in sim:
                    baseline = [
                        {"agent_id": f"agent-{i+1:04d}", "opinion_score": score}
                        for i, score in enumerate(sim["baseline_scores"])
                    ]
                    self.store.replace_checkpoint_records(session_id, "baseline", baseline)
                if "final_scores" in sim:
                    final = [
                        {"agent_id": f"agent-{i+1:04d}", "opinion_score": score}
                        for i, score in enumerate(sim["final_scores"])
                    ]
                    self.store.replace_checkpoint_records(session_id, "final", final)
            
            # Update session status
            self.store.upsert_console_session(session_id=session_id, mode="demo", status="simulation_completed")
        
        return {
            "session_id": session_id,
            "mode": "demo",
            "status": "created",
        }

    def get_analysis_questions(self) -> list[dict[str, Any]]:
        """Return cached analysis questions bundled with the demo output."""
        cache = self._load_demo_cache() or {}
        candidates = cache.get("analysis_questions")
        if not isinstance(candidates, list):
            source_run = cache.get("source_run")
            if isinstance(source_run, dict):
                source_candidates = source_run.get("analysis_questions")
                candidates = source_candidates if isinstance(source_candidates, list) else []
            else:
                candidates = []
        return [dict(item) for item in candidates if isinstance(item, dict)]
    
    def get_knowledge_artifact(self, session_id: str) -> dict[str, Any] | None:
        """Get knowledge artifact for demo session."""
        # Always return from cache for demo mode, but update session_id
        cache = self._load_demo_cache()
        if cache and "knowledge" in cache:
            knowledge = dict(cache["knowledge"])
            knowledge["session_id"] = session_id
            return knowledge
        
        # Fall back to database (shouldn't happen if cache exists)
        return self.store.get_knowledge_artifact(session_id)
    
    def get_population_artifact(self, session_id: str) -> dict[str, Any] | None:
        """Get population artifact for demo session."""
        # Always return from cache for demo mode, but update session_id
        cache = self._load_demo_cache()
        if cache and "population" in cache:
            population = dict(cache["population"])
            population["session_id"] = session_id
            return population
        
        # Fall back to database
        return self.store.get_population_artifact(session_id)
    
    def get_simulation_state(self, session_id: str) -> dict[str, Any] | None:
        """Get simulation state for demo session."""
        # Always return from cache for demo mode, but update session_id
        cache = self._load_demo_cache()
        if cache and "simulationState" in cache:
            sim_state = dict(cache["simulationState"])
            sim_state["session_id"] = session_id
            return sim_state
        
        # Fall back to database
        return self.store.get_simulation_state_snapshot(session_id)

    def _cached_analytics_payload(self, key: str) -> dict[str, Any] | None:
        cache = self._load_demo_cache()
        if not cache:
            return None
        analytics = cache.get("analytics")
        if not isinstance(analytics, dict):
            return None
        payload = analytics.get(key)
        if not isinstance(payload, dict):
            return None
        return dict(payload)

    def get_simulation_stream_events(self, session_id: str) -> list[dict[str, Any]]:
        """Build replay events for demo-mode simulation stream."""
        events: list[dict[str, Any]] = []

        cascades = self.get_analytics_cascades(session_id)
        viral_posts = cascades.get("viral_posts")
        if isinstance(viral_posts, list):
            for idx, post in enumerate(viral_posts[:24]):
                if not isinstance(post, dict):
                    continue
                post_id = post.get("post_id") or f"demo-post-{idx + 1}"
                actor_agent_id = str(post.get("author") or post.get("author_agent_id") or f"agent-{idx + 1:04d}")
                actor_name = str(post.get("author_name") or post.get("actor_name") or actor_agent_id)
                title = str(post.get("title") or f"Discussion thread {idx + 1}").strip()
                content = str(post.get("content") or post.get("body") or title).strip()
                round_no = int(post.get("round_no") or post.get("round") or 1)

                if not title and not content:
                    continue

                events.append(
                    {
                        "event_type": "post_created",
                        "session_id": session_id,
                        "round_no": max(1, round_no),
                        "post_id": post_id,
                        "actor_agent_id": actor_agent_id,
                        "actor_name": actor_name,
                        "title": title or content,
                        "content": content or title,
                    }
                )

                comments = post.get("comments")
                if isinstance(comments, list):
                    for comment_idx, comment in enumerate(comments[:8]):
                        if not isinstance(comment, dict):
                            continue
                        comment_text = str(comment.get("content") or comment.get("body") or "").strip()
                        if not comment_text:
                            continue
                        comment_id = comment.get("comment_id") or f"{post_id}-c{comment_idx + 1}"
                        comment_actor_id = str(comment.get("author") or comment.get("actor_agent_id") or actor_agent_id)
                        comment_actor_name = str(comment.get("author_name") or comment.get("actor_name") or comment_actor_id)
                        events.append(
                            {
                                "event_type": "comment_created",
                                "session_id": session_id,
                                "round_no": max(1, round_no),
                                "post_id": post_id,
                                "comment_id": comment_id,
                                "actor_agent_id": comment_actor_id,
                                "actor_name": comment_actor_name,
                                "content": comment_text,
                            }
                        )

        if not events:
            sim_state = self.get_simulation_state(session_id) or {}
            recent_events = sim_state.get("recent_events") if isinstance(sim_state, dict) else []
            if isinstance(recent_events, list):
                events = [dict(event) for event in recent_events if isinstance(event, dict)]

        sim_state = self.get_simulation_state(session_id) or {}
        last_round = int(sim_state.get("last_round") or sim_state.get("current_round") or 0)
        events.append(
            {
                "event_type": "run_completed",
                "session_id": session_id,
                "round_no": max(0, last_round),
                "status": "completed",
            }
        )

        return events

    def get_analytics_polarization(self, session_id: str) -> dict[str, Any]:
        payload = self._cached_analytics_payload("polarization") or {"series": []}
        payload["session_id"] = session_id
        payload.setdefault("series", [])
        return payload

    def get_analytics_opinion_flow(self, session_id: str) -> dict[str, Any]:
        payload = self._cached_analytics_payload("opinion_flow") or {}
        payload["session_id"] = session_id
        payload.setdefault("initial", {"supporter": 0, "neutral": 0, "dissenter": 0})
        payload.setdefault("final", {"supporter": 0, "neutral": 0, "dissenter": 0})
        payload.setdefault("flows", [])
        return payload

    def get_analytics_influence(self, session_id: str) -> dict[str, Any]:
        payload = self._cached_analytics_payload("influence")
        if payload:
            payload["session_id"] = session_id
            return payload

        influential = self.get_interaction_hub(session_id).get("influential_agents", [])
        top_influencers: list[dict[str, Any]] = []
        if isinstance(influential, list):
            for row in influential[:10]:
                if not isinstance(row, dict):
                    continue
                agent_id = str(row.get("agent_id") or "").strip()
                if not agent_id:
                    continue
                top_influencers.append(
                    {
                        "agent_id": agent_id,
                        "agent_name": row.get("agent_name") or agent_id,
                        "influence_score": float(row.get("influence_score", 0.0) or 0.0),
                        "stance": row.get("segment") or "mixed",
                    }
                )

        return {
            "session_id": session_id,
            "top_influencers": top_influencers,
            "nodes": [],
            "edges": [],
            "total_nodes": 0,
            "total_edges": 0,
        }

    def get_analytics_cascades(self, session_id: str) -> dict[str, Any]:
        payload = self._cached_analytics_payload("cascades")
        if payload:
            payload["session_id"] = session_id
            return payload

        sim_state = self.get_simulation_state(session_id) or {}
        top_threads = sim_state.get("top_threads") if isinstance(sim_state, dict) else []
        viral_posts: list[dict[str, Any]] = []
        if isinstance(top_threads, list):
            for idx, thread in enumerate(top_threads):
                if not isinstance(thread, dict):
                    continue
                post_id = thread.get("post_id") or f"demo-thread-{idx + 1}"
                title = str(thread.get("title") or f"Thread {idx + 1}")
                author_name = str(thread.get("author_name") or thread.get("author_agent_id") or "Agent")
                viral_posts.append(
                    {
                        "post_id": post_id,
                        "author": author_name,
                        "author_name": author_name,
                        "title": title,
                        "content": title,
                        "likes": int(thread.get("likes", 0) or 0),
                        "dislikes": int(thread.get("dislikes", 0) or 0),
                        "comments": [],
                    }
                )

        return {
            "session_id": session_id,
            "cascades": viral_posts,
            "posts": viral_posts,
            "top_threads": viral_posts,
            "viral_posts": viral_posts,
            "post_id": None,
            "tree_size": len(viral_posts),
            "total_engagement": sum(
                int(item.get("likes", 0) or 0) + int(item.get("dislikes", 0) or 0)
                for item in viral_posts
            ),
            "mean_opinion_delta": 0.0,
            "engaged_agents": [],
        }
    
    def get_report(self, session_id: str) -> dict[str, Any] | None:
        """Get report for demo session."""
        # Always return from cache for demo mode
        cache = self._load_demo_cache()
        if cache and "reportFull" in cache:
            report = dict(cache["reportFull"])
            report["session_id"] = session_id
            return report
        if cache and "report" in cache:
            report = dict(cache["report"])
            report["session_id"] = session_id
            return report
        
        # Fall back to database
        return self.store.get_report_state(session_id)
    
    def get_report_opinions(self, session_id: str) -> dict[str, Any]:
        """Get report opinions for demo session."""
        cache = self._load_demo_cache()
        
        feed = []
        influential = []
        
        if cache:
            if "reportOpinions" in cache:
                ro = cache["reportOpinions"]
                feed = ro.get("feed", [])
                influential = ro.get("influential_agents", [])
            elif "report" in cache and "influential_agents" in cache["report"]:
                influential = cache["report"]["influential_agents"]
        
        # Get interactions from database if available
        if not feed:
            interactions = self.store.get_interactions(session_id)[-50:]
            feed = [
                {
                    "event_type": "post_created",
                    "session_id": session_id,
                    "round_no": i.get("round_no", 1),
                    "actor_agent_id": i.get("actor_agent_id"),
                    "content": i.get("content"),
                }
                for i in interactions
            ]
        
        return {
            "session_id": session_id,
            "feed": feed,
            "influential_agents": influential,
        }
    
    def get_friction_map(self, session_id: str) -> dict[str, Any]:
        """Get friction map for demo session."""
        cache = self._load_demo_cache()
        
        friction = []
        anomaly_summary = "No friction data available"
        
        if cache:
            if "reportFriction" in cache:
                rf = cache["reportFriction"]
                friction = rf.get("map_metrics", [])
                anomaly_summary = rf.get("anomaly_summary", anomaly_summary)
            elif "report" in cache:
                friction = cache["report"].get("friction_by_planning_area", [])
                if friction:
                    anomaly_summary = f"Highest friction: {friction[0]['planning_area']}"
        
        return {
            "session_id": session_id,
            "map_metrics": friction,
            "anomaly_summary": anomaly_summary,
        }
    
    def get_interaction_hub(self, session_id: str, agent_id: str | None = None) -> dict[str, Any]:
        """Get interaction hub data for demo session."""
        cache = self._load_demo_cache()
        
        influential = []
        selected_agent = None
        
        if cache:
            if "interactionHub" in cache:
                ih = cache["interactionHub"]
                influential = ih.get("influential_agents", [])
                selected_agent = ih.get("selected_agent")
            elif "report" in cache:
                influential = cache["report"].get("influential_agents", [])
        
        # Use provided agent_id or first influential agent
        if agent_id:
            selected_agent = next((a for a in influential if str(a.get("agent_id")) == agent_id), None)
        elif influential and not selected_agent:
            selected_agent = influential[0]
        
        return {
            "session_id": session_id,
            "selected_agent_id": agent_id or (selected_agent.get("agent_id") if selected_agent else None),
            "report_agent": {
                "starter_prompt": "Ask about dissent clusters, mitigation options, or demographic shifts.",
                "transcript": [],
            },
            "influential_agents": influential,
            "selected_agent": selected_agent,
        }
    
    def generate_demo_report_chat(self, session_id: str, message: str) -> dict[str, Any]:
        """Generate a demo report chat response."""
        # Get report data for context
        report = self.get_report(session_id) or {}
        friction = report.get("friction_by_planning_area", [])
        
        # Simple response based on message content
        message_lower = message.lower()
        
        if "friction" in message_lower or "dissent" in message_lower:
            if friction:
                top = friction[0]
                response = (
                    f"The highest friction is in {top['planning_area']} with a friction index of "
                    f"{top['friction_index']:.2f}. This area showed a mean opinion shift of "
                    f"{top['mean_shift']:+.2f} from {top['avg_pre_opinion']:.2f} to {top['avg_post_opinion']:.2f}."
                )
            else:
                response = "No significant friction clusters were identified in this simulation."
        elif "mitigation" in message_lower or "recommend" in message_lower:
            recommendations = report.get("recommendations", [])
            if recommendations:
                rec = recommendations[0]
                response = f"Consider: {rec.get('title', 'Targeted outreach to high-friction demographics')}. {rec.get('description', '')}"
            else:
                response = "Based on the simulation, consider targeted outreach to high-friction planning areas and addressing specific cost-of-living concerns."
        elif "approval" in message_lower or "support" in message_lower:
            pre = report.get("approval_rates", {}).get("stage3a", 0)
            post = report.get("approval_rates", {}).get("stage3b", 0)
            response = f"Approval shifted from {pre:.1%} to {post:.1%} after deliberation."
        else:
            response = (
                "This is a demo simulation of Singapore FY2026 Budget reception. "
                "The simulation shows how different demographic groups respond to policy proposals. "
                "Ask about friction clusters, mitigations, or approval rates for more details."
            )
        
        return {
            "response": response,
            "zep_context_used": False,
            "demo_mode": True,
        }
    
    def generate_demo_agent_chat(self, session_id: str, agent_id: str, message: str) -> dict[str, Any]:
        """Generate a demo agent chat response."""
        # Get agent info
        agents = self.store.get_agents(session_id)
        agent = next((a for a in agents if a.get("agent_id") == agent_id), None)
        
        if not agent:
            return {
                "response": "Agent not found in demo data.",
                "zep_context_used": False,
                "demo_mode": True,
            }
        
        persona = agent.get("persona", {})
        planning_area = persona.get("planning_area", "Unknown")
        occupation = persona.get("occupation", "Unknown")
        
        # Simple response based on message content
        message_lower = message.lower()
        
        if "opinion" in message_lower or "think" in message_lower or "view" in message_lower:
            pre = agent.get("opinion_pre", 5)
            post = agent.get("opinion_post", 5)
            response = (
                f"As a {occupation} from {planning_area}, my opinion shifted from {pre:.1f} to {post:.1f} "
                f"during the deliberation. The budget measures directly impact my household's cost-of-living concerns."
            )
        elif "budget" in message_lower or "policy" in message_lower:
            response = (
                f"From my perspective as a {occupation} in {planning_area}, the FY2026 Budget has "
                f"mixed implications. The cost-of-living support measures are welcome, but I have concerns "
                f"about long-term economic resilience given the global uncertainties mentioned."
            )
        else:
            response = (
                f"I'm a {occupation} living in {planning_area}. The simulation allowed me to "
                f"engage with others and refine my views on the budget proposals through discussion."
            )
        
        return {
            "response": response,
            "zep_context_used": False,
            "demo_mode": True,
        }
