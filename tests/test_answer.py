"""Tests for :mod:`collection_letter_navigator.answer`.

Related: FR-08, FR-09, FR-10, FR-21 AC2, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import answer


def test_module_imports() -> None:
    """The answer module imports."""
    assert answer.answer_question is not None


@pytest.mark.skip(reason="not implemented: FR-08 AC2")
def test_fr08_ac2_answer_cites_at_least_one_retrieved_chunk() -> None:
    """A grounded answer names the chunks it relies on."""


@pytest.mark.skip(reason="not implemented: FR-08 AC3")
def test_fr08_ac3_no_supporting_chunk_yields_the_not_found_answer() -> None:
    """Without support the app refuses instead of using general knowledge."""


@pytest.mark.skip(reason="not implemented: FR-09 AC1")
def test_fr09_ac1_known_chunk_ids_are_kept() -> None:
    """IDs that were retrieved for this question survive validation."""


@pytest.mark.skip(reason="not implemented: FR-09 AC1")
def test_fr09_ac1_unknown_chunk_ids_are_dropped_and_counted() -> None:
    """An invented chunk ID is removed and recorded for the metrics."""


@pytest.mark.skip(reason="not implemented: FR-09 AC2")
def test_fr09_ac2_exact_quote_passes_the_check() -> None:
    """A quote identical to the source text is kept."""


@pytest.mark.skip(reason="not implemented: FR-09 AC2")
def test_fr09_ac2_quote_with_different_whitespace_passes() -> None:
    """Whitespace is normalised before the comparison."""


@pytest.mark.skip(reason="not implemented: FR-09 AC3")
def test_fr09_ac3_fabricated_quote_is_replaced_by_a_reference() -> None:
    """A quote absent from the cited chunks becomes "see § ... below"."""


@pytest.mark.skip(reason="not implemented: FR-09 AC3")
def test_fr09_ac3_replaced_quotes_are_counted() -> None:
    """Each replacement is counted for the answer checks of §7.4."""


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
