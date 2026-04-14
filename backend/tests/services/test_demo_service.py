from __future__ import annotations

import json
from pathlib import Path

from miroworld.config import Settings
from miroworld.services.demo_service import DemoService


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        simulation_db_path=str(tmp_path / "simulation.db"),
        console_demo_output_path=str(tmp_path / "demo-output.json"),
        console_demo_frontend_output_path=str(tmp_path / "frontend-demo-output.json"),
        huggingface_api_key="",
    )


def test_demo_service_reads_metric_specific_cached_analytics(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    demo_output = {
        "session": {"session_id": "demo-session"},
        "analytics": {
            "polarization": {"series": [{"round": "Start", "polarization_index": 0.1}]},
            "opinion_flow": {
                "initial": {"supporter": 2, "neutral": 1, "dissenter": 0},
                "final": {"supporter": 3, "neutral": 0, "dissenter": 0},
                "flows": [{"from": "neutral", "to": "supporter", "count": 1}],
            },
            "agent_stances": {
                "stances": [
                    {"agent_id": "agent-0001", "score": 6.0},
                ],
            },
            "by_metric": {
                "approval_rate": {
                    "polarization": {"series": [{"round": "Start", "polarization_index": 0.6}]},
                    "opinion_flow": {
                        "initial": {"supporter": 1, "neutral": 0, "dissenter": 0},
                        "final": {"supporter": 0, "neutral": 0, "dissenter": 1},
                        "flows": [{"from": "supporter", "to": "dissenter", "count": 1}],
                    },
                    "agent_stances": {
                        "stances": [
                            {"agent_id": "agent-0001", "score": 2.0},
                        ],
                    },
                }
            },
        },
    }
    Path(settings.console_demo_output_path).write_text(json.dumps(demo_output), encoding="utf-8")

    service = DemoService(settings)

    aggregate_polarization = service.get_analytics_polarization("session-demo")
    metric_polarization = service.get_analytics_polarization("session-demo", "approval_rate")
    aggregate_flow = service.get_analytics_opinion_flow("session-demo")
    metric_flow = service.get_analytics_opinion_flow("session-demo", "approval_rate")
    aggregate_stances = service.get_analytics_agent_stances("session-demo")
    metric_stances = service.get_analytics_agent_stances("session-demo", "approval_rate")

    assert aggregate_polarization["series"][0]["polarization_index"] == 0.1
    assert metric_polarization["series"][0]["polarization_index"] == 0.6
    assert aggregate_flow["final"]["supporter"] == 3
    assert metric_flow["final"]["dissenter"] == 1
    assert aggregate_stances["stances"][0]["score"] == 6.0
    assert metric_stances["stances"][0]["score"] == 2.0
