from __future__ import annotations

from datetime import UTC, datetime
import os
from typing import Any

try:  # pragma: no cover - optional dependency
    from graphiti_core import Graphiti as _Graphiti
    from graphiti_core.cross_encoder import OpenAIRerankerClient as _OpenAIRerankerClient
    from graphiti_core.driver.falkordb_driver import FalkorDriver as _FalkorDriver
    from graphiti_core.embedder import OpenAIEmbedder as _OpenAIEmbedder, OpenAIEmbedderConfig as _OpenAIEmbedderConfig
    from graphiti_core.llm_client.config import LLMConfig as _LLMConfig
    from graphiti_core.llm_client.gemini_client import GeminiClient as _GeminiClient
    from graphiti_core.llm_client.openai_client import OpenAIClient as _OpenAIClient
except Exception:  # noqa: BLE001
    _Graphiti = None
    _OpenAIRerankerClient = None
    _FalkorDriver = None
    _OpenAIEmbedder = None
    _OpenAIEmbedderConfig = None
    _GeminiClient = None
    _LLMConfig = None
    _OpenAIClient = None

Graphiti = _Graphiti
OpenAIRerankerClient = _OpenAIRerankerClient
FalkorDriver = _FalkorDriver
OpenAIEmbedder = _OpenAIEmbedder
OpenAIEmbedderConfig = _OpenAIEmbedderConfig
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
        self.embed_model = session_config.get("embed_model", "text-embedding-3-small")
        self.base_url = str(session_config.get("base_url") or "").strip()
        self.db_url = os.getenv("FALKORDB_HOST", "localhost")
        self.db_port = int(os.getenv("FALKORDB_PORT", "6379"))
        self.graphiti = None

    async def initialize(self) -> None:
        if Graphiti is None or LLMConfig is None:
            raise RuntimeError("graphiti_core is not installed.")

        llm_client = self._build_llm_client()
        embedder_client = self._build_embedder_client()
        cross_encoder_client = self._build_cross_encoder_client()
        graph_driver = self._build_graph_driver()
        if graph_driver is not None:
            self.graphiti = Graphiti(
                llm_client=llm_client,
                embedder=embedder_client,
                cross_encoder=cross_encoder_client,
                graph_driver=graph_driver,
            )
        else:
            self.graphiti = Graphiti(
                f"bolt://{self.db_url}:{self.db_port}",
                "default",
                "",
                llm_client=llm_client,
                embedder=embedder_client,
                cross_encoder=cross_encoder_client,
            )
        await self.graphiti.build_indices_and_constraints()

    async def add_agent_memory(self, agent_id: str, content: str, round_no: int, timestamp: str) -> None:
        graphiti = self._require_graphiti()
        reference_time = self._coerce_reference_time(timestamp)
        await graphiti.add_episode(
            name=f"agent_{agent_id}_round_{round_no}",
            episode_body=content,
            source_description=f"Agent {agent_id} during round {round_no}",
            reference_time=reference_time,
            group_id=f"session_{self.session_id}",
        )

    async def add_opinion_checkpoint(self, agent_id: str, opinion_score: float, round_no: int, timestamp: str) -> None:
        graphiti = self._require_graphiti()
        reference_time = self._coerce_reference_time(timestamp)
        await graphiti.add_episode(
            name=f"checkpoint_{agent_id}_round_{round_no}",
            episode_body=f"Agent {agent_id} rated their opinion as {opinion_score}/10 at round {round_no}.",
            source_description=f"Checkpoint interview for agent {agent_id}",
            reference_time=reference_time,
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
        if LLMConfig is None:
            raise RuntimeError("graphiti_core LLM config is unavailable.")

        if self.provider in {"gemini", "google"}:
            if GeminiClient is None:
                raise RuntimeError("graphiti_core Gemini client is unavailable.")
            return GeminiClient(
                config=LLMConfig(
                    api_key=self.api_key,
                    model=self.model,
                    small_model=self.model,
                )
            )
        if self.provider in {"openai", "openrouter"}:
            if OpenAIClient is None:
                raise RuntimeError("graphiti_core OpenAI client is unavailable.")
            config_kwargs: dict[str, Any] = {
                "api_key": self.api_key,
                "model": self.model,
                "small_model": self.model,
            }
            if self.base_url:
                config_kwargs["base_url"] = self._normalize_openai_base_url(self.base_url)
            return OpenAIClient(config=LLMConfig(**config_kwargs))
        if self.provider == "ollama":
            if OpenAIClient is None:
                raise RuntimeError("graphiti_core OpenAI client is unavailable.")
            base_url = self._normalize_openai_base_url(self.base_url or "http://127.0.0.1:11434/v1")
            return OpenAIClient(
                config=LLMConfig(
                    api_key=self.api_key or "ollama",
                    model=self.model,
                    small_model=self.model,
                    base_url=base_url,
                )
            )
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _build_embedder_client(self) -> Any:
        if OpenAIEmbedder is None or OpenAIEmbedderConfig is None:
            raise RuntimeError("graphiti_core OpenAI embedder is unavailable.")

        base_url = self._normalize_openai_base_url(self.base_url or "http://127.0.0.1:11434/v1")
        api_key = self.api_key or "ollama"
        return OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=api_key,
                base_url=base_url,
                embedding_model=self.embed_model,
            )
        )

    def _build_cross_encoder_client(self) -> Any:
        if OpenAIRerankerClient is None:
            raise RuntimeError("graphiti_core OpenAI reranker is unavailable.")
        if LLMConfig is None:
            raise RuntimeError("graphiti_core LLM config is unavailable.")

        base_url = self._normalize_openai_base_url(self.base_url or "http://127.0.0.1:11434/v1")
        api_key = self.api_key or "ollama"
        return OpenAIRerankerClient(
            config=LLMConfig(
                api_key=api_key,
                model=self.model,
                small_model=self.model,
                base_url=base_url,
            )
        )

    def _build_graph_driver(self) -> Any | None:
        if FalkorDriver is None:
            return None
        self._patch_falkor_driver_class(FalkorDriver)
        return FalkorDriver(host=self.db_url, port=self.db_port)

    def _patch_falkor_driver_class(self, driver_cls: type[Any]) -> None:
        if getattr(driver_cls, "_mckainsey_group_escape_patch", False):
            return

        build_fulltext_query = getattr(driver_cls, "build_fulltext_query", None)
        if not callable(build_fulltext_query):
            return

        def _safe_build_fulltext_query(
            driver: Any,
            query: str,
            group_ids: list[str] | None = None,
            max_query_length: int = 128,
        ) -> str:
            built = str(build_fulltext_query(driver, query, group_ids, max_query_length))
            if not group_ids:
                return built

            escaped = {
                group_id: GraphitiService._escape_falkor_group_id_value(group_id)
                for group_id in group_ids
            }
            for raw_group_id, escaped_group_id in escaped.items():
                built = built.replace(f'"{raw_group_id}"', f'"{escaped_group_id}"')
                built = built.replace(f'{{{raw_group_id}}}', f'{{{escaped_group_id}}}')
            return built

        setattr(driver_cls, "build_fulltext_query", _safe_build_fulltext_query)
        setattr(driver_cls, "_mckainsey_group_escape_patch", True)

    @staticmethod
    def _escape_falkor_group_id_value(group_id: str) -> str:
        raw = str(group_id)
        escaped: list[str] = []
        for ch in raw:
            # Falkor full-text filters accept hyphens inside quoted values.
            # Escaping '-' produced invalid queries for session ids.
            if ch.isalnum() or ch in {"_", "-"}:
                escaped.append(ch)
            else:
                escaped.append(f"\\{ch}")
        return "".join(escaped)

    @staticmethod
    def _coerce_reference_time(timestamp: str | datetime) -> datetime:
        if isinstance(timestamp, datetime):
            dt = timestamp
        else:
            raw = str(timestamp or "").strip()
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else datetime.now(UTC)
            except ValueError:
                dt = datetime.now(UTC)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    def _normalize_openai_base_url(self, base_url: str) -> str:
        cleaned = str(base_url or "").strip()
        if cleaned.endswith("/"):
            return cleaned[:-1]
        return cleaned

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
