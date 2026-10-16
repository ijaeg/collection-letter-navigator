"""Model prices from the OpenRouter models endpoint, cached for one session.

Adapted from Sprint 1. If the endpoint is unavailable the app keeps working and
shows "cost unavailable" instead of a number.

Related: FR-19 AC1, FR-19 AC2, FR-19 AC3, NFR-02
"""

from __future__ import annotations

from dataclasses import dataclass


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


def fetch_model_prices() -> dict[str, ModelPrice]:
    """Fetch the price table from the OpenRouter models endpoint.

    Returns:
        A mapping from model identifier to its price; empty if the endpoint is
        unavailable, in which case the UI shows "cost unavailable".

    Related: FR-19 AC2, NFR-02
    """
    raise NotImplementedError("FR-19 AC2: fetch prices once per session and cache them")


def get_price(model: str) -> ModelPrice | None:
    """Look up the cached price of one model.

    Args:
        model: Model identifier.

    Returns:
        The price, or None if the model is unknown or prices are unavailable.

    Related: FR-19 AC2
    """
    raise NotImplementedError("FR-19 AC2: read one model price from the session cache")


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Price one call.

    Args:
        model: Model identifier.
        prompt_tokens: Tokens in the prompt.
        completion_tokens: Tokens in the completion, including reasoning tokens.

    Returns:
        The cost in USD, or None when the price is unknown.

    Related: FR-19 AC1, FR-19 AC2
    """
    raise NotImplementedError("FR-19 AC1: multiply token counts by the model price")
