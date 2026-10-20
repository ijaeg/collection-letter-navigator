"""Tests for :mod:`collection_letter_navigator.ingest`.

Uses a minimal XML excerpt in the structure of gesetze-im-internet.de
(``tests/fixtures/mini_law.xml``) and a fake embedding model, so no network
call is made.

Related: FR-04, NFR-06
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from collection_letter_navigator import ingest

FIXTURE = Path(__file__).parent / "fixtures" / "mini_law.xml"
SNAPSHOT = date(2026, 10, 16)


def _sections(scope: list[str]) -> list:
    return ingest.parse_law_xml(FIXTURE, "ZPO", scope, retrieved_at=SNAPSHOT)


def test_fr04_ac1_load_kb_scope_rejects_unknown_law(tmp_path: Path) -> None:
    """Only laws from config.KB_LAWS are accepted; empty lists are dropped."""
    scope_file = tmp_path / "scope.yaml"
    scope_file.write_text("ZPO: ['688-703a']\nBGB: []\n", encoding="utf-8")
    assert ingest.load_kb_scope(scope_file) == {"ZPO": ["688-703a"]}

    scope_file.write_text("StGB: ['1']\n", encoding="utf-8")
    with pytest.raises(ValueError, match="StGB"):
        ingest.load_kb_scope(scope_file)


def test_fr04_ac1_ranges_resolve_in_document_order() -> None:
    """A range includes lettered sections without listing them one by one."""
    available = ["688", "692", "703a", "704"]
    assert ingest.expand_scope(["688-703a"], available) == ["688", "692", "703a"]
    assert ingest.expand_scope(["704", "688"], available) == ["688", "704"]


def test_fr04_ac1_unknown_section_raises() -> None:
    """A scope entry that does not exist in the XML is an error, not silently skipped."""
    with pytest.raises(ValueError, match="999"):
        ingest.expand_scope(["999"], ["688"])


def test_fr04_ac1_only_provisions_in_scope_are_indexed() -> None:
    """Sections outside kb_scope.yaml, headings and the preamble are skipped."""
    sections = _sections(["688-703a"])
    assert [s.metadata["section"] for s in sections] == ["688", "692", "703a"]


def test_fr04_ac3_section_text_and_metadata() -> None:
    """Text keeps one line per <P>, lists are flattened, footnotes are left out."""
    section = _sections(["692"])[0]
    assert section.page_content.splitlines()[0].startswith("(1) Der Mahnbescheid enthält:")
    assert "enthält: 1. die Angaben des Antrags; 3. die Aufforderung" in section.page_content
    assert "binnen zwei Wochen seit der Zustellung" in section.page_content
    assert "Fußnote" not in section.page_content
    assert section.metadata == {
        "law": "ZPO",
        "section": "692",
        "title": "Mahnbescheid",
        "source_url": "https://www.gesetze-im-internet.de/zpo/__692.html",
        "retrieved_at": "2026-10-16",
    }


def test_fr04_ac3_snapshot_date_defaults_to_xml_builddate() -> None:
    """Without an explicit date, the version date of the XML is used (FR-21 AC6)."""
    section = ingest.parse_law_xml(FIXTURE, "ZPO", ["688"])[0]
    assert section.metadata["retrieved_at"] == "2026-01-01"


def test_fr04_ac2_short_section_stays_one_chunk() -> None:
    """A section below the character limit is not split."""
    chunks = ingest.chunk_section(_sections(["692"])[0])
    assert len(chunks) == 1
    assert chunks[0].id == "ZPO-692"
    assert chunks[0].metadata["subsection"] == ""
    assert chunks[0].page_content.startswith("§ 692 ZPO Mahnbescheid\n")


def test_fr04_ac2_long_section_split_by_subsection() -> None:
    """A section above the limit is split at subsection boundaries."""
    chunks = ingest.chunk_section(_sections(["692"])[0], max_characters=50)
    assert [c.id for c in chunks] == ["ZPO-692-1", "ZPO-692-2"]
    assert [c.metadata["subsection"] for c in chunks] == ["1", "2"]
    assert chunks[1].page_content.startswith("§ 692 ZPO Mahnbescheid – Absatz 2\n")


def test_fr04_ac2_no_chunk_crosses_a_section_boundary() -> None:
    """Every chunk belongs to exactly one section."""
    for section in _sections(["688-704"]):
        for chunk in ingest.chunk_section(section, max_characters=50):
            assert chunk.metadata["section"] == section.metadata["section"]
            assert section.page_content.count(chunk.page_content.split("\n", 1)[1]) == 1


def test_fr04_ac3_every_chunk_carries_the_required_metadata() -> None:
    """law, section, subsection, title, source_url, retrieved_at and chunk_id are set."""
    required = {"law", "section", "subsection", "title", "source_url", "retrieved_at", "chunk_id"}
    for section in _sections(["688-704"]):
        for chunk in ingest.chunk_section(section):
            assert required <= set(chunk.metadata)
            assert all(isinstance(v, str) for v in chunk.metadata.values())  # Chroma: no None


def test_fr04_ac5_second_run_yields_same_chunk_ids_and_count(tmp_path: Path) -> None:
    """Running the ingestion twice on the same XML is idempotent."""
    cache = tmp_path / "raw"
    (cache / "zpo").mkdir(parents=True)
    (cache / "zpo" / "mini.xml").write_bytes(FIXTURE.read_bytes())
    first = ingest.build_chunks({"ZPO": ["688-704"]}, cache_dir=cache)
    second = ingest.build_chunks({"ZPO": ["688-704"]}, cache_dir=cache)
    assert [c.id for c in first] == [c.id for c in second]
    assert len(first) == 4


def test_fr04_ac4_index_and_manifest_round_trip(tmp_path: Path) -> None:
    """The index is written with the chunk IDs; the manifest records what the UI shows."""
    chunks = [c for s in _sections(["688-704"]) for c in ingest.chunk_section(s)]
    index_dir = tmp_path / "index"
    ingest.write_index(chunks, index_dir, embeddings=DeterministicFakeEmbedding(size=8))
    ingest.write_manifest(chunks, index_dir, embedding_model="fake-model")

    manifest = ingest.read_manifest(index_dir)
    assert manifest["snapshot_date"] == "2026-10-16"
    assert manifest["embedding_model"] == "fake-model"
    assert manifest["chunk_count"] == 4
    assert manifest["chunks_per_law"] == {"ZPO": 4}


def test_fr04_ac4_manifest_records_the_version_date_per_law(tmp_path: Path) -> None:
    """Each law keeps its own snapshot date; the overall date is the most recent one."""
    zpo = [c for s in _sections(["688"]) for c in ingest.chunk_section(s)]
    bgb = [c.model_copy(deep=True) for c in zpo]
    for chunk in bgb:
        chunk.metadata.update(law="BGB", retrieved_at="2026-09-26")
    ingest.write_manifest(zpo + bgb, tmp_path, embedding_model="m", built_at="2026-10-16T16:40:11")

    manifest = ingest.read_manifest(tmp_path)
    assert manifest["snapshot_dates"] == {"ZPO": "2026-10-16", "BGB": "2026-09-26"}
    assert manifest["snapshot_date"] == "2026-10-16"
    assert manifest["built_at"] == "2026-10-16T16:40:11"


def test_fr04_ac4_write_index_leaves_no_partial_index(tmp_path: Path) -> None:
    """If embedding fails, the target directory does not exist afterwards."""

    class FailingEmbeddings(DeterministicFakeEmbedding):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise ConnectionError("network down")

    index_dir = tmp_path / "index"
    chunks = ingest.chunk_section(_sections(["688"])[0])
    with pytest.raises(RuntimeError, match="no index was written"):
        ingest.write_index(chunks, index_dir, embeddings=FailingEmbeddings(size=8))
    assert not index_dir.exists()


def test_fr04_ac4_read_manifest_without_index_raises(tmp_path: Path) -> None:
    """A missing index gives a clear error instead of a crash later."""
    with pytest.raises(FileNotFoundError, match="build_index"):
        ingest.read_manifest(tmp_path)
