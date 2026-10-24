"""Tests for :mod:`collection_letter_navigator.schemas`.

Related: FR-05, FR-08, FR-10 AC2, FR-16, §6
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from collection_letter_navigator import schemas


def test_module_imports() -> None:
    """The contract models are importable."""
    assert schemas.RetrievalPlan is not None
    assert schemas.ToolResult is not None


def test_s61_retrieval_plan_rejects_more_than_four_queries() -> None:
    """A RetrievalPlan accepts 1-4 German queries and rejects 0 or 5."""
    for n in (1, 4):
        assert (
            len(schemas.RetrievalPlan(queries_de=["Verjährung"] * n, rationale="r").queries_de) == n
        )
    for n in (0, 5):
        with pytest.raises(ValidationError):
            schemas.RetrievalPlan(queries_de=["Verjährung"] * n, rationale="r")


def test_s61_retrieval_plan_rejects_unknown_law_in_filter() -> None:
    """law_filter accepts only BGB, ZPO and RDG."""
    plan = schemas.RetrievalPlan(
        queries_de=["Mahnbescheid"], law_filter=["BGB", "ZPO", "RDG"], rationale="r"
    )
    assert plan.law_filter == ["BGB", "ZPO", "RDG"]
    with pytest.raises(ValidationError):
        schemas.RetrievalPlan(queries_de=["Kündigung"], law_filter=["HGB"], rationale="r")  # type: ignore[list-item]


def test_fr10_ac2_tool_result_allows_null_result_with_reason() -> None:
    """A ToolResult may carry no result as long as it says why."""
    out = schemas.ToolResult(
        tool="check_limitation",
        not_applicable_reason="The claim date is missing.",
        missing_information=["Date of the original invoice"],
    )
    assert out.result is None and out.not_applicable_reason
    with pytest.raises(ValidationError):  # extra="forbid": no invented fields
        schemas.ToolResult(tool="check_limitation", verdict="time-barred")  # type: ignore[call-arg]


def test_s63_answer_with_sources_defaults_to_in_scope() -> None:
    """out_of_scope defaults to False and used_tools to an empty list."""
    out = schemas.AnswerWithSources(answer_en="The period is two weeks.")
    assert out.out_of_scope is False
    assert out.used_tools == [] and out.source_chunk_ids == []


def test_s64_triage_result_requires_delivery_date() -> None:
    """A TriageResult without a delivery date is rejected."""
    with pytest.raises(ValidationError):
        schemas.TriageResult(sender="court")  # type: ignore[call-arg]
    triage = schemas.TriageResult(sender="court", delivered_on=date(2026, 10, 14))
    assert triage.court_document is None


def test_s65_letter_facts_fields_default_to_null() -> None:
    """Every optional LetterFacts field defaults to None, never to a guess."""
    facts = schemas.LetterFacts(letter_type="unknown", sender_type="unknown")
    optional = set(schemas.LetterFacts.model_fields) - {"letter_type", "sender_type"}
    assert optional and all(getattr(facts, name) is None for name in optional)
