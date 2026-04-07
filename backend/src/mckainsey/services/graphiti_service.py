from __future__ import annotations

import os
from typing import Any

try:  # pragma: no cover - optional dependency
    from graphiti_core import Graphiti as _Graphiti
    from graphiti_core.llm_client.gemini_client import GeminiClient as _GeminiClient, LLMConfig as _LLMConfig
    from graphiti_core.llm_client.openai_client import OpenAIClient as _OpenAIClient
except Exception:  # noqa: BLE001
    _Graphiti = None
    _GeminiClient = None
    _LLMConfig = None
    _OpenAIClient = None

Graphiti = _Graphiti
GeminiClient = _GeminiClient
OpenAIClient = _OpenAIClient
LLMConfig = _LLMConfig


class GraphitiService:
    """Provider-aware wrapper around Graphiti temporal memory."""

    @classmethod
    def is_available(cls) -> bool:
        return Graphiti is not None and LLMConfig is not None

    def __init__(self, session_config: dict[str, Any]) -> None:
        self.session_id = session_config["session_id"]
        self.provider = str(session_config.get("provider", "gemini")).strip().lower()
        self.api_key = session_config.get("api_key", "")
        self.model = session_config.get("model", "gemini-2.0-flash")
        self.db_url = os.getenv("FALKORDB_HOST", "localhost")
        self.db_port = int(os.getenv("FALKORDB_PORT", "6379"))
        self.graphiti = None

    async def initialize(self) -> None:
        if Graphiti is None or LLMConfig is None:
            raise RuntimeError("graphiti_core is not installed.")

        llm_client = self._build_llm_client()
        self.graphiti = Graphiti(
            f"bolt://{self.db_url}:{self.db_port}",
            "default",
            "",
            llm_client=llm_client,
        )
        await self.graphiti.build_indices_and_constraints()

    async def add_agent_memory(self, agent_id: str, content: str, round_no: int, timestamp: str) -> None:
        graphiti = self._require_graphiti()
        await graphiti.add_episode(
            name=f"agent_{agent_id}_round_{round_no}",
            episode_body=content,
            source_description=f"Agent {agent_id} during round {round_no}",
            reference_time=timestamp,
            group_id=f"session_{self.session_id}",
        )

    async def add_opinion_checkpoint(self, agent_id: str, opinion_score: float, round_no: int, timestamp: str) -> None:
        graphiti = self._require_graphiti()
        await graphiti.add_episode(
            name=f"checkpoint_{agent_id}_round_{round_no}",
            episode_body=f"Agent {agent_id} rated their opinion as {opinion_score}/10 at round {round_no}.",
            source_description=f"Checkpoint interview for agent {agent_id}",
            reference_time=timestamp,
            group_id=f"session_{self.session_id}",
        )

    async def search_agent_context(self, agent_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        graphiti = self._require_graphiti()
        results = await graphiti.search(
            query=query,
            group_ids=[f"session_{self.session_id}"],
            num_results=limit,
        )
        return [self._normalize_result(item) for item in results]

    async def get_agent_opinion_history(self, agent_id: str) -> list[dict[str, Any]]:
        graphiti = self._require_graphiti()
        results = await graphiti.search(
            query=f"opinion score for agent {agent_id}",
            group_ids=[f"session_{self.session_id}"],
            num_results=20,
        )
        return [{"fact": item.get("fact") if isinstance(item, dict) else item.fact, "timestamp": str(item.get("valid_at") if isinstance(item, dict) else item.valid_at)} for item in results]

    async def cleanup(self) -> None:
        if self.graphiti is not None:
            await self.graphiti.close()
            self.graphiti = None

    def _build_llm_client(self) -> Any:
        if self.provider in {"gemini", "google"}:
            if GeminiClient is None:
                raise RuntimeError("graphiti_core Gemini client is unavailable.")
            return GeminiClient(config=LLMConfig(api_key=self.api_key, model=self.model))
        if self.provider in {"openai", "openrouter"}:
            if OpenAIClient is None:
                raise RuntimeError("graphiti_core OpenAI client is unavailable.")
            return OpenAIClient(config=LLMConfig(api_key=self.api_key, model=self.model))
        if self.provider == "ollama":
            if OpenAIClient is None:
                raise RuntimeError("graphiti_core OpenAI client is unavailable.")
            return OpenAIClient(
                config=LLMConfig(
                    api_key="ollama",
                    model=self.model,
                    base_url="http://host.docker.internal:11434/v1",
                )
            )
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _require_graphiti(self) -> Any:
        if self.graphiti is None:
            raise RuntimeError("GraphitiService.initialize() must be called first.")
        return self.graphiti

    def _normalize_result(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return {
                "content": item.get("fact") or item.get("content"),
                "timestamp": str(item.get("valid_at") or item.get("timestamp") or ""),
                "confidence": item.get("score", 0),
            }
        return {
            "content": getattr(item, "fact", None),
            "timestamp": str(getattr(item, "valid_at", "")),
            "confidence": getattr(item, "score", 0),
        }
