from __future__ import annotations

from typing import Any

from zep_cloud import EpisodeData, Zep

from mckainsey.config import Settings
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.storage import SimulationStore


class MemoryService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        api_key = settings.resolved_zep_key
        self.client = Zep(api_key=api_key) if api_key else None

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

    def search_simulation_context(self, simulation_id: str, query: str, limit: int = 6) -> dict[str, Any]:
        self._require_realtime_clients()
        sync_result = self.sync_simulation(simulation_id)
        if not sync_result.get("zep_enabled"):
            detail = sync_result.get("sync_error") or "Check ZEP_API_KEY/ZEP_CLOUD and connectivity."
            raise RuntimeError(f"Zep Cloud sync failed. {detail}")
        assert self.client is not None
        try:
            results = self.client.graph.search(
                user_id=simulation_id,
                query=query,
                limit=limit,
                scope="episodes",
                reranker="rrf",
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Zep Cloud search failed: {exc}") from exc
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
        }

    def search_agent_context(self, simulation_id: str, agent_id: str, query: str, limit: int = 8) -> dict[str, Any]:
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
            result = self.search_simulation_context(simulation_id, normalized, limit=limit)
            if result["episodes"]:
                return result
        return {
            "episodes": [],
            "synced_events": 0,
            "zep_context_used": False,
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

    def agent_chat_realtime(self, simulation_id: str, agent_id: str, message: str) -> dict[str, Any]:
        self._require_realtime_clients()
        memories = self.get_agent_memory(simulation_id, agent_id)
        zep_context = self.search_agent_context(simulation_id, agent_id, message, limit=8)
        agents = {agent["agent_id"]: agent for agent in self.store.get_agents(simulation_id)}
        agent = agents.get(agent_id)
        if not agent:
            raise RuntimeError(f"Agent not found in simulation: {agent_id}")

        memory_excerpt = "\n".join(
            f"- round {item['round_no']} {item['action_type']}: {item.get('content', '')}"
            for item in memories[-8:]
        )
        zep_excerpt = "\n".join(
            f"- {item['content']}"
            for item in zep_context["episodes"][:6]
        )
        prompt = (
            f"You are persona agent {agent_id} from McKAInsey simulation {simulation_id}.\n"
            f"Persona profile: {agent['persona']}\n\n"
            f"Recent local memory:\n{memory_excerpt or '- none'}\n\n"
            f"Relevant Zep Cloud memory search results:\n{zep_excerpt or '- none'}\n\n"
            f"User question: {message}\n"
            "Answer in-character in 3-5 sentences, grounded only in the memories above."
        )
        response = self.llm.complete_required(
            prompt,
            system_prompt="You are a simulated Singapore persona agent. Stay grounded in supplied memory.",
        )
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "response": response,
            "memory_used": bool(memories or zep_context["episodes"]),
            "model_provider": self.llm.provider,
            "model_name": self.llm.model_name,
            "gemini_model": self.llm.model_name,
            "zep_context_used": zep_context["zep_context_used"],
        }

    def _require_realtime_clients(self) -> None:
        if self.client is None:
            raise RuntimeError("Zep Cloud is required for Stage 5 chat but no ZEP_API_KEY/ZEP_CLOUD is configured.")
        if not self.llm.is_enabled():
            raise RuntimeError("A valid model provider API key is required for Stage 5 chat.")
