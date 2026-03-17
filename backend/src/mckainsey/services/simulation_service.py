from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from mckainsey.config import Settings
from mckainsey.models.phase_a import PersonaFilterRequest
from mckainsey.models.phase_b import SimulationRunRequest
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.persona_sampler import PersonaSampler
from mckainsey.services.storage import SimulationStore


@dataclass
class SimulationService:
    settings: Settings

    def __post_init__(self) -> None:
        self.store = SimulationStore(self.settings.simulation_db_path)
        self.sampler = PersonaSampler(self.settings.nemotron_dataset, self.settings.nemotron_split)
        self.llm = GeminiChatClient(self.settings)

    def run(self, req: SimulationRunRequest) -> dict[str, Any]:
        sample_req = PersonaFilterRequest(
            min_age=req.min_age,
            max_age=req.max_age,
            planning_areas=req.planning_areas,
            income_brackets=req.income_brackets,
            limit=req.agent_count,
            mode="stream",
        )
        personas = self.sampler.sample(sample_req)
        if not personas:
            raise ValueError("No personas matched provided filters.")

        agents = self._build_agents(personas)
        interactions: list[dict[str, Any]] = []

        for round_no in range(1, req.rounds + 1):
            round_delta = self._run_round(req.policy_summary, agents, round_no, interactions)
            for agent in agents:
                agent["opinion_post"] = max(1.0, min(10.0, agent["opinion_post"] + round_delta * 0.05))

        self.store.upsert_simulation(req.simulation_id, req.policy_summary, req.rounds, len(agents))
        self.store.replace_agents(req.simulation_id, agents)
        self.store.replace_interactions(req.simulation_id, interactions)

        pre = [a["opinion_pre"] for a in agents]
        post = [a["opinion_post"] for a in agents]
        return {
            "simulation_id": req.simulation_id,
            "platform": self.settings.simulation_platform,
            "agent_count": len(agents),
            "rounds": req.rounds,
            "stage3a_approval_rate": _approval_rate(pre),
            "stage3b_approval_rate": _approval_rate(post),
            "net_opinion_shift": (sum(post) / len(post)) - (sum(pre) / len(pre)),
            "sqlite_path": self.settings.simulation_db_path,
        }

    def snapshot(self, simulation_id: str) -> dict[str, Any]:
        simulation = self.store.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation not found: {simulation_id}")

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        stage3a = [a["opinion_pre"] for a in agents]
        stage3b = [a["opinion_post"] for a in agents]

        post_interactions = [i for i in interactions if i["action_type"] == "create_post"]
        top_posts = sorted(post_interactions, key=lambda x: abs(x.get("delta", 0)), reverse=True)[:10]

        return {
            "simulation_id": simulation_id,
            "stats": {
                "agent_count": len(agents),
                "rounds": simulation["rounds"],
                "interactions": len(interactions),
                "approval_pre": _approval_rate(stage3a),
                "approval_post": _approval_rate(stage3b),
            },
            "stage3a_scores": stage3a,
            "stage3b_scores": stage3b,
            "top_posts": top_posts,
        }

    def _build_agents(self, personas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        agents: list[dict[str, Any]] = []
        for idx, persona in enumerate(personas):
            base = _persona_seed_opinion(persona)
            agents.append(
                {
                    "agent_id": f"agent-{idx+1:04d}",
                    "persona": persona,
                    "opinion_pre": base,
                    "opinion_post": base,
                }
            )
        return agents

    def _run_round(
        self,
        policy_summary: str,
        agents: list[dict[str, Any]],
        round_no: int,
        interactions: list[dict[str, Any]],
    ) -> float:
        deltas: list[float] = []
        avg = sum(a["opinion_post"] for a in agents) / len(agents)

        for agent in agents:
            jitter = random.uniform(-0.45, 0.45)
            social_pull = (avg - agent["opinion_post"]) * 0.18
            delta = jitter + social_pull
            agent["opinion_post"] = max(1.0, min(10.0, agent["opinion_post"] + delta))
            deltas.append(delta)

            sentiment = "support" if agent["opinion_post"] >= 7 else "oppose" if agent["opinion_post"] <= 4 else "neutral"
            content = f"Round {round_no} {sentiment} stance on policy: {policy_summary[:120]}"

            interactions.append(
                {
                    "round_no": round_no,
                    "actor_agent_id": agent["agent_id"],
                    "target_agent_id": None,
                    "action_type": "create_post",
                    "content": content,
                    "delta": delta,
                }
            )

            target = random.choice(agents)["agent_id"]
            if target != agent["agent_id"]:
                interactions.append(
                    {
                        "round_no": round_no,
                        "actor_agent_id": agent["agent_id"],
                        "target_agent_id": target,
                        "action_type": "comment",
                        "content": f"Responding to {target} in round {round_no}",
                        "delta": delta * 0.4,
                    }
                )

        return sum(deltas) / len(deltas)


def _persona_seed_opinion(persona: dict[str, Any]) -> float:
    # Demographic-prior heuristic for Stage 3a baseline before social influence.
    base = 5.5
    age = persona.get("age")
    if isinstance(age, (int, float)):
        if age >= 60:
            base -= 0.8
        elif age <= 30:
            base += 0.4

    income = str(persona.get("income_bracket", "")).lower()
    if "$1,000" in income or "$2,000" in income or "$3,000" in income:
        base -= 0.5
    if "$10,000" in income or "$12,000" in income:
        base += 0.6

    return max(1.0, min(10.0, base + random.uniform(-1.0, 1.0)))


def _approval_rate(scores: list[float]) -> float:
    if not scores:
        return 0.0
    approved = [s for s in scores if s >= 7.0]
    return round(len(approved) / len(scores), 4)
