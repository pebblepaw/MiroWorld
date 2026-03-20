from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
import random
from typing import Any

from fastapi import HTTPException
from fastapi import UploadFile

from mckainsey.config import Settings
from mckainsey.models.phase_a import PersonaFilterRequest
from mckainsey.services.document_parser import extract_document_text
from mckainsey.services.lightrag_service import LightRAGService
from mckainsey.services.memory_service import MemoryService
from mckainsey.services.persona_relevance_service import PersonaRelevanceService
from mckainsey.services.persona_sampler import PersonaSampler
from mckainsey.services.report_service import ReportService
from mckainsey.services.simulation_service import SimulationService
from mckainsey.services.simulation_stream_service import SimulationStreamService
from mckainsey.services.storage import SimulationStore

MAX_AFFECTED_GROUPS_CANDIDATES = 1000
MAX_BASELINE_CANDIDATES = 1200
MIN_AFFECTED_GROUPS_CANDIDATES = 400
MIN_BASELINE_CANDIDATES = 600


class ConsoleService:
    def __init__(self, settings: Settings):
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

    def create_session(self, requested_session_id: str | None = None, mode: str = "demo") -> dict[str, Any]:
        session_id = requested_session_id or f"session-{uuid.uuid4().hex[:8]}"
        self.store.upsert_console_session(session_id=session_id, mode=mode, status="created")
        return {"session_id": session_id, "mode": mode, "status": "created"}

    async def process_knowledge(
        self,
        session_id: str,
        *,
        document_text: str | None = None,
        source_path: str | None = None,
        guiding_prompt: str | None = None,
        demographic_focus: str | None = None,
        use_default_demo_document: bool = False,
    ) -> dict[str, Any]:
        session = self.store.get_console_session(session_id)
        if not session:
            self.create_session(session_id)

        resolved_source = source_path
        resolved_text = document_text
        if use_default_demo_document and not resolved_text:
            path = Path(self.settings.demo_default_policy_markdown)
            if not path.exists():
                alt = Path("..") / self.settings.demo_default_policy_markdown
                path = alt
            resolved_source = str(path)
            resolved_text = path.read_text(encoding="utf-8")

        if not resolved_text:
            raise HTTPException(status_code=422, detail="document_text or use_default_demo_document is required")

        artifact = await self.lightrag.process_document(
            simulation_id=session_id,
            document_text=resolved_text,
            source_path=resolved_source,
            guiding_prompt=guiding_prompt,
            demographic_focus=demographic_focus,
        )
        artifact["session_id"] = session_id
        artifact["guiding_prompt"] = guiding_prompt
        self.store.save_knowledge_artifact(session_id, artifact)
        self.store.upsert_console_session(session_id=session_id, mode=session.get("mode", "demo") if session else "demo", status="knowledge_ready")
        return artifact

    async def process_uploaded_knowledge(
        self,
        session_id: str,
        *,
        upload: UploadFile,
        guiding_prompt: str | None = None,
        demographic_focus: str | None = None,
    ) -> dict[str, Any]:
        filename = upload.filename or "uploaded-document"
        payload = await upload.read()
        if not payload:
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")

        upload_dir = Path(self.settings.console_upload_dir)
        if not upload_dir.is_absolute():
            upload_dir = Path.cwd() / upload_dir
        session_dir = upload_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        stored_path = session_dir / filename
        stored_path.write_bytes(payload)

        try:
            document_text = extract_document_text(filename, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return await self.process_knowledge(
            session_id,
            document_text=document_text,
            source_path=str(stored_path),
            guiding_prompt=guiding_prompt,
            demographic_focus=demographic_focus,
        )

    def preview_population(self, session_id: str, request: Any) -> dict[str, Any]:
        knowledge = self.store.get_knowledge_artifact(session_id)
        if not knowledge:
            raise HTTPException(status_code=404, detail=f"Knowledge artifact not found for session {session_id}")

        parsed_instructions = self.relevance.parse_sampling_instructions(
            request.sampling_instructions,
            knowledge_artifact=knowledge,
        )
        effective_seed = int(request.seed if request.seed is not None else random.randint(1, 2_147_483_647))
        if request.sample_mode == "population_baseline":
            candidate_limit = min(
                max(request.agent_count * 3, MIN_BASELINE_CANDIDATES),
                MAX_BASELINE_CANDIDATES,
            )
        else:
            candidate_limit = min(
                max(request.agent_count * 2, MIN_AFFECTED_GROUPS_CANDIDATES),
                MAX_AFFECTED_GROUPS_CANDIDATES,
            )
        merged_filters = self._merge_population_filters(request, parsed_instructions)
        personas = self.sampler.query_candidates(
            limit=candidate_limit,
            seed=effective_seed,
            min_age=merged_filters["min_age"],
            max_age=merged_filters["max_age"],
            planning_areas=merged_filters["planning_areas"],
            sexes=merged_filters["sexes"],
            marital_statuses=merged_filters["marital_statuses"],
            education_levels=merged_filters["education_levels"],
            occupations=merged_filters["occupations"],
            industries=merged_filters["industries"],
        )
        if not personas:
            raise HTTPException(status_code=422, detail="No personas matched the current sampling configuration.")

        artifact = self.relevance.build_population_artifact(
            session_id,
            personas=personas,
            knowledge_artifact=knowledge,
            filters={
                **request.model_dump(),
                **merged_filters,
            },
            agent_count=request.agent_count,
            sample_mode=request.sample_mode,
            seed=effective_seed,
            parsed_sampling_instructions=parsed_instructions,
        )
        self.store.save_population_artifact(session_id, artifact)
        return artifact

    def start_simulation(self, session_id: str, *, policy_summary: str, rounds: int, mode: str | None = None) -> dict[str, Any]:
        session = self.store.get_console_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        effective_mode = mode or session.get("mode", "demo")
        if effective_mode == "live" and not self.settings.enable_real_oasis:
            raise HTTPException(status_code=409, detail="Live mode requires ENABLE_REAL_OASIS=true")

        population = self.store.get_population_artifact(session_id)
        if not population:
            raise HTTPException(status_code=404, detail=f"Population artifact not found: {session_id}")

        sampled_rows = list(population.get("sampled_personas", []))
        personas = [dict(row["persona"], agent_id=row.get("agent_id")) for row in sampled_rows]
        if not sampled_rows:
            raise HTTPException(status_code=422, detail="No sampled personas available for simulation start")

        events_dir = Path(self.settings.oasis_db_dir).parent / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        events_path = events_dir / f"{session_id}.ndjson"
        if events_path.exists():
            events_path.unlink()

        self.store.clear_simulation_events(session_id)
        self.store.clear_simulation_state_snapshot(session_id)
        self.store.clear_report_cache(session_id)
        self.store.clear_report_state(session_id)
        self.store.clear_checkpoint_records(session_id)
        self.store.clear_interaction_transcripts(session_id)
        self.store.reset_memory_sync_state(session_id)
        initial_estimate = self._estimate_initial_runtime(agent_count=len(sampled_rows), rounds=rounds)
        self.store.save_simulation_state_snapshot(
            session_id,
            {
                "session_id": session_id,
                "status": "running",
                "platform": self.settings.simulation_platform,
                "planned_rounds": rounds,
                "event_count": 0,
                "last_round": 0,
                "current_round": 0,
                "elapsed_seconds": 0,
                "estimated_total_seconds": initial_estimate,
                "estimated_remaining_seconds": initial_estimate,
                "counters": {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
                "checkpoint_status": {
                    "baseline": {"status": "pending", "completed_agents": 0, "total_agents": len(sampled_rows)},
                    "final": {"status": "pending", "completed_agents": 0, "total_agents": len(sampled_rows)},
                },
                "top_threads": [],
                "discussion_momentum": {"approval_delta": 0.0, "dominant_stance": "mixed"},
                "latest_metrics": {},
                "recent_events": [],
                "events_path": str(events_path),
                "stream_offset_bytes": 0,
            },
        )
        self.store.upsert_console_session(session_id=session_id, mode=effective_mode, status="simulation_running")

        thread = threading.Thread(
            target=self._run_simulation_background,
            args=(session_id, policy_summary, rounds, sampled_rows, personas, events_path, effective_mode),
            daemon=True,
        )
        thread.start()
        return self.streams.get_state(session_id)

    def generate_report(self, session_id: str) -> dict[str, Any]:
        state = self.store.get_report_state(session_id)
        if state and state.get("status") in {"running", "completed"}:
            return state

        initial_state = self._empty_report_state(session_id, status="running")
        self.store.save_report_state(session_id, initial_state)
        thread = threading.Thread(
            target=self._run_report_generation_background,
            args=(session_id,),
            daemon=True,
        )
        thread.start()
        return initial_state

    def get_report_full(self, session_id: str) -> dict[str, Any]:
        return self.store.get_report_state(session_id) or self._empty_report_state(session_id, status="idle")

    def get_report_opinions(self, session_id: str) -> dict[str, Any]:
        report = self.report.build_report(session_id)
        feed = self.store.get_interactions(session_id)[-50:]
        return {
            "session_id": session_id,
            "feed": feed,
            "influential_agents": report.get("influential_agents", []),
        }

    def get_report_friction_map(self, session_id: str) -> dict[str, Any]:
        report = self.report.build_report(session_id)
        friction = report.get("friction_by_planning_area", [])
        top = friction[0]["planning_area"] if friction else "N/A"
        return {
            "session_id": session_id,
            "map_metrics": friction,
            "anomaly_summary": f"Highest observed friction cluster: {top}",
        }

    def get_interaction_hub(self, session_id: str, agent_id: str | None = None) -> dict[str, Any]:
        report = self.report.build_report(session_id)
        influential = report.get("influential_agents", [])
        selected_agent_id = agent_id or (str(influential[0].get("agent_id")) if influential else None)
        selected = self._build_selected_agent_state(session_id, selected_agent_id, influential)
        report_transcript = self.store.list_interaction_transcript(session_id, channel="report_agent", limit=12)
        return {
            "session_id": session_id,
            "selected_agent_id": selected_agent_id,
            "report_agent": {
                "starter_prompt": "Ask about dissent clusters, mitigation options, or demographic shifts.",
                "transcript": report_transcript,
            },
            "influential_agents": influential,
            "selected_agent": selected,
        }

    def report_chat(self, session_id: str, message: str) -> dict[str, Any]:
        payload = self.report.report_chat_payload(session_id, message)
        self.store.append_interaction_transcript(session_id, "report_agent", "user", message)
        self.store.append_interaction_transcript(session_id, "report_agent", "assistant", payload["response"])
        return payload

    def agent_chat(self, session_id: str, agent_id: str, message: str) -> dict[str, Any]:
        payload = self.memory.agent_chat_realtime(session_id, agent_id, message)
        self.store.append_interaction_transcript(session_id, "agent_chat", "user", message, agent_id=agent_id)
        self.store.append_interaction_transcript(session_id, "agent_chat", "assistant", payload["response"], agent_id=agent_id)
        return payload

    def _build_selected_agent_state(
        self,
        session_id: str,
        agent_id: str | None,
        influential_agents: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not agent_id:
            return None

        by_agent_id = {str(agent["agent_id"]): agent for agent in self.store.get_agents(session_id)}
        influential = next((agent for agent in influential_agents if str(agent.get("agent_id")) == agent_id), None)
        stored = by_agent_id.get(agent_id)
        recent_memory = self.memory.get_agent_memory(session_id, agent_id)[-8:]
        transcript = self.store.list_interaction_transcript(session_id, "agent_chat", agent_id=agent_id, limit=12)
        persona = stored.get("persona", {}) if stored else {}
        merged = dict(influential or {})
        merged.update(
            {
                "agent_id": agent_id,
                "persona": persona,
                "recent_memory": recent_memory,
                "transcript": transcript,
            }
        )
        return merged

    def _run_simulation_background(
        self,
        session_id: str,
        policy_summary: str,
        rounds: int,
        sampled_rows: list[dict[str, Any]],
        personas: list[dict[str, Any]],
        events_path: Path,
        mode: str,
    ) -> None:
        try:
            knowledge = self.store.get_knowledge_artifact(session_id) or {}
            context_bundles = self.simulation.build_context_bundles(
                simulation_id=session_id,
                policy_summary=policy_summary,
                knowledge_artifact=knowledge,
                sampled_personas=sampled_rows,
            )
            checkpoint_estimate = self._estimate_checkpoint_runtime(agent_count=len(sampled_rows))
            baseline_started_at = time.monotonic()
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_started",
                        "session_id": session_id,
                        "checkpoint_kind": "baseline",
                        "total_agents": len(sampled_rows),
                    }
                ],
            )
            baseline = self.simulation.run_opinion_checkpoint(
                simulation_id=session_id,
                checkpoint_kind="baseline",
                policy_summary=policy_summary,
                agent_context_bundles=context_bundles,
            )
            baseline_elapsed = max(1, int(time.monotonic() - baseline_started_at))
            self.store.replace_checkpoint_records(session_id, "baseline", baseline)
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_completed",
                        "session_id": session_id,
                        "checkpoint_kind": "baseline",
                        "completed_agents": len(baseline),
                        "total_agents": len(sampled_rows),
                    },
                    {
                        "event_type": "metrics_updated",
                        "session_id": session_id,
                        "round_no": 0,
                        "elapsed_seconds": baseline_elapsed,
                        "estimated_total_seconds": baseline_elapsed + (rounds * max(10, int(len(sampled_rows) * 0.05) + 6)) + checkpoint_estimate,
                        "estimated_remaining_seconds": (rounds * max(10, int(len(sampled_rows) * 0.05) + 6)) + checkpoint_estimate,
                        "counters": {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
                        "discussion_momentum": {"approval_delta": 0.0, "dominant_stance": "mixed"},
                        "top_threads": [],
                        "metrics": {"checkpoint": "baseline"},
                    },
                ],
            )
            enriched_personas = self._enrich_personas_for_simulation(personas, sampled_rows, context_bundles)
            simulation_result = self.simulation.run_with_personas(
                simulation_id=session_id,
                policy_summary=policy_summary,
                rounds=rounds,
                personas=enriched_personas,
                events_path=events_path,
                force_live=(mode == "live"),
                on_progress=lambda path, elapsed: self.streams.ingest_events_incremental(session_id, path),
                elapsed_offset_seconds=baseline_elapsed,
                tail_checkpoint_estimate_seconds=checkpoint_estimate,
            )
            self.streams.ingest_events_incremental(session_id, events_path)
            final_bundles = self._build_final_checkpoint_bundles(session_id, context_bundles)
            final_started_at = time.monotonic()
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_started",
                        "session_id": session_id,
                        "checkpoint_kind": "final",
                        "total_agents": len(sampled_rows),
                    }
                ],
            )
            final = self.simulation.run_opinion_checkpoint(
                simulation_id=session_id,
                checkpoint_kind="final",
                policy_summary=policy_summary,
                agent_context_bundles=final_bundles,
            )
            final_elapsed = max(1, int(time.monotonic() - final_started_at))
            total_elapsed = int(simulation_result.get("elapsed_seconds", 0) or 0) + final_elapsed
            final_counters = dict(simulation_result.get("counters") or {})
            current_state = self.streams.get_state(session_id)
            self.store.replace_checkpoint_records(session_id, "final", final)
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "checkpoint_completed",
                        "session_id": session_id,
                        "checkpoint_kind": "final",
                        "completed_agents": len(final),
                        "total_agents": len(sampled_rows),
                    },
                    {
                        "event_type": "metrics_updated",
                        "session_id": session_id,
                        "round_no": rounds,
                        "elapsed_seconds": total_elapsed,
                        "estimated_total_seconds": total_elapsed,
                        "estimated_remaining_seconds": 0,
                        "counters": final_counters or {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
                        "discussion_momentum": current_state.get("discussion_momentum", {"approval_delta": 0.0, "dominant_stance": "mixed"}),
                        "top_threads": current_state.get("top_threads", []),
                        "metrics": {"checkpoint": "final"},
                    },
                    {
                        "event_type": "run_completed",
                        "session_id": session_id,
                        "round_no": rounds,
                        "elapsed_seconds": total_elapsed,
                    },
                ],
            )
            self._apply_checkpoint_scores_to_agents(session_id, sampled_rows, baseline, final)
            self.store.upsert_console_session(session_id=session_id, mode=mode, status="simulation_completed")
        except Exception as exc:  # noqa: BLE001
            self.streams.append_events(
                session_id,
                [
                    {
                        "event_type": "run_failed",
                        "session_id": session_id,
                        "error": str(exc),
                    }
                ],
            )
            failure_state = {
                "session_id": session_id,
                "status": "failed",
                "event_count": 0,
                "last_round": 0,
                "latest_metrics": {"error": str(exc)},
                "recent_events": [],
                "events_path": str(events_path),
            }
            self.store.save_simulation_state_snapshot(session_id, failure_state)
            self.store.upsert_console_session(session_id=session_id, mode=mode, status="simulation_failed")

    def _run_report_generation_background(self, session_id: str) -> None:
        try:
            payload = self.report.generate_structured_report(session_id)
            self.store.save_report_state(session_id, payload)
        except Exception as exc:  # noqa: BLE001
            failed = self._empty_report_state(session_id, status="failed")
            failed["error"] = str(exc)
            self.store.save_report_state(session_id, failed)

    def _merge_population_filters(self, request: Any, parsed_instructions: dict[str, Any]) -> dict[str, Any]:
        hard_filters = parsed_instructions.get("hard_filters", {})

        min_age = request.min_age
        max_age = request.max_age
        requested_age_cohorts = hard_filters.get("age_cohort", [])
        if requested_age_cohorts:
            age_bounds = [self._age_bounds_for_cohort(cohort) for cohort in requested_age_cohorts]
            age_bounds = [bounds for bounds in age_bounds if bounds is not None]
            if age_bounds:
                derived_min = min(bounds[0] for bounds in age_bounds)
                derived_max = max(bounds[1] for bounds in age_bounds)
                min_age = derived_min if min_age is None else max(min_age, derived_min)
                max_age = derived_max if max_age is None else min(max_age, derived_max)

        return {
            "min_age": min_age,
            "max_age": max_age,
            "planning_areas": self._merge_unique_values(request.planning_areas, hard_filters.get("planning_area", []), title_case=True),
            "sexes": self._merge_unique_values([], hard_filters.get("sex", []), title_case=True),
            "marital_statuses": self._merge_unique_values([], hard_filters.get("marital_status", [])),
            "education_levels": self._merge_unique_values([], hard_filters.get("education_level", [])),
            "occupations": self._merge_unique_values([], hard_filters.get("occupation", [])),
            "industries": self._merge_unique_values([], hard_filters.get("industry", [])),
        }

    def _merge_unique_values(self, primary: list[str], secondary: list[str], *, title_case: bool = False) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for raw in [*(primary or []), *(secondary or [])]:
            text = str(raw).strip()
            if not text:
                continue
            value = text.replace("_", " ")
            if title_case:
                value = value.title()
            slug = value.lower()
            if slug in seen:
                continue
            seen.add(slug)
            merged.append(value)
        return merged

    def _age_bounds_for_cohort(self, cohort: str) -> tuple[int, int] | None:
        normalized = str(cohort).strip().lower()
        if normalized == "youth":
            return (18, 24)
        if normalized == "adult":
            return (25, 59)
        if normalized == "senior":
            return (60, 100)
        return None

    def _estimate_initial_runtime(self, *, agent_count: int, rounds: int) -> int:
        checkpoint_seconds = self._estimate_checkpoint_runtime(agent_count=agent_count)
        round_seconds = max(10, int(agent_count * 0.05) + 6)
        return (checkpoint_seconds * 2) + (round_seconds * rounds)

    def _estimate_checkpoint_runtime(self, *, agent_count: int) -> int:
        return max(8, int(agent_count * 0.18))

    def _empty_report_state(self, session_id: str, *, status: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "status": status,
            "generated_at": None,
            "executive_summary": None,
            "insight_cards": [],
            "support_themes": [],
            "dissent_themes": [],
            "demographic_breakdown": [],
            "influential_content": [],
            "recommendations": [],
            "risks": [],
        }

    def _enrich_personas_for_simulation(
        self,
        personas: list[dict[str, Any]],
        sampled_rows: list[dict[str, Any]],
        context_bundles: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        by_agent = {str(row.get("agent_id")): row for row in sampled_rows}
        for persona in personas:
            agent_id = str(persona.get("agent_id", "")).strip()
            row = by_agent.get(agent_id, {})
            reason = dict(row.get("selection_reason") or {})
            bundle = context_bundles.get(agent_id, {})
            enriched_persona = dict(persona)
            enriched_persona["mckainsey_context"] = bundle.get("brief")
            enriched_persona["mckainsey_matched_context_nodes"] = bundle.get("matched_context_nodes", [])
            enriched_persona["mckainsey_relevance_score"] = reason.get("score") or reason.get("selection_score") or 0.0
            enriched.append(enriched_persona)
        return enriched

    def _build_final_checkpoint_bundles(
        self,
        session_id: str,
        context_bundles: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        interactions = self.store.get_interactions(session_id)
        by_agent: dict[str, list[str]] = {}
        for interaction in interactions:
            agent_id = str(interaction.get("actor_agent_id", "")).strip()
            content = str(interaction.get("content", "")).strip()
            if not agent_id or not content:
                continue
            by_agent.setdefault(agent_id, []).append(content)

        bundles: dict[str, dict[str, Any]] = {}
        for agent_id, bundle in context_bundles.items():
            discussion = " ".join(by_agent.get(agent_id, [])[:4]).strip()
            updated = dict(bundle)
            if discussion:
                updated["brief"] = f"{bundle['brief']} Discussion excerpt: {discussion}"
            bundles[agent_id] = updated
        return bundles

    def _apply_checkpoint_scores_to_agents(
        self,
        session_id: str,
        sampled_rows: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
    ) -> None:
        baseline_map = {str(row.get("agent_id")): row for row in baseline}
        final_map = {str(row.get("agent_id")): row for row in final}
        updated_agents: list[dict[str, Any]] = []
        for row in sampled_rows:
            agent_id = str(row.get("agent_id"))
            persona = dict(row.get("persona") or {})
            pre_score = float(baseline_map.get(agent_id, {}).get("stance_score", 0.5))
            post_score = float(final_map.get(agent_id, baseline_map.get(agent_id, {})).get("stance_score", pre_score))
            updated_agents.append(
                {
                    "agent_id": agent_id,
                    "persona": persona,
                    "opinion_pre": round(1 + (pre_score * 9), 4),
                    "opinion_post": round(1 + (post_score * 9), 4),
                }
            )
        self.store.replace_agents(session_id, updated_agents)
