"""Tests for :mod:`collection_letter_navigator.retrieval`.

Related: FR-05, FR-06, FR-07, FR-08 AC4, FR-18, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import retrieval


def test_module_imports() -> None:
    """The retrieval module imports."""
    assert retrieval.retrieve is not None


@pytest.mark.skip(reason="not implemented: FR-05 AC1")
def test_fr05_ac1_plan_contains_one_to_four_german_queries() -> None:
    """The mocked model's plan is validated to 1-4 German queries."""


@pytest.mark.skip(reason="not implemented: FR-05 AC2")
def test_fr05_ac2_query_translation_always_runs_in_the_pipeline() -> None:
    """Query translation is a fixed step, not a tool the model may skip."""


@pytest.mark.skip(reason="not implemented: FR-05 AC5")
def test_fr05_ac5_translation_off_means_unfiltered_english_query() -> None:
    """With translation off the English question is used and no filter applies."""


@pytest.mark.skip(reason="not implemented: FR-06 AC1")
def test_fr06_ac1_court_letter_includes_zpo_in_the_filter() -> None:
    """A court document in the triage puts ZPO into the law filter."""


@pytest.mark.skip(reason="not implemented: FR-06 AC2")
def test_fr06_ac2_no_chunk_outside_the_filter_is_returned() -> None:
    """The filter applies to the vector and the keyword search alike."""


@pytest.mark.skip(reason="not implemented: FR-06 AC3")
def test_fr06_ac3_fallback_to_unfiltered_search_below_two_hits() -> None:
    """A filtered search with fewer than 2 hits is retried unfiltered."""


@pytest.mark.skip(reason="not implemented: FR-06 AC3")
def test_fr06_ac3_fallback_is_recorded_in_the_outcome() -> None:
    """The RAG panel can tell that the fallback ran."""


@pytest.mark.skip(reason="not implemented: FR-07 AC1")
def test_fr07_ac1_duplicates_across_queries_are_merged() -> None:
    """A chunk found by two queries appears once, with a fused score."""


@pytest.mark.skip(reason="not implemented: FR-07 AC2")
def test_fr07_ac2_context_is_capped_at_k_chunks() -> None:
    """The fused context holds at most k chunks."""


@pytest.mark.skip(reason="not implemented: FR-07 AC3")
def test_fr07_ac3_explicit_provision_reference_lands_in_top_three() -> None:
    """A query naming "§ 199 BGB" returns that section in the top 3."""


@pytest.mark.skip(reason="not implemented: FR-08 AC4")
def test_fr08_ac4_sources_are_wrapped_in_source_delimiters() -> None:
    """Chunks reach the model inside <source id="..."> blocks."""


@pytest.mark.skip(reason="not implemented: FR-08 AC2")
def test_fr08_ac2_chunk_lookup_by_id_returns_the_stored_text() -> None:
    """The displayed German text comes from the store, not from the model."""
