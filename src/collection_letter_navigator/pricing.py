"""Model prices from the OpenRouter models endpoint, cached for one session.

Adapted from Sprint 1. OpenRouter does not always report the cost of a call
(it was missing for the structured answer calls in the smoke test), so the app
prices token counts itself. If the endpoint is unavailable the app keeps
working and shows "cost unavailable" instead of a number.

Related: FR-19 AC1, FR-19 AC2, FR-19 AC3, NFR-02
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from collection_letter_navigator import config
from collection_letter_navigator.llm import LlmUsage

#: Reads the raw response body of a URL; replaced by a stub in tests.
Fetcher = Callable[[str], bytes]

#: Seconds to wait for the models endpoint before giving up (NFR-02).
PRICES_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """Price of one model, in USD per token.

    Attributes:
        model: Model identifier as used by OpenRouter.
        prompt_usd_per_token: Price of one prompt token.
        completion_usd_per_token: Price of one completion token.

    Related: FR-19 AC2
    """

    model: str
    prompt_usd_per_token: float
    completion_usd_per_token: float


_cache: dict[str, ModelPrice] | None = None


def _http_get(url: str) -> bytes:
    """Fetch a URL; the models endpoint needs no API key."""
    with urllib.request.urlopen(url, timeout=PRICES_TIMEOUT_SECONDS) as response:  # noqa: S310
        body: bytes = response.read()
        return body


def fetch_model_prices(fetch: Fetcher | None = None) -> dict[str, ModelPrice]:
    """Fetch the price table from the OpenRouter models endpoint.

    Args:
        fetch: Reads a URL; defaults to an HTTP GET with a short timeout.

    Returns:
        A mapping from model identifier to its price; empty if the endpoint is
        unavailable or the answer cannot be read, in which case the UI shows
        "cost unavailable".

    Related: FR-19 AC2, NFR-02
    """
    try:
        payload: Any = json.loads((fetch or _http_get)(config.OPENROUTER_MODELS_URL))
        prices: dict[str, ModelPrice] = {}
        for entry in payload.get("data", []):
            pricing = entry.get("pricing") or {}
            try:
                prices[entry["id"]] = ModelPrice(
                    model=entry["id"],
                    prompt_usd_per_token=float(pricing["prompt"]),
                    completion_usd_per_token=float(pricing["completion"]),
                )
            except (KeyError, TypeError, ValueError):
                continue  # one malformed entry does not spoil the table
        return prices
    except Exception:  # network, HTTP or JSON error: the app keeps working
        return {}


def get_prices(fetch: Fetcher | None = None) -> dict[str, ModelPrice]:
    """Return the price table, fetching it only on the first call.

    An empty table (endpoint unavailable) is not cached, so a later call can
    try again; failures are never cached (NFR-02).

    Related: FR-19 AC2
    """
    global _cache
    if not _cache:
        _cache = fetch_model_prices(fetch)
    return _cache


def clear_cache() -> None:
    """Forget the cached prices (used by tests)."""
    global _cache
    _cache = None


def get_price(model: str, fetch: Fetcher | None = None) -> ModelPrice | None:
    """Look up the cached price of one model.

    Args:
        model: Model identifier.
        fetch: Passed on to :func:`get_prices`.

    Returns:
        The price, or None if the model is unknown or prices are unavailable.

    Related: FR-19 AC2
    """
    return get_prices(fetch).get(model)


def estimate_cost_usd(
    model: str, prompt_tokens: int, completion_tokens: int, fetch: Fetcher | None = None
) -> float | None:
    """Price one call.

    Args:
        model: Model identifier.
        prompt_tokens: Tokens in the prompt.
        completion_tokens: Tokens in the completion, including reasoning tokens.
        fetch: Passed on to :func:`get_prices`.

    Returns:
        The cost in USD, or None when the price is unknown.

    Related: FR-19 AC1, FR-19 AC2
    """
    price = get_price(model, fetch)
    if price is None:
        return None
    return (
        prompt_tokens * price.prompt_usd_per_token
        + completion_tokens * price.completion_usd_per_token
    )


def cost_of(usage: LlmUsage, fetch: Fetcher | None = None) -> float | None:
    """Cost of one call: the cost OpenRouter reported, else the token-based estimate.

    Related: FR-19 AC1, FR-19 AC2
    """
    if usage.cost_usd is not None:
        return usage.cost_usd
    return estimate_cost_usd(usage.model, usage.prompt_tokens, usage.completion_tokens, fetch)
