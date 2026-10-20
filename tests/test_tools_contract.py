"""Tests for :mod:`collection_letter_navigator.tools.contract` and the tool runner.

Related: FR-10 AC2, FR-10 AC3, FR-10 AC6, NFR-06
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from collection_letter_navigator import tools
from collection_letter_navigator.schemas import ToolResult
from collection_letter_navigator.tools import contract, deadlines, interest, limitation

#: One valid call per Must tool (FR-10 AC2).
VALID_CALLS: dict[str, dict[str, Any]] = {
    deadlines.TOOL_NAME: {"document_type": "mahnbescheid", "service_date": "2026-10-14"},
    limitation.TOOL_NAME: {"claim_date": "2023-06-15"},
    interest.TOOL_NAME: {
        "principal": 1000,
        "start_date": "2026-01-01",
        "end_date": "2026-06-30",
    },
}


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """All tools see the same 'today'."""
    for module in (deadlines, limitation, interest):
        monkeypatch.setattr(module, "_today", lambda: date(2026, 10, 19))


def test_module_imports() -> None:
    """The tool contract module imports."""
    assert contract.not_applicable is not None


@pytest.mark.parametrize("name", sorted(VALID_CALLS))
def test_fr10_ac2_every_tool_returns_the_full_contract(name: str) -> None:
    """Each bound tool returns all five ToolResult fields, filled in."""
    outcome = tools.invoke_tool(name, VALID_CALLS[name])
    assert isinstance(outcome, ToolResult)
    assert outcome.tool == name
    assert outcome.result and outcome.assumptions and outcome.legal_basis
    assert outcome.not_applicable_reason is None


def test_fr10_ac2_not_applicable_result_is_null_with_a_reason() -> None:
    """No result and a reason always appear together."""
    outcome = contract.not_applicable("x", "Because.", missing_information=["the date"])
    assert outcome.result is None
    assert outcome.not_applicable_reason == "Because."
    assert outcome.missing_information == ["the date"]


def test_fr10_ac3_schema_violation_becomes_not_applicable() -> None:
    """Invalid model arguments never raise to the UI: unknown and missing fields."""
    outcome = tools.invoke_tool(deadlines.TOOL_NAME, {"service_date": "2026-10-14", "foo": 1})
    assert outcome.result is None
    assert "document_type" in (outcome.not_applicable_reason or "")
    assert "foo" in (outcome.not_applicable_reason or "")


def test_fr10_ac3_impossible_date_becomes_not_applicable() -> None:
    """A date like 2026-02-30 is reported back, not raised."""
    outcome = tools.invoke_tool(
        deadlines.TOOL_NAME, {"document_type": "mahnbescheid", "service_date": "2026-02-30"}
    )
    assert outcome.result is None
    assert "service_date" in (outcome.not_applicable_reason or "")


def test_fr10_ac3_negative_amount_becomes_not_applicable() -> None:
    """A negative principal is reported back, not raised."""
    outcome = tools.invoke_tool(interest.TOOL_NAME, {"principal": -5, "start_date": "2026-01-01"})
    assert outcome.result is None
    assert "principal" in (outcome.not_applicable_reason or "")


def test_fr10_ac3_values_outside_the_schema_limits_become_not_applicable() -> None:
    """Values the schemas reject arrive as a message, never as an exception."""
    too_high = tools.invoke_tool(
        interest.TOOL_NAME, {"principal": 100_001, "start_date": "2026-01-01"}
    )
    state = tools.invoke_tool(
        deadlines.TOOL_NAME,
        {"document_type": "mahnbescheid", "service_date": "2026-10-12", "federal_state": "XX"},
    )
    assert too_high.result is None and "principal" in (too_high.not_applicable_reason or "")
    assert state.result is None and "federal_state" in (state.not_applicable_reason or "")


def test_fr10_ac3_unknown_tool_name_becomes_not_applicable() -> None:
    """A tool name the model made up is answered, not raised."""
    outcome = tools.invoke_tool("pay_now", {})
    assert outcome.result is None
    assert "pay_now" in (outcome.not_applicable_reason or "")


def test_fr10_ac6_unexpected_exception_becomes_not_applicable() -> None:
    """An unexpected failure inside a tool is caught and shown on the card."""

    @contract.guard_tool_errors("broken_tool")
    def broken() -> ToolResult:
        raise ZeroDivisionError("boom")

    outcome = broken()
    assert outcome.tool == "broken_tool"
    assert outcome.result is None
    assert "ZeroDivisionError" in (outcome.not_applicable_reason or "")
