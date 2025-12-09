"""Lightweight token usage tracker for OpenAI completions.

This module extracts token usage from completion responses when available,
keeps per-request history, aggregates totals, and estimates cost using
model-specific pricing.
"""

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPricing:
    """Pricing information per 1K tokens for a model."""

    input_per_1k: float
    output_per_1k: float


# Pricing is stored per 1K tokens to simplify calculations.
# Values are based on publicly available OpenAI pricing as of mid-2024.
DEFAULT_MODEL_PRICING: Dict[str, ModelPricing] = {
    "gpt-5-nano": ModelPricing(input_per_1k=0.00005, output_per_1k=0.00015),
    "gpt-4.1-mini": ModelPricing(input_per_1k=0.00015, output_per_1k=0.0006),
    "gpt-4.1": ModelPricing(input_per_1k=0.005, output_per_1k=0.015),
    "gpt-4o-mini": ModelPricing(input_per_1k=0.00015, output_per_1k=0.0006),
    "gpt-4o": ModelPricing(input_per_1k=0.0025, output_per_1k=0.01),
}


@dataclass
class UsageRecord:
    """Represents the usage and costs for a single request."""

    request_name: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float


@dataclass
class UsageTotals:
    """Aggregated usage across all requests."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0


class TokenUsageTracker:
    """Tracks per-request token usage and aggregates totals."""

    def __init__(self, model_pricing: Optional[Dict[str, ModelPricing]] = None):
        self.model_pricing = model_pricing or DEFAULT_MODEL_PRICING
        self.history: List[UsageRecord] = []
        self.totals: UsageTotals = UsageTotals()

    def track_completion_response(
        self,
        *,
        model: str,
        response,
        request_name: str = "completion",
    ) -> Optional[UsageRecord]:
        """Extract usage info from a completion response and record it.

        Args:
            model: Model used for the completion.
            response: Completion response object (should contain `.usage`).
            request_name: Human-readable name for the request (for logging).

        Returns:
            UsageRecord if usage information was found, otherwise None.
        """

        usage = getattr(response, "usage", None)
        if not usage:
            logger.debug(
                "No usage information available for %s request with model %s",
                request_name,
                model,
            )
            return None

        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (
            prompt_tokens + completion_tokens
        )

        pricing = self._resolve_pricing(model)
        input_cost = self._calculate_cost(prompt_tokens, pricing.input_per_1k) if pricing else 0.0
        output_cost = self._calculate_cost(completion_tokens, pricing.output_per_1k) if pricing else 0.0

        record = UsageRecord(
            request_name=request_name,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
        )

        self.history.append(record)
        self._update_totals(record)

        logger.info(
            "Token usage for %s (%s): prompt=%s, completion=%s, total=%s, cost=$%.6f",
            request_name,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            record.total_cost,
        )

        logger.debug(
            "Updated totals: prompt=%s, completion=%s, total=%s, cost=$%.6f",
            self.totals.prompt_tokens,
            self.totals.completion_tokens,
            self.totals.total_tokens,
            self.totals.total_cost,
        )

        return record

    def _resolve_pricing(self, model: str) -> Optional[ModelPricing]:
        """Resolve pricing for a model using exact or prefix matching."""

        if model in self.model_pricing:
            return self.model_pricing[model]

        # Fallback: check if the model starts with a known prefix (e.g., versioned names)
        for key, pricing in self.model_pricing.items():
            if model.startswith(key):
                return pricing
        return None

    def _calculate_cost(self, tokens: int, rate_per_1k: float) -> float:
        """Calculate dollar cost for a token count at the provided rate."""

        return (tokens / 1000.0) * rate_per_1k

    def _update_totals(self, record: UsageRecord) -> None:
        """Update aggregate totals with a new usage record."""

        self.totals.prompt_tokens += record.prompt_tokens
        self.totals.completion_tokens += record.completion_tokens
        self.totals.total_tokens += record.total_tokens
        self.totals.input_cost += record.input_cost
        self.totals.output_cost += record.output_cost
        self.totals.total_cost += record.total_cost


# Shared tracker instance for application-wide usage tracking
usage_tracker = TokenUsageTracker()


__all__ = [
    "ModelPricing",
    "UsageRecord",
    "UsageTotals",
    "TokenUsageTracker",
    "usage_tracker",
]

