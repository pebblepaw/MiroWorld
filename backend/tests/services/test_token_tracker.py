from __future__ import annotations

import pytest

from miroworld.services.token_tracker import TokenTracker


def test_token_tracker_uses_configured_gemini_flash_lite_pricing() -> None:
    tracker = TokenTracker(model="gemini-2.5-flash-lite")
    tracker.record(input_tokens=1_000_000, output_tokens=1_000_000)

    summary = tracker.get_summary()

    assert summary["estimated_cost_usd"] == 0.5
    assert summary["pricing_last_updated"]


def test_token_tracker_estimate_cost_reports_pricing_version() -> None:
    tracker = TokenTracker(model="gemini-2.5-flash-lite")

    estimate = tracker.estimate_cost(
        agent_count=10,
        rounds=2,
        avg_input_tokens=1_000_000,
        avg_output_tokens=1_000_000,
        cached_ratio=0.0,
    )

    assert estimate["with_caching_usd"] == 10.0
    assert estimate["pricing_last_updated"]


def test_token_tracker_rejects_unknown_model_pricing() -> None:
    tracker = TokenTracker(model="missing-model")

    with pytest.raises(ValueError, match="No pricing configured"):
        tracker.estimate_cost(agent_count=10, rounds=2)
