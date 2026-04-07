from __future__ import annotations


class TokenTracker:
    """Track token usage and estimate provider-aware costs."""

    PRICING = {
        "gemini-2.0-flash": {"input": 0.075, "output": 0.30, "cached_input": 0.01875},
        "gemini-2.5-pro": {"input": 1.25, "output": 5.00, "cached_input": 0.3125},
        "gpt-4o": {"input": 2.50, "output": 10.0, "cached_input": None},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached_input": None},
        "ollama": {"input": 0.0, "output": 0.0, "cached_input": 0.0},
    }

    def __init__(self, model: str = "gemini-2.0-flash") -> None:
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cached_tokens = 0

    def record(self, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> None:
        self.total_input_tokens += int(input_tokens)
        self.total_output_tokens += int(output_tokens)
        self.total_cached_tokens += int(cached_tokens)

    def get_summary(self) -> dict[str, float | int | str]:
        pricing = self._pricing_for_model(self.model)
        uncached_cost = self._uncached_cost(
            input_tokens=self.total_input_tokens,
            output_tokens=self.total_output_tokens,
            pricing=pricing,
        )
        cached_savings = self._cached_savings(self.total_cached_tokens, pricing)
        actual_cost = max(0.0, uncached_cost - cached_savings)

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

    def estimate_cost(
        self,
        agent_count: int,
        rounds: int,
        avg_input_tokens: int = 3000,
        avg_output_tokens: int = 500,
        cached_ratio: float = 0.6,
    ) -> dict[str, float | str]:
        total_calls = max(0, int(agent_count)) * max(0, int(rounds))
        total_input = total_calls * max(0, int(avg_input_tokens))
        total_output = total_calls * max(0, int(avg_output_tokens))
        total_cached = int(total_input * max(0.0, min(1.0, float(cached_ratio))))

        pricing = self._pricing_for_model(self.model)
        uncached_cost = self._uncached_cost(total_input, total_output, pricing)
        if pricing["cached_input"] is None:
            actual_cost = uncached_cost
        else:
            actual_cost = (
                ((total_input - total_cached) / 1_000_000) * pricing["input"]
                + (total_cached / 1_000_000) * pricing["cached_input"]
                + (total_output / 1_000_000) * pricing["output"]
            )

        savings = max(0.0, uncached_cost - actual_cost)
        return {
            "with_caching_usd": round(actual_cost, 2),
            "without_caching_usd": round(uncached_cost, 2),
            "savings_pct": round((savings / uncached_cost) * 100, 1) if uncached_cost > 0 else 0,
            "model": self.model,
        }

    def _pricing_for_model(self, model: str) -> dict[str, float | None]:
        return self.PRICING.get(model, self.PRICING["gemini-2.0-flash"])

    def _uncached_cost(self, input_tokens: int, output_tokens: int, pricing: dict[str, float | None]) -> float:
        return (
            (input_tokens / 1_000_000) * float(pricing["input"] or 0.0)
            + (output_tokens / 1_000_000) * float(pricing["output"] or 0.0)
        )

    def _cached_savings(self, cached_tokens: int, pricing: dict[str, float | None]) -> float:
        cached_input = pricing.get("cached_input")
        if cached_input is None or cached_tokens <= 0:
            return 0.0
        full_price = (cached_tokens / 1_000_000) * float(pricing["input"] or 0.0)
        cached_price = (cached_tokens / 1_000_000) * float(cached_input)
        return max(0.0, full_price - cached_price)
