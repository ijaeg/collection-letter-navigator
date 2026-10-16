"""Tests for :mod:`collection_letter_navigator.ingest`.

Related: FR-04, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import ingest


def test_module_imports() -> None:
    """The ingestion module imports."""
    assert ingest.chunk_section is not None


@pytest.mark.skip(reason="not implemented: FR-04 AC1")
def test_fr04_ac1_only_provisions_in_scope_are_indexed() -> None:
    """Sections outside kb_scope.yaml are skipped."""


@pytest.mark.skip(reason="not implemented: FR-04 AC2")
def test_fr04_ac2_short_section_stays_one_chunk() -> None:
    """A section below the character limit is not split."""


@pytest.mark.skip(reason="not implemented: FR-04 AC2")
def test_fr04_ac2_long_section_split_by_subsection() -> None:
    """A section above 2,000 characters is split at subsection boundaries."""


@pytest.mark.skip(reason="not implemented: FR-04 AC2")
def test_fr04_ac2_no_chunk_crosses_a_section_boundary() -> None:
    """Every chunk belongs to exactly one section."""


@pytest.mark.skip(reason="not implemented: FR-04 AC3")
def test_fr04_ac3_every_chunk_carries_the_required_metadata() -> None:
    """law, section, subsection, title, source_url and retrieved_at are set."""


@pytest.mark.skip(reason="not implemented: FR-04 AC5")
def test_fr04_ac5_second_run_yields_same_chunk_ids_and_count() -> None:
    """Running the ingestion twice on the same XML is idempotent."""


@pytest.mark.skip(reason="not implemented: FR-04 AC4")
def test_fr04_ac4_manifest_records_snapshot_date_and_embedding_model() -> None:
    """The manifest holds what the sidebar shows and what reproduces the index."""
