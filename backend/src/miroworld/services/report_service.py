from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
import io
import json
import re
import sqlite3
from typing import Any

from docx import Document

from miroworld.config import Settings
from miroworld.services.config_service import ConfigService
from miroworld.services.llm_client import GeminiChatClient
from miroworld.services.memory_service import MemoryService
from miroworld.services.metrics_service import compute_polarization, compute_opinion_flow, build_influence_graph
from miroworld.services.storage import SimulationStore


def _clean_report_text(value: Any) -> str:
    text = str(value or "").replace("**", "").replace("`", "").strip()
    return " ".join(text.split())


def _format_metric_value(value: float, unit: str) -> str:
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "/10":
        return f"{value:.1f}/10"
    return f"{value:.1f}"


def _extract_numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value or "").strip()
    if not text:
        return None

    ratio_match = re.search(r"(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)", text)
    if ratio_match:
        numerator = float(ratio_match.group(1))
        denominator = float(ratio_match.group(2))
        if denominator != 0:
            return numerator if denominator == 10 else (numerator / denominator) * 10

    number_match = re.search(r"-?\d+(?:\.\d+)?", text)
    if number_match:
        return float(number_match.group(0))

    return None


def _parse_yes_no(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    text = str(value or "").strip().lower()
    if not text:
        return None

    if re.match(r"^(yes|y|true|1)\b", text):
        return True
    if re.match(r"^(no|n|false|0)\b", text):
        return False
    return None


class ReportService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        self.memory = MemoryService(settings)
        self.config = ConfigService(settings)

    def generate_structured_report(self, simulation_id: str, use_case: str | None = None) -> dict[str, Any]:
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

        payload: dict[str, Any] = {}
        if self._should_request_structured_report_seed():
            prompt = self._build_structured_report_prompt(
                simulation_id=simulation_id,
                use_case=use_case,
                knowledge=knowledge,
                population=population,
                agents=agents,
                interactions=interactions,
                baseline=baseline,
                final=final,
                events=events,
            )
            try:
                raw = self.llm.complete_required(
                    prompt,
                    system_prompt=self.config.get_system_prompt_value(
                        "report_agent",
                        "prompts",
                        "structured_seed",
                        "system_prompt",
                    ),
                )
            except Exception:  # noqa: BLE001
                raw = ""
            try:
                parsed_payload = _parse_json_object(raw) if raw else {}
            except Exception:  # noqa: BLE001
                parsed_payload = {}
            if isinstance(parsed_payload, dict):
                payload = parsed_payload

        normalized = self._normalize_structured_report_payload(simulation_id, payload)
        return self._enrich_structured_report_payload(
            simulation_id,
            normalized,
            use_case=use_case,
            agents=agents,
            interactions=interactions,
            baseline=baseline,
            final=final,
            events=events,
            knowledge=knowledge,
            population=population,
        )

    def _should_request_structured_report_seed(self) -> bool:
        # Local Ollama models have been the slowest and least reliable source of
        # large JSON objects in live mode. We still build a report from the real
        # simulation artifacts, but skip the heavyweight seed request here.
        return self.llm.provider != "ollama"

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
            prompt=self.config.get_system_prompt_value(
                "report_agent",
                "prompts",
                "executive_summary",
                "user_template",
            ).format(
                simulation_id=simulation_id,
                pre_approval=f"{_approval(pre):.2f}",
                post_approval=f"{_approval(post):.2f}",
                net_shift=f"{_mean(post)-_mean(pre):.2f}",
                top_dissenting=top_dissenting[:3],
            ),
            system_prompt=self.config.get_system_prompt_value(
                "report_agent",
                "prompts",
                "executive_summary",
                "system_prompt",
            ),
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
        prompt = self.config.get_system_prompt_value(
            "report_agent",
            "prompts",
            "report_chat",
            "user_template",
        ).format(
            report_json=report,
            message=message,
        )
        return self.llm.complete_required(
            prompt,
            system_prompt=self.config.get_system_prompt_value(
                "report_agent",
                "prompts",
                "report_chat",
                "system_prompt",
            ),
        )

    def report_chat_payload(self, simulation_id: str, message: str) -> dict[str, Any]:
        report = self.build_report(simulation_id)
        memory_context = self.memory.search_simulation_context(simulation_id, message, limit=8)
        knowledge = self.store.get_knowledge_artifact(simulation_id) or {}
        memory_excerpt = "\n".join(f"- {item['content']}" for item in memory_context["episodes"][:6])
        checkpoint_excerpt = self.memory.format_checkpoint_records(memory_context["checkpoint_records"], limit=6)
        knowledge_excerpt = "\n".join(self._knowledge_context_lines(knowledge))
        prompt = self.config.get_system_prompt_value(
            "report_agent",
            "prompts",
            "report_chat",
            "user_template_with_memory",
        ).format(
            report_json=report,
            knowledge_excerpt=knowledge_excerpt or "- none",
            memory_excerpt=memory_excerpt or "- none",
            checkpoint_excerpt=checkpoint_excerpt or "- none",
            message=message,
        )
        response = self.llm.complete_required(
            prompt,
            system_prompt=self.config.get_system_prompt_value(
                "report_agent",
                "prompts",
                "report_chat",
                "system_prompt",
            ),
        )
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "response": response,
            "model_provider": self.llm.provider,
            "model_name": self.llm.model_name,
            "gemini_model": self.llm.model_name,
            "zep_context_used": False,
            "graphiti_context_used": False,
            "memory_backend": memory_context.get("memory_backend", "sqlite"),
        }

    def build_v2_report(self, simulation_id: str, use_case: str | None = None) -> dict[str, Any]:
        from miroworld.services.metrics_service import MetricsService

        agents = self.store.get_agents(simulation_id)
        interactions = self.store.get_interactions(simulation_id)
        if not agents:
            raise ValueError(f"Simulation not found: {simulation_id}")

        config_service = ConfigService(self.settings)
        metrics_service = MetricsService(config_service)

        # Resolve analysis questions and metadata
        analysis_questions = self._resolve_analysis_questions(simulation_id=simulation_id, use_case=use_case)
        insight_block_configs = self._resolve_insight_blocks(use_case)
        preset_section_configs = self._resolve_preset_sections(use_case)

        simulation = self.store.get_simulation(simulation_id) or {}
        stored_round_count = int(simulation.get("rounds", 0) or 0)
        interaction_round_count = max((int(item.get("round_no", 0) or 0) for item in interactions), default=0)
        round_count = stored_round_count or interaction_round_count
        evidence_pool = self._extract_evidence(interactions, agents)

        # ── Metric deltas for quantitative questions ──
        baseline_records = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="baseline")
        final_records = self.store.list_checkpoint_records(simulation_id, checkpoint_kind="final")
        metric_deltas: list[dict[str, Any]] = []
        for q in analysis_questions:
            if q.get("type") == "open-ended":
                continue
            name = q.get("metric_name", "")
            if not name:
                continue
            # Compute R1 and final values
            r1_agents = self._agents_from_checkpoint(baseline_records) or agents
            final_agents = self._agents_from_checkpoint(final_records) or agents
            r1_val = self._compute_metric_value(q, r1_agents)
            final_val = self._compute_metric_value(q, final_agents)
            metric_unit = "%" if q.get("type") == "yes-no" or "threshold" in q or str(q.get("metric_unit", "")).strip() == "%" else str(q.get("metric_unit", "/10") or "/10")
            initial_display = _format_metric_value(r1_val, metric_unit)
            final_display = _format_metric_value(final_val, metric_unit)
            metric_deltas.append({
                "metric_name": name,
                "metric_label": q.get("metric_label", name),
                "metric_unit": metric_unit,
                "initial_value": r1_val,
                "final_value": final_val,
                "delta": round(final_val - r1_val, 2),
                "direction": "up" if final_val > r1_val else ("down" if final_val < r1_val else "flat"),
                "report_title": q.get("report_title", name),
                "initial_display": initial_display,
                "final_display": final_display,
                "delta_display": f"{initial_display} -> {final_display}",
            })

        # ── Build report sections from analysis questions ──
        sections: list[dict[str, Any]] = []
        for q in analysis_questions:
            question_text = q.get("question", "")
            q_type = q.get("type", "scale")
            answer = self._answer_guiding_question(
                simulation_id,
                question_text,
                agents,
                interactions,
                use_case=use_case,
            )
            answer = _clean_report_text(answer)
            section_evidence = self._select_section_evidence(
                question_text,
                answer,
                evidence_pool,
                limit=4,
            )
            answer = self._replace_post_id_references(answer, section_evidence or evidence_pool)

            section: dict[str, Any] = {
                "question": question_text,
                "report_title": q.get("report_title", question_text[:60]),
                "type": q_type,
                "answer": answer,
                "evidence": section_evidence,
            }

            # Add metric spotlight for quantitative questions
            if q_type != "open-ended":
                delta_entry = next((d for d in metric_deltas if d["metric_name"] == q.get("metric_name")), None)
                if delta_entry:
                    section["metric"] = delta_entry

            sections.append(section)

        # ── Compute insight blocks ──
        insight_blocks: list[dict[str, Any]] = []
        for block_cfg in insight_block_configs:
            block_type = block_cfg.get("type", "")
            result = metrics_service.compute_insight_block(
                block_type=block_type,
                agents=agents,
                interactions=interactions,
                analysis_questions=analysis_questions,
                metric_ref=block_cfg.get("metric_ref"),
                count=block_cfg.get("count", 5),
            )
            insight_blocks.append({
                "type": block_type,
                "title": block_cfg.get("title", block_type),
                "description": block_cfg.get("description", ""),
                "data": result,
            })

        # ── Generate preset sections via LLM ──
        preset_sections: list[dict[str, Any]] = []
        for preset in preset_section_configs:
            title = preset.get("title", "")
            prompt = preset.get("prompt", "")
            if prompt:
                answer = self._answer_guiding_question(
                    simulation_id,
                    prompt,
                    agents,
                    interactions,
                    use_case=use_case,
                )
            else:
                answer = ""
            clean_answer = self._replace_post_id_references(_clean_report_text(answer), evidence_pool)
            preset_sections.append({"title": title, "answer": clean_answer})

        # ── Executive summary ──
        executive_summary = self._build_v2_executive_summary_from_metrics(
            simulation_id=simulation_id,
            metric_deltas=metric_deltas,
            round_count=round_count,
            agent_count=len(agents),
            use_case=use_case,
        )

        return {
            "session_id": simulation_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "executive_summary": _clean_report_text(executive_summary),
            "metric_deltas": metric_deltas,
            "quick_stats": {
                "agent_count": len(agents),
                "round_count": round_count,
                "model": self.llm.model_name,
                "provider": self.llm.provider,
            },
            "sections": sections,
            "insight_blocks": insight_blocks,
            "preset_sections": preset_sections,
        }

    def export_v2_report_docx(self, simulation_id: str, report: dict[str, Any] | None = None, use_case: str | None = None) -> bytes:
        payload = report or self.build_v2_report(simulation_id, use_case=use_case)
        document = Document()
        document.add_heading("MiroWorld Analysis Report", level=0)
        document.add_paragraph(f"Session: {payload.get('session_id', simulation_id)}")
        document.add_paragraph(f"Generated: {payload.get('generated_at', '')}")

        document.add_heading("Executive Summary", level=1)
        document.add_paragraph(str(payload.get("executive_summary", "")))

        quick_stats = payload.get("quick_stats", {})
        if isinstance(quick_stats, dict):
            document.add_heading("Quick Stats", level=1)
            document.add_paragraph(
                f"Agents: {quick_stats.get('agent_count', 0)} | Rounds: {quick_stats.get('round_count', 0)}"
            )
            document.add_paragraph(
                f"Model: {quick_stats.get('model', '')} ({quick_stats.get('provider', '')})"
            )

        metric_deltas = payload.get("metric_deltas", [])
        if isinstance(metric_deltas, list) and metric_deltas:
            document.add_heading("Metric Deltas", level=1)
            for metric in metric_deltas:
                if not isinstance(metric, dict):
                    continue
                label = str(metric.get("metric_label", metric.get("metric_name", "Metric")))
                initial_value = metric.get("initial_value", 0)
                final_value = metric.get("final_value", 0)
                delta = metric.get("delta", 0)
                unit = str(metric.get("metric_unit", ""))
                document.add_paragraph(
                    f"{label}: {initial_value}{unit} -> {final_value}{unit} ({delta:+}{unit})",
                    style="List Bullet",
                )

        document.add_heading("Analysis Question Sections", level=1)
        for section in payload.get("sections", []):
            if not isinstance(section, dict):
                continue
            section_title = str(section.get("report_title") or section.get("question") or "Section")
            document.add_heading(section_title, level=2)
            if section.get("question"):
                document.add_paragraph(f"Question: {section.get('question')}")
            document.add_paragraph(str(section.get("answer", "")))
            evidence = section.get("evidence", [])
            if isinstance(evidence, list) and evidence:
                document.add_paragraph("Evidence:")
                for item in evidence:
                    if isinstance(item, dict):
                        quote = str(item.get("quote", "")).strip()
                        agent_id = str(item.get("agent_id", ""))
                        post_id = str(item.get("post_id", ""))
                        document.add_paragraph(
                            f"{agent_id} / {post_id}: {quote}",
                            style="List Bullet",
                        )

        insight_blocks = payload.get("insight_blocks", [])
        if isinstance(insight_blocks, list) and insight_blocks:
            document.add_heading("Use-Case Insights", level=1)
            for block in insight_blocks:
                if not isinstance(block, dict):
                    continue
                document.add_heading(str(block.get("title", "Insight")), level=2)
                description = str(block.get("description", "")).strip()
                if description:
                    document.add_paragraph(description)

        preset_sections = payload.get("preset_sections", [])
        if isinstance(preset_sections, list) and preset_sections:
            document.add_heading("Preset Sections", level=1)
            for section in preset_sections:
                if not isinstance(section, dict):
                    continue
                document.add_heading(str(section.get("title", "Section")), level=2)
                document.add_paragraph(str(section.get("answer", "")))

        # ── Analytics Summary ──
        try:
            store = SimulationStore(self.settings.simulation_db_path)
            agents_raw = store.get_agents(simulation_id)
            interactions = store.get_interactions(simulation_id)
            checkpoint_records = store.list_checkpoint_records(simulation_id, checkpoint_kind="post")
            if not checkpoint_records:
                checkpoint_records = store.list_checkpoint_records(simulation_id)

            # Enrich agents with checkpoint metrics
            metric_by_agent: dict[str, dict[str, Any]] = {}
            for record in checkpoint_records:
                aid = str(record.get("agent_id", "")).strip()
                if not aid:
                    continue
                answers = record.get("metric_answers") or {}
                if isinstance(answers, dict):
                    metric_by_agent.setdefault(aid, {}).update(answers)

            enriched_agents: list[dict[str, Any]] = []
            for row in agents_raw:
                agent = dict(row)
                agent["id"] = agent.get("id") or agent.get("agent_id")
                aid = str(agent.get("agent_id") or agent.get("id") or "")
                for metric_name, value in metric_by_agent.get(aid, {}).items():
                    agent[f"checkpoint_{metric_name}"] = value
                enriched_agents.append(agent)

            # Resolve analysis questions from config
            resolved_use_case = use_case or payload.get("use_case", "")
            analysis_questions: list[dict[str, Any]] = []
            if resolved_use_case:
                config_service = ConfigService(self.settings)
                try:
                    analysis_questions = config_service.get_checkpoint_questions(str(resolved_use_case))
                except Exception:  # noqa: BLE001
                    analysis_questions = []

            has_analytics = False

            # Per-metric analytics
            for q in analysis_questions:
                if not isinstance(q, dict) or q.get("type") == "open-ended":
                    continue
                name = str(q.get("metric_name", "")).strip()
                label = str(q.get("metric_label", name)).strip()
                if not name:
                    continue

                score_field = f"checkpoint_{name}"
                pol = compute_polarization(enriched_agents, score_field=score_field)
                flow = compute_opinion_flow(enriched_agents, score_field=score_field)

                if not has_analytics:
                    document.add_heading("Analytics Summary", level=1)
                    has_analytics = True

                document.add_heading(f"{label}", level=2)
                dist = pol.get("distribution", {})
                document.add_paragraph(
                    f"Polarization Index: {pol.get('polarization_index', 0):.2f} ({pol.get('severity', 'low')})",
                    style="List Bullet",
                )
                document.add_paragraph(
                    f"Distribution: {dist.get('supporter_pct', 0):.0f}% supporters, "
                    f"{dist.get('neutral_pct', 0):.0f}% neutral, "
                    f"{dist.get('dissenter_pct', 0):.0f}% dissenters",
                    style="List Bullet",
                )
                initial = flow.get("initial", {})
                final = flow.get("final", {})
                document.add_paragraph(
                    f"Opinion Shift: Supporters {initial.get('supporter', 0)} → {final.get('supporter', 0)}, "
                    f"Neutral {initial.get('neutral', 0)} → {final.get('neutral', 0)}, "
                    f"Dissenters {initial.get('dissenter', 0)} → {final.get('dissenter', 0)}",
                    style="List Bullet",
                )

            # KOL section
            influence = build_influence_graph(interactions, enriched_agents)
            top_influencers = influence.get("top_influencers", [])[:5]
            if top_influencers:
                if not has_analytics:
                    document.add_heading("Analytics Summary", level=1)
                    has_analytics = True
                document.add_heading("Key Opinion Leaders", level=2)
                for inf in top_influencers:
                    name_str = inf.get("name", inf.get("agent_id", ""))
                    stance = inf.get("stance", "unknown")
                    score = inf.get("influence_score", 0)
                    document.add_paragraph(
                        f"{name_str} ({stance}) — Influence: {score:.2f}",
                        style="List Bullet",
                    )
        except Exception:  # noqa: BLE001
            pass  # Analytics section is best-effort; don't fail export

        document.add_paragraph(
            f"Methodology: Simulated agents={quick_stats.get('agent_count', 0)}, "
            f"rounds={quick_stats.get('round_count', 0)}, "
            f"model={quick_stats.get('model', '')} ({quick_stats.get('provider', '')})."
        )

        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _resolve_guiding_questions(self, use_case: str | None) -> list[str]:
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                checkpoint_questions = config_service.get_checkpoint_questions(use_case)
            except Exception:  # noqa: BLE001
                checkpoint_questions = []
            checkpoint_prompts = [
                str(item.get("question", "")).strip()
                for item in checkpoint_questions
                if isinstance(item, dict) and str(item.get("question", "")).strip()
            ]
            if checkpoint_prompts:
                return checkpoint_prompts
            try:
                sections = config_service.get_report_sections(use_case)
            except Exception:  # noqa: BLE001
                sections = []
            report_prompts = [
                str(item.get("prompt") or item.get("title") or "").strip()
                for item in sections
                if isinstance(item, dict) and str(item.get("prompt") or item.get("title") or "").strip()
            ]
            if report_prompts:
                return report_prompts

        return [
            "What are the major shifts in opinion across rounds?",
            "Which arguments most strongly support the policy?",
            "Which arguments most strongly oppose the policy?",
        ]

    def _extract_evidence(self, interactions: list[dict[str, Any]], agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        agent_names: dict[str, str] = {}
        for agent in agents:
            agent_id = str(agent.get("agent_id") or agent.get("id") or "").strip()
            if not agent_id:
                continue
            persona = agent.get("persona") if isinstance(agent.get("persona"), dict) else {}
            display_name = _clean_report_text(
                agent.get("confirmed_name")
                or agent.get("name")
                or agent.get("agent_name")
                or agent.get("display_name")
                or agent.get("label")
                or persona.get("confirmed_name")
                or persona.get("name")
                or persona.get("agent_name")
                or persona.get("display_name")
                or persona.get("label")
                or agent_id
            )
            agent_names[agent_id] = display_name or agent_id

        discourse_actions = {
            "create_post",
            "post_created",
            "post",
            "comment",
            "comment_created",
            "reply",
        }
        evidence: list[dict[str, Any]] = []
        seen_quotes: set[str] = set()
        for row in interactions:
            action_type = str(row.get("action_type") or "").strip().lower()
            if action_type not in discourse_actions:
                continue

            quote = _clean_report_text(row.get("content") or row.get("body") or row.get("title"))
            if not quote:
                continue
            if self._is_prompt_like_interaction(quote):
                continue
            if not self._is_opinion_like_interaction(quote):
                continue

            quote_key = quote.lower()
            if quote_key in seen_quotes:
                continue
            seen_quotes.add(quote_key)

            agent_id = str(row.get("actor_agent_id", "")).strip()
            agent_name = agent_names.get(agent_id, agent_id)
            source_type = "comment" if "comment" in action_type or "reply" in action_type else "post"
            evidence.append(
                {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "post_id": str(row.get("post_id") or row.get("id") or ""),
                    "action_type": action_type,
                    "source_type": source_type,
                    "source_label": f"{'Comment' if source_type == 'comment' else 'Post'} by {agent_name or 'Unknown agent'}",
                    "round_no": int(row.get("round_no", 0) or 0),
                    "quote": quote,
                }
            )
        return evidence

    def _tokenize_evidence_text(self, value: str) -> set[str]:
        stopwords = {
            "a", "an", "the", "and", "or", "to", "of", "for", "with", "in", "on", "at", "by",
            "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those",
            "it", "its", "as", "from", "about", "into", "over", "under", "than", "then", "if",
            "but", "we", "our", "ours", "you", "your", "yours", "they", "their", "theirs",
            "agent", "policy", "persona", "perspective", "community", "prompt", "brief",
        }
        tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9']+", str(value).lower()))
        return {token for token in tokens if len(token) >= 3 and token not in stopwords}

    def _is_prompt_like_interaction(self, text: str) -> bool:
        lowered = text.lower()
        if lowered.startswith("community prompt:"):
            return True
        if lowered.startswith("policy brief:"):
            return True
        if "community prompt:" in lowered and "policy brief:" in lowered:
            return True
        if (
            lowered.startswith("from your persona")
            or lowered.startswith("would you")
            or lowered.startswith("how strongly")
        ) and "?" in lowered:
            return True
        return False

    def _is_opinion_like_interaction(self, text: str) -> bool:
        lowered = text.lower().strip()
        if len(lowered.split()) < 8:
            return False
        opinion_markers = (
            "i ",
            "i'm",
            "i am",
            "my ",
            "we ",
            "our ",
            "because",
            "concern",
            "worried",
            "support",
            "oppose",
            "agree",
            "disagree",
            "insufficient",
            "enough",
            "not enough",
            "rate",
            "/10",
        )
        if any(marker in lowered for marker in opinion_markers):
            return True
        return lowered.count("?") == 0

    def _select_section_evidence(
        self,
        question: str,
        answer: str,
        evidence_pool: list[dict[str, Any]],
        *,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        if not evidence_pool:
            return []

        query_tokens = self._tokenize_evidence_text(f"{question} {answer}")
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in evidence_pool:
            quote = str(item.get("quote") or "").strip()
            if not quote:
                continue

            quote_tokens = self._tokenize_evidence_text(quote)
            overlap = len(query_tokens.intersection(quote_tokens))
            base_score = float(overlap * 3)

            source_type = str(item.get("source_type") or "")
            if source_type == "comment":
                base_score += 1.5

            round_no = int(item.get("round_no") or 0)
            if round_no > 0:
                base_score += min(round_no, 5) * 0.1

            # Prefer richer, specific statements over short generic replies.
            base_score += min(len(quote_tokens), 40) / 20.0
            scored.append((base_score, item))

        if not scored:
            return evidence_pool[:limit]

        scored.sort(key=lambda row: row[0], reverse=True)

        selected: list[dict[str, Any]] = []
        seen_agents: set[str] = set()
        for _score, item in scored:
            if len(selected) >= limit:
                break
            agent_id = str(item.get("agent_id") or "")
            if agent_id and agent_id in seen_agents:
                continue
            selected.append(item)
            if agent_id:
                seen_agents.add(agent_id)

        if len(selected) < limit:
            existing_ids = {id(item) for item in selected}
            for _score, item in scored:
                if len(selected) >= limit:
                    break
                if id(item) in existing_ids:
                    continue
                selected.append(item)

        return selected[:limit]

    def _replace_post_id_references(self, text: str, evidence: list[dict[str, Any]]) -> str:
        cleaned = _clean_report_text(text)
        if not cleaned:
            return cleaned

        post_owner: dict[str, str] = {}
        for item in evidence:
            post_id = str(item.get("post_id") or "").strip()
            agent_name = _clean_report_text(item.get("agent_name"))
            if post_id and agent_name:
                post_owner[post_id] = agent_name

        fallback_name = ""
        for item in evidence:
            fallback_name = _clean_report_text(item.get("agent_name"))
            if fallback_name:
                break

        def _replacement(match: re.Match[str]) -> str:
            ref_id = str(match.group(1) or "").strip()
            owner = post_owner.get(ref_id) or fallback_name
            if owner:
                return f"post by {owner}"
            return "post"

        rewritten = re.sub(r"\bpost\s*id\s*#?\s*(\d+)\b", _replacement, cleaned, flags=re.IGNORECASE)
        rewritten = re.sub(r"\bpost\s*#\s*(\d+)\b", _replacement, rewritten, flags=re.IGNORECASE)
        return rewritten

    def _knowledge_context_lines(self, knowledge: dict[str, Any]) -> list[str]:
        if not isinstance(knowledge, dict):
            return []

        lines: list[str] = []
        summary = _clean_report_text(knowledge.get("summary"))
        if summary:
            lines.append(f"Document summary: {summary}")

        document = knowledge.get("document")
        if isinstance(document, dict):
            source_path = _clean_report_text(document.get("source_path"))
            if source_path:
                lines.append(f"Source document: {source_path}")
            text_length = document.get("text_length")
            if text_length is not None:
                lines.append(f"Document length: {text_length}")
            sources = document.get("sources")
            if isinstance(sources, list):
                for source in sources[:3]:
                    if not isinstance(source, dict):
                        continue
                    source_path = _clean_report_text(source.get("source_path"))
                    if source_path:
                        lines.append(f"Document source: {source_path}")
        return lines

    def _answer_guiding_question(
        self,
        simulation_id: str,
        question: str,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        *,
        use_case: str | None = None,
    ) -> str:
        knowledge = self.store.get_knowledge_artifact(simulation_id) or {}
        knowledge_context = "\n".join(self._knowledge_context_lines(knowledge))
        style_rules = self._resolve_report_writer_instructions(use_case)
        style_block = "\n".join(f"- {rule}" for rule in style_rules)
        report_prompt_cfg = self.config.get_system_prompt_config("report_agent")
        recent_char_limits = ((report_prompt_cfg.get("defaults") or {}).get("recent_interactions_chars") or {})
        recent_char_limit = int(recent_char_limits.get(self.llm.provider, recent_char_limits.get("default", 20000)) or 20000)
        min_words = int(((report_prompt_cfg.get("defaults") or {}).get("min_words_per_question") or 300))
        max_words = int(((report_prompt_cfg.get("defaults") or {}).get("max_words_per_question") or 500))
        prompt = self.config.get_system_prompt_value(
            "report_agent",
            "prompts",
            "guiding_question",
            "user_template",
        ).format(
            simulation_id=simulation_id,
            question=question,
            knowledge_context=knowledge_context or "- none",
            agent_count=len(agents),
            recent_interactions=json.dumps(interactions, ensure_ascii=False)[:recent_char_limit],
            style_block=style_block or "- none",
            min_words_per_question=min_words,
            max_words_per_question=max_words,
        )
        try:
            response = self.llm.complete_required(
                prompt,
                system_prompt=self.config.get_system_prompt_value(
                    "report_agent",
                    "prompts",
                    "guiding_question",
                    "system_prompt",
                ),
            )
            response = _clean_report_text(response)
            if _contains_first_person(response):
                rewrite = self.llm.complete_required(
                    (
                        "Rewrite the following text in strict third-person analytical voice. "
                        "Do not use first-person pronouns. Keep all facts and evidence references intact.\n\n"
                        f"Text:\n{response}"
                    ),
                    system_prompt=self.config.get_system_prompt_value(
                        "report_agent",
                        "prompts",
                        "guiding_question",
                        "rewrite_system_prompt",
                    ),
                )
                response = _clean_report_text(rewrite)
            return response
        except Exception:  # noqa: BLE001
            return "The available interactions indicate this question can be answered from observed cohort arguments and sentiment shifts."

    def _resolve_report_writer_instructions(self, use_case: str | None) -> list[str]:
        defaults = [
            "Use third-person analyst voice (e.g., 'agents expressed', 'discussion indicated').",
            "Do not write personal opinions or first-person statements (avoid I/we/my/our).",
            "Summarize what agents think, citing concrete evidence from interactions when possible.",
        ]
        if not use_case:
            return defaults
        config_service = ConfigService(self.settings)
        try:
            configured = config_service.get_report_writer_instructions(use_case)
        except Exception:  # noqa: BLE001
            configured = []
        return configured or defaults

    def _build_demographic_breakdown(self, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"supporter": 0, "neutral": 0, "dissenter": 0})
        for agent in agents:
            segment = str(agent.get("persona", {}).get("planning_area", "Unknown"))
            score = float(agent.get("opinion_post", 5.0) or 5.0)
            if score >= 7:
                grouped[segment]["supporter"] += 1
            elif score >= 5:
                grouped[segment]["neutral"] += 1
            else:
                grouped[segment]["dissenter"] += 1
        rows = [
            {
                "segment": segment,
                "supporter": values["supporter"],
                "neutral": values["neutral"],
                "dissenter": values["dissenter"],
            }
            for segment, values in grouped.items()
        ]
        rows.sort(key=lambda row: row["dissenter"], reverse=True)
        return rows

    def _build_v2_recommendations(self, demographic_breakdown: list[dict[str, Any]], dissenting_views: list[str]) -> list[str]:
        recommendations: list[str] = []
        if demographic_breakdown:
            top = demographic_breakdown[0]
            recommendations.append(
                f"Prioritize communication and safeguards for {top.get('segment', 'top dissent segment')} to reduce concentrated dissent."
            )
        if dissenting_views:
            recommendations.append("Address recurring affordability concerns directly with concrete implementation details.")
        if not recommendations:
            recommendations.append("Maintain transparent rollout updates and monitor stance movement each round.")
        return recommendations[:5]

    def _build_v2_executive_summary(
        self,
        *,
        simulation_id: str,
        initial_metric: float,
        final_metric: float,
        round_count: int,
        supporting_views: list[str],
        dissenting_views: list[str],
    ) -> str:
        prompt = self.config.get_system_prompt_value(
            "report_agent",
            "prompts",
            "v2_executive_summary",
            "user_template",
        ).format(
            simulation_id=simulation_id,
            initial_metric=initial_metric,
            final_metric=final_metric,
            round_count=round_count,
            supporting_views=supporting_views[:3],
            dissenting_views=dissenting_views[:3],
        )
        try:
            return self.llm.complete_required(
                prompt,
                system_prompt=self.config.get_system_prompt_value(
                    "report_agent",
                    "prompts",
                    "v2_executive_summary",
                    "system_prompt",
                ),
            )
        except Exception:  # noqa: BLE001
            direction = "declined" if final_metric < initial_metric else "improved"
            return (
                f"Across {round_count} rounds, overall approval {direction} from {initial_metric} to {final_metric}. "
                "Observed interactions show concentrated disagreement around affordability and rollout fairness."
            )

    # ── New V2 helper methods ──

    def _session_analysis_questions(self, simulation_id: str) -> list[dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.settings.simulation_db_path)
            row = conn.execute(
                "SELECT analysis_questions FROM session_configs WHERE session_id = ?",
                (simulation_id,),
            ).fetchone()
            conn.close()
        except Exception:  # noqa: BLE001
            return []
        if not row or row[0] is None:
            return []
        raw = row[0]
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:  # noqa: BLE001
                return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _resolve_analysis_questions(self, *, simulation_id: str, use_case: str | None) -> list[dict[str, Any]]:
        """Resolve analysis questions from session config first, then fall back to use-case YAML."""
        session_questions = self._session_analysis_questions(simulation_id)
        if session_questions:
            return session_questions

        if use_case:
            config_service = ConfigService(self.settings)
            try:
                questions = config_service.get_analysis_questions(use_case)
                if questions:
                    return questions
                sections = config_service.get_report_sections(use_case)
                normalized_from_sections = [
                    {
                        "question": str(item.get("prompt") or item.get("title") or "").strip(),
                        "type": "open-ended",
                        "metric_name": str(item.get("title", "")).strip().lower().replace(" ", "_") or "section",
                        "report_title": str(item.get("title") or item.get("prompt") or "Section").strip(),
                        "tooltip": "",
                    }
                    for item in sections
                    if isinstance(item, dict) and str(item.get("prompt") or item.get("title") or "").strip()
                ]
                if normalized_from_sections:
                    return normalized_from_sections
            except Exception:  # noqa: BLE001
                pass
        return []

    def _resolve_insight_blocks(self, use_case: str | None) -> list[dict[str, Any]]:
        """Resolve insight block configs from the use-case YAML."""
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                return config_service.get_insight_blocks(use_case)
            except Exception:  # noqa: BLE001
                pass
        return []

    def _resolve_preset_sections(self, use_case: str | None) -> list[dict[str, Any]]:
        """Resolve preset section configs from the use-case YAML."""
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                return config_service.get_preset_sections(use_case)
            except Exception:  # noqa: BLE001
                pass
        return []

    def _agents_from_checkpoint(self, checkpoint_records: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        """Convert checkpoint records into agent-like dicts for metric computation."""
        if not checkpoint_records:
            return None
        rows: list[dict[str, Any]] = []
        for record in checkpoint_records:
            if not isinstance(record, dict):
                continue
            row: dict[str, Any] = {}
            metric_answers = record.get("metric_answers")
            if isinstance(metric_answers, dict):
                for metric_name, value in metric_answers.items():
                    clean_name = str(metric_name or "").strip()
                    if not clean_name:
                        continue
                    row[f"checkpoint_{clean_name}"] = value
            if row:
                rows.append(row)
            else:
                rows.append(record)
        return rows

    def _compute_metric_value(self, question: dict[str, Any], agents: list[dict[str, Any]]) -> float:
        """Compute a single metric value for one analysis question across agents."""
        name = question.get("metric_name", "")
        field = f"checkpoint_{name}"
        q_type = question.get("type", "scale")
        total = max(len(agents), 1)

        if q_type == "scale":
            scores: list[float] = []
            for agent in agents:
                raw_value = agent.get(field, agent.get("opinion_post", 5.0))
                parsed = _extract_numeric_value(raw_value)
                score = parsed if parsed is not None else 5.0
                scores.append(max(0.0, min(10.0, score)))
            if "threshold" in question:
                threshold_raw = question.get("threshold", 7)
                threshold = _extract_numeric_value(threshold_raw)
                threshold = threshold if threshold is not None else 7.0
                pct = sum(1 for s in scores if s >= threshold) / total * 100
                return round(pct, 1)
            return round(sum(scores) / len(scores) if scores else 0.0, 1)
        elif q_type == "yes-no":
            yes_count = 0
            for agent in agents:
                parsed = _parse_yes_no(agent.get(field, ""))
                if parsed is True:
                    yes_count += 1
            return round(yes_count / total * 100, 1)
        return 0.0

    def _build_v2_executive_summary_from_metrics(
        self,
        *,
        simulation_id: str,
        metric_deltas: list[dict[str, Any]],
        round_count: int,
        agent_count: int,
        use_case: str | None = None,
    ) -> str:
        """Build executive summary using metric deltas instead of raw scores."""
        if not metric_deltas:
            return f"Simulation {simulation_id} completed with {agent_count} agents over {round_count} rounds."

        metrics_summary = "; ".join(
            f"{d['metric_label']}: {d['initial_display']} -> {d['final_display']} ({'+' if d['delta'] > 0 else ''}{d['delta']}{d['metric_unit']})"
            for d in metric_deltas
        )
        style_rules = self._resolve_report_writer_instructions(use_case)
        style_block = "\n".join(f"- {rule}" for rule in style_rules)
        knowledge = self.store.get_knowledge_artifact(simulation_id) or {}
        knowledge_context = "\n".join(self._knowledge_context_lines(knowledge))
        prompt = self.config.get_system_prompt_value(
            "report_agent",
            "prompts",
            "metric_delta_summary",
            "user_template",
        ).format(
            simulation_id=simulation_id,
            agent_count=agent_count,
            round_count=round_count,
            knowledge_context=knowledge_context or "- none",
            metrics_summary=metrics_summary,
            style_block=style_block or "- none",
        )
        try:
            response = self.llm.complete_required(
                prompt,
                system_prompt=self.config.get_system_prompt_value(
                    "report_agent",
                    "prompts",
                    "metric_delta_summary",
                    "system_prompt",
                ),
            )
            response = _clean_report_text(response)
            if _contains_first_person(response):
                rewrite = self.llm.complete_required(
                    (
                        "Rewrite the following executive summary in strict third-person analytical voice. "
                        "Do not use first-person pronouns. Keep the same findings.\n\n"
                        f"Text:\n{response}"
                    ),
                    system_prompt=self.config.get_system_prompt_value(
                        "report_agent",
                        "prompts",
                        "metric_delta_summary",
                        "rewrite_system_prompt",
                    ),
                )
                response = _clean_report_text(rewrite)
            return response
        except Exception:  # noqa: BLE001
            return f"Across {round_count} rounds with {agent_count} agents: {metrics_summary}."

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

        prompt = self.config.get_system_prompt_value(
            "report_agent",
            "prompts",
            "recommendations",
            "user_template",
        ).format(
            simulation_id=simulation_id,
            top_dissenting=top_dissenting[:6],
            income_metrics=sorted(income_metrics, key=lambda x: x["approval_post"])[:6],
            arguments_for=arguments_for[:6],
            arguments_against=arguments_against[:6],
        )

        raw = self.llm.complete_required(
            prompt=prompt,
            system_prompt=self.config.get_system_prompt_value(
                "report_agent",
                "prompts",
                "recommendations",
                "system_prompt",
            ),
        )
        parsed = self._parse_recommendations(raw)
        if parsed:
            return parsed
        raise RuntimeError("Report recommendation generation failed because the model did not return valid JSON.")

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
        use_case: str | None,
        knowledge: dict[str, Any],
        population: dict[str, Any],
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> str:
        config_lines: list[str] = []
        if use_case:
            config_service = ConfigService(self.settings)
            try:
                use_case_payload = config_service.get_use_case(use_case)
            except Exception:  # noqa: BLE001
                use_case_payload = {}
            guiding_prompt = str(use_case_payload.get("guiding_prompt") or "").strip()
            if guiding_prompt:
                config_lines.append("Use-case guiding prompt:")
                config_lines.append(guiding_prompt)
            report_sections = [
                item
                for item in use_case_payload.get("report_sections", [])
                if isinstance(item, dict)
            ]
            if report_sections:
                config_lines.append("Report sections from config:")
                for index, section in enumerate(report_sections, start=1):
                    title = str(section.get("title") or "").strip()
                    prompt = str(section.get("prompt") or "").strip()
                    if title or prompt:
                        config_lines.append(f"{index}. {title}: {prompt}".strip())
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
        prompt_lines = [
            "Generate a fixed-format policy simulation report in JSON.",
            "Return an object with exactly these top-level keys:",
            "{\"generated_at\": str, \"executive_summary\": str, "
            "\"insight_cards\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}], "
            "\"support_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"dissent_themes\": [{\"theme\": str, \"summary\": str, \"evidence\": [str]}], "
            "\"demographic_breakdown\": [{\"segment\": str, \"approval_rate\": number, \"dissent_rate\": number, \"sample_size\": number}], "
            "\"influential_content\": [{\"content_type\": str, \"author_agent_id\": str, \"summary\": str, \"engagement_score\": number}], "
            "\"recommendations\": [{\"title\": str, \"rationale\": str, \"priority\": \"high|medium|low\"}], "
            "\"risks\": [{\"title\": str, \"summary\": str, \"severity\": \"high|medium|low\"}]}",
            "",
        ]
        if config_lines:
            prompt_lines.extend(config_lines)
            prompt_lines.append("")
        prompt_lines.extend(
            [
                f"Simulation ID: {simulation_id}",
                f"Knowledge summary: {knowledge.get('summary', '')}",
                f"Population artifact: {json.dumps(population, ensure_ascii=False)[:6000]}",
                f"Checkpoint records: {json.dumps(checkpoints, ensure_ascii=False)[:12000]}",
                f"Influential posts: {json.dumps(influential_posts, ensure_ascii=False)[:6000]}",
                f"Recent simulation events: {json.dumps(events[-80:], ensure_ascii=False)[:12000]}",
                f"Agent records: {json.dumps(agents[:80], ensure_ascii=False)[:12000]}",
            ]
        )
        return "\n".join(prompt_lines)

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
        return normalized

    def _enrich_structured_report_payload(
        self,
        simulation_id: str,
        payload: dict[str, Any],
        *,
        use_case: str | None,
        agents: list[dict[str, Any]],
        interactions: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
        knowledge: dict[str, Any],
        population: dict[str, Any],
    ) -> dict[str, Any]:
        enriched = dict(payload)
        pre_scores = [float(agent.get("opinion_pre", 5.0) or 5.0) for agent in agents]
        post_scores = [float(agent.get("opinion_post", 5.0) or 5.0) for agent in agents]
        approval_pre = _approval(pre_scores)
        approval_post = _approval(post_scores)

        supportive_rows = self._rank_interactions(interactions, positive=True)
        dissent_rows = self._rank_interactions(interactions, positive=False)
        demographic_breakdown = enriched.get("demographic_breakdown") or self._build_demographic_breakdown(agents)

        if not enriched["executive_summary"]:
            enriched["executive_summary"] = self._build_structured_executive_summary(
                simulation_id=simulation_id,
                use_case=use_case,
                demographic_breakdown=demographic_breakdown,
                supportive_rows=supportive_rows,
                dissent_rows=dissent_rows,
                approval_pre=approval_pre,
                approval_post=approval_post,
            )

        if not enriched["insight_cards"]:
            top_segment = str(demographic_breakdown[0].get("segment", "top cohort")) if demographic_breakdown else "top cohort"
            card_summary = (
                f"{top_segment} carried the strongest signal in the simulation, "
                f"with approval moving from {approval_pre:.2f} to {approval_post:.2f} across the run."
            )
            enriched["insight_cards"] = [
                {
                    "title": f"{top_segment} drove the clearest shift",
                    "summary": card_summary,
                    "severity": "high" if abs(approval_post - approval_pre) >= 0.15 else "medium",
                }
            ]
            if supportive_rows:
                first_support = supportive_rows[0]
                enriched["insight_cards"].append(
                    {
                        "title": "Most persuasive support argument",
                        "summary": str(first_support["content"])[:240],
                        "severity": "medium",
                    }
                )
            if dissent_rows:
                first_dissent = dissent_rows[0]
                enriched["insight_cards"].append(
                    {
                        "title": "Main dissent pressure point",
                        "summary": str(first_dissent["content"])[:240],
                        "severity": "medium",
                    }
                )

        if not enriched["support_themes"]:
            enriched["support_themes"] = self._build_theme_items(
                supportive_rows,
                theme_label="support",
                fallback_summary="Support centered on concrete benefits and targeted help.",
            )

        if not enriched["dissent_themes"]:
            enriched["dissent_themes"] = self._build_theme_items(
                dissent_rows,
                theme_label="dissent",
                fallback_summary="Dissent clustered around affordability, fairness, or implementation risk.",
            )

        if not enriched["demographic_breakdown"]:
            enriched["demographic_breakdown"] = demographic_breakdown

        if not enriched["influential_content"]:
            enriched["influential_content"] = self._build_influential_content(interactions)

        if not enriched["recommendations"]:
            enriched["recommendations"] = self._build_structured_recommendations(
                simulation_id=simulation_id,
                demographic_breakdown=demographic_breakdown,
                dissent_rows=dissent_rows,
                supportive_rows=supportive_rows,
                knowledge=knowledge,
                population=population,
                use_case=use_case,
                baseline=baseline,
                final=final,
                events=events,
            )

        if not enriched["risks"]:
            enriched["risks"] = self._build_structured_risks(
                demographic_breakdown=demographic_breakdown,
                dissent_rows=dissent_rows,
                events=events,
            )

        return enriched

    def _rank_interactions(self, interactions: list[dict[str, Any]], *, positive: bool) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in interactions:
            try:
                delta = float(item.get("delta", 0.0) or 0.0)
            except (TypeError, ValueError):
                delta = 0.0
            if positive and delta <= 0:
                continue
            if not positive and delta >= 0:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            rows.append(
                {
                    "content": content,
                    "agent_id": str(item.get("actor_agent_id", "")),
                    "round_no": int(item.get("round_no", 0) or 0),
                    "delta": delta,
                    "likes": float(item.get("likes", 0) or 0),
                    "dislikes": float(item.get("dislikes", 0) or 0),
                }
            )
        rows.sort(key=lambda row: (abs(row["delta"]), row["likes"] + row["dislikes"]), reverse=True)
        return rows[:6]

    def _build_theme_items(
        self,
        rows: list[dict[str, Any]],
        *,
        theme_label: str,
        fallback_summary: str,
    ) -> list[dict[str, Any]]:
        if not rows:
            return [
                {
                    "theme": theme_label,
                    "summary": fallback_summary,
                    "evidence": [],
                }
            ]
        items: list[dict[str, Any]] = []
        for row in rows[:3]:
            summary = f"{row['content'][:180]}"
            items.append(
                {
                    "theme": theme_label,
                    "summary": summary,
                    "evidence": [row["content"]],
                }
            )
        return items

    def _build_influential_content(self, interactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for item in interactions:
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            try:
                delta = abs(float(item.get("delta", 0.0) or 0.0))
            except (TypeError, ValueError):
                delta = 0.0
            try:
                likes = float(item.get("likes", 0) or 0)
            except (TypeError, ValueError):
                likes = 0.0
            try:
                dislikes = float(item.get("dislikes", 0) or 0)
            except (TypeError, ValueError):
                dislikes = 0.0
            engagement_score = round(delta * 10 + likes + dislikes, 2)
            rows.append(
                {
                    "content_type": str(item.get("action_type") or item.get("type") or "post"),
                    "author_agent_id": str(item.get("actor_agent_id", "")),
                    "summary": content[:240],
                    "engagement_score": engagement_score,
                }
            )
        rows.sort(key=lambda row: row["engagement_score"], reverse=True)
        return rows[:6]

    def _build_structured_recommendations(
        self,
        *,
        simulation_id: str,
        demographic_breakdown: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        supportive_rows: list[dict[str, Any]],
        knowledge: dict[str, Any],
        population: dict[str, Any],
        use_case: str | None,
        baseline: list[dict[str, Any]],
        final: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        top_segment = str(demographic_breakdown[0].get("segment", "All cohorts")) if demographic_breakdown else "All cohorts"
        top_dissent = dissent_rows[0]["content"] if dissent_rows else "review implementation gaps"
        support_context = supportive_rows[0]["content"] if supportive_rows else str(knowledge.get("summary", "")).strip()
        base_label = use_case or str(population.get("use_case") or "simulation")
        return [
            {
                "title": f"Address the main friction in {top_segment}",
                "rationale": f"Dissent in {top_segment} is the clearest signal to act on first.",
                "priority": "high",
            },
            {
                "title": f"Turn the strongest support into a clearer message for {base_label}",
                "rationale": support_context[:240] or "Support needs to be translated into a more concrete narrative.",
                "priority": "medium",
            },
            {
                "title": "Use round-by-round evidence to close credibility gaps",
                "rationale": top_dissent[:240] if top_dissent else "Agents responded to concrete examples more than abstract assurances.",
                "priority": "medium",
            },
        ]

    def _build_structured_risks(
        self,
        *,
        demographic_breakdown: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        if demographic_breakdown:
            top = demographic_breakdown[0]
            risks.append(
                {
                    "title": f"Concentrated dissent in {top.get('segment', 'a key cohort')}",
                    "summary": (
                        f"{top.get('segment', 'A cohort')} has {top.get('dissent_rate', 0)} dissent rate "
                        f"across {top.get('sample_size', 0)} agents."
                    ),
                    "severity": "high" if float(top.get("dissent_rate", 0) or 0) >= 0.3 else "medium",
                }
            )
        if dissent_rows:
            risks.append(
                {
                    "title": "Recurring objection pattern",
                    "summary": dissent_rows[0]["content"][:240],
                    "severity": "medium",
                }
            )
        if events:
            risks.append(
                {
                    "title": "Conversation may be dominated by the most active agents",
                    "summary": "Event logs show the report is driven by a small set of highly visible posts.",
                    "severity": "low",
                }
            )
        return risks[:4]

    def _build_structured_executive_summary(
        self,
        *,
        simulation_id: str,
        use_case: str | None,
        demographic_breakdown: list[dict[str, Any]],
        supportive_rows: list[dict[str, Any]],
        dissent_rows: list[dict[str, Any]],
        approval_pre: float,
        approval_post: float,
    ) -> str:
        top_segment = str(demographic_breakdown[0].get("segment", "the main cohort")) if demographic_breakdown else "the main cohort"
        support_excerpt = supportive_rows[0]["content"][:140] if supportive_rows else "support stayed concentrated in a few concrete arguments"
        dissent_excerpt = dissent_rows[0]["content"][:140] if dissent_rows else "dissent stayed centered on implementation risk"
        direction = "improved" if approval_post >= approval_pre else "softened"
        use_case_label = f"for {use_case}" if use_case else "for the simulation"
        return (
            f"Across {use_case_label}, approval {direction} from {approval_pre:.2f} to {approval_post:.2f}. "
            f"{top_segment} was the clearest cohort signal in the run, with support anchored by '{support_excerpt}' "
            f"and dissent concentrated around '{dissent_excerpt}'. "
            "The report sections point to a need for sharper mitigation and clearer rollout messaging."
        )


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


def _contains_first_person(text: str) -> bool:
    lowered = f" {str(text or '').lower()} "
    return any(token in lowered for token in (" i ", " i'm ", " i've ", " i'd ", " we ", " we're ", " we've ", " our ", " my "))
