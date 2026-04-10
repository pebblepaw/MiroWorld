from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from mckainsey.config import Settings
from mckainsey.services.llm_client import GeminiChatClient
from mckainsey.services.storage import SimulationStore


class MemoryService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self.store = SimulationStore(settings.simulation_db_path)
        self.llm = GeminiChatClient(settings)
        self._simulation_context_cache: dict[tuple[str, str, int, bool, str], dict[str, Any]] = {}
        self._interaction_cache: dict[str, list[dict[str, Any]]] = {}
        self._transcript_cache: dict[str, list[dict[str, Any]]] = {}
        self._checkpoint_cache: dict[str, list[dict[str, Any]]] = {}
        self._memory_backend = "sqlite"

    def sync_simulation(self, simulation_id: str) -> dict[str, Any]:
        # The simulation data already lives in SQLite. Legacy sync endpoints are
        # preserved for compatibility but no longer push to an external store.
        return {
            "simulation_id": simulation_id,
            "synced_events": 0,
            "zep_enabled": False,
            "external_sync_enabled": False,
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

        local_context = self._search_local_context(
            simulation_id,
            normalized_query,
            normalized_limit,
            agent_id=agent_id,
        )
        self._simulation_context_cache[cache_key] = deepcopy(local_context)
        return local_context

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
            "zep_context_used": False,
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
        prompt = (
            f"You are persona agent {agent_id} from McKAInsey simulation {simulation_id}.\n"
            "## Your Profile\n"
            f"{agent['persona']}\n\n"
            "## Your Checkpoint Responses\n"
            f"{checkpoint_excerpt or '- none'}\n\n"
            "## Your Social Media Activity (Most Recent First)\n"
            f"{activity_excerpt or '- none'}\n\n"
            f"## Key Discussions You Participated In ({memory_context.get('memory_backend', self._memory_backend)})\n"
            f"{context_excerpt or '- none'}\n\n"
            f"User question: {message}\n"
            "Answer in-character in 3-5 sentences, grounded only in the memories above."
        )

        if self.llm.is_enabled():
            response = self.llm.complete_required(
                prompt,
                system_prompt="You are a simulated Singapore persona agent. Stay grounded in supplied memory.",
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
            "zep_context_used": False,
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
