from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

from mckainsey.config import Settings


PLANNING_AREAS = {
    "woodlands",
    "yishun",
    "tampines",
    "bishan",
    "jurong",
    "punggol",
    "sengkang",
    "orchard",
    "bedok",
    "toa payoh",
    "ang mo kio",
}
DEMOGRAPHIC_TERMS = {
    "seniors",
    "elderly",
    "families",
    "households",
    "commuters",
    "workers",
    "students",
    "retirees",
    "parents",
    "residents",
}
POLICY_TERMS = {
    "transport",
    "budget",
    "housing",
    "healthcare",
    "support",
    "subsidy",
    "rebate",
    "grant",
    "tax",
    "fare",
    "inflation",
    "digital",
}


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

        entity_nodes, relationship_edges = _build_graph_from_text(document_text, demographic_focus)
        entity_type_counts: dict[str, int] = {}
        for node in entity_nodes:
            node_type = str(node.get("type", "unknown"))
            entity_type_counts[node_type] = entity_type_counts.get(node_type, 0) + 1

        return {
            "simulation_id": simulation_id,
            "document_id": document_id,
            "document": {
                "document_id": document_id,
                "source_path": source_path,
                "text_length": len(document_text),
            },
            "summary": summary,
            "demographic_context": demographic_context,
            "entity_nodes": entity_nodes,
            "relationship_edges": relationship_edges,
            "entity_type_counts": entity_type_counts,
            "processing_logs": [
                f"Inserted document {document_id}",
                f"Generated {len(entity_nodes)} nodes",
                f"Generated {len(relationship_edges)} edges",
            ],
            "demographic_focus_summary": demographic_context or demographic_focus,
        }


def _build_graph_from_text(document_text: str, demographic_focus: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = f"{document_text}\n{demographic_focus or ''}".lower()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(node_id: str, label: str, node_type: str) -> None:
        if not any(node["id"] == node_id for node in nodes):
            nodes.append({"id": node_id, "label": label, "type": node_type})

    found_policies = sorted(term for term in POLICY_TERMS if term in text)
    found_areas = sorted(term for term in PLANNING_AREAS if term in text)
    found_groups = sorted(term for term in DEMOGRAPHIC_TERMS if term in text)

    for policy in found_policies[:8]:
        add_node(f"policy:{policy}", policy.title(), "policy")
    for area in found_areas[:8]:
        add_node(f"area:{area}", area.title(), "planning_area")
    for group in found_groups[:8]:
        add_node(f"group:{group}", group.title(), "demographic")

    if not found_policies:
        keyword_nodes = _extract_keywords(document_text)
        for keyword in keyword_nodes[:8]:
            add_node(f"topic:{keyword}", keyword.title(), "topic")

    policy_like = [node for node in nodes if node["type"] in {"policy", "topic"}]
    geographic = [node for node in nodes if node["type"] == "planning_area"]
    cohorts = [node for node in nodes if node["type"] == "demographic"]
    for source in policy_like:
        for target in geographic:
            edges.append({"source": source["id"], "target": target["id"], "type": "impacts_area"})
        for target in cohorts:
            edges.append({"source": source["id"], "target": target["id"], "type": "affects_group"})

    return nodes, edges


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
    stopwords = {"this", "that", "with", "from", "into", "their", "have", "will", "would", "could", "budget"}
    counts: dict[str, int] = {}
    for token in tokens:
        if token in stopwords:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)]
