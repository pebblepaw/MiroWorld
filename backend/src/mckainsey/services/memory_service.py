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
            return {"simulation_id": simulation_id, "synced_events": 0, "zep_enabled": self.client is not None}

        zep_enabled = self.client is not None
        if self.client:
            episodes = [
                EpisodeData(
                    data=f"{i['actor_agent_id']} {i['action_type']} {i.get('content', '')}",
                    type="text",
                )
                for i in interactions
            ]
            try:
                self.client.graph.add_batch(user_id=simulation_id, episodes=episodes)
            except Exception:  # noqa: BLE001
                zep_enabled = False

        return {
            "simulation_id": simulation_id,
            "synced_events": len(interactions),
            "zep_enabled": zep_enabled,
        }

    def get_agent_memory(self, simulation_id: str, agent_id: str) -> list[dict[str, Any]]:
        interactions = self.store.get_interactions(simulation_id)
        filtered = [
            i
            for i in interactions
            if i["actor_agent_id"] == agent_id or i.get("target_agent_id") == agent_id
        ]
        return filtered[-50:]

    def agent_chat(self, simulation_id: str, agent_id: str, message: str) -> dict[str, Any]:
        memories = self.get_agent_memory(simulation_id, agent_id)
        memory_excerpt = "\n".join(
            [f"- r{i['round_no']} {i['action_type']}: {i.get('content', '')}" for i in memories[-10:]]
        )

        prompt = (
            f"You are {agent_id} in simulation {simulation_id}.\n"
            f"Recent memory:\n{memory_excerpt}\n\n"
            f"User question: {message}\n"
            "Respond in-character in 3-5 sentences."
        )
        response = self.llm.complete(prompt, system_prompt="You are a simulated Singapore persona agent.")
        if response.startswith("LLM quota/availability fallback"):
            response = (
                f"As {agent_id}, my recent interactions indicate mixed reactions in my planning-area cohort. "
                "I adjusted my stance based on affordability concerns, peer comments, and perceived policy support details."
            )
        return {
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "response": response,
            "memory_used": bool(memories),
        }
