from __future__ import annotations

import threading
import uuid
from pathlib import Path
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
            demographic_focus=demographic_focus,
        )
        artifact["session_id"] = session_id
        self.store.save_knowledge_artifact(session_id, artifact)
        self.store.upsert_console_session(session_id=session_id, mode=session.get("mode", "demo") if session else "demo", status="knowledge_ready")
        return artifact

    async def process_uploaded_knowledge(
        self,
        session_id: str,
        *,
        upload: UploadFile,
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
            demographic_focus=demographic_focus,
        )

    def preview_population(self, session_id: str, request: Any) -> dict[str, Any]:
        knowledge = self.store.get_knowledge_artifact(session_id)
        if not knowledge:
            raise HTTPException(status_code=404, detail=f"Knowledge artifact not found for session {session_id}")

        candidate_limit = max(request.agent_count * 6, 60)
        personas = self.sampler.sample(
            PersonaFilterRequest(
                min_age=request.min_age,
                max_age=request.max_age,
                planning_areas=request.planning_areas,
                income_brackets=request.income_brackets,
                limit=candidate_limit,
                mode="local",
            )
        )
        artifact = self.relevance.build_population_artifact(
            session_id,
            personas=personas,
            knowledge_artifact=knowledge,
            filters=request.model_dump(),
            agent_count=request.agent_count,
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

        personas = [row["persona"] for row in population.get("sampled_personas", [])]
        if not personas:
            raise HTTPException(status_code=422, detail="No sampled personas available for simulation start")

        events_dir = Path(self.settings.oasis_db_dir).parent / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        events_path = events_dir / f"{session_id}.ndjson"
        if events_path.exists():
            events_path.unlink()

        self.store.clear_simulation_events(session_id)
        self.store.clear_simulation_state_snapshot(session_id)
        self.store.clear_report_cache(session_id)
        self.store.clear_interaction_transcripts(session_id)
        self.store.reset_memory_sync_state(session_id)
        self.store.save_simulation_state_snapshot(
            session_id,
            {
                "session_id": session_id,
                "status": "running",
                "event_count": 0,
                "last_round": 0,
                "latest_metrics": {},
                "recent_events": [],
                "events_path": str(events_path),
            },
        )
        self.store.upsert_console_session(session_id=session_id, mode=effective_mode, status="simulation_running")

        thread = threading.Thread(
            target=self._run_simulation_background,
            args=(session_id, policy_summary, rounds, personas, events_path, effective_mode),
            daemon=True,
        )
        thread.start()
        return self.streams.get_state(session_id)

    def get_report_full(self, session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "report": self.report.build_report(session_id),
        }

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
        personas: list[dict[str, Any]],
        events_path: Path,
        mode: str,
    ) -> None:
        try:
            self.simulation.run_with_personas(
                simulation_id=session_id,
                policy_summary=policy_summary,
                rounds=rounds,
                personas=personas,
                events_path=events_path,
                force_live=(mode == "live"),
            )
            ingested = self.streams.ingest_events_file(session_id, events_path)
            state = self.streams.get_state(session_id)
            state["status"] = "completed"
            state["event_count"] = ingested
            state["events_path"] = str(events_path)
            self.store.save_simulation_state_snapshot(session_id, state)
            self.store.upsert_console_session(session_id=session_id, mode=mode, status="simulation_completed")
        except Exception as exc:  # noqa: BLE001
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
