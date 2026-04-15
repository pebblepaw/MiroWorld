from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.types import KnowledgeGraph, KnowledgeGraphEdge, KnowledgeGraphNode
from lightrag.utils import EmbeddingFunc

from miroworld.config import Settings
from miroworld.services.config_service import ConfigService
from miroworld.services.embedding_fallback_service import arun_with_embedding_model_fallback


logger = logging.getLogger(__name__)


def _constant_slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")


PLANNING_AREA_NAMES = (
    "Ang Mo Kio",
    "Bedok",
    "Bishan",
    "Boon Lay",
    "Bukit Batok",
    "Bukit Merah",
    "Bukit Panjang",
    "Bukit Timah",
    "Changi",
    "Choa Chu Kang",
    "Clementi",
    "Downtown Core",
    "Geylang",
    "Hougang",
    "Jurong East",
    "Jurong West",
    "Kallang",
    "Lim Chu Kang",
    "Mandai",
    "Marine Parade",
    "Museum",
    "Newton",
    "North-Eastern Islands",
    "Novena",
    "Orchard",
    "Outram",
    "Pasir Ris",
    "Paya Lebar",
    "Pioneer",
    "Punggol",
    "Queenstown",
    "River Valley",
    "Rochor",
    "Seletar",
    "Sembawang",
    "Sengkang",
    "Serangoon",
    "Singapore River",
    "Southern Islands",
    "Sungei Kadut",
    "Tampines",
    "Tanglin",
    "Tengah",
    "Toa Payoh",
    "Tuas",
    "Western Water Catchment",
    "Woodlands",
    "Yishun",
)
PLANNING_AREAS = {name.lower() for name in PLANNING_AREA_NAMES}
PLANNING_AREA_SLUGS = {_constant_slugify(name): name for name in PLANNING_AREA_NAMES}
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
DEMOGRAPHIC_NODE_TYPES = {
    "demographic",
    "group",
    "people",
    "person",
    "population",
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
SEP_TOKEN = "<SEP>"
DOCUMENT_FAMILY = "document"
FACET_FAMILY = "facet"
SEX_ALIASES = {
    "female": "female",
    "women": "female",
    "woman": "female",
    "male": "male",
    "men": "male",
    "man": "male",
}
AGE_COHORT_ALIASES = {
    "child": "child",
    "children": "child",
    "kid": "child",
    "kids": "child",
    "youth": "youth",
    "young adults": "young_adult",
    "young adult": "young_adult",
    "working adults": "adult",
    "workers": "adult",
    "adults": "adult",
    "adult": "adult",
    "mid career workers": "mid_career",
    "mid-career workers": "mid_career",
    "senior workers": "senior",
    "senior": "senior",
    "seniors": "senior",
    "elderly": "senior",
    "older residents": "senior",
    "older adults": "senior",
    "retirees": "senior",
}
EDUCATION_LEVEL_ALIASES = {
    "lower secondary": "lower_secondary",
    "no qualification": "no_qualification",
    "other diploma": "other_diploma",
    "polytechnic": "polytechnic",
    "post secondary non tertiary": "post_secondary_non_tertiary",
    "post-secondary non-tertiary": "post_secondary_non_tertiary",
    "primary": "primary",
    "secondary": "secondary",
    "university": "university",
}
MARITAL_STATUS_ALIASES = {
    "divorced separated": "divorced_separated",
    "divorced/separated": "divorced_separated",
    "married": "married",
    "single": "single",
    "widowed": "widowed",
}
OCCUPATION_NAMES = (
    "Agricultural or Fishery Worker",
    "Associate Professional or Technician",
    "Cleaner, Labourer or Related Worker",
    "Clerical Worker",
    "Homemaker",
    "National Service",
    "Plant or Machine Operator or Assembler",
    "Production Craftsman or Related Worker",
    "Professional",
    "Retired",
    "Senior Official or Manager",
    "Service or Sales Worker",
    "Student",
    "Unemployed",
)
INDUSTRY_NAMES = (
    "Accommodation & Food Services",
    "Administrative & Support Services",
    "Arts, Entertainment & Recreation",
    "Community, Social & Personal Services",
    "Construction",
    "Financial & Insurance Services",
    "Health & Social Services",
    "Information & Communications",
    "Manufacturing",
    "Professional Services",
    "Public Administration & Education Services",
    "Real Estate Services",
    "Transportation & Storage",
    "Wholesale & Retail Trade",
)
OCCUPATION_SLUGS = {_constant_slugify(name): name for name in OCCUPATION_NAMES}
INDUSTRY_SLUGS = {_constant_slugify(name): name for name in INDUSTRY_NAMES}
COMMON_HOBBIES = {
    "badminton",
    "calligraphy",
    "gardening",
    "jogging",
    "karaoke",
    "mahjong",
    "meditation",
    "photography",
    "yoga",
}
COMMON_SKILLS = {
    "budget management",
    "community volunteering",
    "customer service",
    "data analysis",
    "event coordination",
    "inventory management",
    "negotiation",
    "project management",
    "public speaking",
    "team leadership",
    "time management",
}
HOBBY_SLUGS = {_constant_slugify(name): name for name in COMMON_HOBBIES}
SKILL_SLUGS = {_constant_slugify(name): name for name in COMMON_SKILLS}
EMBEDDING_TEXT_MAX_CHARS = 1200
OLLAMA_INGEST_DOC_MAX_CHARS = 9000
OLLAMA_FALLBACK_GRAPH_DOC_MAX_CHARS = 4500
OLLAMA_GUIDING_PROMPT_MAX_CHARS = 400
GENERIC_PLACEHOLDER_LABELS = {
    "company",
    "concept",
    "country",
    "data",
    "entity",
    "event",
    "group",
    "institution",
    "location",
    "organization",
    "people",
    "person",
    "policy",
    "program",
    "service",
}
PERSON_LIKE_TERMS = {
    "adults",
    "caregivers",
    "children",
    "citizens",
    "commuters",
    "elderly people",
    "families",
    "family",
    "households",
    "parents",
    "people",
    "person",
    "persons",
    "residents",
    "retirees",
    "seniors",
    "singaporeans",
    "students",
    "workers",
    "youth",
}
NAME_TITLE_PREFIXES = {
    "assoc",
    "associate",
    "dr",
    "madam",
    "miss",
    "mr",
    "mrs",
    "ms",
    "prof",
    "professor",
    "sir",
}
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
        self._config = ConfigService(settings)
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
                raise RuntimeError("A provider API key is required for LightRAG operations.")

            active_embed_model_name = self._settings.gemini_embed_model

            async def embedding_func(texts: list[str]) -> np.ndarray:
                nonlocal active_embed_model_name
                sanitized_texts = [text[:EMBEDDING_TEXT_MAX_CHARS] for text in texts]
                previous_model_name = active_embed_model_name
                resolved_model_name, embedding = await arun_with_embedding_model_fallback(
                    self._settings,
                    provider=self._settings.llm_provider,
                    preferred_model=active_embed_model_name,
                    runner=lambda model_name: openai_embed.func(
                        sanitized_texts,
                        model=model_name,
                        api_key=api_key,
                        base_url=self._settings.gemini_openai_base_url,
                    ),
                )
                active_embed_model_name = resolved_model_name
                self._settings.gemini_embed_model = resolved_model_name
                self._settings.llm_embed_model = resolved_model_name
                if resolved_model_name != previous_model_name:
                    logger.warning(
                        "Google embedding model '%s' was rate-limited; switching to '%s' for LightRAG.",
                        previous_model_name,
                        resolved_model_name,
                    )
                return embedding

            test_embedding = await embedding_func(["embedding_probe"])
            embedding_dim = int(test_embedding.shape[1])

            # Ensure session-scoped working directory exists before LightRAG init
            Path(self._settings.lightrag_workdir).mkdir(parents=True, exist_ok=True)

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
        document_id: str | None = None,
        guiding_prompt: str | None = None,
        use_case_id: str | None = None,
        demographic_focus: str | None = None,
        live_mode: bool = False,
        event_callback=None,
    ) -> dict[str, Any]:
        await self.ensure_ready()
        assert self._rag is not None

        document_id = document_id or f"doc-{uuid.uuid4()}"
        file_paths = [source_path] if source_path else None

        provider = str(self._settings.llm_provider or "").strip().lower()
        ingestion_text = document_text
        fallback_graph_text = document_text
        normalized_guiding_prompt = guiding_prompt.strip() if guiding_prompt else None
        summary_mode = "mix"
        demographic_mode = "hybrid"
        processing_logs: list[str] = []

        if provider == "ollama":
            # Local Ollama runs can become unstable on large extraction payloads.
            ingestion_text = _truncate_for_runtime(document_text, OLLAMA_INGEST_DOC_MAX_CHARS)
            fallback_graph_text = _truncate_for_runtime(document_text, OLLAMA_FALLBACK_GRAPH_DOC_MAX_CHARS)
            if normalized_guiding_prompt:
                normalized_guiding_prompt = normalized_guiding_prompt[:OLLAMA_GUIDING_PROMPT_MAX_CHARS].strip()
            summary_mode = "hybrid"
            demographic_mode = "local"
            processing_logs.append("Applied lightweight Ollama ingestion profile.")
            if len(ingestion_text) < len(document_text):
                processing_logs.append(
                    f"Trimmed ingestion text from {len(document_text)} to {len(ingestion_text)} chars for local runtime stability"
                )
            if len(fallback_graph_text) < len(document_text):
                processing_logs.append(
                    f"Trimmed fallback extraction text from {len(document_text)} to {len(fallback_graph_text)} chars"
                )
        chunks = _chunk_document_text(ingestion_text)
        processing_logs.append(f"Split ingestion into {len(chunks)} chunk(s).")

        merged_nodes: dict[str, dict[str, Any]] = {}
        merged_edges: dict[tuple[str, str, str], dict[str, Any]] = {}

        for chunk_index, chunk_text in enumerate(chunks, start=1):
            chunk_id = f"{document_id}-chunk-{chunk_index:03d}"
            if event_callback is not None:
                await event_callback(
                    "knowledge_chunk_started",
                    {
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "chunk_count": len(chunks),
                        "chunk_total": len(chunks),
                    },
                )

            await self._rag.ainsert([chunk_text], ids=[chunk_id], file_paths=file_paths)
            native_graph = await _load_document_native_graph(self._rag, chunk_id)
            chunk_nodes: list[dict[str, Any]] = []
            chunk_edges: list[dict[str, Any]] = []
            if native_graph and (native_graph.nodes or native_graph.edges):
                graph_payload = _adapt_native_lightrag_graph(native_graph)
                chunk_nodes = graph_payload["entity_nodes"]
                chunk_edges = graph_payload["relationship_edges"]

            node_delta = _new_node_delta(merged_nodes, chunk_nodes)
            edge_delta = _new_edge_delta(merged_edges, chunk_edges)

            for node in chunk_nodes:
                node_id = str(node.get("id") or "").strip()
                if node_id:
                    merged_nodes[node_id] = node
            for edge in chunk_edges:
                edge_key = _edge_identity(edge)
                if edge_key is not None:
                    merged_edges[edge_key] = edge

            if event_callback is not None:
                await event_callback(
                    "knowledge_partial",
                    {
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "chunk_count": len(chunks),
                        "chunk_total": len(chunks),
                        "entity_nodes": node_delta,
                        "relationship_edges": edge_delta,
                        "total_nodes": len(merged_nodes),
                        "total_edges": len(merged_edges),
                    },
                )
                await event_callback(
                    "knowledge_chunk_completed",
                    {
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "chunk_count": len(chunks),
                        "chunk_total": len(chunks),
                        "node_delta_count": len(node_delta),
                        "edge_delta_count": len(edge_delta),
                    },
                )

        summary_prompt = self._config.render_prompt_template(
            self._config.get_system_prompt_value(
                "graph_extraction",
                "prompts",
                "document_summary",
                "default_prompt",
            ),
            use_case_id=use_case_id,
        )
        if provider == "ollama":
            summary_prompt = self._config.render_prompt_template(
                self._config.get_system_prompt_value(
                    "graph_extraction",
                    "prompts",
                    "document_summary",
                    "ollama_prompt",
                ),
                use_case_id=use_case_id,
            )
        if normalized_guiding_prompt:
            summary_prompt = (
                f"{summary_prompt} "
                + self._config.render_prompt_template(
                    self._config.get_system_prompt_value(
                        "graph_extraction",
                        "prompts",
                        "document_summary",
                        "guiding_focus_suffix",
                    ),
                    use_case_id=use_case_id,
                    extra_replacements={"guiding_prompt": normalized_guiding_prompt},
                )
            ).strip()
        summary = await self._rag.aquery(
            summary_prompt,
            param=QueryParam(mode=summary_mode),
        )

        demographic_context = None
        if demographic_focus:
            demographic_context = await self._rag.aquery(
                f"Extract only content most relevant to this demographic: {demographic_focus}",
                param=QueryParam(mode=demographic_mode),
            )

        graph_origin = "lightrag_native"
        processing_logs.insert(0, f"Inserted document {document_id} into LightRAG")
        entity_nodes = list(merged_nodes.values())
        relationship_edges = list(merged_edges.values())
        if entity_nodes or relationship_edges:
            processing_logs.append(
                f"Adapted LightRAG entity graph ({len(entity_nodes)} nodes, {len(relationship_edges)} edges)"
            )
        else:
            graph_origin = "fallback_model_extract"
            entity_nodes, relationship_edges = await _build_graph_from_text(
                document_text=fallback_graph_text,
                guiding_prompt=normalized_guiding_prompt,
                settings=self._settings,
            )
            processing_logs.append(
                f"Native LightRAG graph unavailable, used fallback extraction ({len(entity_nodes)} nodes, {len(relationship_edges)} edges)"
            )
            if live_mode:
                processing_logs.append("Live mode accepted fallback graph extraction after empty native LightRAG output.")

        entity_type_counts = dict(Counter(str(node.get("type", "unknown")) for node in entity_nodes))

        return {
            "simulation_id": simulation_id,
            "document_id": document_id,
            "document": {
                "document_id": document_id,
                "source_path": source_path,
                "file_name": Path(source_path).name if source_path else None,
                "file_type": mimetypes.guess_type(source_path)[0] if source_path else None,
                "text_length": len(document_text),
                "paragraph_count": len(
                    [paragraph for paragraph in re.split(r"\n\s*\n+", document_text.strip()) if paragraph.strip()]
                ),
            },
            "summary": summary,
            "guiding_prompt": guiding_prompt,
            "demographic_context": demographic_context,
            "entity_nodes": entity_nodes,
            "relationship_edges": relationship_edges,
            "entity_type_counts": entity_type_counts,
            "graph_origin": graph_origin,
            "processing_logs": processing_logs,
            "demographic_focus_summary": demographic_context or demographic_focus,
        }


async def _load_document_native_graph(rag: LightRAG, document_id: str) -> KnowledgeGraph | None:
    entities_record = await rag.full_entities.get_by_id(document_id)
    relations_record = await rag.full_relations.get_by_id(document_id)

    entity_names = [name for name in (entities_record or {}).get("entity_names", []) if _coerce_text(name)]
    relation_pairs = [
        (_coerce_text(pair[0]), _coerce_text(pair[1]))
        for pair in (relations_record or {}).get("relation_pairs", [])
        if isinstance(pair, (list, tuple)) and len(pair) >= 2 and _coerce_text(pair[0]) and _coerce_text(pair[1])
    ]

    if not entity_names and not relation_pairs:
        return None

    ordered_names: list[str] = []
    seen_names: set[str] = set()
    for name in entity_names + [value for pair in relation_pairs for value in pair]:
        normalized = _coerce_text(name)
        if not normalized or normalized in seen_names:
            continue
        seen_names.add(normalized)
        ordered_names.append(normalized)

    nodes: list[KnowledgeGraphNode] = []
    for name in ordered_names:
        entity_info = await _safe_get_entity_info(rag, name)
        graph_data = dict(entity_info.get("graph_data") or {})
        graph_data.setdefault("entity_id", entity_info.get("entity_name") or name)
        graph_data.setdefault("source_id", entity_info.get("source_id"))
        nodes.append(
            KnowledgeGraphNode(
                id=name,
                labels=[graph_data.get("entity_id") or name],
                properties=graph_data,
            )
        )

    edges: list[KnowledgeGraphEdge] = []
    for source, target in relation_pairs:
        relation_info = await _safe_get_relation_info(rag, source, target)
        graph_data = dict(relation_info.get("graph_data") or {})
        graph_data.setdefault("source_id", relation_info.get("source_id"))
        edges.append(
            KnowledgeGraphEdge(
                id=f"{source}->{target}",
                type=None,
                source=source,
                target=target,
                properties=graph_data,
            )
        )

    return KnowledgeGraph(nodes=nodes, edges=edges)


async def _safe_get_entity_info(rag: LightRAG, entity_name: str) -> dict[str, Any]:
    try:
        info = await rag.get_entity_info(entity_name)
    except Exception:
        info = {}
    return info if isinstance(info, dict) else {}


async def _safe_get_relation_info(rag: LightRAG, source: str, target: str) -> dict[str, Any]:
    try:
        info = await rag.get_relation_info(source, target)
    except Exception:
        info = {}
    return info if isinstance(info, dict) else {}


def _adapt_native_lightrag_graph(native_graph: KnowledgeGraph) -> dict[str, Any]:
    merged_nodes: dict[str, dict[str, Any]] = {}
    merge_key_to_id: dict[str, str] = {}
    alias_to_id: dict[str, str] = {}

    for raw_node in native_graph.nodes:
        node = _normalize_native_graph_node(raw_node)
        merge_key = str(node.get("canonical_key") or _slugify(str(node.get("label", ""))) or str(node.get("id")))
        existing_id = merge_key_to_id.get(merge_key)
        if existing_id:
            merged_nodes[existing_id] = _merge_graph_nodes(merged_nodes[existing_id], node)
            node_id = existing_id
        else:
            node_id = str(node["id"])
            merged_nodes[node_id] = node
            merge_key_to_id[merge_key] = node_id

        for candidate in {
            str(raw_node.id),
            _coerce_text(raw_node.id),
            str(node["id"]),
            _coerce_text(node.get("label")),
            _slugify(_coerce_text(node.get("label"))),
        }:
            if candidate:
                alias_to_id[candidate] = node_id

    relationship_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str, str]] = set()
    for raw_edge in native_graph.edges:
        source_id = _resolve_native_alias(raw_edge.source, alias_to_id)
        target_id = _resolve_native_alias(raw_edge.target, alias_to_id)
        if not source_id or not target_id or source_id == target_id:
            continue
        edge = _normalize_native_graph_edge(raw_edge, source_id, target_id, merged_nodes)
        edge_key = (edge["source"], edge["target"], edge["type"], edge["label"])
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        relationship_edges.append(edge)

    entity_nodes, relationship_edges = _finalize_graph_payload(list(merged_nodes.values()), relationship_edges)
    return {
        "entity_nodes": entity_nodes,
        "relationship_edges": relationship_edges,
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
            return _finalize_graph_payload(nodes, edges)
    except Exception:
        pass

    return _fallback_graph_from_text(document_text, guiding_prompt)


def _normalize_native_graph_node(raw_node: KnowledgeGraphNode) -> dict[str, Any]:
    properties = dict(raw_node.properties or {})
    label = (
        _coerce_text(properties.get("entity_id"))
        or _coerce_text(properties.get("entity_name"))
        or _coerce_text(raw_node.labels[0] if raw_node.labels else "")
        or _coerce_text(raw_node.id)
    )
    node_type = _normalize_node_type(properties.get("entity_type"), label)
    raw_description = _coerce_text(properties.get("description"))
    raw_summary = _coerce_text(properties.get("summary"))
    description = _dedupe_native_text(raw_description) or _dedupe_native_text(raw_summary)
    summary = _dedupe_native_text(raw_summary) or description
    source_ids = _split_sep(properties.get("source_id"))
    file_paths = _split_sep(properties.get("file_path"))
    facet_meta = _infer_facet_metadata(label, node_type=node_type, description=description)
    families = [DOCUMENT_FAMILY]
    if facet_meta:
        families.append(FACET_FAMILY)

    node: dict[str, Any] = {
        "id": _coerce_text(raw_node.id) or label,
        "label": label,
        "type": node_type,
        "families": families,
        "display_bucket": _display_bucket_for_node(
            type=node_type,
            facet_kind=(facet_meta or {}).get("facet_kind"),
            label=label,
        ),
        "source_ids": source_ids,
        "file_paths": file_paths,
        "summary": summary or description,
        "raw_description": raw_description,
        "raw_summary": raw_summary,
        "provenance": {
            "source_ids": source_ids,
            "file_paths": file_paths,
        },
    }
    if description:
        node["description"] = description

    weight = _coerce_weight(properties.get("weight"))
    if weight is None and source_ids:
        weight = round(min(1.0, 0.25 + (0.12 * len(source_ids))), 3)
    if weight is not None:
        node["weight"] = weight

    if facet_meta:
        node.update(facet_meta)

    return node


def _merge_graph_nodes(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged["families"] = sorted(set(existing.get("families", [])) | set(incoming.get("families", [])))
    merged["source_ids"] = _merge_unique_list(existing.get("source_ids"), incoming.get("source_ids"))
    merged["file_paths"] = _merge_unique_list(existing.get("file_paths"), incoming.get("file_paths"))
    merged["raw_description"] = _dedupe_native_text(existing.get("raw_description"), incoming.get("raw_description"))
    merged["raw_summary"] = _dedupe_native_text(existing.get("raw_summary"), incoming.get("raw_summary"))
    merged_description = _dedupe_native_text(existing.get("description"), incoming.get("description"))
    merged_summary = _dedupe_native_text(existing.get("summary"), incoming.get("summary"), merged_description)
    if merged_description:
        merged["description"] = merged_description
    if merged_summary:
        merged["summary"] = merged_summary
    merged["provenance"] = {
        "source_ids": merged["source_ids"],
        "file_paths": merged["file_paths"],
    }

    incoming_weight = _coerce_weight(incoming.get("weight"))
    existing_weight = _coerce_weight(existing.get("weight")) or 0.0
    if incoming_weight is not None:
        merged["weight"] = max(existing_weight, incoming_weight)

    if existing.get("type") in {"entity", "other"} and incoming.get("type") not in {None, "entity", "other"}:
        merged["type"] = incoming["type"]

    for key in ("facet_kind", "canonical_key", "canonical_value"):
        if key not in merged and incoming.get(key):
            merged[key] = incoming[key]
    merged["display_bucket"] = _display_bucket_for_node(
        type=str(merged.get("type", "")),
        facet_kind=str(merged.get("facet_kind", "")) or None,
        label=str(merged.get("label", "")),
    )
    return merged


def _normalize_native_graph_edge(
    raw_edge: KnowledgeGraphEdge,
    source_id: str,
    target_id: str,
    node_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    properties = dict(raw_edge.properties or {})
    raw_description = _coerce_text(properties.get("description"))
    raw_summary = _coerce_text(properties.get("summary"))
    description = _dedupe_native_text(raw_description) or _dedupe_native_text(raw_summary)
    summary = _dedupe_native_text(raw_summary) or description
    raw_relation_text = _coerce_text(
        properties.get("keywords") or properties.get("label") or properties.get("relationship") or raw_edge.type
    )
    if not raw_relation_text:
        raw_relation_text = _derive_relation_text_from_description(description)
    normalized_type = _normalize_native_relation_type(
        raw_relation_text=raw_relation_text,
        description=description,
        source_node=node_lookup.get(source_id, {}),
        target_node=node_lookup.get(target_id, {}),
    )
    source_ids = _split_sep(properties.get("source_id"))
    file_paths = _split_sep(properties.get("file_path"))
    edge: dict[str, Any] = {
        "source": source_id,
        "target": target_id,
        "type": normalized_type,
        "normalized_type": normalized_type,
        "label": raw_relation_text,
        "raw_relation_text": raw_relation_text,
        "source_ids": source_ids,
        "file_paths": file_paths,
        "summary": summary or description,
        "raw_description": raw_description,
        "raw_summary": raw_summary,
        "provenance": {
            "source_ids": source_ids,
            "file_paths": file_paths,
        },
    }
    if description:
        edge["description"] = description
    return edge


def _resolve_native_alias(value: Any, alias_to_id: dict[str, str]) -> str | None:
    text = _coerce_text(value)
    if not text:
        return None
    for candidate in (text, _slugify(text)):
        if candidate in alias_to_id:
            return alias_to_id[candidate]
    return None


def _infer_facet_metadata(label: str, *, node_type: str, description: str) -> dict[str, str] | None:
    if _looks_like_named_person_or_credit(label):
        return None

    normalized_label = _normalized_alias_text(label)
    normalized_description = _normalized_alias_text(description)
    demographic_candidate = _is_demographic_candidate(
        node_type=node_type,
        normalized_label=normalized_label,
        normalized_description=normalized_description,
    )

    if planning_area := _match_canonical_value(normalized_label, PLANNING_AREA_SLUGS):
        return _facet_payload("planning_area", planning_area)

    if demographic_candidate:
        if age_cohort := _match_phrase_alias(normalized_label, AGE_COHORT_ALIASES):
            return _facet_payload("age_cohort", age_cohort)

        if sex := _match_phrase_alias(normalized_label, SEX_ALIASES):
            return _facet_payload("sex", sex)

        if education_level := _match_phrase_alias(normalized_label, EDUCATION_LEVEL_ALIASES):
            return _facet_payload("education_level", education_level)

        if marital_status := _match_phrase_alias(normalized_label, MARITAL_STATUS_ALIASES):
            return _facet_payload("marital_status", marital_status)

        if occupation := _match_canonical_value(normalized_label, OCCUPATION_SLUGS) or _match_canonical_value_in_text(normalized_label, OCCUPATION_SLUGS):
            return _facet_payload("occupation", occupation)

    if _allows_semantic_facet_inference(node_type):
        if industry := _match_canonical_value(normalized_label, INDUSTRY_SLUGS) or _match_canonical_value_in_text(normalized_label, INDUSTRY_SLUGS):
            return _facet_payload("industry", industry)

        if hobby := _match_canonical_value(normalized_label, HOBBY_SLUGS) or _match_canonical_value_in_text(normalized_label, HOBBY_SLUGS):
            return _facet_payload("hobby", hobby)

        if skill := _match_canonical_value(normalized_label, SKILL_SLUGS) or _match_canonical_value_in_text(normalized_label, SKILL_SLUGS):
            return _facet_payload("skill", skill)

    return None


def _is_demographic_candidate(*, node_type: str, normalized_label: str, normalized_description: str) -> bool:
    del normalized_description
    normalized_type = _slugify(node_type)
    if normalized_type in DEMOGRAPHIC_NODE_TYPES:
        return True
    return any(_contains_alias_phrase(normalized_label, term) for term in PERSON_LIKE_TERMS)


def _allows_semantic_facet_inference(node_type: str) -> bool:
    return _slugify(node_type) not in {"event", "location", "metric"}


def _looks_like_named_person_or_credit(label: str) -> bool:
    raw_label = _coerce_text(label)
    normalized_label = _normalized_alias_text(raw_label)
    if not raw_label or not normalized_label:
        return False

    protected_phrase_sets = [
        PERSON_LIKE_TERMS,
        set(AGE_COHORT_ALIASES),
        set(SEX_ALIASES),
        set(EDUCATION_LEVEL_ALIASES),
        set(MARITAL_STATUS_ALIASES),
    ]
    for phrases in protected_phrase_sets:
        if any(_contains_alias_phrase(normalized_label, phrase) for phrase in phrases):
            return False

    canonical_maps = [OCCUPATION_SLUGS, INDUSTRY_SLUGS, HOBBY_SLUGS, SKILL_SLUGS, PLANNING_AREA_SLUGS]
    if any(_match_canonical_value(normalized_label, canonical_map) for canonical_map in canonical_maps):
        return False

    if "/" in raw_label:
        return True

    tokens = re.findall(r"[A-Za-z][A-Za-z'.-]*", raw_label)
    if len(tokens) < 2 or len(tokens) > 5:
        return False

    lower_tokens = [token.lower() for token in tokens]
    if lower_tokens[0] in NAME_TITLE_PREFIXES:
        return True

    capitalized_count = sum(1 for token in tokens if token[0].isupper())
    return capitalized_count == len(tokens)


def _display_bucket_for_node(*, type: str, facet_kind: str | None, label: str) -> str:
    normalized_type = _slugify(type)
    normalized_facet = _slugify(facet_kind or "")
    normalized_label = _slugify(label)

    if normalized_facet in {"age_cohort", "age_group"} or normalized_type in {"age_cohort", "age_group"}:
        return "age_group"
    if normalized_facet == "planning_area" or normalized_type == "location":
        return "location"
    if normalized_facet == "industry" or normalized_type == "industry" or normalized_label in INDUSTRY_SLUGS:
        return "industry"
    if normalized_type in {"organization", "agency", "department", "institution", "ministry"}:
        return "organization"
    if normalized_type in {"person", "people", "demographic", "group", "stakeholder"}:
        return "persons"
    if normalized_type == "population":
        return "persons"
    if normalized_type == "event":
        return "event"
    if normalized_facet == "concept" or normalized_type in {"concept", "topic"}:
        return "concept"
    if normalized_type in {"policy", "program", "service", "funding", "law"}:
        return "concept"
    return "other"


def _match_canonical_value(normalized_label: str, canonical_map: dict[str, str]) -> str | None:
    slug = normalized_label.replace(" ", "_")
    canonical = canonical_map.get(slug)
    if not canonical:
        return None
    return _slugify(canonical)


def _match_canonical_value_in_text(text: str, canonical_map: dict[str, str]) -> str | None:
    for phrase, canonical in sorted(canonical_map.items(), key=lambda item: len(item[0]), reverse=True):
        if _contains_alias_phrase(text, phrase.replace("_", " ")):
            return _slugify(canonical)
    return None


def _find_phrase_match(text: str, aliases: dict[str, str]) -> str | None:
    return _match_phrase_alias(text, aliases)


def _match_phrase_alias(text: str, aliases: dict[str, str]) -> str | None:
    for phrase, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if _contains_alias_phrase(text, phrase):
            return canonical
    return None


def _contains_alias_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    haystack = f" {text} "
    needle = f" {_normalized_alias_text(phrase)} "
    return needle.strip() != "" and needle in haystack


def _normalized_alias_text(value: Any) -> str:
    return _slugify(_coerce_text(value)).replace("_", " ").strip()


def _facet_payload(kind: str, canonical_value: str) -> dict[str, str]:
    value = _slugify(canonical_value)
    return {
        "facet_kind": kind,
        "canonical_value": value,
        "canonical_key": f"{kind}:{value}",
    }


def _normalize_native_relation_type(
    *,
    raw_relation_text: str,
    description: str,
    source_node: dict[str, Any],
    target_node: dict[str, Any],
) -> str:
    _ = source_node
    text = " ".join(
        part for part in [raw_relation_text.lower(), description.lower(), str(target_node.get("label", "")).lower()] if part
    )
    target_facet_kind = str(target_node.get("facet_kind", ""))
    target_type = str(target_node.get("type", ""))

    if target_facet_kind == "planning_area" or target_type == "location":
        if any(token in text for token in ("pilot area", "area", "district", "region", "town", "located", "within", "in ")):
            return "located_in"
    if any(token in text for token in ("target", "targeted", "beneficiar", "eligible", "for seniors", "for families", "support for", "focused on")):
        return "targets"
    if any(token in text for token in ("fund", "grant", "rebate", "subsid", "top-up", "budget allocation", "investment", "financ")):
        return "funds"
    if any(token in text for token in ("implemented", "administered", "managed by", "delivered by", "run by", "led by")):
        return "implemented_by"
    if any(token in text for token in ("regulat", "mandate", "permit", "quota", "tax", "compliance", "oversight")):
        return "regulates"
    if any(token in text for token in ("affect", "impact", "influence", "address", "improve", "reduce", "increase", "pressure", "concern")):
        return "affects"
    return "related_to"


def _derive_relation_text_from_description(description: str) -> str:
    if not description:
        return "related to"
    trimmed = description.strip().split(".")[0]
    return trimmed or "related to"


async def _extract_graph_payload(
    document_text: str,
    guiding_prompt: str | None,
    *,
    settings: Settings,
) -> dict[str, Any]:
    prompt = _build_graph_extraction_prompt(
        document_text,
        guiding_prompt,
        provider=settings.llm_provider,
    )
    api_key = settings.resolved_gemini_key
    if not api_key:
        raise RuntimeError("A provider API key is required for graph extraction.")

    config = ConfigService(settings)
    raw_response = openai_complete_if_cache(
        settings.gemini_model,
        prompt,
        system_prompt=config.get_system_prompt_value(
            "graph_extraction",
            "prompts",
            "graph_extraction",
            "system_prompt",
        ),
        api_key=api_key,
        base_url=settings.gemini_openai_base_url,
        enable_cot=False,
    )
    if asyncio.iscoroutine(raw_response):
        raw_response = await raw_response
    return _parse_graph_payload(str(raw_response))


def _build_graph_extraction_prompt(
    document_text: str,
    guiding_prompt: str | None,
    *,
    provider: str | None = None,
) -> str:
    normalized_provider = str(provider or "").strip().lower()
    prompt_lines = [
        "Document text:",
        document_text.strip(),
    ]
    if guiding_prompt:
        prompt_lines.extend(["", "Guiding prompt:", guiding_prompt.strip()])
    if normalized_provider == "ollama":
        prompt_lines.extend(
            [
                "",
                "Keep extraction compact: at most 30 nodes and 45 edges.",
                "Prefer high-signal entities only; omit weakly relevant details.",
            ]
        )
    prompt_lines.extend(
        [
            "",
            "Return JSON only. Do not include markdown fences, commentary, or extra keys outside nodes and edges.",
        ]
    )
    return "\n".join(prompt_lines)


def _truncate_for_runtime(text: str, max_chars: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    candidate = stripped[:max_chars]
    newline = candidate.rfind("\n")
    if newline > int(max_chars * 0.7):
        candidate = candidate[:newline]
    return candidate.strip()


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

    return _finalize_graph_payload(nodes, edges)


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


def _split_sep(value: Any) -> list[str]:
    text = _coerce_text(value)
    if not text:
        return []
    parts = [part.strip() for part in text.split(SEP_TOKEN) if part.strip()]
    return list(dict.fromkeys(parts))


def _dedupe_native_text(*values: Any) -> str:
    pieces: list[str] = []
    seen: set[str] = set()

    for value in values:
        text = _coerce_text(value)
        if not text:
            continue
        for part in text.split(SEP_TOKEN):
            normalized = _normalize_text_piece(part)
            if not normalized:
                continue
            key = _dedupe_text_key(normalized)
            if key in seen:
                continue
            seen.add(key)
            pieces.append(normalized)

    return " ".join(pieces)


def _normalize_text_piece(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    text = text.strip(" \t\r\n\"'“”‘’`()[]{}<>")
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_text_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _merge_unique_list(left: Any, right: Any) -> list[str]:
    values = list(left or []) + list(right or [])
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _coerce_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _is_generic_placeholder_label(label: str) -> bool:
    return _slugify(label) in GENERIC_PLACEHOLDER_LABELS


def _node_quality_flags(*, label: str, support_count: int, degree_count: int, facet_kind: str | None) -> dict[str, bool]:
    generic_placeholder = _is_generic_placeholder_label(label)
    low_value_orphan = degree_count == 0 and support_count <= 1
    return {
        "generic_placeholder": generic_placeholder,
        "low_value_orphan": low_value_orphan,
        "ui_default_hidden": generic_placeholder or (low_value_orphan and not _coerce_text(facet_kind)),
    }


def _finalize_graph_payload(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    node_lookup = {str(node.get("id")): node for node in nodes if node.get("id")}
    neighbors: dict[str, set[str]] = {node_id: set() for node_id in node_lookup}

    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if not source or not target or source == target:
            continue
        neighbors.setdefault(source, set()).add(target)
        neighbors.setdefault(target, set()).add(source)

    support_counts = {
        node_id: len(
            {
                _coerce_text(source_id)
                for source_id in (node_lookup[node_id].get("source_ids") or [])
                if _coerce_text(source_id)
            }
        )
        for node_id in node_lookup
    }
    degree_counts = {node_id: len(neighbor_ids) for node_id, neighbor_ids in neighbors.items()}
    max_support = max(support_counts.values(), default=0)
    max_degree = max(degree_counts.values(), default=0)

    for node_id, node in node_lookup.items():
        support_count = support_counts.get(node_id, 0)
        degree_count = degree_counts.get(node_id, 0)
        node["support_count"] = support_count
        node["degree_count"] = degree_count
        if max_support and max_degree:
            importance_score = (0.7 * (support_count / max_support)) + (0.3 * (degree_count / max_degree))
        elif max_support:
            importance_score = support_count / max_support
        elif max_degree:
            importance_score = degree_count / max_degree
        else:
            importance_score = 0.0
        node["importance_score"] = round(importance_score, 4)
        node["display_bucket"] = _display_bucket_for_node(
            type=str(node.get("type", "")),
            facet_kind=str(node.get("facet_kind", "")) or None,
            label=str(node.get("label", "")),
        )
        node.update(
            _node_quality_flags(
                label=str(node.get("label", "")),
                support_count=support_count,
                degree_count=degree_count,
                facet_kind=str(node.get("facet_kind", "")) or None,
            )
        )

    return nodes, edges


def _chunk_document_text(document_text: str, target_words: int = 500) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", document_text.strip()) if paragraph.strip()]
    if not paragraphs:
        stripped = document_text.strip()
        return [stripped] if stripped else [document_text]

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for paragraph in paragraphs:
        paragraph_words = len(paragraph.split())
        if current and current_words + paragraph_words > target_words:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_words = paragraph_words
            continue
        current.append(paragraph)
        current_words += paragraph_words

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _edge_identity(edge: dict[str, Any]) -> tuple[str, str, str] | None:
    source = str(edge.get("source") or "").strip()
    target = str(edge.get("target") or "").strip()
    relation = str(edge.get("label") or edge.get("type") or "").strip()
    if not source or not target or not relation:
        return None
    return (source, target, relation)


def _new_node_delta(existing: dict[str, dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    delta: list[dict[str, Any]] = []
    for node in candidates:
        node_id = str(node.get("id") or "").strip()
        if not node_id or node_id in existing:
            continue
        delta.append(node)
    return delta


def _new_edge_delta(
    existing: dict[tuple[str, str, str], dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    delta: list[dict[str, Any]] = []
    for edge in candidates:
        edge_key = _edge_identity(edge)
        if edge_key is None or edge_key in existing:
            continue
        delta.append(edge)
    return delta


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", text.lower())
    stopwords = {"this", "that", "with", "from", "into", "their", "have", "will", "would", "could", "budget"}
    counts: dict[str, int] = {}
    for token in tokens:
        if token in stopwords:
            continue
        counts[token] = counts.get(token, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)]
