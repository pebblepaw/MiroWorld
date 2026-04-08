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
        self._graphiti_search_timeout_seconds = max(20, int(os.getenv("GRAPHITI_SEARCH_TIMEOUT_SECONDS", "90")))
        self._graphiti_sync_batch_size = max(0, int(os.getenv("GRAPHITI_SYNC_BATCH_SIZE", "2")))
        self._graphiti_sync_scan_limit = max(
            1,
            int(os.getenv("GRAPHITI_SYNC_SCAN_LIMIT", str(max(120, self._graphiti_sync_batch_size * 6)))),
        )
        self._simulation_context_cache: dict[tuple[str, str, int, bool], dict[str, Any]] = {}
        self._interaction_cache: dict[str, list[dict[str, Any]]] = {}
        self._checkpoint_cache: dict[str, list[dict[str, Any]]] = {}

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
        normalized_query = " ".join(str(query or "").split())
        cache_key = (simulation_id, normalized_query.lower(), normalized_limit, live_mode)
        cached = self._simulation_context_cache.get(cache_key)
        if cached is not None:
            replay = dict(cached)
            replay["synced_events"] = 0
            return replay

        graphiti = self._search_graphiti_context(
            simulation_id,
            normalized_query,
            normalized_limit,
            live_mode=live_mode,
        )
        if graphiti is not None and graphiti.get("episodes"):
            self._simulation_context_cache[cache_key] = graphiti
            return graphiti

        if not live_mode and self._memory_backend_preference == "zep":
            zep_context = self._search_zep_context(simulation_id, query, normalized_limit)
            if zep_context is not None and zep_context.get("episodes"):
                self._simulation_context_cache[cache_key] = zep_context
                return zep_context

        if graphiti is not None:
            self._simulation_context_cache[cache_key] = graphiti
            return graphiti

        if live_mode:
            raise RuntimeError("Live memory search requires Graphiti and FalkorDB to be available.")

        # Non-live compatibility path for demos and local development only.
        local_context = self._search_local_context(simulation_id, query, normalized_limit)
        self._simulation_context_cache[cache_key] = local_context
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
        attempts = [query] if live_mode else [
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
            if result["episodes"] or live_mode:
                return result
        return {
            "episodes": [],
            "synced_events": 0,
            "zep_context_used": False,
            "graphiti_context_used": live_mode,
            "memory_backend": "graphiti" if live_mode else "local",
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
        live_evidence = self._build_live_agent_evidence(simulation_id, agent_id, message) if live_mode else {
            "interaction_lines": [],
            "checkpoint_lines": [],
        }

        agents = {agent["agent_id"]: agent for agent in self.store.get_agents(simulation_id)}
        agent = agents.get(agent_id)
        if not agent:
            raise RuntimeError(f"Agent not found in simulation: {agent_id}")

        context_excerpt = "\n".join(
            f"- {item['content']}"
            for item in memory_context["episodes"][:6]
        )
        live_interaction_excerpt = "\n".join(
            f"- {line}"
            for line in live_evidence.get("interaction_lines", [])
        )
        live_checkpoint_excerpt = "\n".join(
            f"- {line}"
            for line in live_evidence.get("checkpoint_lines", [])
        )
        memory_backend = str(memory_context.get("memory_backend", "local"))
        if live_mode:
            prompt = (
                f"You are persona agent {agent_id} from McKAInsey simulation {simulation_id}.\n"
                f"Persona profile: {agent['persona']}\n\n"
                f"Relevant memory search results ({memory_backend}):\n{context_excerpt or '- none'}\n\n"
                f"Agent interaction evidence (from simulation timeline):\n{live_interaction_excerpt or '- none'}\n\n"
                f"Checkpoint interview evidence:\n{live_checkpoint_excerpt or '- none'}\n\n"
                f"User question: {message}\n"
                "Answer in-character in 3-5 sentences, grounded in the available memory evidence above. "
                "If memory is sparse, stay consistent with the persona profile and the simulation context without inventing facts."
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
        memory_used = bool(
            memory_context["episodes"]
            if live_mode
            else (memories or memory_context["episodes"])
        )
        if live_mode:
            memory_used = memory_used or bool(live_evidence.get("interaction_lines") or live_evidence.get("checkpoint_lines"))
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
                raise RuntimeError("Live memory requires graphiti_core and a running FalkorDB instance.")
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
            results, synced_events = asyncio.run(
                asyncio.wait_for(_run(), timeout=float(self._graphiti_search_timeout_seconds))
            )
        except asyncio.TimeoutError as exc:
            if live_mode:
                raise RuntimeError(
                    f"Graphiti memory search timed out after {self._graphiti_search_timeout_seconds}s. "
                    "Check FalkorDB health and model provider status."
                ) from exc
            return None
        except Exception as exc:  # noqa: BLE001
            if live_mode:
                raise RuntimeError(f"Graphiti memory search failed: {exc}") from exc
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
        if self._graphiti_sync_batch_size <= 0:
            return 0

        sync_state = self.store.get_memory_sync_state(simulation_id) or {}
        last_interaction_id = int(sync_state.get("last_interaction_id", 0) or 0)
        last_checkpoint_id = int(sync_state.get("last_checkpoint_id", 0) or 0)
        previously_synced = int(sync_state.get("synced_events", 0) or 0)
        remaining = int(self._graphiti_sync_batch_size)
        synced_events = 0
        new_last_interaction_id = last_interaction_id
        new_last_checkpoint_id = last_checkpoint_id

        interaction_candidates = self.store.get_interactions_after_id(
            simulation_id,
            last_interaction_id,
            limit=self._graphiti_sync_scan_limit,
        )
        interaction_events: list[dict[str, Any]] = []
        for interaction in interaction_candidates:
            interaction_id = int(interaction.get("id", 0) or 0)
            new_last_interaction_id = max(new_last_interaction_id, interaction_id)
            if not self._is_memory_worthy_interaction(interaction):
                continue
            interaction_events.append(interaction)
            if len(interaction_events) >= remaining:
                break

        for interaction in interaction_events:
            await service.add_agent_memory(
                agent_id=str(interaction.get("actor_agent_id") or "unknown"),
                content=self._format_graphiti_episode(simulation_id, interaction),
                round_no=int(interaction.get("round_no", 0) or 0),
                timestamp=self._normalize_reference_time(interaction.get("created_at")),
            )
        synced_events += len(interaction_events)
        remaining -= len(interaction_events)

        checkpoint_events: list[dict[str, Any]] = []
        if remaining > 0:
            checkpoint_events = self.store.list_checkpoint_records_after_id(
                simulation_id,
                last_checkpoint_id,
                limit=remaining,
            )
            for checkpoint in checkpoint_events:
                checkpoint_id = int(checkpoint.get("id", 0) or 0)
                new_last_checkpoint_id = max(new_last_checkpoint_id, checkpoint_id)
                await service.add_agent_memory(
                    agent_id=str(checkpoint.get("agent_id") or "unknown"),
                    content=self._format_graphiti_checkpoint_episode(simulation_id, checkpoint),
                    round_no=int(checkpoint.get("round_no", 0) or 0),
                    timestamp=self._normalize_reference_time(checkpoint.get("created_at")),
                )
            synced_events += len(checkpoint_events)

        if (
            new_last_interaction_id != last_interaction_id
            or new_last_checkpoint_id != last_checkpoint_id
            or synced_events > 0
        ):
            self.store.save_memory_sync_state(
                simulation_id,
                last_interaction_id=new_last_interaction_id,
                last_checkpoint_id=new_last_checkpoint_id,
                synced_events=previously_synced + synced_events,
            )
        return synced_events

    def _build_live_agent_evidence(self, simulation_id: str, agent_id: str, query: str) -> dict[str, list[str]]:
        query_terms = self._tokenize_query_terms(query)
        related: list[tuple[int, int, dict[str, Any]]] = []
        fallback_recent: list[dict[str, Any]] = []

        for interaction in self._get_cached_interactions(simulation_id):
            actor_id = str(interaction.get("actor_agent_id") or "")
            target_id = str(interaction.get("target_agent_id") or "")
            if actor_id != agent_id and target_id != agent_id:
                continue
            if not self._is_memory_worthy_interaction(interaction):
                continue

            content = str(interaction.get("content") or "").strip()
            if not content:
                continue
            fallback_recent.append(interaction)
            lowered = content.lower()
            overlap = sum(1 for term in query_terms if term in lowered)
            interaction_id = int(interaction.get("id", 0) or 0)
            related.append((overlap, interaction_id, interaction))

        related.sort(key=lambda row: (row[0], row[1]), reverse=True)
        top_related = [item for item in related if item[0] > 0][:6]
        if not top_related:
            fallback_recent = sorted(
                fallback_recent,
                key=lambda row: int(row.get("id", 0) or 0),
                reverse=True,
            )[:4]
            top_related = [
                (0, int(row.get("id", 0) or 0), row)
                for row in fallback_recent
            ]

        interaction_lines: list[str] = []
        seen_interaction_content: set[str] = set()
        for _score, _interaction_id, interaction in top_related:
            action_type = str(interaction.get("action_type") or "event").strip().lower() or "event"
            content = str(interaction.get("content") or "").strip()
            content_key = content.lower()
            if not content or content_key in seen_interaction_content:
                continue
            seen_interaction_content.add(content_key)
            interaction_lines.append(
                f"round {int(interaction.get('round_no', 0) or 0)} {action_type}: {self._truncate_text(content, 260)}"
            )

        checkpoint_lines: list[str] = []
        checkpoint_records = self._get_cached_checkpoint_records(simulation_id)
        for record in checkpoint_records:
            if str(record.get("agent_id") or "") != agent_id:
                continue
            checkpoint_kind = str(record.get("checkpoint_kind") or "checkpoint").strip().lower() or "checkpoint"
            stance_score = float(record.get("stance_score", 0) or 0)
            stance_class = str(record.get("stance_class") or "neutral").strip().lower() or "neutral"
            confidence = float(record.get("confidence", 0) or 0)
            primary_driver = self._truncate_text(str(record.get("primary_driver") or "unspecified"), 140)
            checkpoint_lines.append(
                f"{checkpoint_kind}: stance={stance_score:.2f} ({stance_class}), confidence={confidence:.2f}, driver={primary_driver}"
            )
        checkpoint_lines = checkpoint_lines[-3:]

        return {
            "interaction_lines": interaction_lines[:6],
            "checkpoint_lines": checkpoint_lines,
        }

    def _get_cached_interactions(self, simulation_id: str) -> list[dict[str, Any]]:
        cached = self._interaction_cache.get(simulation_id)
        if cached is None:
            cached = self.store.get_interactions(simulation_id)
            self._interaction_cache[simulation_id] = cached
        return cached

    def _get_cached_checkpoint_records(self, simulation_id: str) -> list[dict[str, Any]]:
        cached = self._checkpoint_cache.get(simulation_id)
        if cached is None:
            cached = self.store.list_checkpoint_records(simulation_id)
            self._checkpoint_cache[simulation_id] = cached
        return cached

    def _is_memory_worthy_interaction(self, interaction: dict[str, Any]) -> bool:
        action_type = str(interaction.get("action_type") or "").strip().lower()
        content = str(interaction.get("content") or "").strip()
        if not content:
            return False
        if action_type in {"create_post", "post_created", "post", "comment", "comment_created", "reply"}:
            return True
        if "comment" in action_type or "post" in action_type:
            return True
        return False

    def _tokenize_query_terms(self, query: str) -> set[str]:
        tokens = {
            token.strip().lower()
            for token in str(query or "").split()
            if token.strip()
        }
        return {token for token in tokens if len(token) >= 3}

    def _truncate_text(self, value: str, limit: int) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 3)].rstrip()}..."

    def _format_graphiti_episode(self, simulation_id: str, interaction: dict[str, Any]) -> str:
        content = self._truncate_text(str(interaction.get("content", "")), 600)
        return (
            f"simulation={simulation_id} interaction_id={interaction.get('id', '')} "
            f"round={interaction.get('round_no', 0)} "
            f"actor={interaction.get('actor_agent_id', '')} "
            f"target={interaction.get('target_agent_id') or 'none'} "
            f"action={interaction.get('action_type', '')} "
            f"content={content} "
            f"delta={interaction.get('delta', 0)}"
        )

    def _format_graphiti_checkpoint_episode(self, simulation_id: str, checkpoint: dict[str, Any]) -> str:
        primary_driver = self._truncate_text(str(checkpoint.get("primary_driver") or "unspecified"), 280)
        return (
            f"simulation={simulation_id} checkpoint_id={checkpoint.get('id', '')} "
            f"kind={checkpoint.get('checkpoint_kind', 'checkpoint')} "
            f"agent={checkpoint.get('agent_id', '')} "
            f"stance_score={checkpoint.get('stance_score', 0)} "
            f"stance_class={checkpoint.get('stance_class', 'neutral')} "
            f"confidence={checkpoint.get('confidence', 0)} "
            f"primary_driver={primary_driver}"
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
        interactions = self._get_cached_interactions(simulation_id)
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
