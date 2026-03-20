from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import json
from typing import Any

from mckainsey.config import Settings
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.memory_service import MemoryService
from mckainsey.services.storage import SimulationStore


class ReportService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        self.memory = MemoryService(settings)

    def generate_structured_report(self, simulation_id: str) -> dict[str, Any]:
        existing = self.store.get_report_state(simulation_id)
        if existing and existing.get("status") == "completed":
            return existing

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        knowledge = self.store.get_knowledge_artifact(simulation_id) or {}
        population = self.store.get_population_artifact(simulation_id) or {}
        baseline = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="baseline")
        final = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="final")
        events = self.store.list_simulation_events(simulation_id)

        prompt = self._build_structured_report_prompt(
            simulation_id=simulation_id,
            knowledge=knowledge,
            population=population,
            agents=agents,
            interactions=interactions,
            baseline=baseline,
            final=final,
            events=events,
        )
        raw = self.llm.complete_required(
            prompt,
            system_prompt=(
                "You are McKAInsey ReportAgent. Return valid JSON only using the requested schema. "
                "Every claim must be grounded in provided evidence."
            ),
        )
        try:
            payload = _parse_json_object(raw)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Gemini must return valid structured report JSON.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Gemini must return valid structured report JSON.")

        return self._normalize_structured_report_payload(simulation_id, payload)

    def build_report(self, simulation_id: str) -> dict[str, Any]:
        cached = self.store.get_cached_report(simulation_id)
        if cached:
            return cached

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        pre = [float(a["opinion_pre"]) for a in agents]
        post = [float(a["opinion_post"]) for a in agents]

        by_area_pre: dict[str, list[float]] = defaultdict(list)
        by_area_post: dict[str, list[float]] = defaultdict(list)
        by_income_post: dict[str, list[float]] = defaultdict(list)
        influence: dict[str, float] = defaultdict(float)
        agent_persona: dict[str, dict[str, Any]] = {}
        for a in agents:
            area = str(a["persona"].get("planning_area", "Unknown"))
            income = str(a["persona"].get("income_bracket", "Unknown"))
            by_area_pre[area].append(float(a["opinion_pre"]))
            by_area_post[area].append(float(a["opinion_post"]))
            by_income_post[income].append(float(a["opinion_post"]))
            agent_persona[a["agent_id"]] = a["persona"]

        for i in interactions:
            if i.get("target_agent_id"):
                influence[i["actor_agent_id"]] += abs(float(i.get("delta", 0)))

        last_reason_by_agent: dict[str, str] = {}
        for i in interactions:
            text = str(i.get("content", "")).strip()
            if text:
                last_reason_by_agent[i["actor_agent_id"]] = text[:240]

        influential_agents: list[dict[str, Any]] = []
        for agent_id, score in sorted(influence.items(), key=lambda x: x[1], reverse=True)[:10]:
            persona = agent_persona.get(agent_id, {})
            influential_agents.append(
                {
                    "agent_id": agent_id,
                    "influence_score": round(score, 4),
                    "planning_area": str(persona.get("planning_area", "Unknown")),
                    "occupation": str(persona.get("occupation", "Unknown")),
                    "income_bracket": str(persona.get("income_bracket", "Unknown")),
                    "latest_argument": last_reason_by_agent.get(agent_id, "No recent argument captured."),
                }
            )

        area_metrics: list[dict[str, Any]] = []
        for area, post_scores in by_area_post.items():
            pre_scores = by_area_pre.get(area, [])
            post_mean = _mean(post_scores)
            pre_mean = _mean(pre_scores)
            approval_post = _approval(post_scores)
            mean_shift = post_mean - pre_mean
            friction = abs(mean_shift) * (1 - approval_post)
            area_metrics.append(
                {
                    "planning_area": area,
                    "avg_pre_opinion": round(pre_mean, 4),
                    "avg_post_opinion": round(post_mean, 4),
                    "approval_post": round(approval_post, 4),
                    "mean_shift": round(mean_shift, 4),
                    "friction_index": round(friction, 4),
                    "cohort_size": len(post_scores),
                }
            )

        top_dissenting = sorted(
            area_metrics,
            key=lambda x: (x["approval_post"], -x["friction_index"]),
        )[:8]

        income_metrics = [
            {
                "income_bracket": income,
                "approval_post": round(_approval(scores), 4),
                "avg_post_opinion": round(_mean(scores), 4),
                "cohort_size": len(scores),
            }
            for income, scores in by_income_post.items()
        ]

        arguments_for = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
                "strength": round(abs(float(i.get("delta", 0))), 4),
            }
            for i in interactions
            if float(i.get("delta", 0)) > 0
        ]
        arguments_for = sorted(arguments_for, key=lambda x: x["strength"], reverse=True)[:12]

        arguments_against = [
            {
                "text": i.get("content", ""),
                "agent_id": i["actor_agent_id"],
                "round_no": i["round_no"],
                "strength": round(abs(float(i.get("delta", 0))), 4),
            }
            for i in interactions
            if float(i.get("delta", 0)) < 0
        ]
        arguments_against = sorted(arguments_against, key=lambda x: x["strength"], reverse=True)[:12]

        executive_summary = self.llm.complete(
            prompt=(
                f"Generate a concise executive summary for simulation {simulation_id}. "
                f"Pre approval={_approval(pre):.2f}, post approval={_approval(post):.2f}, "
                f"net shift={_mean(post)-_mean(pre):.2f}. "
                f"Top dissent cohorts={top_dissenting[:3]}."
            ),
            system_prompt="You are ReportAgent. Return concise strategic summary.",
        )
        if executive_summary.startswith("LLM quota/availability fallback"):
            top_area = top_dissenting[0]["planning_area"] if top_dissenting else "None"
            executive_summary = (
                f"Simulation {simulation_id} summary: approval shifted from {_approval(pre):.2f} to {_approval(post):.2f} "
                f"(delta {_approval(post) - _approval(pre):.2f}). Highest observed friction cohort: {top_area}."
            )

        recommendations = self._recommend(
            simulation_id=simulation_id,
            top_dissenting=top_dissenting,
            income_metrics=income_metrics,
            arguments_for=arguments_for,
            arguments_against=arguments_against,
        )

        report = {
            "simulation_id": simulation_id,
            "executive_summary": executive_summary,
            "approval_rates": {
                "stage3a": round(_approval(pre), 4),
                "stage3b": round(_approval(post), 4),
                "delta": round(_approval(post) - _approval(pre), 4),
            },
            "top_dissenting_demographics": top_dissenting,
            "friction_by_planning_area": sorted(area_metrics, key=lambda x: x["friction_index"], reverse=True),
            "income_cohorts": sorted(income_metrics, key=lambda x: x["approval_post"]),
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
        response = self.llm.complete(prompt, system_prompt="You are McKAInsey ReportAgent.")
        if response.startswith("LLM quota/availability fallback"):
            rates = report.get("approval_rates", {})
            friction = report.get("friction_by_planning_area", [])
            top_area = friction[0]["planning_area"] if friction else "N/A"
            return (
                "Fallback report answer: "
                f"approval moved from {rates.get('stage3a', 'N/A')} to {rates.get('stage3b', 'N/A')}, "
                f"with highest friction in {top_area}. "
                "Use recommendations tab for cohort-specific mitigation actions."
            )
        return response

    def report_chat_payload(self, simulation_id: str, message: str) -> dict[str, Any]:
        report = self.build_report(simulation_id)
        zep_context = self.memory.search_simulation_context(simulation_id, message, limit=8)
        zep_excerpt = "\n".join(
            f"- {item['content']}"
            for item in zep_context["episodes"][:6]
        )
        prompt = (
            f"Report JSON:\n{report}\n\n"
            f"Relevant Zep Cloud memory search results:\n{zep_excerpt or '- none'}\n\n"
            f"User asks: {message}\n"
            "Provide a direct, data-grounded answer with concrete cohort references."
        )
        response = self.llm.complete_required(prompt, system_prompt="You are McKAInsey ReportAgent.")
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "response": response,
            "gemini_model": self.settings.gemini_model,
            "zep_context_used": zep_context["zep_context_used"],
        }

    def _recommend(
        self,
        simulation_id: str,
        top_dissenting: list[dict[str, Any]],
        income_metrics: list[dict[str, Any]],
        arguments_for: list[dict[str, Any]],
        arguments_against: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not top_dissenting:
            return [
                {
                    "title": "Maintain broad-based communication cadence",
                    "rationale": "No major friction clusters detected in planning-area analysis.",
                    "target_demographic": "All cohorts",
                    "expected_impact": "Medium",
                    "execution_plan": [
                        "Keep monthly policy updates with simple impact examples.",
                        "Run sentiment pulse checks by demographic cohorts.",
                    ],
                    "confidence": 0.62,
                }
            ]

        prompt = (
            "Generate 5 concrete policy communication/mitigation recommendations in JSON. "
            "Use ONLY this schema: "
            "[{\"title\": str, \"rationale\": str, \"target_demographic\": str, "
            "\"expected_impact\": str, \"execution_plan\": [str, str, str], \"confidence\": number}]\n"
            f"simulation_id={simulation_id}\n"
            f"top_dissenting={top_dissenting[:6]}\n"
            f"income_metrics={sorted(income_metrics, key=lambda x: x['approval_post'])[:6]}\n"
            f"arguments_for={arguments_for[:6]}\n"
            f"arguments_against={arguments_against[:6]}\n"
            "Rules: recommendations must be specific, non-generic, and tied to at least one planning area or cohort. "
            "confidence must be between 0 and 1."
        )

        if self.llm.is_enabled():
            raw = self.llm.complete(
                prompt=prompt,
                system_prompt="You are McKAInsey ReportAgent. Return valid JSON only.",
            )
            parsed = self._parse_recommendations(raw)
            if parsed:
                return parsed

        return self._algorithmic_recommendations(top_dissenting, income_metrics)

    def _parse_recommendations(self, raw: str) -> list[dict[str, Any]]:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        out: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            rationale = str(item.get("rationale", "")).strip()
            target = str(item.get("target_demographic", "")).strip()
            impact = str(item.get("expected_impact", "")).strip()
            plan = item.get("execution_plan", [])
            try:
                conf = float(item.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5

            if not title or not rationale or not target:
                continue

            plan_list = [str(x).strip() for x in plan if str(x).strip()]
            if len(plan_list) < 2:
                plan_list = [
                    "Run targeted messaging sessions with affected households.",
                    "Track sentiment changes weekly and refine intervention messaging.",
                ]

            out.append(
                {
                    "title": title,
                    "rationale": rationale,
                    "target_demographic": target,
                    "expected_impact": impact or "Medium",
                    "execution_plan": plan_list[:4],
                    "confidence": max(0.0, min(1.0, round(conf, 2))),
                }
            )

        return out[:6]

    def _algorithmic_recommendations(
        self,
        top_dissenting: list[dict[str, Any]],
        income_metrics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        low_income = sorted(income_metrics, key=lambda x: x["approval_post"])[:2]

        for item in top_dissenting[:4]:
            area = item["planning_area"]
            friction = float(item.get("friction_index", 0.0))
            target_income = low_income[0]["income_bracket"] if low_income else "Lower-income households"
            confidence = 0.55 + min(0.35, friction)
            recommendations.append(
                {
                    "title": f"Targeted affordability mitigation for {area}",
                    "rationale": (
                        f"{area} shows elevated friction ({friction:.2f}) with below-target post approval "
                        f"({item.get('approval_post', 0):.2f})."
                    ),
                    "target_demographic": f"{area} residents, especially {target_income}",
                    "expected_impact": "High" if friction >= 0.3 else "Medium",
                    "execution_plan": [
                        f"Deploy area-specific budget explainers in {area} community channels.",
                        "Add concrete household cashflow examples for affected segments.",
                        "Collect 2-week feedback pulse and adjust subsidy messaging.",
                    ],
                    "confidence": round(min(0.95, confidence), 2),
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "title": "Cross-cohort message calibration",
                    "rationale": "No sharply concentrated friction cluster was detected.",
                    "target_demographic": "Multi-cohort",
                    "expected_impact": "Medium",
                    "execution_plan": [
                        "Segment messages by age and income before public rollout.",
                        "Prioritize FAQs around transport and cost-of-living concerns.",
                    ],
                    "confidence": 0.6,
                }
            )

        return recommendations[:6]

    def _build_structured_report_prompt(
        self,
        *,
        simulation_id: str,
        knowledge: dict[str, Any],
        population: dict[str, Any],
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> str:
        influential_posts = [
            {
                "agent_id": row.get("actor_agent_id"),
                "content": row.get("content"),
                "delta": row.get("delta"),
            }
            for row in interactions
            if row.get("action_type") == "create_post"
        ][:12]
        checkpoints = {
            "baseline": baseline[:50],
            "final": final[:50],
        }
        return (
            "Generate a fixed-format policy simulation report in JSON.\n"
            "Return an object with exactly these top-level keys:\n"
            "{\"generated_at\": str, \"executive_summary\": str, "
            "\"insight_cards\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}], "
            "\"support_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"dissent_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"demographic_breakdown\": [{\"segment\": str, \"approval_rate\": number, \"dissent_rate\": number, \"sample_size\": number}], "
            "\"influential_content\": [{\"content_type\": str, \"author_agent_id\": str, \"summary\": str, \"engagement_score\": number}], "
            "\"recommendations\": [{\"title\": str, \"rationale\": str, \"priority\": \"high|medium|low\"}], "
            "\"risks\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}]}\n\n"
            f"Simulation ID: {simulation_id}\n"
            f"Knowledge summary: {knowledge.get('summary', '')}\n"
            f"Population artifact: {json.dumps(population, ensure_ascii=False)[:6000]}\n"
            f"Checkpoint records: {json.dumps(checkpoints, ensure_ascii=False)[:12000]}\n"
            f"Influential posts: {json.dumps(influential_posts, ensure_ascii=False)[:6000]}\n"
            f"Recent simulation events: {json.dumps(events[-80:], ensure_ascii=False)[:12000]}\n"
            f"Agent records: {json.dumps(agents[:80], ensure_ascii=False)[:12000]}\n"
        )

    def _normalize_structured_report_payload(self, simulation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        generated_at = str(payload.get("generated_at") or datetime.now(UTC).isoformat())
        normalized = {
            "session_id": simulation_id,
            "status": "completed",
            "generated_at": generated_at,
            "executive_summary": str(payload.get("executive_summary", "")).strip(),
            "insight_cards": _normalize_dict_list(payload.get("insight_cards"), required_keys=("title", "summary", "severity")),
            "support_themes": _normalize_dict_list(payload.get("support_themes"), required_keys=("theme", "summary", "evidence")),
            "dissent_themes": _normalize_dict_list(payload.get("dissent_themes"), required_keys=("theme", "summary", "evidence")),
            "demographic_breakdown": _normalize_dict_list(payload.get("demographic_breakdown"), required_keys=("segment", "approval_rate", "dissent_rate", "sample_size")),
            "influential_content": _normalize_dict_list(payload.get("influential_content"), required_keys=("content_type", "author_agent_id", "summary", "engagement_score")),
            "recommendations": _normalize_dict_list(payload.get("recommendations"), required_keys=("title", "rationale", "priority")),
            "risks": _normalize_dict_list(payload.get("risks"), required_keys=("title", "summary", "severity")),
        }
        if not normalized["executive_summary"]:
            raise RuntimeError("Gemini must return valid structured report JSON.")
        return normalized


def _approval(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return len([s for s in scores if s >= 7]) / len(scores)


def _mean(scores: list[float]) -> float:
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _parse_json_object(raw: str) -> Any:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    return json.loads(cleaned)


def _normalize_dict_list(value: Any, *, required_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized.append({key: item.get(key) for key in required_keys})
    return normalized
