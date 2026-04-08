from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import os
from typing import Any

from zep_cloud import EpisodeData, Zep

from mckainsey.config import Settings
from mckainsey.services.graphiti_service import GraphitiService
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.storage import SimulationStore


class MemoryService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        api_key = settings.resolved_zep_key
        self.client = Zep(api_key=api_key) if api_key else None
        self._memory_backend_preference = str(os.getenv("MEMORY_BACKEND", "graphiti")).strip().lower()

    def sync_simulation(self, simulation_id: str) -> dict[str, Any]:
        interactions = self.store.get_interactions(simulation_id)
        if not interactions:
            return {
                "simulation_id": simulation_id,
                "synced_events": 0,
                "zep_enabled": self.client is not None,
                "sync_error": None,
            }

        sync_state = self.store.get_memory_sync_state(simulation_id) or {}
        last_interaction_id = int(sync_state.get("last_interaction_id", 0) or 0)
        previously_synced = int(sync_state.get("synced_events", 0) or 0)
        unsynced = [interaction for interaction in interactions if int(interaction.get("id", 0) or 0) > last_interaction_id]
        zep_enabled = self.client is not None
        sync_error: str | None = None
        if not self.client:
            return {
                "simulation_id": simulation_id,
                "synced_events": len(interactions),
                "zep_enabled": False,
                "sync_error": "Zep client is not configured.",
            }
        if not unsynced:
            return {
                "simulation_id": simulation_id,
                "synced_events": 0,
                "zep_enabled": True,
                "sync_error": None,
            }

        try:
            self.client.user.get(simulation_id)
        except Exception:  # noqa: BLE001
            try:
                self.client.user.add(
                    user_id=simulation_id,
                    metadata={"source": "mckainsey-simulation"},
                )
            except Exception as exc:  # noqa: BLE001
                zep_enabled = False
                sync_error = f"Unable to create Zep user graph: {exc}"

        episodes = [
            EpisodeData(
                data=(
                    f"simulation={simulation_id} round={interaction['round_no']} "
                    f"actor={interaction['actor_agent_id']} target={interaction.get('target_agent_id') or 'none'} "
                    f"action={interaction['action_type']} content={interaction.get('content', '')} "
                    f"delta={interaction.get('delta', 0)}"
                ),
                type="text",
                source_description="McKAInsey simulation interaction",
            )
            for interaction in unsynced
        ]
        if zep_enabled:
            try:
                for episode in episodes:
                    self.client.graph.with_raw_response.add_batch(
                        user_id=simulation_id,
                        episodes=[episode],
                    )
            except Exception as exc:  # noqa: BLE001
                zep_enabled = False
                sync_error = str(exc)
            else:
                self.store.save_memory_sync_state(
                    simulation_id,
                    last_interaction_id=max(int(interaction.get("id", 0) or 0) for interaction in unsynced),
                    synced_events=previously_synced + len(unsynced),
                )

        return {
            "simulation_id": simulation_id,
            "synced_events": len(unsynced),
            "zep_enabled": zep_enabled,
            "sync_error": sync_error,
        }

    def get_agent_memory(self, simulation_id: str, agent_id: str) -> list[dict[str, Any]]:
        interactions = self.store.get_interactions(simulation_id)
        filtered = [
            interaction
            for interaction in interactions
            if interaction["actor_agent_id"] == agent_id or interaction.get("target_agent_id") == agent_id
        ]
        return filtered[-50:]

    def search_simulation_context(
        self,
        simulation_id: str,
        query: str,
        limit: int = 6,
        *,
        live_mode: bool = False,
    ) -> dict[str, Any]:
        normalized_limit = max(1, int(limit))

        graphiti = self._search_graphiti_context(
            simulation_id,
            query,
            normalized_limit,
            live_mode=live_mode,
        )
        if graphiti is not None:
            return graphiti

        if live_mode:
            raise RuntimeError("Live memory search requires Graphiti backend, but Graphiti is unavailable.")

        if self._memory_backend_preference == "zep":
            zep_context = self._search_zep_context(simulation_id, query, normalized_limit)
            if zep_context is not None:
                return zep_context

        # Non-live compatibility path for demos and local development only.
        return self._search_local_context(simulation_id, query, normalized_limit)

    def search_agent_context(
        self,
        simulation_id: str,
        agent_id: str,
        query: str,
        limit: int = 8,
        *,
        live_mode: bool = False,
    ) -> dict[str, Any]:
        attempts = [
            f"actor={agent_id} target={agent_id} {query}".strip(),
            f"{agent_id} {query}".strip(),
            agent_id,
            query,
        ]
        seen: set[str] = set()
        for candidate_query in attempts:
            normalized = " ".join(candidate_query.split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result = self.search_simulation_context(
                simulation_id,
                normalized,
                limit=limit,
                live_mode=live_mode,
            )
            if result["episodes"]:
                return result
        if live_mode:
            raise RuntimeError("Live memory search returned no Graphiti context for the requested agent.")
        return {
            "episodes": [],
            "synced_events": 0,
            "zep_context_used": False,
            "graphiti_context_used": False,
            "memory_backend": "local",
        }

    def agent_chat(self, simulation_id: str, agent_id: str, message: str) -> dict[str, Any]:
        memories = self.get_agent_memory(simulation_id, agent_id)
        memory_excerpt = "\n".join(
            f"- r{item['round_no']} {item['action_type']}: {item.get('content', '')}"
            for item in memories[-10:]
        )
        prompt = (
            f"You are {agent_id} in simulation {simulation_id}.\n"
            f"Recent memory:\n{memory_excerpt}\n\n"
            f"User question: {message}\n"
            "Respond in-character in 3-5 sentences."
        )
        response = self.llm.complete(prompt, system_prompt="You are a simulated Singapore persona agent.")
        return {
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "response": response,
            "memory_used": bool(memories),
        }

    def agent_chat_realtime(
        self,
        simulation_id: str,
        agent_id: str,
        message: str,
        *,
        live_mode: bool = False,
    ) -> dict[str, Any]:
        memories = [] if live_mode else self.get_agent_memory(simulation_id, agent_id)
        memory_context = self.search_agent_context(
            simulation_id,
            agent_id,
            message,
            limit=8,
            live_mode=live_mode,
        )
        if live_mode and memory_context.get("memory_backend") != "graphiti":
            raise RuntimeError("Live agent chat requires Graphiti-backed memory context.")
        if live_mode and not memory_context["episodes"]:
            raise RuntimeError("Live agent chat requires Graphiti memory results, but none were found.")

        agents = {agent["agent_id"]: agent for agent in self.store.get_agents(simulation_id)}
        agent = agents.get(agent_id)
        if not agent:
            raise RuntimeError(f"Agent not found in simulation: {agent_id}")

        context_excerpt = "\n".join(
            f"- {item['content']}"
            for item in memory_context["episodes"][:6]
        )
        if live_mode:
            prompt = (
                f"You are persona agent {agent_id} from McKAInsey simulation {simulation_id}.\n"
                f"Persona profile: {agent['persona']}\n\n"
                f"Relevant Graphiti memory search results:\n{context_excerpt or '- none'}\n\n"
                f"User question: {message}\n"
                "Answer in-character in 3-5 sentences, grounded only in the Graphiti memories above."
            )
        else:
            memory_excerpt = "\n".join(
                f"- round {item['round_no']} {item['action_type']}: {item.get('content', '')}"
                for item in memories[-8:]
            )
            prompt = (
                f"You are persona agent {agent_id} from McKAInsey simulation {simulation_id}.\n"
                f"Persona profile: {agent['persona']}\n\n"
                f"Recent local memory:\n{memory_excerpt or '- none'}\n\n"
                f"Relevant memory search results ({memory_context.get('memory_backend', 'local')}):\n{context_excerpt or '- none'}\n\n"
                f"User question: {message}\n"
                "Answer in-character in 3-5 sentences, grounded only in the memories above."
            )

        response: str
        if self.llm.is_enabled():
            response = self.llm.complete_required(
                prompt,
                system_prompt="You are a simulated Singapore persona agent. Stay grounded in supplied memory.",
            )
        elif live_mode:
            raise RuntimeError("Live agent chat requires a configured model provider.")
        else:
            response = self._local_fallback_agent_response(agent_id, agent, message, memories, memory_context["episodes"])
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "response": response,
            "memory_used": bool(memory_context["episodes"] if live_mode else (memories or memory_context["episodes"])),
            "model_provider": self.llm.provider,
            "model_name": self.llm.model_name,
            "gemini_model": self.llm.model_name,
            "zep_context_used": bool(memory_context.get("zep_context_used", False)),
            "graphiti_context_used": bool(memory_context.get("graphiti_context_used", False)),
            "memory_backend": memory_context.get("memory_backend", "local"),
        }

    def _require_realtime_clients(self) -> None:
        if self.client is None:
            raise RuntimeError("Zep Cloud is required for Stage 5 chat but no ZEP_API_KEY/ZEP_CLOUD is configured.")
        if not self.llm.is_enabled():
            raise RuntimeError("A valid model provider API key is required for Stage 5 chat.")

    def _search_graphiti_context(
        self,
        simulation_id: str,
        query: str,
        limit: int,
        *,
        live_mode: bool = False,
    ) -> dict[str, Any] | None:
        if not GraphitiService.is_available():
            if live_mode:
                raise RuntimeError("Live memory search requires graphiti_core, but it is not installed.")
            return None

        session = self.store.get_console_session(simulation_id) or {}
        provider = session.get("model_provider") or self._settings.llm_provider
        session_config = {
            "session_id": simulation_id,
            "provider": provider,
            "api_key": session.get("api_key") or self._settings.resolved_key_for_provider(provider),
            "model": session.get("model_name") or self._settings.default_model_for_provider(provider),
            "embed_model": session.get("embed_model_name") or self._settings.default_embed_model_for_provider(provider),
            "base_url": session.get("base_url") or self._settings.default_base_url_for_provider(provider),
        }
        service = GraphitiService(session_config)

        async def _run() -> tuple[list[dict[str, Any]], int]:
            await service.initialize()
            try:
                synced_events = await self._sync_graphiti_interactions(service, simulation_id)
                results = await service.search_agent_context("global", query, limit=limit)
                return results, synced_events
            finally:
                await service.cleanup()

        try:
            results, synced_events = asyncio.run(_run())
        except Exception as exc:  # noqa: BLE001
            if live_mode:
                raise RuntimeError("Live memory search failed while querying Graphiti.") from exc
            return None

        episodes = [
            {
                "content": str(item.get("content", "")),
                "score": float(item.get("confidence", 0.0) or 0.0),
                "created_at": item.get("timestamp"),
                "uuid": None,
            }
            for item in results
            if str(item.get("content", "")).strip()
        ]
        return {
            "episodes": episodes[:limit],
            "synced_events": synced_events,
            "zep_context_used": False,
            "graphiti_context_used": bool(episodes),
            "memory_backend": "graphiti",
        }

    async def _sync_graphiti_interactions(self, service: GraphitiService, simulation_id: str) -> int:
        interactions = self.store.get_interactions(simulation_id)
        if not interactions:
            return 0

        sync_state = self.store.get_memory_sync_state(simulation_id) or {}
        last_interaction_id = int(sync_state.get("last_interaction_id", 0) or 0)
        previously_synced = int(sync_state.get("synced_events", 0) or 0)
        unsynced = [interaction for interaction in interactions if int(interaction.get("id", 0) or 0) > last_interaction_id]
        if not unsynced:
            return 0

        for interaction in unsynced:
            await service.add_agent_memory(
                agent_id=str(interaction.get("actor_agent_id") or "unknown"),
                content=self._format_graphiti_episode(simulation_id, interaction),
                round_no=int(interaction.get("round_no", 0) or 0),
                timestamp=self._normalize_reference_time(interaction.get("created_at")),
            )

        self.store.save_memory_sync_state(
            simulation_id,
            last_interaction_id=max(int(interaction.get("id", 0) or 0) for interaction in unsynced),
            synced_events=previously_synced + len(unsynced),
        )
        return len(unsynced)

    def _format_graphiti_episode(self, simulation_id: str, interaction: dict[str, Any]) -> str:
        return (
            f"simulation={simulation_id} interaction_id={interaction.get('id', '')} "
            f"round={interaction.get('round_no', 0)} "
            f"actor={interaction.get('actor_agent_id', '')} "
            f"target={interaction.get('target_agent_id') or 'none'} "
            f"action={interaction.get('action_type', '')} "
            f"content={interaction.get('content', '')} "
            f"delta={interaction.get('delta', 0)}"
        )

    def _normalize_reference_time(self, created_at: Any) -> str:
        if isinstance(created_at, datetime):
            dt = created_at
        else:
            raw = str(created_at or "").strip()
            dt = None
            if raw:
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    dt = None
            if dt is None:
                dt = datetime.now(UTC)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()

    def _search_zep_context(self, simulation_id: str, query: str, limit: int) -> dict[str, Any] | None:
        if self.client is None:
            return None

        sync_result = self.sync_simulation(simulation_id)
        if not sync_result.get("zep_enabled"):
            return None
        assert self.client is not None

        try:
            results = self.client.graph.search(
                user_id=simulation_id,
                query=query,
                limit=limit,
                scope="episodes",
                reranker="rrf",
            )
        except Exception:  # noqa: BLE001
            return None

        episodes = [
            {
                "content": episode.content,
                "score": float(episode.score or 0),
                "created_at": episode.created_at,
                "uuid": episode.uuid_,
            }
            for episode in (results.episodes or [])
        ]
        return {
            "episodes": episodes,
            "synced_events": sync_result.get("synced_events", 0),
            "zep_context_used": bool(episodes),
            "graphiti_context_used": False,
            "memory_backend": "zep",
        }

    def _search_local_context(self, simulation_id: str, query: str, limit: int) -> dict[str, Any]:
        query_terms = {term for term in str(query).lower().split() if term}
        interactions = self.store.get_interactions(simulation_id)
        ranked: list[tuple[int, dict[str, Any]]] = []
        for interaction in interactions:
            content = str(interaction.get("content", "")).strip()
            if not content:
                continue
            lowered = content.lower()
            score = sum(1 for term in query_terms if term in lowered)
            if score == 0 and query_terms:
                continue
            ranked.append((score, interaction))

        ranked.sort(key=lambda item: (item[0], int(item[1].get("id", 0) or 0)), reverse=True)
        if not ranked:
            ranked = [(0, item) for item in interactions if str(item.get("content", "")).strip()][-limit:]

        episodes = [
            {
                "content": str(item.get("content", "")),
                "score": float(score),
                "created_at": item.get("created_at"),
                "uuid": str(item.get("id") or ""),
            }
            for score, item in ranked[:limit]
        ]
        return {
            "episodes": episodes,
            "synced_events": 0,
            "zep_context_used": False,
            "graphiti_context_used": False,
            "memory_backend": "local",
        }

    def _local_fallback_agent_response(
        self,
        agent_id: str,
        agent: dict[str, Any],
        message: str,
        memories: list[dict[str, Any]],
        context_episodes: list[dict[str, Any]],
    ) -> str:
        latest_memory = ""
        if memories:
            latest_memory = str(memories[-1].get("content", "")).strip()
        elif context_episodes:
            latest_memory = str(context_episodes[0].get("content", "")).strip()

        planning_area = str(agent.get("persona", {}).get("planning_area", "my area"))
        if latest_memory:
            return (
                f"As {agent_id} from {planning_area}, my view reflects what I posted previously: "
                f"\"{latest_memory}\". On your question \"{message}\", that remains my main concern."
            )
        return (
            f"As {agent_id} from {planning_area}, I do not have enough stored context yet. "
            f"On \"{message}\", I would focus on affordability and neighborhood-level trade-offs."
        )
