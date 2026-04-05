# Backend: Gemini Context Caching

> **Implements**: Phase Q (Q8)
> **UserInput Refs**: A3 (token tracking)

## Problem

In a multi-agent simulation (e.g., 250 agents × 5 rounds = 1,250 LLM calls), every call sends the same system prompt + scenario description + policy document. That's ~2,000–5,000 shared tokens repeated thousands of times.

## Solution: Gemini Context Caching

Gemini API supports **context caching**: upload the shared prefix once, get a cache ID, and reference it in all subsequent calls. Cached tokens are billed at ~25% of standard rate.

## Architecture

```
┌─ Simulation Start ──────────────────────────────────┐
│  1. Create cache:                                    │
│     system_prompt + policy_doc + guiding_prompts     │
│     → cache_id                                       │
│                                                       │
│  2. For each agent call:                             │
│     [cache_id] + agent_persona + thread_context      │
│     → response                                        │
│                                                       │
│  3. Simulation end:                                  │
│     Delete cache → clean up                          │
└──────────────────────────────────────────────────────┘
```

## What Gets Cached vs. What Varies

| Cached (shared, paid once) | Dynamic (per agent call) |
|:---------------------------|:-------------------------|
| System prompt | Agent persona text |
| Policy document content | Thread context (posts they've seen) |
| Guiding prompts | Current round instructions |
| Simulation rules | Specific comments to respond to |
| Country-specific context | Agent's own previous posts |

## Implementation

```python
# backend/src/mckainsey/services/caching_llm_client.py

import google.generativeai as genai
from google.generativeai import caching as genai_caching

class CachingLLMClient:
    """Wraps Gemini client with context caching for simulation scenarios."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model
        self.cache = None
        self.token_tracker = TokenTracker()

    def create_simulation_cache(self, system_prompt: str, policy_doc: str,
                                 guiding_prompts: list[str]) -> str:
        """Create a cached context for the simulation session.

        Call this once before simulation starts.
        Returns cache ID for reference in agent calls.
        """
        cached_content = "\n\n".join([
            system_prompt,
            f"## Policy Document\n{policy_doc}",
            f"## Guiding Prompts\n" + "\n".join(f"- {p}" for p in guiding_prompts),
        ])

        self.cache = genai_caching.CachedContent.create(
            model=self.model_name,
            contents=[{"role": "user", "parts": [{"text": cached_content}]}],
            display_name=f"sim_cache_{int(time.time())}",
            ttl=datetime.timedelta(hours=2),  # auto-expire
        )
        return self.cache.name

    def generate_with_cache(self, agent_prompt: str) -> str:
        """Generate a response using the cached context + dynamic agent prompt."""
        model = genai.GenerativeModel.from_cached_content(self.cache)
        response = model.generate_content(agent_prompt)

        # Track tokens
        usage = response.usage_metadata
        self.token_tracker.record(
            input_tokens=usage.prompt_token_count,
            output_tokens=usage.candidates_token_count,
            cached_tokens=usage.cached_content_token_count,
        )

        return response.text

    def delete_cache(self):
        """Clean up cached content after simulation ends."""
        if self.cache:
            self.cache.delete()
            self.cache = None

    def get_token_usage(self) -> dict:
        return self.token_tracker.get_summary()
```

## Token Tracker

```python
# backend/src/mckainsey/services/token_tracker.py

class TokenTracker:
    """Tracks token usage and estimates cost across providers."""

    # Pricing per million tokens (as of 2026)
    PRICING = {
        "gemini-2.0-flash": {"input": 0.075, "output": 0.30, "cached_input": 0.01875},
        "gemini-2.5-pro":   {"input": 1.25,  "output": 5.00, "cached_input": 0.3125},
        "gpt-4o":           {"input": 2.50,  "output": 10.0, "cached_input": None},
        "gpt-4o-mini":      {"input": 0.15,  "output": 0.60, "cached_input": None},
        "ollama":           {"input": 0.0,   "output": 0.0,  "cached_input": 0.0},
    }

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cached_tokens = 0

    def record(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cached_tokens += cached_tokens

    def get_summary(self) -> dict:
        pricing = self.PRICING.get(self.model, self.PRICING["gemini-2.0-flash"])
        uncached_cost = (
            (self.total_input_tokens / 1_000_000) * pricing["input"]
            + (self.total_output_tokens / 1_000_000) * pricing["output"]
        )
        # Cached tokens cost less
        cached_savings = 0
        if pricing["cached_input"] is not None and self.total_cached_tokens > 0:
            full_price = (self.total_cached_tokens / 1_000_000) * pricing["input"]
            cached_price = (self.total_cached_tokens / 1_000_000) * pricing["cached_input"]
            cached_savings = full_price - cached_price

        actual_cost = uncached_cost - cached_savings

        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "estimated_cost_usd": round(actual_cost, 4),
            "cost_without_caching_usd": round(uncached_cost, 4),
            "caching_savings_usd": round(cached_savings, 4),
            "caching_savings_pct": round((cached_savings / uncached_cost) * 100, 1) if uncached_cost > 0 else 0,
            "model": self.model,
        }

    def estimate_cost(self, agent_count: int, rounds: int,
                      avg_input_tokens: int = 3000,
                      avg_output_tokens: int = 500,
                      cached_ratio: float = 0.6) -> dict:
        """Pre-simulation cost estimate for the UI."""
        total_calls = agent_count * rounds
        total_input = total_calls * avg_input_tokens
        total_output = total_calls * avg_output_tokens
        total_cached = int(total_input * cached_ratio)

        pricing = self.PRICING.get(self.model, self.PRICING["gemini-2.0-flash"])
        uncached_cost = (
            (total_input / 1_000_000) * pricing["input"]
            + (total_output / 1_000_000) * pricing["output"]
        )
        if pricing["cached_input"] is not None:
            actual_input_cost = (
                ((total_input - total_cached) / 1_000_000) * pricing["input"]
                + (total_cached / 1_000_000) * pricing["cached_input"]
            )
            actual_cost = actual_input_cost + (total_output / 1_000_000) * pricing["output"]
        else:
            actual_cost = uncached_cost

        return {
            "with_caching_usd": round(actual_cost, 2),
            "without_caching_usd": round(uncached_cost, 2),
            "savings_pct": round(((uncached_cost - actual_cost) / uncached_cost) * 100, 1) if uncached_cost > 0 else 0,
            "model": self.model,
        }
```

## Provider Support Matrix

| Provider | Caching | Token Count | Cost Estimate |
|:---------|:--------|:------------|:-------------|
| **Gemini** | ✅ Native context caching | ✅ `usage_metadata` | ✅ Per-model pricing |
| **OpenAI** | ❌ No caching | ✅ `usage` field | ✅ Per-model pricing |
| **Ollama** | ❌ N/A | ⚠️ Varies by model | Shows "Local (Free)" |

For **OpenAI**: All tokens are standard-rate. `caching_savings = 0`. UI shows "N/A" for caching.

For **Ollama**: Token counts may be available via `/api/chat` response `eval_count`. Cost is always $0.00. UI shows "Local (Free)".

## API Endpoint

```
GET /api/v2/token-usage/{session_id}
→ {total_input_tokens, total_output_tokens, total_cached_tokens, estimated_cost_usd, ...}

GET /api/v2/token-usage/{session_id}/estimate?agents=250&rounds=5
→ {with_caching_usd, without_caching_usd, savings_pct, model}
```

## Tests

- [ ] Cache creation succeeds with valid content
- [ ] `generate_with_cache` returns valid text
- [ ] Token tracker accumulates correctly across multiple calls
- [ ] Cost estimate matches expected formula for each provider
- [ ] Cache auto-deletes when TTL expires
- [ ] Non-Gemini providers work without caching (graceful fallback)
