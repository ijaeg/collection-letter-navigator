"""Tests for :mod:`collection_letter_navigator.tools.paragraph`.

Related: FR-14, FR-10 AC4, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator.tools import paragraph


def test_module_imports() -> None:
    """The paragraph tool module imports."""
    assert paragraph.fetch_paragraph is not None


@pytest.mark.skip(reason="not implemented: FR-14 AC1")
def test_fr14_ac1_indexed_provision_is_returned_from_the_store() -> None:
    """A provision in the knowledge base comes back with its German text."""


@pytest.mark.skip(reason="not implemented: FR-14 AC1")
def test_fr14_ac1_no_network_call_at_runtime() -> None:
    """The lookup reads the committed index only."""


@pytest.mark.skip(reason="not implemented: FR-14 AC2")
def test_fr14_ac2_unknown_provision_returns_not_applicable() -> None:
    """A provision outside the scope says "not in the knowledge base"."""
