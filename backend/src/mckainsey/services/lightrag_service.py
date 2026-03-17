from __future__ import annotations

import asyncio
import uuid
from typing import Any

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

from mckainsey.config import Settings


class LightRAGService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._rag: LightRAG | None = None
        self._init_lock = asyncio.Lock()

    async def ensure_ready(self) -> None:
        if self._rag is not None:
            return

        async with self._init_lock:
            if self._rag is not None:
                return

            api_key = self._settings.resolved_gemini_key
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY (or GEMINI_API) is required for LightRAG")

            async def embedding_func(texts: list[str]) -> np.ndarray:
                return await openai_embed.func(
                    texts,
                    model=self._settings.gemini_embed_model,
                    api_key=api_key,
                    base_url=self._settings.gemini_openai_base_url,
                )

            test_embedding = await embedding_func(["embedding_probe"])
            embedding_dim = int(test_embedding.shape[1])

            self._rag = LightRAG(
                working_dir=self._settings.lightrag_workdir,
                llm_model_func=lambda prompt, **kwargs: openai_complete_if_cache(
                    self._settings.gemini_model,
                    prompt,
                    api_key=api_key,
                    base_url=self._settings.gemini_openai_base_url,
                    **kwargs,
                ),
                embedding_func=EmbeddingFunc(embedding_dim=embedding_dim, func=embedding_func),
            )
            await self._rag.initialize_storages()
            await initialize_pipeline_status()

    async def process_document(
        self,
        simulation_id: str,
        document_text: str,
        source_path: str | None,
        demographic_focus: str | None,
    ) -> dict[str, Any]:
        await self.ensure_ready()
        assert self._rag is not None

        document_id = f"doc-{uuid.uuid4()}"
        file_paths = [source_path] if source_path else None

        await self._rag.ainsert([document_text], ids=[document_id], file_paths=file_paths)

        summary = await self._rag.aquery(
            "Summarize this policy document with key entities and relationships.",
            param=QueryParam(mode="mix"),
        )

        demographic_context = None
        if demographic_focus:
            demographic_context = await self._rag.aquery(
                f"Extract only content most relevant to this demographic: {demographic_focus}",
                param=QueryParam(mode="hybrid"),
            )

        return {
            "simulation_id": simulation_id,
            "document_id": document_id,
            "summary": summary,
            "demographic_context": demographic_context,
        }
