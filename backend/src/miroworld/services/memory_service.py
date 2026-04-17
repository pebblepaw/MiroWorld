from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from miroworld.config import Settings
from miroworld.services.config_service import ConfigService
from miroworld.services.llm_client import GeminiChatClient
from miroworld.services.storage import SimulationStore
from miroworld.services.zep_service import ZepService


class MemoryService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        self.config = ConfigService(settings)
        self.zep = ZepService(settings)
        self._simulation_context_cache: dict[tuple[str, str, int, bool, str], dict[str, Any]] = {}
        self._interaction_cache: dict[str, list[dict[str, Any]]] = {}
        self._transcript_cache: dict[str, list[dict[str, Any]]] = {}
        self._checkpoint_cache: dict[str, list[dict[str, Any]]] = {}
        self._memory_backend = "zep-cloud" if self.zep.enabled else "sqlite"

    @property
    def memory_backend(self) -> str:
        return self._memory_backend

    def sync_simulation(self, simulation_id: str) -> dict[str, Any]:
        if not self.zep.enabled:
            return {
                "simulation_id": simulation_id,
                "synced_events": 0,
                "zep_enabled": False,
                "external_sync_enabled": False,
                "memory_backend": self._memory_backend,
            }
        sync_state = self._ensure_zep_synced(simulation_id)
        return {
            "simulation_id": simulation_id,
            "synced_events": int(sync_state.get("synced_events", 0) or 0),
            "zep_enabled": True,
            "external_sync_enabled": True,
            "memory_backend": self._memory_backend,
        }

    def get_agent_memory(self, simulation_id: str, agent_id: str) -> list[dict[str, Any]]:
        interactions = self._get_cached_interactions(simulation_id)
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
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_limit = max(1, int(limit))
        normalized_query = " ".join(str(query or "").split())
        cache_key = (simulation_id, normalized_query.lower(), normalized_limit, live_mode, agent_id or "")
        cached = self._simulation_context_cache.get(cache_key)
        if cached is not None:
            return deepcopy(cached)

        if self.zep.enabled:
            context = self._search_zep_context(
                simulation_id,
                normalized_query,
                normalized_limit,
                agent_id=agent_id,
            )
        else:
            context = self._search_local_context(
                simulation_id,
                normalized_query,
                normalized_limit,
                agent_id=agent_id,
            )
        self._simulation_context_cache[cache_key] = deepcopy(context)
        return context

    def search_agent_context(
        self,
        simulation_id: str,
        agent_id: str,
        query: str,
        limit: int = 8,
        *,
        live_mode: bool = False,
    ) -> dict[str, Any]:
        attempts = [query, ""]
        seen: set[str] = set()
        last_result: dict[str, Any] | None = None

        for candidate_query in attempts:
            normalized = " ".join(candidate_query.split())
            cache_token = normalized or "__recent__"
            if cache_token in seen:
                continue
            seen.add(cache_token)
            result = self.search_simulation_context(
                simulation_id,
                normalized,
                limit=limit,
                live_mode=live_mode,
                agent_id=agent_id,
            )
            last_result = result
            if result["episodes"] or result["checkpoint_records"]:
                return result

        if last_result is not None:
            return last_result

        return {
            "episodes": [],
            "checkpoint_records": [],
            "synced_events": 0,
            "zep_context_used": self.zep.enabled,
            "graphiti_context_used": False,
            "memory_backend": self._memory_backend,
        }

    def agent_chat(self, simulation_id: str, agent_id: str, message: str) -> dict[str, Any]:
        return self.agent_chat_realtime(simulation_id, agent_id, message, live_mode=False)

    def agent_chat_realtime(
        self,
        simulation_id: str,
        agent_id: str,
        message: str,
        *,
        live_mode: bool = False,
    ) -> dict[str, Any]:
        memories = self.get_agent_memory(simulation_id, agent_id)
        memory_context = self.search_agent_context(
            simulation_id,
            agent_id,
            message,
            limit=8,
            live_mode=live_mode,
        )

        agents = {agent["agent_id"]: agent for agent in self.store.get_agents(simulation_id)}
        agent = agents.get(agent_id)
        if not agent:
            raise RuntimeError(f"Agent not found in simulation: {agent_id}")

        context_excerpt = self._format_episode_excerpt(memory_context["episodes"], limit=6)
        checkpoint_excerpt = self.format_checkpoint_records(memory_context["checkpoint_records"], limit=4)
        activity_excerpt = self._format_agent_activity_excerpt(memories, agent_id=agent_id, limit=8)
        prompt = self.config.get_system_prompt_value(
            "memory_context",
            "prompts",
            "agent_chat",
            "user_template",
        ).format(
            agent_id=agent_id,
            simulation_id=simulation_id,
            persona=agent["persona"],
            checkpoint_excerpt=checkpoint_excerpt or "- none",
            activity_excerpt=activity_excerpt or "- none",
            memory_backend=memory_context.get("memory_backend", self._memory_backend),
            context_excerpt=context_excerpt or "- none",
            message=message,
        )

        if self.llm.is_enabled():
            response = self.llm.complete_required(
                prompt,
                system_prompt=self.config.get_system_prompt_value(
                    "memory_context",
                    "prompts",
                    "agent_chat",
                    "system_prompt",
                    default="You are a simulated persona agent. Stay grounded in supplied memory.",
                ),
            )
        else:
            response = self._local_fallback_agent_response(
                agent_id,
                agent,
                message,
                memories,
                memory_context["episodes"],
                memory_context["checkpoint_records"],
            )

        memory_used = bool(memories or memory_context["episodes"] or memory_context["checkpoint_records"])
        return {
            "session_id": simulation_id,
            "simulation_id": simulation_id,
            "agent_id": agent_id,
            "response": response,
            "memory_used": memory_used,
            "model_provider": self.llm.provider,
            "model_name": self.llm.model_name,
            "gemini_model": self.llm.model_name,
            "zep_context_used": bool(memory_context.get("zep_context_used", False)),
            "graphiti_context_used": False,
            "memory_backend": memory_context.get("memory_backend", self._memory_backend),
        }

    def format_checkpoint_records(self, checkpoint_records: list[dict[str, Any]], limit: int = 6) -> str:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in checkpoint_records:
            checkpoint_kind = str(record.get("checkpoint_kind") or "checkpoint").strip().lower() or "checkpoint"
            grouped.setdefault(checkpoint_kind, []).append(record)

        ordered_kinds = [kind for kind in ("baseline", "final") if kind in grouped]
        ordered_kinds.extend(kind for kind in grouped if kind not in {"baseline", "final"})

        selected: dict[str, list[dict[str, Any]]] = {kind: [] for kind in ordered_kinds}
        remaining = max(1, int(limit))

        for checkpoint_kind in ordered_kinds:
            if remaining <= 0:
                break
            records = grouped.get(checkpoint_kind, [])
            if not records:
                continue
            selected[checkpoint_kind].append(records[0])
            remaining -= 1

        if remaining > 0:
            for checkpoint_kind in ordered_kinds:
                if remaining <= 0:
                    break
                records = grouped.get(checkpoint_kind, [])
                for record in records[len(selected[checkpoint_kind]) :]:
                    if remaining <= 0:
                        break
                    selected[checkpoint_kind].append(record)
                    remaining -= 1

        sections: list[str] = []
        for checkpoint_kind in ordered_kinds:
            records = selected.get(checkpoint_kind, [])
            if not records:
                continue
            sections.append(f"{checkpoint_kind.replace('_', ' ').title()}:")
            for record in records:
                sections.append(f"- {self._format_checkpoint_line(record)}")
        return "\n".join(sections)

    def build_question_context_pack(
        self,
        session_id: str,
        *,
        question_text: str,
        metric: dict[str, Any] | None,
        question_type: str,
        report_title: str,
        limit: int = 8,
    ) -> dict[str, Any]:
        query_parts = [report_title, question_text]
        if isinstance(metric, dict):
            query_parts.extend(
                str(metric.get(key) or "").strip()
                for key in ("metric_name", "metric_label")
            )
        query = " ".join(part for part in query_parts if part)
        payload = self.search_simulation_context(session_id, query, limit=max(limit * 4, 12))
        stance_by_agent = self._build_agent_stance_map(session_id, metric=metric)
        discourse_episodes = [
            item
            for item in payload["episodes"]
            if self._is_discourse_episode(item)
        ]
        evidence = self._normalize_report_evidence(
            self._rank_question_evidence(
                discourse_episodes,
                question_text=question_text,
                report_title=report_title,
                metric=metric,
                stance_by_agent=stance_by_agent,
                limit=limit,
            ),
            stance_by_agent=stance_by_agent,
        )

        named_snippets: list[dict[str, Any]] = []
        seen_agents: set[str] = set()
        for desired_stance in ("support", "dissent", "neutral"):
            for item in evidence:
                actor_name = str(item.get("agent_name") or item.get("actor_name") or "").strip()
                stance = str(item.get("stance") or item.get("stance_class") or "").strip().lower()
                if not actor_name or actor_name in seen_agents or stance != desired_stance:
                    continue
                seen_agents.add(actor_name)
                named_snippets.append(
                    {
                        "actor_name": actor_name,
                        "actor_agent_id": item.get("agent_id") or item.get("actor_agent_id"),
                        "snippet": str(item.get("quote") or item.get("content") or "")[:280],
                        "title": item.get("title"),
                        "stance": stance or None,
                    }
                )
                break

        for item in evidence:
            actor_name = str(item.get("agent_name") or item.get("actor_name") or "").strip()
            if not actor_name or actor_name in seen_agents:
                continue
            seen_agents.add(actor_name)
            named_snippets.append(
                {
                    "actor_name": actor_name,
                    "actor_agent_id": item.get("agent_id") or item.get("actor_agent_id"),
                    "snippet": str(item.get("quote") or item.get("content") or "")[:280],
                    "title": item.get("title"),
                    "stance": str(item.get("stance") or item.get("stance_class") or "").strip().lower() or None,
                }
            )
            if len(named_snippets) >= 3:
                break

        metric_payload = deepcopy(metric) if isinstance(metric, dict) else {}
        if metric_payload:
            initial_value = metric_payload.get("initial_value")
            final_value = metric_payload.get("final_value")
            threshold = metric_payload.get("threshold")
            crossed_threshold = None
            if isinstance(initial_value, (int, float)) and isinstance(final_value, (int, float)) and isinstance(threshold, (int, float)):
                crossed_threshold = initial_value < threshold <= final_value or initial_value > threshold >= final_value
            metric_payload["crossed_threshold"] = crossed_threshold

        return {
            "question_profile": {
                "question": question_text,
                "question_type": question_type,
                "report_title": report_title,
                "keywords": self._keywords(question_text),
                "metric_name": str(metric_payload.get("metric_name") or "").strip() or None,
                "metric_label": str(metric_payload.get("metric_label") or "").strip() or None,
                "aliases": [
                    value
                    for value in [
                        report_title,
                        question_text,
                        str(metric_payload.get("metric_label") or "").strip(),
                        str(metric_payload.get("metric_name") or "").strip(),
                    ]
                    if value
                ],
            },
            "metric_movement": metric_payload,
            "top_discourse_evidence": evidence,
            "named_agent_snippets": named_snippets,
        }

    def _search_zep_context(
        self,
        simulation_id: str,
        query: str,
        limit: int,
        *,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        sync_state = self._ensure_zep_synced(simulation_id)
        owner_id, zep_user_id, _thread_id = self._zep_ids_for_session(simulation_id)
        episodes_payload = self.zep.graph_search(
            user_id=zep_user_id,
            query=query or "simulation context",
            scope="episodes",
            limit=max(limit * 3, 8),
        )
        edges_payload = self.zep.graph_search(
            user_id=zep_user_id,
            query=query or "simulation context",
            scope="edges",
            limit=max(limit * 2, 6),
        )
        del owner_id  # Avoid unused variable noise when auth data is unavailable.

        episodes = [self._parse_zep_episode(item) for item in list(episodes_payload.get("episodes") or [])]
        edges = [self._parse_zep_edge(item) for item in list(edges_payload.get("edges") or [])]
        combined = [item for item in [*episodes, *edges] if item.get("content")]
        if agent_id is not None:
            combined = [
                item
                for item in combined
                if str(item.get("actor_agent_id") or item.get("agent_id") or "") == agent_id
                or str(item.get("target_agent_id") or "") == agent_id
            ]
        checkpoint_records = [
            item
            for item in combined
            if str(item.get("source_kind") or "").strip().lower() == "checkpoint"
        ]
        discourse_episodes = [
            item
            for item in combined
            if str(item.get("source_kind") or "").strip().lower() != "checkpoint"
        ]
        return {
            "episodes": discourse_episodes[: max(1, int(limit))],
            "checkpoint_records": checkpoint_records[: max(1, int(limit))],
            "synced_events": int(sync_state.get("synced_events", 0) or 0),
            "zep_context_used": True,
            "graphiti_context_used": False,
            "memory_backend": self._memory_backend,
        }

    def _ensure_zep_synced(self, simulation_id: str) -> dict[str, Any]:
        self.zep.ensure_enabled()
        owner_id, zep_user_id, thread_id = self._zep_ids_for_session(simulation_id)
        self.zep.ensure_user(user_id=zep_user_id, metadata={"app_user_id": owner_id, "session_id": simulation_id})
        self.zep.ensure_thread(user_id=zep_user_id, thread_id=thread_id)

        sync_state = self.store.get_memory_sync_state(simulation_id) or {}
        self._ensure_seed_synced(simulation_id, zep_user_id=zep_user_id, thread_id=thread_id, sync_state=sync_state)

        last_interaction_id = int(sync_state.get("last_interaction_id", 0) or 0)
        last_checkpoint_id = int(sync_state.get("last_checkpoint_id", 0) or 0)
        interactions = self.store.get_interactions_after_id(simulation_id, last_interaction_id)
        checkpoints = self.store.list_checkpoint_records_after_id(simulation_id, last_checkpoint_id)

        messages: list[dict[str, Any]] = []
        messages.extend(self._build_interaction_messages(simulation_id, interactions))
        messages.extend(self._build_checkpoint_messages(simulation_id, checkpoints))
        if messages:
            self.zep.add_messages(thread_id=thread_id, messages=messages)
            self._simulation_context_cache = {
                key: value
                for key, value in self._simulation_context_cache.items()
                if key[0] != simulation_id
            }

        next_interaction_id = max((int(item.get("id", 0) or 0) for item in interactions), default=last_interaction_id)
        next_checkpoint_id = max((int(item.get("id", 0) or 0) for item in checkpoints), default=last_checkpoint_id)
        synced_events = int(sync_state.get("synced_events", 0) or 0) + len(messages)
        self.store.save_memory_sync_state(
            simulation_id,
            last_interaction_id=next_interaction_id,
            synced_events=synced_events,
            last_checkpoint_id=next_checkpoint_id,
        )
        return self.store.get_memory_sync_state(simulation_id) or {}

    def _ensure_seed_synced(
        self,
        simulation_id: str,
        *,
        zep_user_id: str,
        thread_id: str,
        sync_state: dict[str, Any],
    ) -> None:
        if int(sync_state.get("synced_events", 0) or 0) > 0:
            return
        artifact = self.store.get_knowledge_artifact(simulation_id) or {}
        messages = self._build_seed_messages(simulation_id, artifact)
        if messages:
            self.zep.ensure_user(user_id=zep_user_id, metadata={"session_id": simulation_id})
            self.zep.ensure_thread(user_id=zep_user_id, thread_id=thread_id)
            self.zep.add_messages(thread_id=thread_id, messages=messages)
        self.store.save_memory_sync_state(
            simulation_id,
            last_interaction_id=int(sync_state.get("last_interaction_id", 0) or 0),
            synced_events=int(sync_state.get("synced_events", 0) or 0) + len(messages),
            last_checkpoint_id=int(sync_state.get("last_checkpoint_id", 0) or 0),
        )
        self._simulation_context_cache = {
            key: value
            for key, value in self._simulation_context_cache.items()
            if key[0] != simulation_id
        }

    def _zep_ids_for_session(self, simulation_id: str) -> tuple[str, str, str]:
        session = self.store.get_console_session(simulation_id) or {}
        owner_id = str(session.get("user_id") or simulation_id).strip() or simulation_id
        zep_user_id = f"miroworld::{owner_id}::{simulation_id}"
        thread_id = f"session::{simulation_id}"
        return owner_id, zep_user_id, thread_id

    def _build_seed_messages(self, simulation_id: str, artifact: dict[str, Any]) -> list[dict[str, Any]]:
        summary = str(
            artifact.get("summary")
            or artifact.get("subject_summary")
            or artifact.get("neutral_summary")
            or ""
        ).strip()
        if not summary:
            return []

        messages: list[dict[str, Any]] = [
            {
                "name": "Knowledge Seed",
                "role": "tool",
                "content": "\n".join(
                    [
                        "KIND: seed_summary",
                        f"SESSION_ID: {simulation_id}",
                        f"SUMMARY: {summary}",
                    ]
                ),
            }
        ]

        nodes = list(artifact.get("nodes") or [])
        if nodes:
            facts: list[str] = []
            for node in nodes[:20]:
                label = str(node.get("label") or "").strip()
                description = str(node.get("description") or node.get("summary") or "").strip()
                if not label:
                    continue
                if description:
                    facts.append(f"- {label}: {description}")
                else:
                    facts.append(f"- {label}")
            if facts:
                messages.append(
                    {
                        "name": "Knowledge Graph",
                        "role": "tool",
                        "content": "\n".join(
                            [
                                "KIND: seed_graph",
                                f"SESSION_ID: {simulation_id}",
                                "FACTS:",
                                *facts,
                            ]
                        ),
                    }
                )
        return messages

    def _build_interaction_messages(
        self,
        simulation_id: str,
        interactions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not interactions:
            return []
        agents = {
            str(agent.get("agent_id") or ""): agent
            for agent in self.store.get_agents(simulation_id)
        }
        messages: list[dict[str, Any]] = []
        for item in interactions:
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            actor_agent_id = str(item.get("actor_agent_id") or "").strip()
            actor_persona = agents.get(actor_agent_id, {})
            actor_name = self._safe_agent_name(actor_agent_id, actor_persona)
            source_kind = self._interaction_source_kind(item)
            messages.append(
                {
                    "name": actor_name,
                    "role": "assistant",
                    "content": "\n".join(
                        [
                            f"KIND: {source_kind}",
                            f"SOURCE_ID: interaction:{item.get('id')}",
                            f"SESSION_ID: {simulation_id}",
                            f"ROUND_NO: {int(item.get('round_no', 0) or 0)}",
                            f"ACTOR_AGENT_ID: {actor_agent_id}",
                            f"ACTOR_NAME: {actor_name}",
                            f"TARGET_AGENT_ID: {str(item.get('target_agent_id') or '').strip()}",
                            f"EVENT_TYPE: {str(item.get('action_type') or '').strip()}",
                            f"TITLE: {str(item.get('title') or '').strip()}",
                            f"CONTENT: {content}",
                        ]
                    ),
                }
            )
        return messages

    def _build_checkpoint_messages(
        self,
        simulation_id: str,
        checkpoints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not checkpoints:
            return []
        agents = {
            str(agent.get("agent_id") or ""): agent
            for agent in self.store.get_agents(simulation_id)
        }
        messages: list[dict[str, Any]] = []
        for item in checkpoints:
            agent_id = str(item.get("agent_id") or "").strip()
            persona = agents.get(agent_id, {})
            agent_name = self._safe_agent_name(agent_id, persona)
            messages.append(
                {
                    "name": agent_name,
                    "role": "tool",
                    "content": "\n".join(
                        [
                            "KIND: checkpoint",
                            f"SOURCE_ID: checkpoint:{item.get('id')}",
                            f"SESSION_ID: {simulation_id}",
                            f"CHECKPOINT_KIND: {str(item.get('checkpoint_kind') or '').strip()}",
                            f"AGENT_ID: {agent_id}",
                            f"AGENT_NAME: {agent_name}",
                            f"STANCE_CLASS: {str(item.get('stance_class') or '').strip()}",
                            f"STANCE_SCORE: {str(item.get('stance_score') or '').strip()}",
                            f"PRIMARY_DRIVER: {str(item.get('primary_driver') or '').strip()}",
                            f"METRIC_ANSWERS: {self._format_metric_answers(item.get('metric_answers'))}",
                        ]
                    ),
                }
            )
        return messages

    def _parse_zep_episode(self, item: dict[str, Any]) -> dict[str, Any]:
        return self._parse_structured_zep_content(
            item,
            content=str(item.get("content") or "").strip(),
            fallback_source_kind="episode",
            fallback_score=float(item.get("score") or item.get("relevance") or 0.0),
        )

    def _parse_zep_edge(self, item: dict[str, Any]) -> dict[str, Any]:
        fact = str(item.get("fact") or item.get("name") or "").strip()
        return {
            "content": fact,
            "title": str(item.get("name") or "").strip(),
            "score": float(item.get("score") or item.get("relevance") or 0.0),
            "source_kind": "graph_edge",
            "source_label": "Graph fact",
            "created_at": item.get("created_at"),
        }

    def _parse_structured_zep_content(
        self,
        item: dict[str, Any],
        *,
        content: str,
        fallback_source_kind: str,
        fallback_score: float,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content": content,
            "score": fallback_score,
            "source_kind": fallback_source_kind,
            "created_at": item.get("created_at"),
            "episode_uuid": item.get("uuid"),
        }
        for line in content.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized = key.strip().lower()
            payload[normalized] = value.strip()

        source_kind = str(payload.get("kind") or payload.get("source_kind") or fallback_source_kind).strip().lower()
        actor_agent_id = str(payload.get("actor_agent_id") or payload.get("agent_id") or "").strip()
        actor_name = str(payload.get("actor_name") or payload.get("agent_name") or item.get("name") or actor_agent_id or "").strip()
        round_no = payload.get("round_no")
        try:
            round_no = int(round_no) if round_no not in {None, ""} else None
        except (TypeError, ValueError):
            round_no = None
        parsed_content = str(payload.get("content") or "").strip()
        if parsed_content.lower().startswith("kind:"):
            parsed_content = content

        return {
            "content": parsed_content,
            "title": str(payload.get("title") or "").strip(),
            "score": float(payload.get("score") or fallback_score or 0.0),
            "source_kind": source_kind,
            "event_type": str(payload.get("event_type") or "").strip().lower() or None,
            "source_label": self._source_label_for_kind(source_kind, actor_name),
            "created_at": item.get("created_at"),
            "episode_uuid": item.get("uuid"),
            "round_no": round_no,
            "actor_agent_id": actor_agent_id or None,
            "target_agent_id": str(payload.get("target_agent_id") or "").strip() or None,
            "agent_id": actor_agent_id or None,
            "actor_name": actor_name or None,
            "agent_name": actor_name or None,
            "post_id": str(payload.get("source_id") or "").strip() or None,
            "thread_id": str(payload.get("source_id") or "").strip() or None,
            "stance_class": str(payload.get("stance_class") or "").strip().lower() or None,
            "primary_driver": str(payload.get("primary_driver") or "").strip() or None,
            "metric_answers": str(payload.get("metric_answers") or "").strip() or None,
            "checkpoint_kind": str(payload.get("checkpoint_kind") or "").strip().lower() or None,
        }

    def _interaction_source_kind(self, item: dict[str, Any]) -> str:
        action_type = str(item.get("action_type") or "").strip().lower()
        if action_type == "comment":
            return "comment"
        if action_type == "reply":
            return "reply"
        return "post"

    def _safe_agent_name(self, agent_id: str, agent: dict[str, Any]) -> str:
        persona = dict(agent.get("persona") or {}) if isinstance(agent, dict) else {}
        display_name = str(persona.get("display_name") or agent_id or "Agent").strip()
        return display_name or agent_id or "Agent"

    def _source_label_for_kind(self, source_kind: str, actor_name: str) -> str:
        normalized = str(source_kind or "").strip().lower()
        if normalized == "checkpoint":
            return "Checkpoint"
        if normalized == "comment":
            return f"Comment by {actor_name or 'Unknown agent'}"
        if normalized == "reply":
            return f"Reply by {actor_name or 'Unknown agent'}"
        if normalized == "post":
            return f"Post by {actor_name or 'Unknown agent'}"
        if normalized == "seed_summary":
            return "Seed summary"
        if normalized == "seed_graph":
            return "Seed graph"
        return actor_name or "Episode"

    def _search_local_context(
        self,
        simulation_id: str,
        query: str,
        limit: int,
        *,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        query_terms = self._ordered_query_terms(query)
        fts_query = self._build_fts_query(query_terms)
        candidate_limit = max(limit * 4, 16)
        if fts_query:
            interactions = self.store.search_interactions_fts(simulation_id, fts_query, limit=candidate_limit)
            transcripts = self.store.search_interaction_transcripts_fts(simulation_id, fts_query, limit=candidate_limit)
        else:
            interactions = self._get_cached_interactions(simulation_id)
            transcripts = self._get_cached_transcripts(simulation_id)
        interactions = self._filter_agent_interactions(interactions, agent_id=agent_id)
        transcripts = self._filter_agent_transcripts(transcripts, agent_id=agent_id)

        episodes = self._rank_local_episodes(
            interactions=interactions,
            transcripts=transcripts,
            query_terms=query_terms,
            agent_id=agent_id,
            limit=limit,
        )
        if not episodes and fts_query:
            episodes = self._rank_local_episodes(
                interactions=self._filter_agent_interactions(
                    self._get_cached_interactions(simulation_id),
                    agent_id=agent_id,
                ),
                transcripts=self._filter_agent_transcripts(
                    self._get_cached_transcripts(simulation_id),
                    agent_id=agent_id,
                ),
                query_terms=query_terms,
                agent_id=agent_id,
                limit=limit,
            )
        checkpoint_records = self._get_cached_checkpoint_records(simulation_id, agent_id=agent_id)
        return {
            "episodes": episodes[:limit],
            "checkpoint_records": checkpoint_records,
            "synced_events": 0,
            "zep_context_used": False,
            "graphiti_context_used": False,
            "memory_backend": self._memory_backend,
        }

    def _rank_local_episodes(
        self,
        *,
        interactions: list[dict[str, Any]],
        transcripts: list[dict[str, Any]],
        query_terms: list[str],
        agent_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        ranked: list[tuple[float, float, int, int, dict[str, Any]]] = []

        for interaction in interactions:
            content = str(interaction.get("content") or "").strip()
            if not content:
                continue
            score = self._score_episode_text(
                content,
                query_terms,
                source_kind="interaction",
                agent_id=agent_id,
                actor_agent_id=str(interaction.get("actor_agent_id") or ""),
                target_agent_id=str(interaction.get("target_agent_id") or ""),
            )
            if query_terms and score <= 0:
                continue
            ranked.append((score, self._fts_priority(interaction.get("fts_rank")), 2, int(interaction.get("id", 0) or 0), {
                "content": content,
                "score": float(score),
                "created_at": interaction.get("created_at"),
                "uuid": str(interaction.get("id") or ""),
                "source_kind": "interaction",
                "round_no": interaction.get("round_no"),
                "actor_agent_id": interaction.get("actor_agent_id"),
                "target_agent_id": interaction.get("target_agent_id"),
                "action_type": interaction.get("action_type"),
            }))

        for transcript in transcripts:
            content = str(transcript.get("content") or "").strip()
            if not content:
                continue
            score = self._score_episode_text(
                content,
                query_terms,
                source_kind="transcript",
                agent_id=agent_id,
                transcript_agent_id=str(transcript.get("agent_id") or ""),
                channel=str(transcript.get("channel") or ""),
                role=str(transcript.get("role") or ""),
            )
            if query_terms and score <= 0:
                continue
            ranked.append((score, self._fts_priority(transcript.get("fts_rank")), 1, int(transcript.get("id", 0) or 0), {
                "content": content,
                "score": float(score),
                "created_at": transcript.get("created_at"),
                "uuid": str(transcript.get("id") or ""),
                "source_kind": "transcript",
                "channel": transcript.get("channel"),
                "role": transcript.get("role"),
                "agent_id": transcript.get("agent_id"),
            }))

        if not ranked:
            fallback_candidates: list[dict[str, Any]] = []
            for interaction in interactions:
                content = str(interaction.get("content") or "").strip()
                if content:
                    fallback_candidates.append({
                        "content": content,
                        "score": 0.0,
                        "created_at": interaction.get("created_at"),
                        "uuid": str(interaction.get("id") or ""),
                        "source_kind": "interaction",
                        "round_no": interaction.get("round_no"),
                        "actor_agent_id": interaction.get("actor_agent_id"),
                        "target_agent_id": interaction.get("target_agent_id"),
                        "action_type": interaction.get("action_type"),
                    })
            for transcript in transcripts:
                content = str(transcript.get("content") or "").strip()
                if content:
                    fallback_candidates.append({
                        "content": content,
                        "score": 0.0,
                        "created_at": transcript.get("created_at"),
                        "uuid": str(transcript.get("id") or ""),
                        "source_kind": "transcript",
                        "channel": transcript.get("channel"),
                        "role": transcript.get("role"),
                        "agent_id": transcript.get("agent_id"),
                    })
            fallback_candidates.sort(
                key=lambda item: (
                    int(item.get("uuid", "0") or 0),
                    1 if item.get("source_kind") == "interaction" else 0,
                ),
                reverse=True,
            )
            return fallback_candidates[:limit]

        ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
        return [item[4] for item in ranked[:limit]]

    def _score_episode_text(
        self,
        content: str,
        query_terms: list[str],
        *,
        source_kind: str,
        agent_id: str | None = None,
        actor_agent_id: str | None = None,
        target_agent_id: str | None = None,
        transcript_agent_id: str | None = None,
        channel: str | None = None,
        role: str | None = None,
    ) -> float:
        lowered = content.lower()
        score = 0.0
        for index, term in enumerate(query_terms):
            if term in lowered:
                score += float((len(query_terms) - index) * 10)

        if agent_id:
            if actor_agent_id == agent_id or target_agent_id == agent_id or transcript_agent_id == agent_id:
                score += 6.0

        if source_kind == "interaction":
            score += 2.0
        elif source_kind == "transcript":
            score += 1.0

        if channel and channel.lower() in {"agent_chat", "group_chat", "report_agent"}:
            score += 0.5
        if role and role.lower() == "assistant":
            score += 0.25
        return score

    def _format_episode_excerpt(self, episodes: list[dict[str, Any]], limit: int = 6) -> str:
        lines: list[str] = []
        for item in episodes[: max(1, int(limit))]:
            source_kind = str(item.get("source_kind") or "episode")
            content = self._truncate_text(str(item.get("content") or ""), 260)
            if source_kind == "interaction":
                round_no = item.get("round_no")
                action_type = str(item.get("action_type") or "event").strip().lower() or "event"
                actor = str(item.get("actor_agent_id") or "unknown")
                target = str(item.get("target_agent_id") or "none")
                lines.append(f"round {round_no} {action_type} {actor}->{target}: {content}")
            elif source_kind == "transcript":
                channel = str(item.get("channel") or "transcript")
                role = str(item.get("role") or "message")
                agent = str(item.get("agent_id") or "none")
                lines.append(f"{channel} {role} {agent}: {content}")
            else:
                lines.append(content)
        return "\n".join(lines)

    def _format_recent_memory_excerpt(self, memories: list[dict[str, Any]], limit: int = 8) -> str:
        lines = [
            f"- round {item['round_no']} {item['action_type']}: {item.get('content', '')}"
            for item in reversed(memories[-max(1, int(limit)) :])
        ]
        return "\n".join(lines)

    def _format_agent_activity_excerpt(
        self,
        memories: list[dict[str, Any]],
        *,
        agent_id: str,
        limit: int = 8,
    ) -> str:
        lines: list[str] = []
        for item in reversed(memories[-max(1, int(limit)) :]):
            round_no = item.get("round_no")
            action_label = str(item.get("action_type") or "event").strip().lower().replace("_", " ") or "event"
            content = self._truncate_text(str(item.get("content") or ""), 220)
            actor = str(item.get("actor_agent_id") or "unknown")
            target = str(item.get("target_agent_id") or "").strip()
            if actor == agent_id:
                if target:
                    lines.append(f"Round {round_no}: Your {action_label} to {target}: \"{content}\"")
                else:
                    lines.append(f"Round {round_no}: Your {action_label}: \"{content}\"")
            elif target == agent_id:
                lines.append(f"Round {round_no}: {actor}'s {action_label} to you: \"{content}\"")
            else:
                lines.append(f"Round {round_no}: {actor}'s {action_label}: \"{content}\"")
        return "\n".join(lines)

    def _format_checkpoint_line(self, record: dict[str, Any]) -> str:
        checkpoint_kind = str(record.get("checkpoint_kind") or "checkpoint").strip().lower() or "checkpoint"
        agent = str(record.get("agent_id") or "unknown")
        stance_score = float(record.get("stance_score", 0) or 0)
        stance_class = str(record.get("stance_class") or "neutral").strip().lower() or "neutral"
        confidence = float(record.get("confidence", 0) or 0)
        primary_driver = self._truncate_text(str(record.get("primary_driver") or "unspecified"), 140)
        metric_summary = self._format_metric_answers(record.get("metric_answers"))
        return (
            f"{checkpoint_kind}: agent={agent}, stance={stance_score:.2f} ({stance_class}), "
            f"confidence={confidence:.2f}, driver={primary_driver}, metrics={metric_summary}"
        )

    def _get_cached_interactions(self, simulation_id: str) -> list[dict[str, Any]]:
        cached = self._interaction_cache.get(simulation_id)
        if cached is None:
            cached = self.store.get_interactions(simulation_id)
            self._interaction_cache[simulation_id] = cached
        return cached

    def _get_cached_transcripts(self, simulation_id: str) -> list[dict[str, Any]]:
        cached = self._transcript_cache.get(simulation_id)
        if cached is None:
            cached = self.store.get_interaction_transcripts(simulation_id)
            self._transcript_cache[simulation_id] = cached
        return cached

    def _get_cached_checkpoint_records(
        self,
        simulation_id: str,
        *,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        cached = self._checkpoint_cache.get(simulation_id)
        if cached is None:
            cached = self.store.list_checkpoint_records(simulation_id)
            self._checkpoint_cache[simulation_id] = cached
        records = cached
        if agent_id is not None:
            records = [record for record in records if str(record.get("agent_id") or "") == agent_id]
        records = sorted(
            records,
            key=lambda record: (
                0
                if str(record.get("checkpoint_kind") or "").strip().lower() in {"final", "post"}
                else 1
                if str(record.get("checkpoint_kind") or "").strip().lower() == "baseline"
                else 2
            ),
        )
        return [
            {
                **record,
                "source_kind": "checkpoint",
            }
            for record in records
        ]

    def _filter_agent_interactions(
        self,
        interactions: list[dict[str, Any]],
        *,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if agent_id is None:
            return interactions
        return [
            interaction
            for interaction in interactions
            if str(interaction.get("actor_agent_id") or "") == agent_id
            or str(interaction.get("target_agent_id") or "") == agent_id
        ]

    def _filter_agent_transcripts(
        self,
        transcripts: list[dict[str, Any]],
        *,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if agent_id is None:
            return transcripts
        return [
            transcript
            for transcript in transcripts
            if str(transcript.get("agent_id") or "") == agent_id
        ]

    def _ordered_query_terms(self, query: str) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for token in re.findall(r"[a-z0-9]+", str(query or "").lower()):
            cleaned = token.strip()
            if len(cleaned) < 3 or cleaned in seen:
                continue
            seen.add(cleaned)
            ordered.append(cleaned)
        return ordered

    def _build_fts_query(self, query_terms: list[str]) -> str:
        if not query_terms:
            return ""
        return " OR ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in query_terms)

    def _fts_priority(self, raw_rank: Any) -> float:
        try:
            return -float(raw_rank)
        except (TypeError, ValueError):
            return 0.0

    def _format_metric_answers(self, metric_answers: Any) -> str:
        if not isinstance(metric_answers, dict) or not metric_answers:
            return "none"
        parts = [f"{key}={value}" for key, value in sorted(metric_answers.items())]
        return ", ".join(parts)

    def _truncate_text(self, value: str, limit: int) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 3)].rstrip()}..."

    def _normalize_report_evidence(
        self,
        episodes: list[dict[str, Any]],
        *,
        stance_by_agent: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in episodes:
            quote = str(item.get("content") or "").strip()
            if not quote:
                continue
            agent_id = str(item.get("actor_agent_id") or item.get("agent_id") or "").strip()
            agent_name = str(item.get("actor_name") or item.get("agent_name") or agent_id or "Unknown agent").strip()
            source_kind = str(item.get("source_kind") or "").strip().lower()
            event_type = str(item.get("event_type") or "").strip().lower()
            source_type = "comment" if source_kind in {"comment", "reply"} or event_type == "comment_created" else "post"
            source_label = str(item.get("source_label") or "").strip()
            if not source_label:
                source_label = f"{'Comment' if source_type == 'comment' else 'Post'} by {agent_name or 'Unknown agent'}"
            stance_class = self._normalize_stance_label(
                item.get("stance") or item.get("stance_class") or (stance_by_agent or {}).get(agent_id)
            )
            normalized.append(
                {
                    "agent_id": agent_id,
                    "agent_name": agent_name or agent_id or "Unknown agent",
                    "quote": quote,
                    "content": quote,
                    "title": str(item.get("title") or "").strip(),
                    "source_kind": source_kind,
                    "source_type": source_type,
                    "source_label": source_label,
                    "round_no": int(item.get("round_no") or 0),
                    "post_id": str(item.get("post_id") or item.get("thread_id") or "").strip(),
                    "engagement": float(item.get("engagement") or item.get("likes") or 0.0),
                    "stance": stance_class,
                    "stance_class": stance_class,
                }
            )
        return normalized

    def _keywords(self, question_text: str) -> list[str]:
        tokens = [token.strip(".,!?;:()[]{}").lower() for token in str(question_text or "").split()]
        seen: set[str] = set()
        ordered: list[str] = []
        for token in tokens:
            if len(token) < 4 or token in seen:
                continue
            seen.add(token)
            ordered.append(token)
        return ordered

    def _rank_question_evidence(
        self,
        episodes: list[dict[str, Any]],
        *,
        question_text: str,
        report_title: str,
        metric: dict[str, Any] | None,
        stance_by_agent: dict[str, str] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        metric_terms = ""
        if isinstance(metric, dict):
            metric_terms = " ".join(
                value
                for value in [
                    str(metric.get("metric_name") or "").strip(),
                    str(metric.get("metric_label") or "").strip(),
                ]
                if value
            )
        keywords = set(self._keywords(f"{report_title} {question_text} {metric_terms}"))
        scored_rows: list[tuple[tuple[float, float, float, float], dict[str, Any]]] = []
        seen_tree_counts: dict[str, int] = {}
        seen_agent_counts: dict[str, int] = {}
        total = max(1, len(episodes))
        for index, item in enumerate(episodes):
            content = str(item.get("content") or "")
            title = str(item.get("title") or "")
            haystack = f"{title} {content}".lower()
            overlap = float(sum(1 for keyword in keywords if keyword in haystack))
            retrieval_rank = 1.0 - (index / total)
            engagement = float(item.get("engagement") or item.get("likes") or item.get("score") or 0.0)
            recency = 1.0 if str(item.get("created_at") or "").strip() else 0.0
            tree_id = str(item.get("post_id") or item.get("thread_id") or item.get("title") or "")
            actor_agent_id = str(item.get("actor_agent_id") or item.get("agent_id") or "")
            score = (retrieval_rank, overlap, engagement, recency)
            seen_tree_counts.setdefault(tree_id, 0)
            seen_agent_counts.setdefault(actor_agent_id, 0)
            scored_rows.append((score, item))

        ranked = sorted(scored_rows, key=lambda row: row[0], reverse=True)
        selected: list[dict[str, Any]] = []
        for desired_stance in ("support", "dissent", "neutral"):
            if len(selected) >= max(1, int(limit)):
                break
            for _score, item in ranked:
                if self._resolve_episode_stance(item, stance_by_agent) != desired_stance:
                    continue
                tree_id = str(item.get("post_id") or item.get("thread_id") or item.get("title") or "")
                actor_agent_id = str(item.get("actor_agent_id") or item.get("agent_id") or "")
                if tree_id and seen_tree_counts[tree_id] >= 2:
                    continue
                if actor_agent_id and seen_agent_counts[actor_agent_id] >= 2:
                    continue
                if item in selected:
                    continue
                if tree_id:
                    seen_tree_counts[tree_id] += 1
                if actor_agent_id:
                    seen_agent_counts[actor_agent_id] += 1
                selected.append(item)
                break

        for _score, item in ranked:
            tree_id = str(item.get("post_id") or item.get("thread_id") or item.get("title") or "")
            actor_agent_id = str(item.get("actor_agent_id") or item.get("agent_id") or "")
            if item in selected:
                continue
            if tree_id and seen_tree_counts[tree_id] >= 2:
                continue
            if actor_agent_id and seen_agent_counts[actor_agent_id] >= 2:
                continue
            if tree_id:
                seen_tree_counts[tree_id] += 1
            if actor_agent_id:
                seen_agent_counts[actor_agent_id] += 1
            selected.append(item)
            if len(selected) >= max(1, int(limit)):
                break
        return selected

    def _build_agent_stance_map(
        self,
        session_id: str,
        *,
        metric: dict[str, Any] | None,
    ) -> dict[str, str]:
        records = self.store.list_checkpoint_records(session_id, checkpoint_kind="final")
        if not records:
            records = self.store.list_checkpoint_records(session_id, checkpoint_kind="post")
        if not records:
            records = self.store.list_checkpoint_records(session_id)

        metric_candidates = {
            self._metric_key(str(metric.get("metric_name") or "")) if isinstance(metric, dict) else "",
            self._metric_key(str(metric.get("metric_label") or "")) if isinstance(metric, dict) else "",
        } - {""}

        stances: dict[str, str] = {}
        for record in records:
            agent_id = str(record.get("agent_id") or "").strip()
            if not agent_id:
                continue
            score = self._checkpoint_metric_score(record, metric_candidates=metric_candidates)
            stance = self._normalize_stance_label(record.get("stance_class"))
            if score is not None:
                stance = self._stance_from_score(score)
            if stance:
                stances[agent_id] = stance
        return stances

    def _checkpoint_metric_score(
        self,
        record: dict[str, Any],
        *,
        metric_candidates: set[str],
    ) -> float | None:
        answers = record.get("metric_answers")
        if isinstance(answers, dict) and metric_candidates:
            for key, value in answers.items():
                if self._metric_key(key) not in metric_candidates:
                    continue
                parsed = self._extract_metric_score(value)
                if parsed is not None:
                    return parsed
        stance_score = record.get("stance_score")
        try:
            if stance_score is not None:
                return 1.0 + (float(stance_score) * 9.0)
        except (TypeError, ValueError):
            return None
        return None

    def _extract_metric_score(self, value: Any) -> float | None:
        text = str(value or "").strip()
        if not text:
            return None
        lowered = text.lower()
        if lowered == "yes":
            return 10.0
        if lowered == "no":
            return 1.0
        match = re.match(r"(\d+(?:\.\d+)?)", text)
        if match is None:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    def _metric_key(self, value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()

    def _is_discourse_episode(self, item: dict[str, Any]) -> bool:
        source_kind = str(item.get("source_kind") or "").strip().lower()
        event_type = str(item.get("event_type") or "").strip().lower()
        if source_kind in {"post", "comment", "reply"}:
            return True
        return event_type in {"post_created", "comment_created"}

    def _normalize_stance_label(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"approve", "support", "supporter"}:
            return "support"
        if text in {"dissent", "dissenter", "oppose"}:
            return "dissent"
        if text == "neutral":
            return "neutral"
        return ""

    def _stance_from_score(self, score: float) -> str:
        if score >= 7.0:
            return "support"
        if score < 5.0:
            return "dissent"
        return "neutral"

    def _resolve_episode_stance(
        self,
        item: dict[str, Any],
        stance_by_agent: dict[str, str] | None,
    ) -> str:
        direct = self._normalize_stance_label(item.get("stance") or item.get("stance_class"))
        if direct:
            return direct
        agent_id = str(item.get("actor_agent_id") or item.get("agent_id") or "").strip()
        if agent_id:
            mapped = self._normalize_stance_label((stance_by_agent or {}).get(agent_id))
            if mapped:
                return mapped
        return "neutral"

    def _local_fallback_agent_response(
        self,
        agent_id: str,
        agent: dict[str, Any],
        message: str,
        memories: list[dict[str, Any]],
        context_episodes: list[dict[str, Any]],
        checkpoint_records: list[dict[str, Any]],
    ) -> str:
        latest_memory = ""
        if memories:
            latest_memory = str(memories[-1].get("content", "")).strip()
        elif context_episodes:
            latest_memory = str(context_episodes[0].get("content", "")).strip()

        planning_area = str(agent.get("persona", {}).get("planning_area", "my area"))
        checkpoint_summary = self._fallback_checkpoint_summary(checkpoint_records)
        if latest_memory or checkpoint_summary:
            evidence_parts: list[str] = []
            if latest_memory:
                evidence_parts.append(f'my recent activity said "{latest_memory}"')
            if checkpoint_summary:
                evidence_parts.append(checkpoint_summary)
            evidence_text = " and ".join(evidence_parts)
            return (
                f"As {agent_id} from {planning_area}, my view is grounded in {evidence_text}. "
                f'On "{message}", that remains my main concern.'
            )
        return (
            f"As {agent_id} from {planning_area}, I do not have enough stored context yet. "
            f"On \"{message}\", I would focus on affordability and neighborhood-level trade-offs."
        )

    def _fallback_checkpoint_summary(self, checkpoint_records: list[dict[str, Any]]) -> str:
        if not checkpoint_records:
            return ""

        final_record = next(
            (
                record
                for record in checkpoint_records
                if str(record.get("checkpoint_kind") or "").strip().lower() in {"final", "post"}
            ),
            None,
        )
        baseline_record = next(
            (
                record
                for record in checkpoint_records
                if str(record.get("checkpoint_kind") or "").strip().lower() == "baseline"
            ),
            None,
        )
        chosen = final_record or baseline_record or checkpoint_records[0]
        driver = self._truncate_text(str(chosen.get("primary_driver") or "unspecified"), 100)
        stance = str(chosen.get("stance_class") or "neutral").strip().lower() or "neutral"
        metrics = self._format_metric_answers(chosen.get("metric_answers"))
        return f"my {chosen.get('checkpoint_kind', 'checkpoint')} checkpoint was {stance} with driver {driver} and metrics {metrics}"
