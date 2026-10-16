"""Tests for :mod:`collection_letter_navigator.pricing`.

Related: FR-19, NFR-02
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import pricing


def test_module_imports() -> None:
    """The pricing module imports."""
    assert pricing.estimate_cost_usd is not None


@pytest.mark.skip(reason="not implemented: FR-19 AC2")
def test_fr19_ac2_prices_fetched_once_per_session() -> None:
    """The models endpoint is called once and the result is cached."""


@pytest.mark.skip(reason="not implemented: FR-19 AC2")
def test_fr19_ac2_unavailable_endpoint_yields_cost_unavailable() -> None:
    """A failing endpoint returns no prices instead of raising."""


@pytest.mark.skip(reason="not implemented: FR-19 AC1")
def test_fr19_ac1_cost_is_prompt_plus_completion_tokens() -> None:
    """Cost is the sum of both token counts priced with the model's rates."""
