"""
Comprehensive Demo Cache Generator for McKAInsey

This script generates a complete demo cache that:
1. Creates Screen 1: Knowledge Graph from fy2026_budget_statement.md
2. Creates Screen 2: 500 agents from Nemotron dataset  
3. Creates Screen 3: 6 rounds of simulation data
4. Stores agent memory in Zep Cloud for retrieval

Usage:
    cd backend && python scripts/generate_comprehensive_demo_cache.py
    
Environment:
    GEMINI_API_KEY or GEMINI_API - Required for initial knowledge extraction
    ZEP_CLOUD or ZEP_API_KEY - Required for agent memory storage
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from mckainsey.config import get_settings
from mckainsey.services.lightrag_service import LightRAGService
from mckainsey.services.persona_sampler import PersonaSampler
from mckainsey.services.persona_relevance_service import PersonaRelevanceService
from mckainsey.services.simulation_service import SimulationService
from mckainsey.services.memory_service import MemoryService
from mckainsey.services.report_service import ReportService
from mckainsey.services.storage import SimulationStore
from mckainsey.services.simulation_stream_service import SimulationStreamService


DEMO_SESSION_ID = "demo-session-fy2026-budget"
DEMO_AGENT_COUNT = 500
DEMO_ROUNDS = 6
DEMO_POLICY_SUMMARY = (
    "Singapore FY2026 Budget: Cost-of-living support through CDC vouchers, "
    "U-Save rebates, transport subsidies, SkillsFuture enhancements, "
    "and CPF top-ups for seniors. Focus on economic resilience and "
    "household support in a changed global environment."
)


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


class ComprehensiveDemoCacheGenerator:
    def __init__(self, settings: Any):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.lightrag = LightRAGService(settings)
        self.sampler = PersonaSampler(
            settings.nemotron_dataset,
            settings.nemotron_split,
            cache_dir=settings.nemotron_cache_dir,
            download_workers=settings.nemotron_download_workers,
        )
        self.relevance = PersonaRelevanceService(settings)
        self.simulation = SimulationService(settings)
        self.streams = SimulationStreamService(settings)
        self.memory = MemoryService(settings)
        self.report = ReportService(settings)
        
        self.scratch_dir = Path("data/demo-run")
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_all(self, force_regenerate: bool = False) -> dict[str, Any]:
        """Generate complete demo cache for all screens."""
        _log("=" * 60)
        _log("Starting Comprehensive Demo Cache Generation")
        _log("=" * 60)
        _log(f"Session ID: {DEMO_SESSION_ID}")
        _log(f"Agent Count: {DEMO_AGENT_COUNT}")
        _log(f"Simulation Rounds: {DEMO_ROUNDS}")
        
        # Initialize session
        self._init_demo_session()
        
        # Stage 1: Knowledge Graph
        knowledge = self._generate_knowledge(force_regenerate)
        
        # Stage 2: Population Sampling (500 agents)
        population = self._generate_population(knowledge, force_regenerate)
        
        # Stage 3: Simulation (6 rounds)
        simulation = self._generate_simulation(population, force_regenerate)
        
        # Stage 4: Memory Sync to Zep Cloud
        memory_sync = self._sync_to_zep(simulation, force_regenerate)
        
        # Stage 5: Generate Report
        report = self._generate_report(force_regenerate)
        
        # Create unified demo output
        demo_output = self._create_unified_output(
            knowledge, population, simulation, memory_sync, report
        )
        
        _log("=" * 60)
        _log("Demo Cache Generation Complete!")
        _log("=" * 60)
        _log(f"Output files:")
        _log(f"  - Backend: {self.settings.console_demo_output_path}")
        _log(f"  - Frontend: {self.settings.console_demo_frontend_output_path}")
        _log(f"  - Session ID: {DEMO_SESSION_ID}")
        
        return demo_output
    
    def _init_demo_session(self) -> None:
        """Initialize demo session in database."""
        _log("Initializing demo session...")
        self.store.upsert_console_session(
            session_id=DEMO_SESSION_ID,
            mode="demo",
            status="created"
        )
        _log(f"Demo session created: {DEMO_SESSION_ID}")
    
    def _generate_knowledge(self, force: bool = False) -> dict[str, Any]:
        """Generate Screen 1: Knowledge Graph from budget statement."""
        cache_path = self.scratch_dir / "screen1_knowledge.json"
        
        if not force and cache_path.exists():
            _log("Loading cached knowledge artifact...")
            return _load_json_if_exists(cache_path)
        
        _log("Generating Screen 1: Knowledge Graph...")
        
        # Try to load from existing demo-snapshot.json first (fallback)
        snapshot_path = Path("data/demo-snapshot.json")
        if not force and snapshot_path.exists():
            try:
                snapshot = _load_json_if_exists(snapshot_path)
                if snapshot and "knowledge" in snapshot:
                    _log("Using knowledge from existing demo-snapshot.json")
                    knowledge = snapshot["knowledge"]
                    knowledge["session_id"] = DEMO_SESSION_ID
                    knowledge["demo_mode"] = True
                    knowledge["generated_at"] = _now()
                    knowledge["source"] = "demo-snapshot-fallback"
                    self.store.save_knowledge_artifact(DEMO_SESSION_ID, knowledge)
                    _write_json(cache_path, knowledge)
                    return knowledge
            except Exception as e:
                _log(f"Could not load from snapshot: {e}")
        
        # Check if Gemini API is available
        if not self.settings.resolved_gemini_key:
            _log("ERROR: No Gemini API key available for knowledge extraction")
            _log("Please set GEMINI_API or GEMINI_API_KEY environment variable")
            raise RuntimeError("Gemini API key required for knowledge extraction")
        
        # Read the budget statement
        doc_path = Path(self.settings.demo_default_policy_markdown)
        if not doc_path.exists():
            # Try relative path
            doc_path = Path("..") / self.settings.demo_default_policy_markdown
        
        document_text = doc_path.read_text(encoding="utf-8")
        _log(f"Loaded document: {doc_path} ({len(document_text)} chars)")
        
        # Process with LightRAG (async -> sync wrapper)
        try:
            async def _process():
                return await self.lightrag.process_document(
                    simulation_id=DEMO_SESSION_ID,
                    document_text=document_text,
                    source_path=str(doc_path),
                    guiding_prompt="Extract key policy entities, demographic groups, and their relationships for Singapore FY2026 Budget",
                    demographic_focus="Singapore residents by planning area, income cohorts, age groups, and occupation",
                )
            
            artifact = asyncio.run(_process())
        except Exception as e:
            _log(f"LightRAG processing failed: {e}")
            _log("Falling back to basic extraction...")
            # Create a minimal artifact
            artifact = {
                "simulation_id": DEMO_SESSION_ID,
                "document_id": f"doc-{uuid.uuid4()}",
                "document": {
                    "document_id": f"doc-{uuid.uuid4()}",
                    "source_path": str(doc_path),
                    "file_name": doc_path.name,
                    "file_type": "text/markdown",
                    "text_length": len(document_text),
                    "paragraph_count": len([p for p in document_text.split("\n\n") if p.strip()]),
                },
                "summary": "Singapore FY2026 Budget focuses on cost-of-living support, economic resilience, and household assistance through various measures including CDC vouchers, U-Save rebates, and SkillsFuture enhancements.",
                "guiding_prompt": None,
                "demographic_context": None,
                "entity_nodes": [
                    {"id": "Singaporeans", "label": "Singaporeans", "type": "population", "families": ["document"], "display_bucket": "persons"},
                    {"id": "Budget 2026", "label": "Budget 2026", "type": "policy", "families": ["document"], "display_bucket": "concept"},
                    {"id": "Cost-of-Living Support", "label": "Cost-of-Living Support", "type": "program", "families": ["document"], "display_bucket": "concept"},
                ],
                "relationship_edges": [
                    {"source": "Budget 2026", "target": "Singaporeans", "type": "affects", "label": "affects"},
                    {"source": "Budget 2026", "target": "Cost-of-Living Support", "type": "includes", "label": "includes"},
                ],
                "entity_type_counts": {"population": 1, "policy": 1, "program": 1},
                "graph_origin": "fallback_minimal",
                "processing_logs": ["Fallback extraction due to API error"],
            }
        
        artifact["session_id"] = DEMO_SESSION_ID
        artifact["demo_mode"] = True
        artifact["generated_at"] = _now()
        
        # Save to database
        self.store.save_knowledge_artifact(DEMO_SESSION_ID, artifact)
        self.store.upsert_console_session(
            session_id=DEMO_SESSION_ID,
            mode="demo",
            status="knowledge_ready"
        )
        
        _write_json(cache_path, artifact)
        _log(f"Knowledge graph generated: {len(artifact.get('entity_nodes', []))} entities, "
             f"{len(artifact.get('relationship_edges', []))} relationships")
        
        return artifact
    
    def _generate_population(
        self, 
        knowledge: dict[str, Any], 
        force: bool = False
    ) -> dict[str, Any]:
        """Generate Screen 2: Sample 500 agents from Nemotron."""
        cache_path = self.scratch_dir / "screen2_population.json"
        
        if not force and cache_path.exists():
            _log("Loading cached population artifact...")
            return _load_json_if_exists(cache_path)
        
        _log("Generating Screen 2: Population Sampling (500 agents)...")
        
        # Query candidates from Nemotron
        _log("Querying Nemotron dataset...")
        personas = self.sampler.query_candidates(
            limit=DEMO_AGENT_COUNT * 3,  # Get extra for selection
            seed=42,  # Fixed seed for reproducibility
        )
        _log(f"Retrieved {len(personas)} candidate personas")
        
        # Build population artifact with relevance scoring
        artifact = self.relevance.build_population_artifact(
            session_id=DEMO_SESSION_ID,
            personas=personas[:DEMO_AGENT_COUNT],
            knowledge_artifact=knowledge,
            filters={
                "agent_count": DEMO_AGENT_COUNT,
                "sample_mode": "population_baseline",
                "seed": 42,
            },
            agent_count=DEMO_AGENT_COUNT,
            sample_mode="population_baseline",
            seed=42,
            parsed_sampling_instructions={
                "hard_filters": {},
                "soft_boosts": {},
                "exclusions": {},
                "distribution_targets": {},
                "notes_for_ui": ["Demo mode: 500 agents sampled from Singapore population"],
            },
        )
        
        artifact["demo_mode"] = True
        artifact["generated_at"] = _now()
        
        # Save to database
        self.store.save_population_artifact(DEMO_SESSION_ID, artifact)
        
        # Store agents in simulation database
        for row in artifact.get("sampled_personas", []):
            agent_id = row.get("agent_id")
            persona = row.get("persona", {})
            self.store.upsert_agent(
                simulation_id=DEMO_SESSION_ID,
                agent_id=agent_id,
                persona_json=json.dumps(persona),
            )
        
        _write_json(cache_path, artifact)
        _log(f"Population artifact generated: {artifact.get('sample_count', 0)} agents")
        
        return artifact
    
    def _generate_simulation(
        self, 
        population: dict[str, Any], 
        force: bool = False
    ) -> dict[str, Any]:
        """Generate Screen 3: Run 6 rounds of simulation."""
        cache_path = self.scratch_dir / "screen3_simulation.json"
        events_path = self.scratch_dir / "screen3_events.ndjson"
        
        if not force and cache_path.exists():
            _log("Loading cached simulation...")
            return _load_json_if_exists(cache_path)
        
        _log("Generating Screen 3: Simulation (6 rounds)...")
        
        sampled_rows = list(population.get("sampled_personas", []))
        personas = [dict(row["persona"], agent_id=row.get("agent_id")) for row in sampled_rows]
        
        # Build context bundles
        knowledge = self.store.get_knowledge_artifact(DEMO_SESSION_ID) or {}
        context_bundles = self.simulation.build_context_bundles(
            simulation_id=DEMO_SESSION_ID,
            policy_summary=DEMO_POLICY_SUMMARY,
            knowledge_artifact=knowledge,
            sampled_personas=sampled_rows,
        )
        
        # Run baseline checkpoint
        _log("Running baseline opinion checkpoint...")
        baseline = self.simulation.run_opinion_checkpoint(
            simulation_id=DEMO_SESSION_ID,
            checkpoint_kind="baseline",
            policy_summary=DEMO_POLICY_SUMMARY,
            agent_context_bundles=context_bundles,
        )
        self.store.replace_checkpoint_records(DEMO_SESSION_ID, "baseline", baseline)
        _log(f"Baseline checkpoint complete: {len(baseline)} agents")
        
        # Run simulation rounds
        _log(f"Running {DEMO_ROUNDS} simulation rounds...")
        
        events_dir = Path(self.settings.oasis_db_dir).parent / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        events_file = events_dir / f"{DEMO_SESSION_ID}.ndjson"
        if events_file.exists():
            events_file.unlink()
        
        # Use heuristic simulation for demo (no OASIS required)
        simulation_result = self.simulation.run_with_personas(
            simulation_id=DEMO_SESSION_ID,
            policy_summary=DEMO_POLICY_SUMMARY,
            rounds=DEMO_ROUNDS,
            personas=personas,
            events_path=events_file,
            force_live=False,  # Use heuristic for demo
            on_progress=lambda path, elapsed: None,
        )
        
        # Run final checkpoint
        _log("Running final opinion checkpoint...")
        final_bundles = self._build_final_checkpoint_bundles(DEMO_SESSION_ID, context_bundles)
        final = self.simulation.run_opinion_checkpoint(
            simulation_id=DEMO_SESSION_ID,
            checkpoint_kind="final",
            policy_summary=DEMO_POLICY_SUMMARY,
            agent_context_bundles=final_bundles,
        )
        self.store.replace_checkpoint_records(DEMO_SESSION_ID, "final", final)
        _log(f"Final checkpoint complete: {len(final)} agents")
        
        # Calculate metrics
        baseline_scores = [r.get("opinion_score", 5.0) for r in baseline]
        final_scores = [r.get("opinion_score", 5.0) for r in final]
        
        stage3a_approval = sum(1 for s in baseline_scores if s >= 6) / len(baseline_scores) if baseline_scores else 0
        stage3b_approval = sum(1 for s in final_scores if s >= 6) / len(final_scores) if final_scores else 0
        
        shifts = [f - b for b, f in zip(baseline_scores, final_scores)]
        net_shift = sum(shifts) / len(shifts) if shifts else 0
        
        artifact = {
            "session_id": DEMO_SESSION_ID,
            "simulation_id": DEMO_SESSION_ID,
            "platform": "reddit",
            "agent_count": DEMO_AGENT_COUNT,
            "rounds": DEMO_ROUNDS,
            "stage3a_approval_rate": round(stage3a_approval, 4),
            "stage3b_approval_rate": round(stage3b_approval, 4),
            "net_opinion_shift": round(net_shift, 4),
            "baseline_scores": baseline_scores,
            "final_scores": final_scores,
            "runtime": "heuristic",
            "demo_mode": True,
            "generated_at": _now(),
        }
        
        # Update session status
        self.store.upsert_console_session(
            session_id=DEMO_SESSION_ID,
            mode="demo",
            status="simulation_completed"
        )
        
        _write_json(cache_path, artifact)
        _log(f"Simulation complete: approval {stage3a_approval:.2%} -> {stage3b_approval:.2%}, "
             f"shift: {net_shift:+.3f}")
        
        return artifact
    
    def _sync_to_zep(
        self, 
        simulation: dict[str, Any], 
        force: bool = False
    ) -> dict[str, Any]:
        """Sync simulation events to Zep Cloud for demo retrieval."""
        cache_path = self.scratch_dir / "screen3_memory_sync.json"
        
        if not force and cache_path.exists():
            _log("Loading cached memory sync...")
            return _load_json_if_exists(cache_path)
        
        _log("Syncing simulation memory to Zep Cloud...")
        
        # Sync to Zep
        sync_result = self.memory.sync_simulation(DEMO_SESSION_ID)
        
        artifact = {
            "session_id": DEMO_SESSION_ID,
            "simulation_id": DEMO_SESSION_ID,
            "synced_events": sync_result.get("synced_events", 0),
            "zep_enabled": sync_result.get("zep_enabled", False),
            "sync_error": sync_result.get("sync_error"),
            "demo_mode": True,
            "generated_at": _now(),
        }
        
        _write_json(cache_path, artifact)
        
        if artifact["zep_enabled"]:
            _log(f"Memory synced to Zep Cloud: {artifact['synced_events']} events")
        else:
            _log(f"Warning: Zep Cloud not enabled - {artifact.get('sync_error', 'unknown error')}")
        
        return artifact
    
    def _generate_report(self, force: bool = False) -> dict[str, Any]:
        """Generate Screen 4: Analysis report."""
        cache_path = self.scratch_dir / "screen4_report.json"
        
        if not force and cache_path.exists():
            _log("Loading cached report...")
            return _load_json_if_exists(cache_path)
        
        _log("Generating Screen 4: Analysis Report...")
        
        # Try to generate structured report
        try:
            report = self.report.generate_structured_report(DEMO_SESSION_ID)
        except Exception as e:
            _log(f"Structured report generation failed: {e}")
            _log("Creating fallback report...")
            
            # Get agents for basic stats
            agents = self.store.get_agents(DEMO_SESSION_ID)
            interactions = self.store.get_interactions(DEMO_SESSION_ID)
            
            # Calculate basic metrics
            pre_scores = [float(a.get("opinion_pre", 5)) for a in agents if a.get("opinion_pre")]
            post_scores = [float(a.get("opinion_post", 5)) for a in agents if a.get("opinion_post")]
            
            pre_approval = sum(1 for s in pre_scores if s >= 6) / len(pre_scores) if pre_scores else 0
            post_approval = sum(1 for s in post_scores if s >= 6) / len(post_scores) if post_scores else 0
            
            # Group by planning area
            by_area = {}
            for a in agents:
                area = a.get("persona", {}).get("planning_area", "Unknown")
                if area not in by_area:
                    by_area[area] = {"pre": [], "post": []}
                if a.get("opinion_pre"):
                    by_area[area]["pre"].append(float(a["opinion_pre"]))
                if a.get("opinion_post"):
                    by_area[area]["post"].append(float(a["opinion_post"]))
            
            friction = []
            for area, scores in by_area.items():
                if scores["pre"] and scores["post"]:
                    avg_pre = sum(scores["pre"]) / len(scores["pre"])
                    avg_post = sum(scores["post"]) / len(scores["post"])
                    friction.append({
                        "planning_area": area,
                        "avg_pre_opinion": round(avg_pre, 2),
                        "avg_post_opinion": round(avg_post, 2),
                        "approval_post": round(sum(1 for s in scores["post"] if s >= 6) / len(scores["post"]), 2) if scores["post"] else 0,
                        "mean_shift": round(avg_post - avg_pre, 2),
                        "friction_index": round(abs(avg_post - 5) / 5, 2),
                        "cohort_size": len(scores["post"]),
                    })
            
            friction.sort(key=lambda x: x["friction_index"], reverse=True)
            
            report = {
                "session_id": DEMO_SESSION_ID,
                "status": "completed",
                "generated_at": _now(),
                "executive_summary": f"Demo simulation with {len(agents)} agents over {DEMO_ROUNDS} rounds. Approval shifted from {pre_approval:.1%} to {post_approval:.1%}.",
                "insight_cards": [
                    {"title": "Sample Insight", "content": "This is a demo report with sample insights.", "confidence": "medium"}
                ],
                "support_themes": [],
                "dissent_themes": [],
                "demographic_breakdown": [
                    {"cohort": area, "pre_approval": d["avg_pre_opinion"], "post_approval": d["avg_post_opinion"], "shift": d["mean_shift"]}
                    for area, d in [(f["planning_area"], f) for f in friction[:5]]
                ],
                "influential_content": [],
                "recommendations": [
                    {"title": "Demo Recommendation", "description": "This is a sample recommendation for demo purposes.", "target": "general"}
                ],
                "risks": [],
                "friction_by_planning_area": friction,
                "influential_agents": [
                    {"agent_id": a.get("agent_id"), "influence_score": 0.5, "planning_area": a.get("persona", {}).get("planning_area", "Unknown")}
                    for a in agents[:10]
                ],
            }
        
        report["demo_mode"] = True
        report["generated_at"] = _now()
        
        _write_json(cache_path, report)
        _log(f"Report generated: {len(report.get('insight_cards', []))} insights")
        
        return report
    
    def _create_unified_output(
        self,
        knowledge: dict[str, Any],
        population: dict[str, Any],
        simulation: dict[str, Any],
        memory_sync: dict[str, Any],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Create unified demo output file."""
        
        # Get interactions for feed
        interactions = self.store.get_interactions(DEMO_SESSION_ID)[-50:]
        feed = [
            {
                "event_type": "post_created",
                "session_id": DEMO_SESSION_ID,
                "round_no": i.get("round_no", 1),
                "actor_agent_id": i.get("actor_agent_id"),
                "content": i.get("content"),
            }
            for i in interactions
        ]
        
        # Build friction map data
        friction_data = report.get("friction_by_planning_area", [])
        
        output = {
            "generated_at": _now(),
            "simulation_id": DEMO_SESSION_ID,
            "session": {
                "session_id": DEMO_SESSION_ID,
                "mode": "demo",
                "status": "simulation_completed",
                "created_at": _now(),
                "updated_at": _now(),
            },
            "knowledge": knowledge,
            "population": population,
            "simulation": simulation,
            "simulationState": {
                "session_id": DEMO_SESSION_ID,
                "status": "completed",
                "event_count": len(interactions),
                "last_round": DEMO_ROUNDS,
                "platform": "reddit",
                "planned_rounds": DEMO_ROUNDS,
                "current_round": DEMO_ROUNDS,
                "latest_metrics": {
                    "approval_pre": simulation.get("stage3a_approval_rate", 0),
                    "approval_post": simulation.get("stage3b_approval_rate", 0),
                    "net_shift": simulation.get("net_opinion_shift", 0),
                },
                "recent_events": feed[-20:],
            },
            "memory_sync": memory_sync,
            "report": report,
            "reportFull": {
                "session_id": DEMO_SESSION_ID,
                "status": "completed",
                "generated_at": _now(),
                **report,
            },
            "reportOpinions": {
                "session_id": DEMO_SESSION_ID,
                "feed": feed,
                "influential_agents": report.get("influential_agents", []),
            },
            "reportFriction": {
                "session_id": DEMO_SESSION_ID,
                "map_metrics": friction_data,
                "anomaly_summary": f"Highest friction: {friction_data[0]['planning_area']}" if friction_data else "No friction data",
            },
            "interactionHub": {
                "session_id": DEMO_SESSION_ID,
                "report_agent": {
                    "starter_prompt": "Ask about dissent clusters, mitigation options, or demographic shifts.",
                },
                "influential_agents": report.get("influential_agents", []),
                "selected_agent": report.get("influential_agents", [{}])[0],
            },
            "demo_metadata": {
                "agent_count": DEMO_AGENT_COUNT,
                "rounds": DEMO_ROUNDS,
                "document": "Sample_Inputs/fy2026_budget_statement.md",
                "zep_enabled": memory_sync.get("zep_enabled", False),
                "cached_at": _now(),
            },
        }
        
        # Write to both backend and frontend locations
        backend_path = Path(self.settings.console_demo_output_path)
        frontend_path = Path(self.settings.console_demo_frontend_output_path)
        
        _write_json(backend_path, output)
        _write_json(frontend_path, output)
        
        return output
    
    def _build_final_checkpoint_bundles(
        self,
        session_id: str,
        context_bundles: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Build context bundles for final checkpoint."""
        # Get interactions to enrich context
        interactions = self.store.get_interactions(session_id)
        
        # Group interactions by agent
        agent_interactions: dict[str, list[dict]] = {}
        for i in interactions:
            agent_id = i.get("actor_agent_id")
            if agent_id:
                agent_interactions.setdefault(agent_id, []).append(i)
        
        # Enrich bundles with simulation experience
        enriched = {}
        for agent_id, bundle in context_bundles.items():
            agent_ints = agent_interactions.get(agent_id, [])
            experience_summary = self._summarize_experience(agent_ints)
            
            enriched[agent_id] = {
                **bundle,
                "simulation_experience": experience_summary,
                "interaction_count": len(agent_ints),
            }
        
        return enriched
    
    def _summarize_experience(self, interactions: list[dict]) -> str:
        """Create a summary of agent's simulation experience."""
        if not interactions:
            return "No interactions during simulation."
        
        posts = [i for i in interactions if i.get("action_type") == "post"]
        comments = [i for i in interactions if i.get("action_type") == "comment"]
        reactions = [i for i in interactions if i.get("action_type") in ("like", "dislike")]
        
        return (
            f"Made {len(posts)} posts, {len(comments)} comments, "
            f"and {len(reactions)} reactions during the simulation."
        )


def main():
    parser = argparse.ArgumentParser(
        description="Generate comprehensive demo cache for McKAInsey"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of all demo cache files",
    )
    parser.add_argument(
        "--screen",
        choices=["knowledge", "population", "simulation", "memory", "report", "all"],
        default="all",
        help="Generate specific screen only",
    )
    args = parser.parse_args()
    
    settings = get_settings()
    
    # Validate API keys
    if not settings.resolved_gemini_key:
        _log("WARNING: No Gemini API key found. Knowledge extraction may fail.")
        _log("Set GEMINI_API or GEMINI_API_KEY environment variable.")
    
    if not settings.resolved_zep_key:
        _log("WARNING: No Zep Cloud API key found. Memory sync will be disabled.")
        _log("Set ZEP_CLOUD or ZEP_API_KEY environment variable.")
    
    generator = ComprehensiveDemoCacheGenerator(settings)
    
    if args.screen == "all":
        generator.generate_all(force_regenerate=args.force)
    else:
        # Generate specific screen
        generator._init_demo_session()
        
        if args.screen == "knowledge":
            generator._generate_knowledge(force=True)
        elif args.screen == "population":
            knowledge = generator._generate_knowledge(force=False)
            generator._generate_population(knowledge, force=True)
        elif args.screen == "simulation":
            knowledge = generator._generate_knowledge(force=False)
            population = generator._generate_population(knowledge, force=False)
            generator._generate_simulation(population, force=True)
        elif args.screen == "memory":
            simulation = generator._generate_simulation({}, force=False)
            generator._sync_to_zep(simulation, force=True)
        elif args.screen == "report":
            generator._generate_report(force=True)


if __name__ == "__main__":
    main()
