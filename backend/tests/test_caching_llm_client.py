from mckainsey.services.caching_llm_client import CachingLLMClient


def test_caching_llm_client_tracks_usage_with_cache_for_gemini():
    captured: dict[str, object] = {}

    def fake_generate(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {
            "text": "Generated answer",
            "usage": {
                "input_tokens": 1200,
                "output_tokens": 180,
                "cached_tokens": 900,
            },
        }

    client = CachingLLMClient(
        provider="google",
        model="gemini-2.0-flash",
        generate_fn=fake_generate,
    )
    cache_id = client.create_simulation_cache(
        system_prompt="System instructions",
        policy_doc="Policy document body",
        guiding_prompts=["Focus on affordability", "Track demographic shifts"],
    )
    response = client.generate_with_cache("How will this affect commuters?")
    usage = client.get_token_usage()

    assert cache_id.startswith("cache-")
    assert response == "Generated answer"
    assert captured["cache_id"] == cache_id
    assert captured["agent_prompt"] == "How will this affect commuters?"
    assert "System instructions" in client._cached_context
    assert "Policy document body" in client._cached_context
    assert "Focus on affordability" in client._cached_context
    assert usage["total_input_tokens"] == 1200
    assert usage["total_output_tokens"] == 180
    assert usage["total_cached_tokens"] == 900
    assert usage["model"] == "gemini-2.0-flash"
    assert usage["caching_savings_usd"] > 0


def test_caching_llm_client_non_gemini_provider_zeroes_cached_tokens():
    def fake_generate(payload: dict[str, object]) -> dict[str, object]:
        assert payload["cache_id"] is None
        return {
            "text": "OpenAI answer",
            "usage": {
                "input_tokens": 600,
                "output_tokens": 120,
                "cached_tokens": 500,
            },
        }

    client = CachingLLMClient(
        provider="openai",
        model="gpt-4o",
        generate_fn=fake_generate,
    )
    _ = client.create_simulation_cache(
        system_prompt="System instructions",
        policy_doc="Policy document body",
        guiding_prompts=["Focus on affordability"],
    )
    response = client.generate_with_cache("Summarize major objections.")
    usage = client.get_token_usage()

    assert response == "OpenAI answer"
    assert usage["total_cached_tokens"] == 0
    assert usage["caching_savings_usd"] == 0
    assert usage["model"] == "gpt-4o"


def test_caching_llm_client_estimate_delegates_to_token_tracker():
    client = CachingLLMClient(provider="google", model="gemini-2.5-pro", generate_fn=lambda payload: {"text": "", "usage": {}})

    estimate = client.estimate_usage(agent_count=5, rounds=2, avg_input_tokens=1000, avg_output_tokens=250, cached_ratio=0.4)

    assert estimate["model"] == "gemini-2.5-pro"
    assert estimate["without_caching_usd"] > estimate["with_caching_usd"]


def test_caching_llm_client_auto_deletes_expired_cache(monkeypatch):
    captured: dict[str, object] = {}
    time_values = iter([1000.0, 1011.0, 1011.0])

    def fake_time():
        return next(time_values)

    def fake_generate(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {
            "text": "Expired cache response",
            "usage": {
                "input_tokens": 40,
                "output_tokens": 10,
                "cached_tokens": 25,
            },
        }

    monkeypatch.setattr("mckainsey.services.caching_llm_client.time.time", fake_time)

    client = CachingLLMClient(provider="google", model="gemini-2.0-flash", generate_fn=fake_generate)
    cache_id = client.create_simulation_cache("System", "Policy", ["Prompt"], ttl_seconds=10)
    response = client.generate_with_cache("Explain the latest change.")

    assert cache_id.startswith("cache-")
    assert response == "Expired cache response"
    assert captured["cache_id"] is None
    assert captured["cached_context"] is None
    assert client._cache_id is None
    assert client._cached_context is None
    assert client.get_token_usage()["total_cached_tokens"] == 0
