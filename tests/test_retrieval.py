"""Tests for :mod:`collection_letter_navigator.retrieval`.

No test calls OpenRouter: the chat model is a scripted fake, and vector search
runs on a temporary Chroma store with deterministic fake embeddings. Tests
marked "real index" read the committed index in ``data/index/`` (no API call).

Related: FR-05, FR-06, FR-07, FR-08 AC4, FR-18, NFR-06
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import pytest
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import AIMessage

from collection_letter_navigator import config, llm, retrieval
from collection_letter_navigator.retrieval import ScoredChunk
from collection_letter_navigator.schemas import RetrievalPlan, TriageResult

COURT = TriageResult(sender="court", court_document="mahnbescheid", delivered_on=date(2026, 10, 14))


class ScriptedPlanner:
    """Stands in for ``model.with_structured_output(...)``; replays prepared replies."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.calls: list[list[Any]] = []

    def invoke(self, messages: list[Any]) -> Any:
        self.calls.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeChatModel:
    """Minimal chat model fake: only ``with_structured_output`` is needed here."""

    def __init__(self, replies: list[Any]) -> None:
        self.planner = ScriptedPlanner(replies)
        self.schema: Any = None

    def with_structured_output(self, schema: Any, **_: Any) -> ScriptedPlanner:
        self.schema = schema
        return self.planner


def plan_dict(queries: list[str], law_filter: list[str] | None = None) -> dict[str, Any]:
    """A raw model reply in the shape of a RetrievalPlan."""
    return {"queries_de": queries, "law_filter": law_filter, "rationale": "Test plan."}


def chunk(chunk_id: str, law: str = "BGB") -> ScoredChunk:
    """A small scored chunk for fusion tests."""
    doc = Document(id=chunk_id, page_content=f"text {chunk_id}", metadata={"law": law})
    return ScoredChunk(chunk_id, doc, 1.0)


def test_module_imports() -> None:
    """The retrieval module imports."""
    assert retrieval.retrieve is not None


# --- FR-05 Query translation -------------------------------------------------


def test_fr05_ac1_plan_contains_one_to_four_german_queries() -> None:
    """A plan with five queries fails validation and is retried once."""
    model = FakeChatModel(
        [plan_dict(["a", "b", "c", "d", "e"]), plan_dict(["Mahnbescheid Widerspruch Frist"])]
    )
    plan = retrieval.create_retrieval_plan("How long do I have?", model=model)  # type: ignore[arg-type]
    assert plan.queries_de == ["Mahnbescheid Widerspruch Frist"]
    assert len(model.planner.calls) == 2
    assert model.schema is RetrievalPlan


def test_fr05_ac1_invalid_plan_twice_raises_llm_call_error() -> None:
    """After the retry budget, an invalid plan becomes a friendly error (NFR-02)."""
    model = FakeChatModel([plan_dict([]), plan_dict([])])
    with pytest.raises(llm.LlmCallError, match="invalid"):
        retrieval.create_retrieval_plan("How long?", model=model)  # type: ignore[arg-type]


def test_r11_unparsable_raw_reply_is_retried_and_usage_recorded() -> None:
    """With ``include_raw``, a failed parse is retried; each call's usage is kept (R-11)."""
    raw = AIMessage(
        content="{}",
        usage_metadata={"input_tokens": 500, "output_tokens": 40, "total_tokens": 540},
    )
    model = FakeChatModel(
        [
            {"raw": raw, "parsed": None, "parsing_error": ValueError("bad json")},
            {"raw": raw, "parsed": plan_dict(["Mahnbescheid"]), "parsing_error": None},
        ]
    )
    usages: list[llm.LlmUsage] = []
    plan = retrieval.create_retrieval_plan("What is it?", model=model, usages=usages)  # type: ignore[arg-type]
    assert plan.queries_de == ["Mahnbescheid"]
    assert [u.prompt_tokens for u in usages] == [500, 500]


def test_fr05_provider_error_becomes_llm_call_error() -> None:
    """A failing call never raises a raw exception to the caller (NFR-02)."""
    model = FakeChatModel([TimeoutError("read timed out")])
    with pytest.raises(llm.LlmCallError, match="could not be created"):
        retrieval.create_retrieval_plan("How long?", model=model)  # type: ignore[arg-type]


def test_fr05_question_and_triage_are_sent_inside_delimiters() -> None:
    """The question and the triage context reach the model as delimited data (FR-22 L4)."""
    model = FakeChatModel([plan_dict(["Widerspruch Mahnbescheid"], ["ZPO"])])
    retrieval.create_retrieval_plan("How long do I have?", COURT, model=model)  # type: ignore[arg-type]
    system, human = model.planner.calls[0]
    assert system.content == llm.load_prompt("retrieval_plan")
    assert "<question>\nHow long do I have?\n</question>" in human.content
    assert "Sender: court" in human.content
    assert "Court document: mahnbescheid" in human.content


def test_fr05_ac5_translation_off_means_unfiltered_english_query() -> None:
    """With translation off the English question is used and no filter applies."""
    plan = retrieval.passthrough_plan("Is this debt too old?")
    assert plan.queries_de == ["Is this debt too old?"]
    assert plan.law_filter is None


# --- FR-06 Structured retrieval ----------------------------------------------


def test_fr06_ac1_court_letter_includes_zpo_in_the_filter() -> None:
    """A court document in the triage puts ZPO into the law filter."""
    model = FakeChatModel([plan_dict(["Verjährung"], ["BGB"])])
    plan = retrieval.create_retrieval_plan("Too old?", COURT, model=model)  # type: ignore[arg-type]
    assert plan.law_filter == ["BGB", "ZPO"]


def test_fr06_ac1_filter_with_every_law_becomes_no_filter() -> None:
    """Naming all three laws is the same as an unfiltered search."""
    model = FakeChatModel([plan_dict(["Frist", "Frist "], ["BGB", "ZPO", "RDG"])])
    plan = retrieval.create_retrieval_plan("Deadline?", model=model)  # type: ignore[arg-type]
    assert plan.law_filter is None
    assert plan.queries_de == ["Frist"]  # duplicates are merged


def test_fr06_ac2_no_chunk_outside_the_filter_is_returned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """The filter applies to the vector and the keyword search alike (real index)."""
    corpus = list(retrieval.load_corpus())
    store = Chroma(
        collection_name="filter_test",
        embedding_function=DeterministicFakeEmbedding(size=32),
        persist_directory=str(tmp_path),
    )
    store.add_documents(corpus, ids=[doc.id or "" for doc in corpus])
    monkeypatch.setattr(retrieval, "load_vector_store", lambda: store)

    for law_filter in (["ZPO"], ["RDG"], ["BGB", "RDG"]):
        vector = retrieval.vector_search("Forderung Frist Zahlung", law_filter=law_filter, k=20)
        keyword = retrieval.keyword_search("Forderung Frist Zahlung", law_filter=law_filter, k=20)
        assert vector and keyword
        assert {hit.document.metadata["law"] for hit in vector + keyword} <= set(law_filter)


class CountingEmbedding(DeterministicFakeEmbedding):
    """Fake embeddings that count the requests (one batch vs. one per query)."""

    batch_calls: int = 0
    single_calls: int = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls += 1
        return super().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        self.single_calls += 1
        return super().embed_query(text)


def test_r11_all_queries_are_embedded_in_one_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Three queries cost one embedding request, with the same hits as before (R-11)."""
    inner = CountingEmbedding(size=32)
    corpus = list(retrieval.load_corpus())
    store = Chroma(
        collection_name="batch_test",
        embedding_function=llm.PrefixedEmbeddings(inner),
        persist_directory=str(tmp_path),
    )
    store.add_documents(corpus, ids=[doc.id or "" for doc in corpus])
    monkeypatch.setattr(retrieval, "load_vector_store", lambda: store)
    queries = ["Widerspruch Mahnbescheid Frist", "Verjährung Beginn", "Verzugszinsen Höhe"]
    one_by_one = [retrieval.vector_search(q, k=20) for q in queries]

    inner.batch_calls = inner.single_calls = 0
    plan = RetrievalPlan(queries_de=queries, rationale="x")
    outcome = retrieval.retrieve(plan, mode="vector", k=6)
    assert (inner.batch_calls, inner.single_calls) == (1, 0)
    expected = retrieval.reciprocal_rank_fusion(one_by_one, k=6)
    assert [c.chunk_id for c in outcome.chunks] == [c.chunk_id for c in expected]


def test_fr06_ac3_fallback_to_unfiltered_search_below_two_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A filtered search with fewer than 2 hits is retried unfiltered."""

    def fake_search(
        query: str, *, law_filter: Any = None, k: Any = None, **_: Any
    ) -> list[ScoredChunk]:
        return [] if law_filter else [chunk("BGB-195"), chunk("BGB-199")]

    monkeypatch.setattr(retrieval, "embed_queries", lambda queries: [[0.0]] * len(queries))
    monkeypatch.setattr(retrieval, "vector_search", fake_search)
    monkeypatch.setattr(retrieval, "keyword_search", fake_search)
    plan = RetrievalPlan(queries_de=["Verjährung"], law_filter=["RDG"], rationale="x")
    outcome = retrieval.retrieve(plan, mode="hybrid")
    assert [c.chunk_id for c in outcome.chunks] == ["BGB-195", "BGB-199"]


def test_fr06_ac3_fallback_is_recorded_in_the_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    """The RAG panel can tell that the fallback ran, and which filter was applied."""

    def fake_search(query: str, *, law_filter: Any = None, k: Any = None) -> list[ScoredChunk]:
        return [chunk("RDG-13a-1", "RDG")] if law_filter else [chunk("BGB-195"), chunk("BGB-199")]

    monkeypatch.setattr(retrieval, "keyword_search", fake_search)
    plan = RetrievalPlan(queries_de=["Inkasso"], law_filter=["RDG"], rationale="x")
    fallback = retrieval.retrieve(plan, mode="bm25")
    assert fallback.filter_fallback is True
    assert fallback.applied_filter is None

    monkeypatch.setattr(retrieval, "keyword_search", lambda *a, **kw: [chunk("A"), chunk("B")])
    filtered = retrieval.retrieve(plan, mode="bm25")
    assert filtered.filter_fallback is False
    assert filtered.applied_filter == ["RDG"]


def test_retrieve_rejects_an_unknown_mode() -> None:
    """A typo in RETRIEVAL_MODE fails loudly instead of silently searching nothing."""
    plan = retrieval.passthrough_plan("x")
    with pytest.raises(ValueError, match="Unknown retrieval mode"):
        retrieval.retrieve(plan, mode="semantic")  # type: ignore[arg-type]


# --- FR-07 Hybrid search -----------------------------------------------------


def test_fr07_ac1_duplicates_across_queries_are_merged() -> None:
    """A chunk found by two queries appears once, with a fused score."""
    fused = retrieval.reciprocal_rank_fusion(
        [[chunk("A"), chunk("B")], [chunk("B"), chunk("C")]], k=10, rrf_k=60
    )
    assert [c.chunk_id for c in fused] == ["B", "A", "C"]
    assert fused[0].score == pytest.approx(1 / 62 + 1 / 61)


def test_fr07_ac2_context_is_capped_at_k_chunks() -> None:
    """The fused context holds at most k chunks."""
    lists = [[chunk(f"C{i}") for i in range(10)]]
    assert len(retrieval.reciprocal_rank_fusion(lists, k=6)) == 6
    assert len(retrieval.reciprocal_rank_fusion(lists)) == config.RETRIEVAL_TOP_K


def test_fr07_ac3_explicit_provision_reference_lands_in_top_three() -> None:
    """A query naming "§ 199 BGB" returns that section in the top 3 (real index)."""
    plan = RetrievalPlan(queries_de=["§ 199 BGB"], rationale="x")
    outcome = retrieval.retrieve(plan, mode="bm25")
    assert "BGB-199" in [c.chunk_id for c in outcome.chunks[:3]]


def test_fr07_ac3_explicit_references_are_recognised() -> None:
    """Both spellings of a reference are found; the law is upper-cased."""
    refs = retrieval.explicit_references("§ 199 BGB, ZPO § 692 und § 204 Abs. 1 bgb")
    assert refs == {("BGB", "199"), ("ZPO", "692"), ("BGB", "204")}


def test_fr07_tokenizer_keeps_section_numbers_and_strips_one_ending() -> None:
    """Inflected forms match their base form; section numbers stay intact."""
    assert retrieval.tokenize("§ 703a ZPO: Fristen") == ["703a", "zpo", "frist"]


# --- FR-08 Sources -----------------------------------------------------------


def test_fr08_ac4_sources_are_wrapped_in_source_delimiters() -> None:
    """Chunks reach the model inside <source id="..."> blocks."""
    block = retrieval.format_sources_block([chunk("ZPO-692")])
    assert block == '<source id="ZPO-692">\ntext ZPO-692\n</source>'


def test_fr08_ac2_chunk_lookup_by_id_returns_the_stored_text() -> None:
    """The displayed German text comes from the store, not from the model (real index)."""
    doc = retrieval.get_chunk_by_id("ZPO-692")
    assert doc is not None
    assert doc.page_content.startswith("§ 692 ZPO")
    assert retrieval.get_chunk_by_id("ZPO-9999") is None


def test_fr04_ac4_reading_the_index_leaves_the_committed_files_unchanged() -> None:
    """Searches run on a working copy, so data/index/ stays as committed."""

    def digest() -> str:
        files = sorted(p for p in config.INDEX_DIR.rglob("*") if p.is_file())
        return hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()

    for cached in (retrieval._working_index_dir, retrieval.load_corpus, retrieval._bm25_index):
        cached.cache_clear()  # force a fresh open of the index
    before = digest()
    retrieval.load_corpus()
    retrieval.keyword_search("Verjährung")
    assert digest() == before


# --- D-8 experiment: pin explicit references after fusion ---------------------


def test_d8_pinning_moves_named_provisions_to_the_top(monkeypatch: pytest.MonkeyPatch) -> None:
    """Named provisions come first, in the order named; the rest keeps the fused order."""
    monkeypatch.setattr(config, "PIN_EXPLICIT_REFERENCES", True)
    fused = [chunk("BGB-200"), chunk("BGB-201"), chunk("BGB-195")]
    monkeypatch.setattr(retrieval, "_run_queries", lambda *a, **kw: fused)
    plan = RetrievalPlan(
        queries_de=["Verjährungsfrist § 199 BGB", "regelmäßige Frist § 195 BGB"], rationale="x"
    )
    ids = [c.chunk_id for c in retrieval.retrieve(plan, mode="bm25", k=4).chunks]
    assert ids == ["BGB-199", "BGB-195", "BGB-200", "BGB-201"]


def test_d8_pinning_is_limited_and_respects_the_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """At most two provisions are pinned, and none outside the law filter."""
    monkeypatch.setattr(config, "PIN_EXPLICIT_REFERENCES", True)
    fused = [chunk("ZPO-700", "ZPO"), chunk("ZPO-339", "ZPO")]
    monkeypatch.setattr(retrieval, "_run_queries", lambda *a, **kw: fused)
    plan = RetrievalPlan(
        queries_de=["§ 199 BGB § 692 ZPO § 694 ZPO § 699 ZPO"], law_filter=["ZPO"], rationale="x"
    )
    ids = [c.chunk_id for c in retrieval.retrieve(plan, mode="bm25", k=6).chunks]
    assert ids[:2] == ["ZPO-692", "ZPO-694"]
    assert "BGB-199" not in ids and "ZPO-699" not in ids


def test_d8_pinning_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """With PIN_EXPLICIT_REFERENCES=off, the fused order stays as it is."""
    monkeypatch.setattr(config, "PIN_EXPLICIT_REFERENCES", False)
    fused = [chunk("BGB-200"), chunk("BGB-201")]
    monkeypatch.setattr(retrieval, "_run_queries", lambda *a, **kw: fused)
    plan = RetrievalPlan(queries_de=["§ 199 BGB"], rationale="x")
    ids = [c.chunk_id for c in retrieval.retrieve(plan, mode="bm25").chunks]
    assert ids == ["BGB-200", "BGB-201"]
