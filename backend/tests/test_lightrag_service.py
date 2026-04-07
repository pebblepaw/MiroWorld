from __future__ import annotations

import asyncio
import json

import pytest
from lightrag.types import KnowledgeGraph, KnowledgeGraphEdge, KnowledgeGraphNode

from mckainsey.config import Settings
from mckainsey.services.lightrag_service import (
    LightRAGService,
    _adapt_native_lightrag_graph,
    _build_graph_extraction_prompt,
    _build_graph_from_text,
)


def test_lightrag_extraction_returns_multiple_normalized_relation_labels(monkeypatch, tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        lightrag_workdir=str(tmp_path / "lightrag"),
        gemini_api_key="test-key",
    )

    extracted = {
        "nodes": [
            {
                "id": "policy:transport_subsidy",
                "label": "Transport Subsidy",
                "type": "policy",
                "description": "A subsidy for public transport fares.",
                "weight": 0.93,
            },
            {
                "id": "program:commuter_rebate",
                "label": "Commuter Rebate",
                "type": "program",
                "description": "Monthly rebate for eligible commuters.",
                "weight": 0.87,
            },
            {
                "id": "group:seniors",
                "label": "Seniors",
                "type": "population",
                "description": "Older residents with higher transport sensitivity.",
                "weight": 0.81,
            },
            {
                "id": "area:woodlands",
                "label": "Woodlands",
                "type": "location",
                "description": "Planning area where the program is piloted.",
                "weight": 0.76,
            },
        ],
        "edges": [
            {
                "source": "policy:transport_subsidy",
                "target": "program:commuter_rebate",
                "type": "funded by",
                "label": "Funded by",
            },
            {
                "source": "program:commuter_rebate",
                "target": "group:seniors",
                "type": "targets",
                "label": "Targets seniors",
            },
            {
                "source": "program:commuter_rebate",
                "target": "area:woodlands",
                "type": "located in",
                "label": "Located in Woodlands",
            },
            {
                "source": "policy:transport_subsidy",
                "target": "group:seniors",
                "type": "affects",
                "label": "Affects seniors",
            },
        ],
    }

    def fake_complete(model, prompt, **kwargs):
        assert model == settings.gemini_model
        assert "transport costs" in prompt.lower()
        assert "Woodlands" in prompt
        return json.dumps(extracted)

    monkeypatch.setattr("mckainsey.services.lightrag_service.openai_complete_if_cache", fake_complete)

    result_nodes, result_edges = asyncio.run(
        _build_graph_from_text(
            document_text=(
                "The Ministry of Transport will fund a commuter rebate to offset transport costs. "
                "The program targets seniors and is piloted in Woodlands."
            ),
            guiding_prompt="Focus on how the policy funds transport costs for seniors in Woodlands.",
            settings=settings,
        )
    )

    edge_types = {edge["type"] for edge in result_edges}
    assert {"funds", "targets", "located_in", "affects"}.issubset(edge_types)

    node_by_id = {node["id"]: node for node in result_nodes}
    assert node_by_id["policy:transport_subsidy"]["description"] == "A subsidy for public transport fares."
    assert node_by_id["policy:transport_subsidy"]["weight"] == 0.93
    assert node_by_id["area:woodlands"]["type"] == "location"
    assert all("label" in edge for edge in result_edges)


def test_build_graph_extraction_prompt_adds_compact_guidance_for_ollama_provider():
    prompt = _build_graph_extraction_prompt(
        "Policy text about transport credits and planning-area pilots.",
        "Focus on seniors in Woodlands and Yishun.",
        provider="ollama",
    )

    lowered = prompt.lower()
    assert "document text" in lowered
    assert "guiding prompt" in lowered
    assert "at most 30 nodes" in lowered
    assert "45 edges" in lowered


def test_native_lightrag_graph_adapter_adds_facet_metadata_and_preserves_relation_labels():
    native_graph = KnowledgeGraph(
        nodes=[
            KnowledgeGraphNode(
                id="Budget 2026",
                labels=["Budget 2026"],
                properties={
                    "entity_id": "Budget 2026",
                    "entity_type": "policy",
                    "description": "Budget 2026 support measures.",
                    "source_id": "chunk-1<SEP>chunk-2",
                    "file_path": "budget.md",
                },
            ),
            KnowledgeGraphNode(
                id="Woodlands",
                labels=["Woodlands"],
                properties={
                    "entity_id": "Woodlands",
                    "entity_type": "location",
                    "description": "Planning area in Singapore.",
                    "source_id": "chunk-2",
                    "file_path": "budget.md",
                },
            ),
            KnowledgeGraphNode(
                id="Seniors",
                labels=["Seniors"],
                properties={
                    "entity_id": "Seniors",
                    "entity_type": "population",
                    "description": "Older residents affected by the plan.",
                    "source_id": "chunk-3",
                    "file_path": "budget.md",
                },
            ),
            KnowledgeGraphNode(
                id="Gardening",
                labels=["Gardening"],
                properties={
                    "entity_id": "Gardening",
                    "entity_type": "concept",
                    "description": "A common hobby among some residents.",
                    "source_id": "chunk-4",
                    "file_path": "budget.md",
                },
            ),
            KnowledgeGraphNode(
                id="Residents",
                labels=["Residents"],
                properties={
                    "entity_id": "Residents",
                    "entity_type": "demographic",
                    "description": "Residents affected by the plan.",
                    "source_id": "chunk-5",
                    "file_path": "budget.md",
                },
            ),
        ],
        edges=[
            KnowledgeGraphEdge(
                id="Budget 2026->Seniors",
                type=None,
                source="Budget 2026",
                target="Seniors",
                properties={
                    "keywords": "transport support, targeted assistance",
                    "description": "Budget 2026 targets seniors with transport support.",
                    "source_id": "chunk-3",
                    "file_path": "budget.md",
                },
            ),
            KnowledgeGraphEdge(
                id="Budget 2026->Woodlands",
                type=None,
                source="Budget 2026",
                target="Woodlands",
                properties={
                    "keywords": "pilot area",
                    "description": "The measures are piloted in Woodlands.",
                    "source_id": "chunk-2",
                    "file_path": "budget.md",
                },
            ),
        ],
    )

    graph = _adapt_native_lightrag_graph(native_graph)
    node_by_id = {node["id"]: node for node in graph["entity_nodes"]}
    edge_by_id = {(edge["source"], edge["target"]): edge for edge in graph["relationship_edges"]}

    assert node_by_id["Woodlands"]["facet_kind"] == "planning_area"
    assert "facet" in node_by_id["Woodlands"]["families"]
    assert node_by_id["Woodlands"]["canonical_key"] == "planning_area:woodlands"

    assert node_by_id["Seniors"]["facet_kind"] == "age_cohort"
    assert node_by_id["Seniors"]["canonical_key"] == "age_cohort:senior"
    assert "document" in node_by_id["Seniors"]["families"]

    assert node_by_id["Gardening"]["facet_kind"] == "hobby"
    assert node_by_id["Gardening"]["canonical_key"] == "hobby:gardening"
    assert node_by_id["Residents"]["display_bucket"] == "persons"

    transport_edge = edge_by_id[("Budget 2026", "Seniors")]
    assert transport_edge["label"] == "transport support, targeted assistance"
    assert transport_edge["normalized_type"] == "targets"
    assert transport_edge["raw_relation_text"] == "transport support, targeted assistance"

    woodlands_edge = edge_by_id[("Budget 2026", "Woodlands")]
    assert woodlands_edge["label"] == "pilot area"
    assert woodlands_edge["normalized_type"] == "located_in"


def test_native_lightrag_graph_adapter_dedupes_descriptions_and_applies_display_buckets_and_importance():
    native_graph = KnowledgeGraph(
        nodes=[
            KnowledgeGraphNode(
                id="Singapore",
                labels=["Singapore"],
                properties={
                    "entity_id": "Singapore",
                    "entity_type": "location",
                    "description": "A country with older residents.<SEP>A country with older residents.",
                    "source_id": "chunk-1<SEP>chunk-1<SEP>chunk-2",
                    "file_path": "policy.md<SEP>policy.md",
                },
            ),
            KnowledgeGraphNode(
                id="TFR",
                labels=["TFR"],
                properties={
                    "entity_id": "TFR",
                    "entity_type": "metric",
                    "description": "Total fertility rate remains low.<SEP>Total fertility rate remains low.",
                    "source_id": "chunk-3<SEP>chunk-3",
                    "file_path": "policy.md",
                },
            ),
            KnowledgeGraphNode(
                id="Seniors",
                labels=["Seniors"],
                properties={
                    "entity_id": "Seniors",
                    "entity_type": "population",
                    "description": "Older residents affected by the policy.<SEP>Older residents affected by the policy.",
                    "source_id": "chunk-4<SEP>chunk-5",
                    "file_path": "policy.md",
                },
            ),
            KnowledgeGraphNode(
                id="Manufacturing",
                labels=["Manufacturing"],
                properties={
                    "entity_id": "Manufacturing",
                    "entity_type": "concept",
                    "description": "An affected industry segment.",
                    "source_id": "chunk-6",
                    "file_path": "policy.md",
                },
            ),
            KnowledgeGraphNode(
                id="Ministry of Manpower",
                labels=["Ministry of Manpower"],
                properties={
                    "entity_id": "Ministry of Manpower",
                    "entity_type": "organization",
                    "description": "Government agency overseeing manpower policy.",
                    "source_id": "chunk-7<SEP>chunk-8<SEP>chunk-9",
                    "file_path": "policy.md",
                },
            ),
        ],
        edges=[
            KnowledgeGraphEdge(
                id="Ministry of Manpower->Seniors",
                type=None,
                source="Ministry of Manpower",
                target="Seniors",
                properties={
                    "keywords": "targets, supports",
                    "description": (
                        "The policy supports seniors through training grants."
                        "<SEP>The policy supports seniors through training grants."
                    ),
                    "source_id": "chunk-8<SEP>chunk-8<SEP>chunk-10",
                    "file_path": "policy.md<SEP>policy.md",
                },
            ),
            KnowledgeGraphEdge(
                id="Ministry of Manpower->Singapore",
                type=None,
                source="Ministry of Manpower",
                target="Singapore",
                properties={
                    "keywords": "located in",
                    "description": "The policy is implemented in Singapore.",
                    "source_id": "chunk-9",
                    "file_path": "policy.md",
                },
            ),
            KnowledgeGraphEdge(
                id="Ministry of Manpower->Manufacturing",
                type=None,
                source="Ministry of Manpower",
                target="Manufacturing",
                properties={
                    "keywords": "affects",
                    "description": "The policy affects manufacturing employers.",
                    "source_id": "chunk-9",
                    "file_path": "policy.md",
                },
            ),
        ],
    )

    graph = _adapt_native_lightrag_graph(native_graph)
    node_by_id = {node["id"]: node for node in graph["entity_nodes"]}
    edge_by_id = {(edge["source"], edge["target"]): edge for edge in graph["relationship_edges"]}

    assert node_by_id["Singapore"].get("facet_kind") != "age_cohort"
    assert node_by_id["TFR"].get("facet_kind") != "age_cohort"
    assert node_by_id["Seniors"]["facet_kind"] == "age_cohort"

    assert node_by_id["Ministry of Manpower"]["display_bucket"] == "organization"
    assert node_by_id["Seniors"]["display_bucket"] == "age_group"
    assert node_by_id["Singapore"]["display_bucket"] == "location"
    assert node_by_id["Manufacturing"]["display_bucket"] == "industry"
    assert node_by_id["TFR"]["display_bucket"] == "other"

    assert node_by_id["Singapore"]["description"] == "A country with older residents."
    assert node_by_id["TFR"]["description"] == "Total fertility rate remains low."

    seniors_edge = edge_by_id[("Ministry of Manpower", "Seniors")]
    assert seniors_edge["description"] == "The policy supports seniors through training grants."
    assert seniors_edge["summary"] == "The policy supports seniors through training grants."
    assert seniors_edge["source_ids"] == ["chunk-8", "chunk-10"]

    assert node_by_id["Ministry of Manpower"]["support_count"] == 3
    assert node_by_id["Ministry of Manpower"]["degree_count"] == 3
    assert node_by_id["Ministry of Manpower"]["importance_score"] == 1.0
    assert node_by_id["Singapore"]["support_count"] == 2
    assert node_by_id["Singapore"]["degree_count"] == 1
    assert node_by_id["Singapore"]["importance_score"] == 0.5667
    assert node_by_id["TFR"]["source_ids"] == ["chunk-3"]
    assert node_by_id["TFR"]["file_paths"] == ["policy.md"]
    assert node_by_id["TFR"]["provenance"]["source_ids"] == ["chunk-3"]


def test_native_lightrag_graph_adapter_broadens_demographic_facets_and_flags_hidden_placeholder_nodes():
    native_graph = KnowledgeGraph(
        nodes=[
            KnowledgeGraphNode(
                id="Elderly People",
                labels=["Elderly People"],
                properties={
                    "entity_id": "Elderly People",
                    "entity_type": "population",
                    "description": "Older Singaporeans facing high living costs.",
                    "source_id": "chunk-1<SEP>chunk-2",
                    "file_path": "article.docx",
                },
            ),
            KnowledgeGraphNode(
                id="Japan",
                labels=["Japan"],
                properties={
                    "entity_id": "Japan",
                    "entity_type": "location",
                    "description": "Japan has an ageing population.",
                    "source_id": "chunk-3",
                    "file_path": "article.docx",
                },
            ),
            KnowledgeGraphNode(
                id="Concept",
                labels=["Concept"],
                properties={
                    "entity_id": "Concept",
                    "entity_type": "entity",
                    "description": "Generic placeholder text.",
                    "source_id": "chunk-4",
                    "file_path": "article.docx",
                },
            ),
        ],
        edges=[
            KnowledgeGraphEdge(
                id="Japan->Elderly People",
                type=None,
                source="Japan",
                target="Elderly People",
                properties={
                    "keywords": "comparison",
                    "description": "Japan is used as a comparison point for elderly people.",
                    "source_id": "chunk-3",
                    "file_path": "article.docx",
                },
            ),
        ],
    )

    graph = _adapt_native_lightrag_graph(native_graph)
    node_by_id = {node["id"]: node for node in graph["entity_nodes"]}

    assert node_by_id["Elderly People"]["facet_kind"] == "age_cohort"
    assert node_by_id["Elderly People"]["canonical_key"] == "age_cohort:senior"
    assert node_by_id["Japan"].get("facet_kind") != "age_cohort"

    assert node_by_id["Concept"]["generic_placeholder"] is True
    assert node_by_id["Concept"]["low_value_orphan"] is True
    assert node_by_id["Concept"]["ui_default_hidden"] is True
    assert node_by_id["Concept"]["source_ids"] == ["chunk-4"]


def test_native_lightrag_graph_adapter_keeps_isolated_facet_nodes_visible():
    native_graph = KnowledgeGraph(
        nodes=[
            KnowledgeGraphNode(
                id="Elderly People",
                labels=["Elderly People"],
                properties={
                    "entity_id": "Elderly People",
                    "entity_type": "population",
                    "description": "Older people affected by the policy.",
                    "source_id": "chunk-1",
                    "file_path": "article.docx",
                },
            ),
        ],
        edges=[],
    )

    graph = _adapt_native_lightrag_graph(native_graph)
    elderly = graph["entity_nodes"][0]

    assert elderly["facet_kind"] == "age_cohort"
    assert elderly["low_value_orphan"] is True
    assert elderly["ui_default_hidden"] is False


def test_process_document_prefers_native_lightrag_graph(monkeypatch, tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        lightrag_workdir=str(tmp_path / "lightrag"),
        gemini_api_key="test-key",
    )
    service = LightRAGService(settings)

    class FakeRag:
        async def ainsert(self, *args, **kwargs):
            return None

        async def aquery(self, *args, **kwargs):
            return "Native LightRAG summary."

    async def fake_ensure_ready():
        return None

    async def fake_load_document_native_graph(rag, document_id):
        assert document_id.startswith("doc-")
        return KnowledgeGraph(
            nodes=[
                KnowledgeGraphNode(
                    id="Budget 2026",
                    labels=["Budget 2026"],
                    properties={"entity_id": "Budget 2026", "entity_type": "policy", "source_id": "chunk-1"},
                ),
                KnowledgeGraphNode(
                    id="Woodlands",
                    labels=["Woodlands"],
                    properties={"entity_id": "Woodlands", "entity_type": "location", "source_id": "chunk-2"},
                ),
            ],
            edges=[
                KnowledgeGraphEdge(
                    id="Budget 2026->Woodlands",
                    type=None,
                    source="Budget 2026",
                    target="Woodlands",
                    properties={"keywords": "pilot area", "description": "The measures are piloted in Woodlands."},
                )
            ],
        )

    async def fail_fallback(*args, **kwargs):
        raise AssertionError("Fallback graph extraction should not run when native LightRAG graph is available")

    service._rag = FakeRag()
    monkeypatch.setattr(service, "ensure_ready", fake_ensure_ready)
    monkeypatch.setattr("mckainsey.services.lightrag_service._load_document_native_graph", fake_load_document_native_graph)
    monkeypatch.setattr("mckainsey.services.lightrag_service._build_graph_from_text", fail_fallback)

    payload = asyncio.run(
        service.process_document(
            simulation_id="session-native",
            document_text="Budget 2026 pilots transport support in Woodlands.",
            source_path=str(tmp_path / "budget.md"),
            guiding_prompt="Focus on place-based transport support.",
        )
    )

    assert payload["graph_origin"] == "lightrag_native"
    assert payload["summary"] == "Native LightRAG summary."
    assert payload["relationship_edges"][0]["label"] == "pilot area"
    assert payload["entity_nodes"][1]["canonical_key"] == "planning_area:woodlands"
    assert payload["document"]["paragraph_count"] == 1


def test_process_document_live_mode_rejects_fallback_graph(monkeypatch, tmp_path):
    settings = Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        lightrag_workdir=str(tmp_path / "lightrag"),
        gemini_api_key="test-key",
    )
    service = LightRAGService(settings)

    class FakeRag:
        async def ainsert(self, *args, **kwargs):
            return None

        async def aquery(self, *args, **kwargs):
            return "Native LightRAG summary."

    async def fake_ensure_ready():
        return None

    async def fake_load_document_native_graph(rag, document_id):
        assert document_id.startswith("doc-")
        return None

    async def fail_fallback(*args, **kwargs):
        raise AssertionError("Fallback graph extraction should not run in live mode")

    service._rag = FakeRag()
    monkeypatch.setattr(service, "ensure_ready", fake_ensure_ready)
    monkeypatch.setattr("mckainsey.services.lightrag_service._load_document_native_graph", fake_load_document_native_graph)
    monkeypatch.setattr("mckainsey.services.lightrag_service._build_graph_from_text", fail_fallback)

    with pytest.raises(RuntimeError, match="Live"):
        asyncio.run(
            service.process_document(
                simulation_id="session-live",
                document_text="Budget 2026 pilots transport support in Woodlands.",
                source_path=str(tmp_path / "budget.md"),
                guiding_prompt="Focus on place-based transport support.",
                live_mode=True,
            )
        )
