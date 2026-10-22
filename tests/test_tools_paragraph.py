"""Tests for :mod:`collection_letter_navigator.tools.paragraph`.

Related: FR-14, FR-10 AC4, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import llm, tools
from collection_letter_navigator.tools import paragraph
from collection_letter_navigator.tools.paragraph import FetchParagraphArgs


def test_module_imports() -> None:
    """The paragraph tool module imports."""
    assert paragraph.fetch_paragraph is not None


def test_fr14_ac1_indexed_provision_is_returned_from_the_store() -> None:
    """A provision in the knowledge base comes back with its German text."""
    out = paragraph.fetch_paragraph(FetchParagraphArgs(law="ZPO", section="690"))
    assert out.result is not None and out.not_applicable_reason is None
    assert out.result["chunk_ids"] == ["ZPO-690"]
    assert str(out.result["text"]).startswith("§ 690 ZPO")
    assert out.legal_basis == ["ZPO § 690"]


def test_fr14_ac1_section_split_into_subsections_is_returned_whole() -> None:
    """§ 13a RDG is indexed per subsection; the tool joins them, '§' is tolerated."""
    out = paragraph.fetch_paragraph(FetchParagraphArgs(law="RDG", section="§ 13a"))
    assert out.result is not None
    assert out.result["chunk_ids"] == [f"RDG-13a-{i}" for i in range(1, 6)]


def test_fr14_ac1_no_network_call_at_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lookup reads the committed index only: no embedding or chat client is built."""

    def forbidden(*_: object, **__: object) -> None:
        raise AssertionError("network client built")

    monkeypatch.setattr(llm, "build_embeddings", forbidden)
    monkeypatch.setattr(llm, "build_chat_model", forbidden)
    assert paragraph.fetch_paragraph(FetchParagraphArgs(law="BGB", section="212")).result


def test_fr14_ac2_unknown_provision_returns_not_applicable() -> None:
    """A provision outside the scope says "not in the knowledge base"."""
    out = paragraph.fetch_paragraph(FetchParagraphArgs(law="ZPO", section="850c"))
    assert out.result is None
    assert "not in the knowledge base" in (out.not_applicable_reason or "")


def test_fr14_invalid_law_from_the_model_never_raises() -> None:
    """A law outside the three becomes not_applicable via the tool contract (FR-10 AC3)."""
    out = tools.invoke_tool("fetch_paragraph", {"law": "StGB", "section": "263"})
    assert out.result is None and out.not_applicable_reason
