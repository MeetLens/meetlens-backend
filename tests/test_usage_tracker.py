from types import SimpleNamespace

from services.usage_tracker import ModelPricing, TokenUsageTracker


class DummyResponse:
    def __init__(self, prompt_tokens=0, completion_tokens=0, total_tokens=None):
        total = total_tokens if total_tokens is not None else prompt_tokens + completion_tokens
        self.usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
        )


def test_usage_tracker_accumulates_tokens_and_costs():
    tracker = TokenUsageTracker(
        model_pricing={"test-model": ModelPricing(input_per_1k=0.001, output_per_1k=0.002)}
    )

    response = DummyResponse(prompt_tokens=1000, completion_tokens=500)
    record = tracker.track_completion_response(model="test-model", response=response, request_name="unit-test")

    assert record is not None
    assert record.prompt_tokens == 1000
    assert record.completion_tokens == 500
    assert record.total_tokens == 1500
    assert abs(record.input_cost - 0.001) < 1e-9
    assert abs(record.output_cost - 0.001) < 1e-9
    assert abs(record.total_cost - 0.002) < 1e-9

    assert tracker.totals.prompt_tokens == 1000
    assert tracker.totals.completion_tokens == 500
    assert tracker.totals.total_tokens == 1500
    assert abs(tracker.totals.total_cost - 0.002) < 1e-9


def test_usage_tracker_handles_missing_usage():
    tracker = TokenUsageTracker()

    class ResponseWithoutUsage:
        pass

    record = tracker.track_completion_response(
        model="unknown-model",
        response=ResponseWithoutUsage(),
        request_name="missing-usage",
    )

    assert record is None
    assert tracker.totals.prompt_tokens == 0
    assert tracker.totals.total_cost == 0.0

