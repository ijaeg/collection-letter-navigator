"""Tests for :mod:`collection_letter_navigator.answer`.

Related: FR-08, FR-09, FR-10, FR-21 AC2, NFR-06
"""

from __future__ import annotations

import pytest
from langchain_core.documents import Document

from collection_letter_navigator import answer
from collection_letter_navigator.retrieval import RetrievalOutcome, ScoredChunk
from collection_letter_navigator.schemas import AnswerWithSources, RetrievalPlan

#: Verbatim from ZPO § 692 (1) no. 2 in the committed index.
REAL_QUOTE = (
    "dass das Gericht nicht geprüft hat, ob dem Antragsteller der geltend gemachte Anspruch zusteht"
)


def outcome_with(*chunk_ids: str) -> RetrievalOutcome:
    """A retrieval outcome holding the given chunk IDs."""
    plan = RetrievalPlan(queries_de=["x"], rationale="x")
    chunks = [ScoredChunk(i, Document(id=i, page_content="", metadata={}), 1.0) for i in chunk_ids]
    return RetrievalOutcome(plan, chunks)


def answer_with(text: str, ids: list[str] | None = None) -> AnswerWithSources:
    """A structured answer with the given text and cited IDs."""
    return AnswerWithSources(answer_en=text, source_chunk_ids=ids or ["ZPO-692"])


def test_module_imports() -> None:
    """The answer module imports."""
    assert answer.answer_question is not None


@pytest.mark.skip(reason="not implemented: FR-08 AC2")
def test_fr08_ac2_answer_cites_at_least_one_retrieved_chunk() -> None:
    """A grounded answer names the chunks it relies on."""


@pytest.mark.skip(reason="not implemented: FR-08 AC3")
def test_fr08_ac3_no_supporting_chunk_yields_the_not_found_answer() -> None:
    """Without support the app refuses instead of using general knowledge."""


def test_fr09_ac1_known_chunk_ids_are_kept() -> None:
    """IDs that were retrieved for this question survive validation, in order, once."""
    kept, dropped = answer.validate_source_ids(
        answer_with("x", ["ZPO-694", "ZPO-692", "ZPO-694"]), outcome_with("ZPO-692", "ZPO-694")
    )
    assert kept == ["ZPO-694", "ZPO-692"]
    assert dropped == []


def test_fr09_ac1_unknown_chunk_ids_are_dropped_and_counted() -> None:
    """An invented chunk ID is removed and recorded for the metrics."""
    kept, dropped = answer.validate_source_ids(
        answer_with("x", ["ZPO-692", "BGB-999"]), outcome_with("ZPO-692")
    )
    assert kept == ["ZPO-692"]
    assert dropped == ["BGB-999"]


def test_fr09_ac2_exact_quote_passes_the_check() -> None:
    """A quote identical to the source text is kept (real index)."""
    text = f"The order says „{REAL_QUOTE}“."
    assert answer.extract_german_quotes(text) == [REAL_QUOTE]
    assert answer.quote_is_grounded(REAL_QUOTE, ["ZPO-692"])
    cleaned, replaced = answer.enforce_quote_fidelity(answer_with(text), ["ZPO-692"])
    assert replaced == 0 and cleaned.answer_en == text


def test_fr09_ac2_quote_with_different_whitespace_passes() -> None:
    """Whitespace and an ellipsis inside the quote are tolerated."""
    spaced = REAL_QUOTE.replace(" nicht ", "  nicht\n ")
    assert answer.quote_is_grounded(spaced, ["ZPO-692"])
    assert answer.quote_is_grounded(
        "dass das Gericht nicht geprüft hat … Anspruch zusteht", ["ZPO-692"]
    )


def test_fr09_ac3_fabricated_quote_is_replaced_by_a_reference() -> None:
    """A quote absent from the cited chunks becomes "see § ... below"."""
    text = 'It says "Sie müssen die Forderung sofort bezahlen" in the law.'
    cleaned, replaced = answer.enforce_quote_fidelity(answer_with(text), ["ZPO-692"])
    assert replaced == 1
    assert cleaned.answer_en == "It says (see § 692 ZPO below) in the law."


def test_fr09_ac3_replaced_quotes_are_counted() -> None:
    """Each replacement is counted; single quoted terms and English quotes are left alone."""
    text = (
        f"„{REAL_QUOTE}“, “das ist frei erfunden worden”, "
        '"Sie müssen sofort zahlen", the term "Widerspruch" and "you must reply".'
    )
    cleaned, replaced = answer.enforce_quote_fidelity(answer_with(text), ["ZPO-692"])
    assert replaced == 2
    assert REAL_QUOTE in cleaned.answer_en
    assert '"Widerspruch"' in cleaned.answer_en and '"you must reply"' in cleaned.answer_en


@pytest.mark.skip(reason="not implemented: FR-10 AC1")
def test_fr10_ac1_model_tool_call_is_executed_and_returned_as_tool_message() -> None:
    """The loop runs the called tool and feeds the result back to the model."""


@pytest.mark.skip(reason="not implemented: FR-10 AC5")
def test_fr10_ac5_loop_stops_after_three_tool_calls() -> None:
    """A fourth tool call ends the loop with a message, not an endless loop."""


@pytest.mark.skip(reason="not implemented: FR-10 AC6")
def test_fr10_ac6_failing_tool_does_not_end_the_chat() -> None:
    """The answer is produced without that tool and the failure is shown."""


@pytest.mark.skip(reason="not implemented: FR-10 AC7")
def test_fr10_ac7_answer_never_states_a_claim_is_time_barred() -> None:
    """Tool-derived statements stay provisional and name their assumptions."""


@pytest.mark.skip(reason="not implemented: FR-21 AC2")
def test_fr21_ac2_court_document_answer_ends_with_the_deadline_reminder() -> None:
    """Answers about what to do next repeat the deadline in one line."""


def test_fr09_quote_from_an_uncited_chunk_does_not_count() -> None:
    """A real statute quote still fails if the answer does not cite its chunk."""
    assert not answer.quote_is_grounded(REAL_QUOTE, ["BGB-195"])
    assert not answer.quote_is_grounded(REAL_QUOTE, [])
