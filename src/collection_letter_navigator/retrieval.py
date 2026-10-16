"""Advanced RAG: query translation, metadata filter, hybrid search and fusion.

One LLM call turns the English question into German legal queries plus a law
filter (FR-05, FR-06); each query then runs against Chroma and a BM25 index over
the same chunks, and the result lists are fused with reciprocal rank fusion
(FR-07). The outcome carries everything the RAG panel displays (FR-18).

Related: FR-05, FR-06, FR-07, FR-08 AC4, FR-14, FR-18, FR-20 AC1, §5.2, §7.2
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

from collection_letter_navigator.schemas import LawCode, RetrievalPlan, TriageResult

#: Retrieval modes that can be selected in the developer settings (FR-07 AC4).
RetrievalMode = Literal["vector", "bm25", "hybrid"]


@dataclass(slots=True)
class ScoredChunk:
    """One retrieved chunk with its fused score.

    Attributes:
        chunk_id: Stable chunk ID, cited by the answer call (FR-08 AC2).
        document: The chunk, including its metadata.
        score: Fused score; higher is better.

    Related: FR-07 AC1, FR-18 AC1
    """

    chunk_id: str
    document: Document
    score: float


@dataclass(slots=True)
class RetrievalOutcome:
    """Everything one retrieval run produced, including what the RAG panel shows.

    Attributes:
        plan: The retrieval plan the queries came from.
        chunks: The fused top *k* chunks.
        mode: The retrieval mode that was used.
        applied_filter: The law filter that was actually applied, or None.
        filter_fallback: True if the filtered search was retried unfiltered.

    Related: FR-06 AC3, FR-06 AC4, FR-07 AC2, FR-18 AC1
    """

    plan: RetrievalPlan
    chunks: list[ScoredChunk] = field(default_factory=list)
    mode: RetrievalMode = "hybrid"
    applied_filter: list[LawCode] | None = None
    filter_fallback: bool = False


def create_retrieval_plan(
    question_en: str,
    triage: TriageResult | None = None,
    *,
    model: BaseChatModel | None = None,
) -> RetrievalPlan:
    """Translate the English question into German queries and a law filter.

    This is a fixed step of the pipeline, not a tool the model may skip
    (FR-05 AC2). The question and the triage context are passed inside
    delimiters as untrusted data (FR-22 L4).

    Args:
        question_en: The user's question in English.
        triage: Triage answers used as context, if available.
        model: Chat model to use; defaults to the configured small model.

    Returns:
        The validated plan with 1–4 German queries and an optional law filter.

    Raises:
        LlmCallError: If the call fails or the output never validates.

    Related: FR-05 AC1, FR-05 AC2, FR-06 AC1, FR-22
    """
    raise NotImplementedError("FR-05 AC1: translate the question into German legal queries")


def passthrough_plan(question_en: str) -> RetrievalPlan:
    """Build the plan used when query translation is switched off.

    The English question is used directly and the search stays unfiltered,
    because the filter comes from the same call (FR-05 AC5).

    Args:
        question_en: The user's question in English.

    Returns:
        A plan with the English question as its only query and no filter.

    Related: FR-05 AC4, FR-05 AC5, §7.2
    """
    raise NotImplementedError("FR-05 AC5: use the English question unfiltered when translation off")


def load_vector_store() -> Chroma:
    """Open the committed Chroma index.

    Returns:
        The vector store backed by :data:`config.INDEX_DIR`.

    Raises:
        FileNotFoundError: If the index has not been built or committed.

    Related: FR-04 AC4, FR-07 AC1
    """
    raise NotImplementedError("FR-07 AC1: open the committed Chroma index")


def load_bm25_retriever(law_filter: Sequence[LawCode] | None = None) -> BM25Retriever:
    """Build the BM25 index over the same chunks as the vector store.

    Args:
        law_filter: Laws to restrict the index to, or None for all chunks.

    Returns:
        A BM25 retriever over the (filtered) chunks.

    Related: FR-06 AC2, FR-07 AC1
    """
    raise NotImplementedError("FR-07 AC1: build BM25 over the same chunks as the vector store")


def vector_search(
    query_de: str,
    *,
    law_filter: Sequence[LawCode] | None = None,
    k: int | None = None,
) -> list[ScoredChunk]:
    """Run one German query against the vector store.

    Args:
        query_de: The German search query; the query prefix is applied by
            :func:`llm.apply_embedding_prefix`.
        law_filter: Laws the search is restricted to, or None.
        k: Number of hits; defaults to :data:`config.RETRIEVAL_TOP_K`.

    Returns:
        The hits, ranked best first.

    Related: FR-04 AC6, FR-06 AC2, FR-07 AC1
    """
    raise NotImplementedError("FR-07 AC1: run the filtered vector search")


def keyword_search(
    query_de: str,
    *,
    law_filter: Sequence[LawCode] | None = None,
    k: int | None = None,
) -> list[ScoredChunk]:
    """Run one German query against the BM25 index.

    Args:
        query_de: The German search query.
        law_filter: Laws the search is restricted to, or None.
        k: Number of hits; defaults to :data:`config.RETRIEVAL_TOP_K`.

    Returns:
        The hits, ranked best first.

    Related: FR-06 AC2, FR-07 AC1, FR-07 AC3
    """
    raise NotImplementedError("FR-07 AC1: run the filtered BM25 search")


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[ScoredChunk]],
    *,
    k: int | None = None,
    rrf_k: int | None = None,
) -> list[ScoredChunk]:
    """Fuse several ranked lists into one, merging duplicates.

    Args:
        result_lists: One ranked list per query and per retriever.
        k: Size of the fused list; defaults to :data:`config.RETRIEVAL_TOP_K`.
        rrf_k: Rank constant; defaults to :data:`config.RRF_K`.

    Returns:
        At most *k* chunks, ranked by fused score, each appearing once.

    Related: FR-07 AC1, FR-07 AC2
    """
    raise NotImplementedError("FR-07 AC1: fuse the ranked lists and merge duplicates")


def retrieve(
    plan: RetrievalPlan,
    *,
    mode: RetrievalMode | None = None,
    k: int | None = None,
) -> RetrievalOutcome:
    """Run the whole retrieval for one plan.

    Runs every German query in the selected mode, applies the law filter to both
    retrievers, falls back to an unfiltered search when the filtered one returns
    fewer than :data:`config.MIN_FILTERED_RESULTS` chunks, and fuses the results.

    Args:
        plan: The retrieval plan.
        mode: Retrieval mode; defaults to :data:`config.RETRIEVAL_MODE`.
        k: Context size; defaults to :data:`config.RETRIEVAL_TOP_K`.

    Returns:
        The outcome, including the applied filter and whether the fallback ran.

    Related: FR-06 AC2, FR-06 AC3, FR-07 AC1, FR-07 AC2, FR-18 AC1
    """
    raise NotImplementedError("FR-07 AC1: run filtered hybrid retrieval with fallback")


def get_chunk_by_id(chunk_id: str) -> Document | None:
    """Look up one chunk in the knowledge base.

    Used to render the German source text from the store rather than from the
    model (FR-08 AC2), and by the ``fetch_paragraph`` tool (FR-14).

    Args:
        chunk_id: The chunk ID.

    Returns:
        The chunk, or None if the ID is unknown.

    Related: FR-08 AC2, FR-09 AC1, FR-14 AC1
    """
    raise NotImplementedError("FR-08 AC2: read the displayed source text from the store")


def format_sources_block(chunks: Sequence[ScoredChunk]) -> str:
    """Wrap the retrieved chunks in the source delimiters of the answer call.

    Args:
        chunks: The chunks to pass to the model.

    Returns:
        The chunks rendered as ``<source id="…">…</source>`` blocks; the system
        prompt declares this content to be data, never instructions.

    Related: FR-08 AC4, FR-22 L4
    """
    raise NotImplementedError("FR-08 AC4: wrap sources in <source id=...> delimiters")
