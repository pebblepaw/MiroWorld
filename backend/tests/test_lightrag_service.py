from __future__ import annotations

import asyncio
import json

from mckainsey.config import Settings
from mckainsey.services.lightrag_service import _build_graph_from_text


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
