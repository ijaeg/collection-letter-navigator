"""Tests for :mod:`collection_letter_navigator.tools.contract`.

Related: FR-10 AC2, FR-10 AC3, FR-10 AC6, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator.tools import contract


def test_module_imports() -> None:
    """The tool contract module imports."""
    assert contract.not_applicable is not None


@pytest.mark.skip(reason="not implemented: FR-10 AC2")
def test_fr10_ac2_every_tool_returns_the_full_contract() -> None:
    """Each bound tool returns all five ToolResult fields."""


@pytest.mark.skip(reason="not implemented: FR-10 AC2")
def test_fr10_ac2_not_applicable_result_is_null_with_a_reason() -> None:
    """No result and a reason always appear together."""


@pytest.mark.skip(reason="not implemented: FR-10 AC3")
def test_fr10_ac3_schema_violation_becomes_not_applicable() -> None:
    """Invalid model arguments never raise to the UI."""


@pytest.mark.skip(reason="not implemented: FR-10 AC3")
def test_fr10_ac3_impossible_date_becomes_not_applicable() -> None:
    """A date like 2026-02-30 is reported back, not raised."""


@pytest.mark.skip(reason="not implemented: FR-10 AC3")
def test_fr10_ac3_negative_amount_becomes_not_applicable() -> None:
    """A negative principal is reported back, not raised."""


@pytest.mark.skip(reason="not implemented: FR-10 AC6")
def test_fr10_ac6_unexpected_exception_becomes_not_applicable() -> None:
    """An unexpected failure inside a tool is caught and shown on the card."""
