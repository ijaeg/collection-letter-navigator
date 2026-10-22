"""Tests for :mod:`collection_letter_navigator.pricing`. No test reaches OpenRouter.

Related: FR-19, NFR-02
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from collection_letter_navigator import pricing
from collection_letter_navigator.llm import LlmUsage

MODELS = {
    "data": [
        {"id": "openai/gpt-5-mini", "pricing": {"prompt": "0.00000025", "completion": "0.000002"}},
        {"id": "broken/model", "pricing": {"prompt": "n/a"}},
    ]
}


class CountingFetcher:
    """Returns the prepared models list and counts the calls."""

    def __init__(self, body: bytes | Exception) -> None:
        self.body = body
        self.calls = 0

    def __call__(self, url: str) -> bytes:
        self.calls += 1
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


@pytest.fixture(autouse=True)
def fresh_cache() -> Iterator[None]:
    """Every test starts without cached prices."""
    pricing.clear_cache()
    yield
    pricing.clear_cache()


def test_module_imports() -> None:
    """The pricing module imports."""
    assert pricing.estimate_cost_usd is not None


def test_fr19_ac2_prices_fetched_once_per_session() -> None:
    """The models endpoint is called once and the result is cached."""
    fetch = CountingFetcher(json.dumps(MODELS).encode())
    assert pricing.get_price("openai/gpt-5-mini", fetch) is not None
    assert pricing.get_price("openai/gpt-5-mini", fetch) is not None
    assert pricing.get_price("broken/model", fetch) is None  # malformed entry skipped
    assert fetch.calls == 1


def test_fr19_ac2_unavailable_endpoint_yields_cost_unavailable() -> None:
    """A failing endpoint returns no prices instead of raising, and is retried later."""
    failing = CountingFetcher(TimeoutError("timed out"))
    assert pricing.estimate_cost_usd("openai/gpt-5-mini", 1000, 100, failing) is None
    assert pricing.estimate_cost_usd("openai/gpt-5-mini", 1000, 100, failing) is None
    assert failing.calls == 2  # an empty table is not cached (NFR-02)
    assert pricing.fetch_model_prices(CountingFetcher(b"not json")) == {}


def test_fr19_ac1_cost_is_prompt_plus_completion_tokens() -> None:
    """Cost is the sum of both token counts priced with the model's rates."""
    fetch = CountingFetcher(json.dumps(MODELS).encode())
    cost = pricing.estimate_cost_usd("openai/gpt-5-mini", 4000, 500, fetch)
    assert cost == pytest.approx(4000 * 0.00000025 + 500 * 0.000002)


def test_fr19_ac1_reported_cost_wins_over_the_estimate() -> None:
    """If OpenRouter reported a cost, that number is used as is."""
    fetch = CountingFetcher(json.dumps(MODELS).encode())
    reported = LlmUsage("openai/gpt-5-mini", 4000, 500, 0, 0.0042)
    unreported = LlmUsage("openai/gpt-5-mini", 4000, 500, 0, None)
    assert pricing.cost_of(reported, fetch) == 0.0042
    assert pricing.cost_of(unreported, fetch) == pytest.approx(0.002)
    assert fetch.calls == 1
