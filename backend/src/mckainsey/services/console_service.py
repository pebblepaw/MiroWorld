from __future__ import annotations

import threading
import time
import uuid
import re
from pathlib import Path
import random
from typing import Any

from fastapi import HTTPException
from fastapi import UploadFile

from mckainsey.config import Settings
from mckainsey.models.phase_a import PersonaFilterRequest
from mckainsey.services.demo_service import DemoService
from mckainsey.services.document_parser import extract_document_text
from mckainsey.services.lightrag_service import LightRAGService
from mckainsey.services.memory_service import MemoryService
from mckainsey.services.model_provider_service import (
    ensure_ollama_models_available,
    mask_api_key,
    normalize_provider,
    provider_catalog,
    resolve_model_selection,
    selection_to_settings_update,
)
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
        self.sampler = PersonaSampler(
            settings.nemotron_dataset,
            settings.nemotron_split,
            cache_dir=settings.nemotron_cache_dir,
            download_workers=settings.nemotron_download_workers,
        )
        self.streams = SimulationStreamService(settings)
        self.demo = DemoService(settings)

    def _session_record(self, session_id: str) -> dict[str, Any] | None:
        return self.store.get_console_session(session_id)

    def _session_model_overrides(self, session: dict[str, Any] | None) -> dict[str, Any]:
        if not session:
            return {}
        return {
            "provider": session.get("model_provider"),
            "model_name": session.get("model_name"),
            "embed_model_name": session.get("embed_model_name"),
            "api_key": session.get("api_key"),
            "base_url": session.get("base_url"),
        }

    def _runtime_settings_for_session(self, session_id: str) -> Settings:
        session = self._session_record(session_id)
        selection = resolve_model_selection(
            self.settings,
            **self._session_model_overrides(session),
        )
        updates = selection_to_settings_update(selection)
        updates["lightrag_workdir"] = self._session_lightrag_workdir(
            session_id,
            provider=selection.provider,
            embed_model_name=selection.embed_model_name,
        )
        return self.settings.model_copy(update=updates)

    def _session_lightrag_workdir(self, session_id: str, *, provider: str, embed_model_name: str) -> str:
        base = Path(self.settings.lightrag_workdir)
        provider_slug = re.sub(r"[^a-zA-Z0-9]+", "_", provider.lower()).strip("_") or "provider"
        embed_slug = re.sub(r"[^a-zA-Z0-9]+", "_", embed_model_name.lower()).strip("_") or "embed"
        return str((base / "sessions" / session_id / f"{provider_slug}_{embed_slug}").resolve())

    def _session_model_payload(self, session_id: str) -> dict[str, Any]:
        session = self._session_record(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        selection = resolve_model_selection(
            self.settings,
            **self._session_model_overrides(session),
        )
        return {
            "session_id": session_id,
            "model_provider": selection.provider,
            "model_name": selection.model_name,
            "embed_model_name": selection.embed_model_name,
            "base_url": selection.base_url,
            "api_key_configured": selection.api_key_configured,
            "api_key_masked": mask_api_key(selection.api_key),
        }

    def _format_runtime_failure_detail(self, session_id: str, exc: Exception, *, action: str) -> str:
        try:
            runtime_settings = self._runtime_settings_for_session(session_id)
            provider = runtime_settings.llm_provider
            model_name = runtime_settings.llm_model
        except Exception:  # noqa: BLE001
            provider = self.settings.llm_provider
            model_name = self.settings.llm_model

        raw_message = str(exc).strip() or exc.__class__.__name__
        lowered = raw_message.lower()
        hint = ""

        if "insufficient_quota" in lowered or "quota" in lowered:
            hint = "Provider quota or billing limits were hit for the configured API key."
        elif provider == "ollama" and any(token in lowered for token in ("timed out", "timeout", "connection", "refused")):
            hint = "Local Ollama runtime appears unavailable or overloaded."

        detail = f"{action} failed for provider '{provider}' model '{model_name}': {raw_message}"
        if hint:
            detail = f"{detail}. {hint}"
        return detail

    def model_provider_catalog(self) -> dict[str, Any]:
        return {"providers": provider_catalog(self.settings)}

    def list_provider_models(
        self,
        provider: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_provider(provider)
        from mckainsey.services.model_provider_service import list_models_for_provider

        models = list_models_for_provider(
            self.settings,
            provider=normalized,
            api_key=api_key,
            base_url=base_url,
        )
        return {
            "provider": normalized,
            "models": models,
        }

    def get_session_model_config(self, session_id: str) -> dict[str, Any]:
        return self._session_model_payload(session_id)

    def update_session_model_config(
        self,
        session_id: str,
        *,
        model_provider: str,
        model_name: str,
        embed_model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        session = self._session_record(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        selection = resolve_model_selection(
            self.settings,
            provider=model_provider,
            model_name=model_name,
            embed_model_name=embed_model_name,
            api_key=api_key,
            base_url=base_url,
        )
        if selection.provider == "ollama":
            ensure_ollama_models_available(self.settings, selection)

        self.store.upsert_console_session(
            session_id=session_id,
            mode=session.get("mode", "demo"),
            status=session.get("status", "created"),
            model_provider=selection.provider,
            model_name=selection.model_name,
            embed_model_name=selection.embed_model_name,
            api_key=selection.api_key,
            base_url=selection.base_url,
        )
        return self._session_model_payload(session_id)

    def create_session(
        self,
        requested_session_id: str | None = None,
        mode: str = "demo",
        *,
        model_provider: str | None = None,
        model_name: str | None = None,
        embed_model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        selection = resolve_model_selection(
            self.settings,
            provider=model_provider,
            model_name=model_name,
            embed_model_name=embed_model_name,
            api_key=api_key,
            base_url=base_url,
        )
        if selection.provider == "ollama" and mode == "live":
            ensure_ollama_models_available(self.settings, selection)

        # If demo mode and demo cache is available, use demo service.
        if mode == "demo" and self.demo.is_demo_available():
            demo_payload = self.demo.create_demo_session(requested_session_id)
            session_id = str(demo_payload["session_id"])
            self.store.upsert_console_session(
                session_id=session_id,
                mode=mode,
                status=str(demo_payload.get("status", "created")),
                model_provider=selection.provider,
                model_name=selection.model_name,
                embed_model_name=selection.embed_model_name,
                api_key=selection.api_key,
                base_url=selection.base_url,
            )
            return {
                **demo_payload,
                "model_provider": selection.provider,
                "model_name": selection.model_name,
                "embed_model_name": selection.embed_model_name,
                "base_url": selection.base_url,
                "api_key_configured": selection.api_key_configured,
                "api_key_masked": mask_api_key(selection.api_key),
            }

        session_id = requested_session_id or f"session-{uuid.uuid4().hex[:8]}"
        self.store.upsert_console_session(
            session_id=session_id,
            mode=mode,
            status="created",
            model_provider=selection.provider,
            model_name=selection.model_name,
            embed_model_name=selection.embed_model_name,
            api_key=selection.api_key,
            base_url=selection.base_url,
        )
        return {
            "session_id": session_id,
            "mode": mode,
            "status": "created",
            "model_provider": selection.provider,
            "model_name": selection.model_name,
            "embed_model_name": selection.embed_model_name,
            "base_url": selection.base_url,
            "api_key_configured": selection.api_key_configured,
            "api_key_masked": mask_api_key(selection.api_key),
        }

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

        runtime_settings = self._runtime_settings_for_session(session_id)
        lightrag = LightRAGService(runtime_settings)
        try:
            artifact = await lightrag.process_document(
                simulation_id=session_id,
                document_text=resolved_text,
                source_path=resolved_source,
                guiding_prompt=guiding_prompt,
                demographic_focus=demographic_focus,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            detail = self._format_runtime_failure_detail(
                session_id,
                exc,
                action="Screen 1 knowledge extraction",
            )
            raise HTTPException(status_code=502, detail=detail) from exc

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

        runtime_settings = self._runtime_settings_for_session(session_id)
        relevance = PersonaRelevanceService(runtime_settings)

        try:
            parsed_instructions = relevance.parse_sampling_instructions(
                request.sampling_instructions,
                knowledge_artifact=knowledge,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            detail = self._format_runtime_failure_detail(
                session_id,
                exc,
                action="Screen 2 agent sampling",
            )
            raise HTTPException(status_code=502, detail=detail) from exc
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

        artifact = relevance.build_population_artifact(
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
        runtime_settings = self._runtime_settings_for_session(session_id)
        effective_mode = mode or session.get("mode", "demo")

        population = self.store.get_population_artifact(session_id)
        if not population:
            raise HTTPException(status_code=404, detail=f"Population artifact not found: {session_id}")

        sampled_rows = list(population.get("sampled_personas", []))
        personas = [dict(row["persona"], agent_id=row.get("agent_id")) for row in sampled_rows]
        if not sampled_rows:
            raise HTTPException(status_code=422, detail="No sampled personas available for simulation start")

        events_dir = Path(runtime_settings.oasis_db_dir).parent / "events"
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
        initial_estimate = self._estimate_initial_runtime(
            agent_count=len(sampled_rows),
            rounds=rounds,
            provider=runtime_settings.llm_provider,
        )
        self.store.save_simulation_state_snapshot(
            session_id,
            {
                "session_id": session_id,
                "status": "running",
                "platform": runtime_settings.simulation_platform,
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

    def _is_demo_session(self, session_id: str) -> bool:
        """Check if this is a demo session."""
        session = self.store.get_console_session(session_id)
        return session is not None and session.get("mode") == "demo"

    def generate_report(self, session_id: str) -> dict[str, Any]:
        # Check if demo mode
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            return self.demo.get_report(session_id) or self._empty_report_state(session_id, status="completed")
        
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
        # Check if demo mode
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            return self.demo.get_report(session_id) or self._empty_report_state(session_id, status="completed")
        
        return self.store.get_report_state(session_id) or self._empty_report_state(session_id, status="idle")

    def get_report_opinions(self, session_id: str) -> dict[str, Any]:
        # Check if demo mode
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            return self.demo.get_report_opinions(session_id)

        runtime_settings = self._runtime_settings_for_session(session_id)
        report_service = ReportService(runtime_settings)
        report = report_service.build_report(session_id)
        feed = self.store.get_interactions(session_id)[-50:]
        return {
            "session_id": session_id,
            "feed": feed,
            "influential_agents": report.get("influential_agents", []),
        }

    def get_report_friction_map(self, session_id: str) -> dict[str, Any]:
        # Check if demo mode
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            return self.demo.get_friction_map(session_id)

        runtime_settings = self._runtime_settings_for_session(session_id)
        report_service = ReportService(runtime_settings)
        report = report_service.build_report(session_id)
        friction = report.get("friction_by_planning_area", [])
        top = friction[0]["planning_area"] if friction else "N/A"
        return {
            "session_id": session_id,
            "map_metrics": friction,
            "anomaly_summary": f"Highest observed friction cluster: {top}",
        }

    def get_interaction_hub(self, session_id: str, agent_id: str | None = None) -> dict[str, Any]:
        # Check if demo mode
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            return self.demo.get_interaction_hub(session_id, agent_id)

        runtime_settings = self._runtime_settings_for_session(session_id)
        report_service = ReportService(runtime_settings)
        report = report_service.build_report(session_id)
        influential = report.get("influential_agents", [])
        selected_agent_id = agent_id or (str(influential[0].get("agent_id")) if influential else None)
        selected = self._build_selected_agent_state(
            session_id,
            selected_agent_id,
            influential,
            runtime_settings=runtime_settings,
        )
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
        # Check if demo mode
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            model_payload = self._session_model_payload(session_id)
            payload = {
                **self.demo.generate_demo_report_chat(session_id, message),
                "session_id": session_id,
                "model_provider": model_payload["model_provider"],
                "model_name": model_payload["model_name"],
                "gemini_model": model_payload["model_name"],
            }
            self.store.append_interaction_transcript(session_id, "report_agent", "user", message)
            self.store.append_interaction_transcript(session_id, "report_agent", "assistant", payload["response"])
            return payload

        runtime_settings = self._runtime_settings_for_session(session_id)
        report_service = ReportService(runtime_settings)
        payload = report_service.report_chat_payload(session_id, message)
        self.store.append_interaction_transcript(session_id, "report_agent", "user", message)
        self.store.append_interaction_transcript(session_id, "report_agent", "assistant", payload["response"])
        return payload

    def agent_chat(self, session_id: str, agent_id: str, message: str) -> dict[str, Any]:
        # Check if demo mode
        if self._is_demo_session(session_id) and self.demo.is_demo_available():
            model_payload = self._session_model_payload(session_id)
            payload = {
                **self.demo.generate_demo_agent_chat(session_id, agent_id, message),
                "session_id": session_id,
                "agent_id": agent_id,
                "memory_used": True,
                "model_provider": model_payload["model_provider"],
                "model_name": model_payload["model_name"],
                "gemini_model": model_payload["model_name"],
            }
            self.store.append_interaction_transcript(session_id, "agent_chat", "user", message, agent_id=agent_id)
            self.store.append_interaction_transcript(session_id, "agent_chat", "assistant", payload["response"], agent_id=agent_id)
            return payload

        runtime_settings = self._runtime_settings_for_session(session_id)
        memory_service = MemoryService(runtime_settings)
        payload = memory_service.agent_chat_realtime(session_id, agent_id, message)
        self.store.append_interaction_transcript(session_id, "agent_chat", "user", message, agent_id=agent_id)
        self.store.append_interaction_transcript(session_id, "agent_chat", "assistant", payload["response"], agent_id=agent_id)
        return payload

    def _build_selected_agent_state(
        self,
        session_id: str,
        agent_id: str | None,
        influential_agents: list[dict[str, Any]],
        *,
        runtime_settings: Settings,
    ) -> dict[str, Any] | None:
        if not agent_id:
            return None

        by_agent_id = {str(agent["agent_id"]): agent for agent in self.store.get_agents(session_id)}
        influential = next((agent for agent in influential_agents if str(agent.get("agent_id")) == agent_id), None)
        stored = by_agent_id.get(agent_id)
        memory_service = MemoryService(runtime_settings)
        recent_memory = memory_service.get_agent_memory(session_id, agent_id)[-8:]
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
            runtime_settings = self._runtime_settings_for_session(session_id)
            simulation_service = SimulationService(runtime_settings)
            knowledge = self.store.get_knowledge_artifact(session_id) or {}
            context_bundles = simulation_service.build_context_bundles(
                simulation_id=session_id,
                policy_summary=policy_summary,
                knowledge_artifact=knowledge,
                sampled_personas=sampled_rows,
            )
            checkpoint_estimate = self._estimate_checkpoint_runtime(
                agent_count=len(sampled_rows),
                provider=runtime_settings.llm_provider,
            )
            round_estimate = self._estimate_round_runtime(
                agent_count=len(sampled_rows),
                provider=runtime_settings.llm_provider,
            )
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
            baseline = simulation_service.run_opinion_checkpoint(
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
                        "estimated_total_seconds": baseline_elapsed + (rounds * round_estimate) + checkpoint_estimate,
                        "estimated_remaining_seconds": (rounds * round_estimate) + checkpoint_estimate,
                        "counters": {"posts": 0, "comments": 0, "reactions": 0, "active_authors": 0},
                        "discussion_momentum": {"approval_delta": 0.0, "dominant_stance": "mixed"},
                        "top_threads": [],
                        "metrics": {"checkpoint": "baseline"},
                    },
                ],
            )
            enriched_personas = self._enrich_personas_for_simulation(personas, sampled_rows, context_bundles)

            def _ingest_progress(path: Path, elapsed: int) -> None:
                del elapsed
                self.streams.ingest_events_incremental(session_id, path)

            simulation_result = simulation_service.run_with_personas(
                simulation_id=session_id,
                policy_summary=policy_summary,
                rounds=rounds,
                personas=enriched_personas,
                events_path=events_path,
                force_live=(mode == "live"),
                on_progress=_ingest_progress,
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
            final = simulation_service.run_opinion_checkpoint(
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
            runtime_settings = self._runtime_settings_for_session(session_id)
            report_service = ReportService(runtime_settings)
            payload = report_service.generate_structured_report(session_id)
            self.store.save_report_state(session_id, payload)
        except Exception as exc:  # noqa: BLE001
            failed = self._empty_report_state(session_id, status="failed")
            failed["error"] = str(exc)
            self.store.save_report_state(session_id, failed)

    def _merge_population_filters(self, request: Any, parsed_instructions: dict[str, Any]) -> dict[str, Any]:
        hard_filters = parsed_instructions.get("hard_filters", {})

        min_age = request.min_age
        max_age = request.max_age

        hard_min_age = self._parse_age_filter_value(hard_filters.get("min_age", []))
        hard_max_age = self._parse_age_filter_value(hard_filters.get("max_age", []))
        if hard_min_age is not None:
            min_age = hard_min_age if min_age is None else max(min_age, hard_min_age)
        if hard_max_age is not None:
            max_age = hard_max_age if max_age is None else min(max_age, hard_max_age)

        requested_age_cohorts = hard_filters.get("age_cohort", [])
        if requested_age_cohorts:
            age_bounds = [self._age_bounds_for_cohort(cohort) for cohort in requested_age_cohorts]
            age_bounds = [bounds for bounds in age_bounds if bounds is not None]
            if age_bounds:
                derived_min = min(bounds[0] for bounds in age_bounds)
                derived_max = max(bounds[1] for bounds in age_bounds)
                min_age = derived_min if min_age is None else max(min_age, derived_min)
                max_age = derived_max if max_age is None else min(max_age, derived_max)

        if min_age is not None and max_age is not None and min_age > max_age:
            raise HTTPException(status_code=422, detail="Sampling constraints are contradictory: min_age exceeds max_age.")

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
        range_match = re.match(r"^(\d{1,3})_(\d{1,3})$", normalized)
        if range_match:
            lower = max(0, min(120, int(range_match.group(1))))
            upper = max(0, min(120, int(range_match.group(2))))
            return (min(lower, upper), max(lower, upper))
        plus_match = re.match(r"^(\d{1,3})_plus$", normalized)
        if plus_match:
            lower = max(0, min(120, int(plus_match.group(1))))
            return (lower, 120)
        if normalized == "youth":
            return (18, 24)
        if normalized == "adult":
            return (25, 59)
        if normalized == "senior":
            return (60, 100)
        return None

    def _parse_age_filter_value(self, values: Any) -> int | None:
        candidates = values if isinstance(values, list) else [values]
        for value in candidates:
            match = re.search(r"\d{1,3}", str(value))
            if not match:
                continue
            return max(0, min(120, int(match.group(0))))
        return None

    def _estimate_initial_runtime(self, *, agent_count: int, rounds: int, provider: str) -> int:
        checkpoint_seconds = self._estimate_checkpoint_runtime(agent_count=agent_count, provider=provider)
        round_seconds = self._estimate_round_runtime(agent_count=agent_count, provider=provider)
        return (checkpoint_seconds * 2) + (round_seconds * rounds)

    def _estimate_checkpoint_runtime(self, *, agent_count: int, provider: str) -> int:
        normalized_provider = str(provider or "ollama").strip().lower()
        if normalized_provider == "ollama":
            return max(40, int(agent_count * 3.6))
        return max(8, int(agent_count * 0.22))

    def _estimate_round_runtime(self, *, agent_count: int, provider: str) -> int:
        normalized_provider = str(provider or "ollama").strip().lower()
        if normalized_provider == "ollama":
            return max(45, int(agent_count * 6.8) + 20)
        return max(10, int(agent_count * 0.06) + 6)

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
