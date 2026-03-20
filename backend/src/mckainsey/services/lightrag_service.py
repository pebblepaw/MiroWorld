from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import uuid
from pathlib import Path
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
GRAPH_EXTRACTION_SYSTEM_PROMPT = (
    "Extract a policy knowledge graph from the document. Return valid JSON only, "
    "with keys nodes and edges. Nodes should include id, label, type, and optional "
    "description or weight. Edges should include source, target, type, and label. "
    "Use active-voice relation labels when possible and normalize them to canonical "
    "semantics such as administers, funds, affects, regulates, implemented_by, "
    "targets, and located_in. Prefer entities and relationships relevant to any "
    "guiding prompt that is provided."
)

NODE_TYPE_ALIASES = {
    "agency": "organization",
    "authorities": "organization",
    "authority": "organization",
    "department": "organization",
    "entity": "entity",
    "group": "population",
    "initiative": "program",
    "institution": "organization",
    "law": "law",
    "location": "location",
    "metric": "metric",
    "ministry": "organization",
    "organisation": "organization",
    "organization": "organization",
    "organisation_unit": "organization",
    "org": "organization",
    "people": "population",
    "person": "population",
    "planning_area": "location",
    "population": "population",
    "program": "program",
    "project": "program",
    "policy": "policy",
    "service": "service",
    "subsidy": "funding",
    "topic": "topic",
    "venue": "location",
}

RELATION_TYPE_ALIASES = {
    "administered_by": "implemented_by",
    "administered by": "implemented_by",
    "administers": "administers",
    "affects": "affects",
    "affected_by": "affects",
    "affected by": "affects",
    "allocates": "funds",
    "backed_by": "funds",
    "backed by": "funds",
    "delivered_by": "implemented_by",
    "delivered by": "implemented_by",
    "enabled_by": "implemented_by",
    "enabled by": "implemented_by",
    "funded_by": "funds",
    "funded by": "funds",
    "funds": "funds",
    "implements": "implemented_by",
    "implemented_by": "implemented_by",
    "implemented by": "implemented_by",
    "influences": "affects",
    "impacts": "affects",
    "located_in": "located_in",
    "located in": "located_in",
    "oversees": "regulates",
    "overseen_by": "regulates",
    "overseen by": "regulates",
    "regulated_by": "regulates",
    "regulated by": "regulates",
    "regulates": "regulates",
    "serves": "targets",
    "targets": "targets",
    "targeted_at": "targets",
    "targeted at": "targets",
    "used_by": "implemented_by",
    "used by": "implemented_by",
    "within": "located_in",
    "in": "located_in",
    "at": "located_in",
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
        guiding_prompt: str | None = None,
        demographic_focus: str | None = None,
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

        entity_nodes, relationship_edges = await _build_graph_from_text(
            document_text=document_text,
            guiding_prompt=guiding_prompt,
            settings=self._settings,
        )
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
                "file_name": Path(source_path).name if source_path else None,
                "file_type": mimetypes.guess_type(source_path)[0] if source_path else None,
                "text_length": len(document_text),
            },
            "summary": summary,
            "guiding_prompt": guiding_prompt,
            "demographic_context": demographic_context,
            "entity_nodes": entity_nodes,
            "relationship_edges": relationship_edges,
            "entity_type_counts": entity_type_counts,
            "processing_logs": [
                f"Inserted document {document_id}",
                f"Extracted graph with Gemini ({len(entity_nodes)} nodes, {len(relationship_edges)} edges)",
            ],
            "demographic_focus_summary": demographic_context or demographic_focus,
        }


async def _build_graph_from_text(
    document_text: str,
    guiding_prompt: str | None,
    *,
    settings: Settings,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        raw_payload = await _extract_graph_payload(
            document_text=document_text,
            guiding_prompt=guiding_prompt,
            settings=settings,
        )
        nodes, node_lookup = _normalize_graph_nodes(raw_payload.get("nodes", []))
        edges = _normalize_graph_edges(raw_payload.get("edges", []), node_lookup)
        if nodes or edges:
            return nodes, edges
    except Exception:
        pass

    return _fallback_graph_from_text(document_text, guiding_prompt)


async def _extract_graph_payload(
    document_text: str,
    guiding_prompt: str | None,
    *,
    settings: Settings,
) -> dict[str, Any]:
    prompt = _build_graph_extraction_prompt(document_text, guiding_prompt)
    api_key = settings.resolved_gemini_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (or GEMINI_API) is required for graph extraction")

    raw_response = openai_complete_if_cache(
        settings.gemini_model,
        prompt,
        system_prompt=GRAPH_EXTRACTION_SYSTEM_PROMPT,
        api_key=api_key,
        base_url=settings.gemini_openai_base_url,
        enable_cot=False,
    )
    if asyncio.iscoroutine(raw_response):
        raw_response = await raw_response
    return _parse_graph_payload(str(raw_response))


def _build_graph_extraction_prompt(document_text: str, guiding_prompt: str | None) -> str:
    prompt_lines = [
        "Document text:",
        document_text.strip(),
    ]
    if guiding_prompt:
        prompt_lines.extend(["", "Guiding prompt:", guiding_prompt.strip()])
    prompt_lines.extend(
        [
            "",
            "Return JSON only. Do not include markdown fences, commentary, or extra keys outside nodes and edges.",
        ]
    )
    return "\n".join(prompt_lines)


def _parse_graph_payload(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            cleaned = match.group(0)
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("Graph extraction response must be a JSON object")
    return payload


def _normalize_graph_nodes(raw_nodes: Any) -> tuple[list[dict[str, Any]], dict[str, str]]:
    nodes: list[dict[str, Any]] = []
    lookup: dict[str, str] = {}
    seen_ids: set[str] = set()

    for index, raw_node in enumerate(raw_nodes if isinstance(raw_nodes, list) else []):
        if not isinstance(raw_node, dict):
            continue
        label = _coerce_text(raw_node.get("label") or raw_node.get("name") or raw_node.get("title") or raw_node.get("id"))
        if not label:
            label = f"Entity {index + 1}"
        node_type = _normalize_node_type(raw_node.get("type"), label)
        node_id = _coerce_text(raw_node.get("id")) or f"{node_type}:{_slugify(label)}"
        node: dict[str, Any] = {"id": node_id, "label": label, "type": node_type}
        description = _coerce_text(raw_node.get("description") or raw_node.get("summary"))
        if description:
            node["description"] = description
        raw_weight = raw_node.get("weight")
        if raw_weight is None:
            raw_weight = raw_node.get("confidence")
        weight = _coerce_weight(raw_weight)
        if weight is not None:
            node["weight"] = weight
        if node_id in seen_ids:
            continue
        nodes.append(node)
        seen_ids.add(node_id)
        for key in {node_id, label, _slugify(node_id), _slugify(label)}:
            if key:
                lookup[key] = node_id

    return nodes, lookup


def _normalize_graph_edges(raw_edges: Any, node_lookup: dict[str, str]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, str]] = set()

    for raw_edge in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(raw_edge, dict):
            continue
        source = _resolve_node_reference(
            raw_edge.get("source") or raw_edge.get("source_id") or raw_edge.get("from"),
            node_lookup,
        )
        target = _resolve_node_reference(
            raw_edge.get("target") or raw_edge.get("target_id") or raw_edge.get("to"),
            node_lookup,
        )
        if not source or not target:
            continue
        relation = _normalize_relation_type(raw_edge.get("type") or raw_edge.get("relation") or raw_edge.get("label"))
        label = _coerce_text(raw_edge.get("label") or raw_edge.get("relation_label") or relation.replace("_", " "))
        if not label:
            label = relation.replace("_", " ").title()
        edge = {"source": source, "target": target, "type": relation, "label": label}
        edge_key = (edge["source"], edge["target"], edge["type"], edge["label"])
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        edges.append(edge)

    return edges


def _resolve_node_reference(value: Any, node_lookup: dict[str, str]) -> str | None:
    text = _coerce_text(value)
    if not text:
        return None
    for candidate in (text, _slugify(text)):
        if candidate in node_lookup:
            return node_lookup[candidate]
    return text


def _normalize_node_type(value: Any, label: str) -> str:
    slug = _slugify(_coerce_text(value))
    if not slug:
        slug = _infer_node_type_from_label(label)
    return NODE_TYPE_ALIASES.get(slug, slug or "entity")


def _infer_node_type_from_label(label: str) -> str:
    lower = label.lower()
    if any(term in lower for term in PLANNING_AREAS):
        return "location"
    if any(term in lower for term in DEMOGRAPHIC_TERMS):
        return "population"
    if any(term in lower for term in POLICY_TERMS):
        return "policy"
    return "entity"


def _normalize_relation_type(value: Any) -> str:
    slug = _slugify(_coerce_text(value))
    if not slug:
        return "related_to"
    return RELATION_TYPE_ALIASES.get(slug, slug)


def _fallback_graph_from_text(document_text: str, guiding_prompt: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = f"{document_text}\n{guiding_prompt or ''}".lower()
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
        add_node(f"area:{area}", area.title(), "location")
    for group in found_groups[:8]:
        add_node(f"group:{group}", group.title(), "population")

    if not found_policies:
        keyword_nodes = _extract_keywords(document_text)
        for keyword in keyword_nodes[:8]:
            add_node(f"topic:{keyword}", keyword.title(), "topic")

    policy_like = [node for node in nodes if node["type"] in {"policy", "topic"}]
    geographic = [node for node in nodes if node["type"] == "location"]
    cohorts = [node for node in nodes if node["type"] == "population"]
    for source in policy_like:
        for target in geographic:
            edges.append({"source": source["id"], "target": target["id"], "type": "located_in", "label": "Located in"})
        for target in cohorts:
            edges.append({"source": source["id"], "target": target["id"], "type": "affects", "label": "Affects"})

    return nodes, edges


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _coerce_weight(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
    stopwords = {"this", "that", "with", "from", "into", "their", "have", "will", "would", "could", "budget"}
    counts: dict[str, int] = {}
    for token in tokens:
        if token in stopwords:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)]
