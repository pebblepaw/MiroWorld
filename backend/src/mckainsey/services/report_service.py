from __future__ import annotations

from collections import defaultdict
from typing import Any

from mckainsey.config import Settings
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.storage import SimulationStore


class ReportService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)

    def build_report(self, simulation_id: str) -> dict[str, Any]:
        cached = self.store.get_cached_report(simulation_id)
        if cached:
            return cached

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        pre = [a["opinion_pre"] for a in agents]
        post = [a["opinion_post"] for a in agents]

        by_area: dict[str, list[float]] = defaultdict(list)
        influence: dict[str, float] = defaultdict(float)
        for a in agents:
            area = str(a["persona"].get("planning_area", "Unknown"))
            by_area[area].append(a["opinion_post"])

        for i in interactions:
            if i.get("target_agent_id"):
                influence[i["actor_agent_id"]] += abs(float(i.get("delta", 0)))

        influential_agents = [
            {
                "agent_id": agent_id,
                "influence_score": round(score, 4),
            }
            for agent_id, score in sorted(influence.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        top_dissenting = sorted(
            [
                {
                    "planning_area": area,
                    "avg_post_opinion": round(sum(scores) / len(scores), 4),
                    "cohort_size": len(scores),
                }
                for area, scores in by_area.items()
            ],
            key=lambda x: x["avg_post_opinion"],
        )[:5]

        arguments_for = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
            }
            for i in interactions
            if float(i.get("delta", 0)) > 0
        ][:10]

        arguments_against = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
            }
            for i in interactions
            if float(i.get("delta", 0)) < 0
        ][:10]

        executive_summary = self.llm.complete(
            prompt=(
                f"Generate a concise executive summary for simulation {simulation_id}. "
                f"Pre approval={_approval(pre):.2f}, post approval={_approval(post):.2f}, "
                f"net shift={_mean(post)-_mean(pre):.2f}."
            ),
            system_prompt="You are ReportAgent. Return concise strategic summary.",
        )

        recommendations = self._recommend(top_dissenting)

        report = {
            "simulation_id": simulation_id,
            "executive_summary": executive_summary,
            "approval_rates": {
                "stage3a": round(_approval(pre), 4),
                "stage3b": round(_approval(post), 4),
            },
            "top_dissenting_demographics": top_dissenting,
            "influential_agents": influential_agents,
            "key_arguments_for": arguments_for,
            "key_arguments_against": arguments_against,
            "recommendations": recommendations,
        }

        self.store.cache_report(simulation_id, report)
        return report

    def report_chat(self, simulation_id: str, message: str) -> str:
        report = self.build_report(simulation_id)
        prompt = (
            f"Report JSON:\n{report}\n\n"
            f"User asks: {message}\n"
            "Provide a direct, data-grounded answer with concrete cohort references."
        )
        return self.llm.complete(prompt, system_prompt="You are McKAInsey ReportAgent.")

    def _recommend(self, top_dissenting: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for item in top_dissenting[:3]:
            area = item["planning_area"]
            output.append(
                {
                    "title": f"Targeted mitigation for {area}",
                    "rationale": "Post-deliberation sentiment remains low in this area.",
                    "target_demographic": area,
                    "expected_impact": "Medium to high",
                }
            )
        if not output:
            output.append(
                {
                    "title": "Maintain messaging consistency",
                    "rationale": "No significant dissent clusters detected.",
                    "target_demographic": "All cohorts",
                    "expected_impact": "Medium",
                }
            )
        return output


def _approval(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return len([s for s in scores if s >= 7]) / len(scores)


def _mean(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
