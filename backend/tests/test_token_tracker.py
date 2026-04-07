from __future__ import annotations

import pytest


def test_token_tracker_accumulates_usage_and_applies_gemini_caching_savings():
    from mckainsey.services.token_tracker import TokenTracker

    tracker = TokenTracker(model="gemini-2.0-flash")
    tracker.record(input_tokens=1_000_000, output_tokens=500_000, cached_tokens=250_000)
    tracker.record(input_tokens=500_000, output_tokens=250_000, cached_tokens=250_000)

    summary = tracker.get_summary()

    assert summary["total_input_tokens"] == 1_500_000
    assert summary["total_output_tokens"] == 750_000
    assert summary["total_cached_tokens"] == 500_000
    assert summary["model"] == "gemini-2.0-flash"
    assert summary["cost_without_caching_usd"] == 0.3375
    assert summary["caching_savings_usd"] == 0.0281
    assert summary["estimated_cost_usd"] == 0.3094
    assert summary["caching_savings_pct"] == 8.3


@pytest.mark.parametrize(
    "model,expected_with,expected_without",
    [
        ("gpt-4o", 1.65, 1.65),
        ("ollama", 0.0, 0.0),
    ],
)
def test_token_tracker_estimate_cost_handles_openai_and_ollama(model, expected_with, expected_without):
    from mckainsey.services.token_tracker import TokenTracker

    tracker = TokenTracker(model=model)
    estimate = tracker.estimate_cost(agent_count=10, rounds=3, avg_input_tokens=10_000, avg_output_tokens=3_000, cached_ratio=0.6)

    assert estimate["model"] == model
    assert estimate["with_caching_usd"] == expected_with
    assert estimate["without_caching_usd"] == expected_without


def test_token_tracker_estimate_cost_uses_cached_ratio_for_gemini():
    from mckainsey.services.token_tracker import TokenTracker

    tracker = TokenTracker(model="gemini-2.5-pro")
    estimate = tracker.estimate_cost(agent_count=1, rounds=1, avg_input_tokens=1_000_000, avg_output_tokens=200_000, cached_ratio=0.5)

    assert estimate["without_caching_usd"] == 2.25
    assert estimate["with_caching_usd"] == 1.78
    assert estimate["savings_pct"] == 20.8
