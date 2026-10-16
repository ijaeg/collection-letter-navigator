"""Tests for :mod:`collection_letter_navigator.schemas`.

Related: FR-05, FR-08, FR-10 AC2, FR-16, §6
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import schemas


def test_module_imports() -> None:
    """The contract models are importable."""
    assert schemas.RetrievalPlan is not None
    assert schemas.ToolResult is not None


@pytest.mark.skip(reason="not implemented: §6.1")
def test_s61_retrieval_plan_rejects_more_than_four_queries() -> None:
    """A RetrievalPlan accepts 1-4 German queries and rejects 0 or 5."""


@pytest.mark.skip(reason="not implemented: §6.1")
def test_s61_retrieval_plan_rejects_unknown_law_in_filter() -> None:
    """law_filter accepts only BGB, ZPO and RDG."""


@pytest.mark.skip(reason="not implemented: FR-10 AC2")
def test_fr10_ac2_tool_result_allows_null_result_with_reason() -> None:
    """A ToolResult may carry no result as long as it says why."""


@pytest.mark.skip(reason="not implemented: §6.3")
def test_s63_answer_with_sources_defaults_to_in_scope() -> None:
    """out_of_scope defaults to False and used_tools to an empty list."""


@pytest.mark.skip(reason="not implemented: §6.4")
def test_s64_triage_result_requires_delivery_date() -> None:
    """A TriageResult without a delivery date is rejected."""


@pytest.mark.skip(reason="not implemented: §6.5")
def test_s65_letter_facts_fields_default_to_null() -> None:
    """Every optional LetterFacts field defaults to None, never to a guess."""
