"""Advanced RAG: query translation, metadata filter, hybrid search and fusion.

One LLM call turns the English question into German legal queries plus a law
filter (FR-05, FR-06); each query then runs against Chroma and a BM25 index over
the same chunks, and the result lists are fused with reciprocal rank fusion
(FR-07). The outcome carries everything the RAG panel displays (FR-18).

Related: FR-05, FR-06, FR-07, FR-08 AC4, FR-14, FR-18, FR-20 AC1, §5.2, §7.2
"""

from __future__ import annotations

import re
import shutil
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast, get_args

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from rank_bm25 import BM25Okapi

from collection_letter_navigator import config, guards, llm
from collection_letter_navigator.schemas import LawCode, RetrievalPlan, TriageResult

#: Retrieval modes that can be selected in the developer settings (FR-07 AC4).
RetrievalMode = Literal["vector", "bm25", "hybrid"]

#: Word characters for the BM25 tokenizer: lower-case letters incl. umlauts, digits.
_TOKEN = re.compile(r"[0-9]+[a-z]?|[a-zäöüß]+")

#: Endings removed once from longer tokens, so "Fristen" matches "Frist" (FR-07 AC1).
_ENDINGS = ("en", "es", "er", "e", "s", "n")

#: Explicit provision references such as "§ 199 BGB" or "BGB § 199" (FR-07 AC3).
_REFERENCE = re.compile(
    r"§+\s*(?P<s1>\d+[a-z]?)(?:\s*abs\.?\s*\d+)?\s*(?P<l1>bgb|zpo|rdg)\b"
    r"|\b(?P<l2>bgb|zpo|rdg)\s*§+\s*(?P<s2>\d+[a-z]?)",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ScoredChunk:
    """One retrieved chunk with its score.

    Attributes:
        chunk_id: Stable chunk ID, cited by the answer call (FR-08 AC2).
        document: The chunk, including its metadata.
        score: Retriever score, or the fused RRF score after fusion; higher is better.

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


@dataclass(frozen=True, slots=True)
class Bm25Index:
    """A BM25 index over a fixed list of chunks.

    Attributes:
        chunks: The indexed chunks, in index order.
        bm25: The BM25 scorer built from the tokenized chunks.

    Related: FR-07 AC1
    """

    chunks: tuple[Document, ...]
    bm25: BM25Okapi


# ---------------------------------------------------------------------------
# Query translation (FR-05, FR-06 AC1)
# ---------------------------------------------------------------------------


def _triage_context(triage: TriageResult | None) -> str:
    """Render the triage answers as plain context lines for the plan call."""
    if triage is None:
        return "No triage information."
    lines = [f"Sender: {triage.sender}", f"Delivered on: {triage.delivered_on.isoformat()}"]
    if triage.court_document:
        lines.append(f"Court document: {triage.court_document}")
    return "\n".join(lines)


def _normalise_plan(plan: RetrievalPlan, triage: TriageResult | None) -> RetrievalPlan:
    """Apply the deterministic filter rules on top of the model's plan.

    A filter that names all laws is the same as no filter; a court letter always
    keeps ZPO in a filter (FR-06 AC1). Duplicate and empty queries are dropped.

    Related: FR-05 AC1, FR-06 AC1
    """
    queries = list(dict.fromkeys(q.strip() for q in plan.queries_de if q.strip()))
    law_filter = list(dict.fromkeys(plan.law_filter)) if plan.law_filter else None
    if law_filter and triage is not None and triage.sender == "court" and "ZPO" not in law_filter:
        law_filter.append("ZPO")
    if law_filter and set(law_filter) >= set(config.KB_LAWS):
        law_filter = None
    return RetrievalPlan(
        queries_de=queries or plan.queries_de, law_filter=law_filter, rationale=plan.rationale
    )


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
        model: Chat model to use; defaults to the configured model.

    Returns:
        The validated plan with 1–4 German queries and an optional law filter.

    Raises:
        LlmCallError: If the call fails or the output never validates.

    Related: FR-05 AC1, FR-05 AC2, FR-06 AC1, FR-22
    """
    chat = model or llm.build_chat_model()
    # AI: structured output - LangChain sends the Pydantic schema and parses the reply back.
    planner = chat.with_structured_output(RetrievalPlan, method="json_schema")
    messages = [
        SystemMessage(llm.load_prompt("retrieval_plan")),
        HumanMessage(
            guards.wrap_untrusted(question_en, "question")
            + "\n"
            + guards.wrap_untrusted(_triage_context(triage), "context")
        ),
    ]
    last_error: Exception | None = None
    for _ in range(1 + config.JSON_RETRY_ATTEMPTS):
        try:
            # AI: the query-translation call, with retries on rate limits and timeouts
            started = time.perf_counter()
            reply = llm.call_with_retry(lambda: planner.invoke(messages))
            plan = RetrievalPlan.model_validate(reply)
            normalised = _normalise_plan(plan, triage)
            llm.log_call(
                "retrieval_plan",
                {
                    "seconds": round(time.perf_counter() - started, 2),
                    "question": question_en,
                    "plan": normalised.model_dump(),
                },
            )
            return normalised
        except ValidationError as error:  # schema violated: one retry (NFR-02)
            last_error = error
        except llm.LlmCallError:
            raise
        except Exception as error:  # anything else the client raises
            raise llm.LlmCallError(
                f"The search plan could not be created: {llm.friendly_error_message(error)}"
            ) from error
    raise llm.LlmCallError(f"The search plan was invalid: {last_error}")


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
    return RetrievalPlan(
        queries_de=[question_en],
        law_filter=None,
        rationale="Query translation is off: the English question is searched as it is, "
        "without a law filter.",
    )


# ---------------------------------------------------------------------------
# Stores (FR-04 AC4, FR-07 AC1)
# ---------------------------------------------------------------------------


@cache
def _working_index_dir() -> Path:
    """Copy the committed index to a temporary directory, once per process.

    Chroma writes to its files even when it only reads, which would leave the
    committed index modified after every run. Working on a copy keeps
    ``data/index/`` unchanged (FR-04 AC4).
    """
    if not (config.INDEX_DIR / "chroma.sqlite3").exists():
        raise FileNotFoundError(
            f"No index found in {config.INDEX_DIR}; run scripts/build_index.py first."
        )
    target = Path(tempfile.mkdtemp(prefix="cln-index-")) / "index"
    shutil.copytree(config.INDEX_DIR, target)
    return target


@cache
def load_vector_store() -> Chroma:
    """Open the committed Chroma index (a working copy of it).

    Returns:
        The vector store backed by a copy of :data:`config.INDEX_DIR`.

    Raises:
        FileNotFoundError: If the index has not been built or committed.

    Related: FR-04 AC4, FR-07 AC1
    """
    return Chroma(
        collection_name=config.CHROMA_COLLECTION_NAME,
        embedding_function=llm.build_embeddings(),  # AI: same model as at indexing time
        persist_directory=str(_working_index_dir()),
    )


@cache
def load_corpus() -> tuple[Document, ...]:
    """Read every chunk of the index, without any embedding call.

    Returns:
        All chunks in index order, each with its ``id`` set to the chunk ID.

    Raises:
        FileNotFoundError: If the index has not been built or committed.

    Related: FR-07 AC1, FR-08 AC2
    """
    store = Chroma(
        collection_name=config.CHROMA_COLLECTION_NAME,
        persist_directory=str(_working_index_dir()),
    )
    raw = store.get(include=["documents", "metadatas"])
    return tuple(
        Document(id=chunk_id, page_content=text or "", metadata=dict(metadata or {}))
        for chunk_id, text, metadata in zip(
            raw["ids"], raw["documents"], raw["metadatas"], strict=True
        )
    )


def tokenize(text: str) -> list[str]:
    """Split German text into lower-case BM25 tokens.

    Section numbers stay tokens of their own ("§ 199 BGB" → ``["199", "bgb"]``);
    one common ending is removed from longer words so that inflected forms match.

    Args:
        text: German text or query.

    Returns:
        The tokens.

    Related: FR-07 AC1, FR-07 AC3
    """
    tokens = []
    for token in _TOKEN.findall(text.lower()):
        if len(token) > 5 and not token[0].isdigit():
            for ending in _ENDINGS:
                if token.endswith(ending):
                    token = token[: -len(ending)]
                    break
        tokens.append(token)
    return tokens


def explicit_references(query: str) -> set[tuple[str, str]]:
    """Find provisions the query names explicitly.

    Args:
        query: A search query, e.g. ``"Beginn der Verjährung § 199 BGB"``.

    Returns:
        ``(law, section)`` pairs, e.g. ``{("BGB", "199")}``.

    Related: FR-07 AC3
    """
    found = set()
    for match in _REFERENCE.finditer(query):
        law = match.group("l1") or match.group("l2")
        section = match.group("s1") or match.group("s2")
        found.add((law.upper(), section.lower()))
    return found


@cache
def _bm25_index(law_filter: tuple[LawCode, ...] | None) -> Bm25Index:
    """Build (once) the BM25 index for one filter value."""
    chunks = tuple(
        doc for doc in load_corpus() if law_filter is None or doc.metadata.get("law") in law_filter
    )
    corpus = [tokenize(doc.page_content) for doc in chunks] or [[""]]
    return Bm25Index(chunks=chunks, bm25=BM25Okapi(corpus))  # AI: keyword relevance scorer


def _filter_key(law_filter: Sequence[LawCode] | None) -> tuple[LawCode, ...] | None:
    """Turn a filter into a hashable, order-independent cache key."""
    return tuple(sorted(set(law_filter))) if law_filter else None


def load_bm25_retriever(law_filter: Sequence[LawCode] | None = None) -> Bm25Index:
    """Build the BM25 index over the same chunks as the vector store.

    Args:
        law_filter: Laws to restrict the index to, or None for all chunks.

    Returns:
        A BM25 index over the (filtered) chunks.

    Related: FR-06 AC2, FR-07 AC1
    """
    return _bm25_index(_filter_key(law_filter))


# ---------------------------------------------------------------------------
# Searches and fusion (FR-06 AC2, FR-07)
# ---------------------------------------------------------------------------


def _chunk_id(doc: Document) -> str:
    """Read the stable chunk ID of a document."""
    return str(doc.metadata.get("chunk_id") or doc.id)


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
    key = _filter_key(law_filter)
    # AI: metadata filter, applied inside Chroma before the nearest-neighbour search
    where: Any = {"law": {"$in": list(key)}} if key else None
    hits = load_vector_store().similarity_search_with_score(  # AI: nearest neighbours
        query_de, k=k or config.RETRIEVAL_TOP_K, filter=where
    )
    return [ScoredChunk(_chunk_id(doc), doc, 1.0 / (1.0 + distance)) for doc, distance in hits]


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
        The hits with a positive score, ranked best first.

    Related: FR-06 AC2, FR-07 AC1, FR-07 AC3
    """
    index = load_bm25_retriever(law_filter)
    if not index.chunks:
        return []
    scores = list(index.bm25.get_scores(tokenize(query_de)))  # AI: BM25 score per chunk
    # A provision the query names explicitly is pinned to the top (FR-07 AC3).
    pinned = explicit_references(query_de)
    top = max(scores, default=0.0) + 1.0
    for i, doc in enumerate(index.chunks):
        if (doc.metadata.get("law"), doc.metadata.get("section")) in pinned:
            scores[i] = top
    ranked = sorted(range(len(index.chunks)), key=lambda i: scores[i], reverse=True)
    return [
        ScoredChunk(_chunk_id(index.chunks[i]), index.chunks[i], float(scores[i]))
        for i in ranked[: k or config.RETRIEVAL_TOP_K]
        if scores[i] > 0
    ]


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[ScoredChunk]],
    *,
    k: int | None = None,
    rrf_k: int | None = None,
) -> list[ScoredChunk]:
    """Fuse several ranked lists into one, merging duplicates.

    Each chunk scores ``sum(1 / (rrf_k + rank))`` over the lists it appears in
    (rank starting at 1). Only ranks count, so scores of different retrievers
    never have to be compared.

    Args:
        result_lists: One ranked list per query and per retriever.
        k: Size of the fused list; defaults to :data:`config.RETRIEVAL_TOP_K`.
        rrf_k: Rank constant; defaults to :data:`config.RRF_K`.

    Returns:
        At most *k* chunks, ranked by fused score, each appearing once.

    Related: FR-07 AC1, FR-07 AC2
    """
    constant = config.RRF_K if rrf_k is None else rrf_k
    scores: dict[str, float] = {}
    documents: dict[str, Document] = {}
    for results in result_lists:
        for rank, hit in enumerate(results, start=1):
            # AI: reciprocal rank fusion - a good rank in any list lifts the chunk
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (constant + rank)
            documents.setdefault(hit.chunk_id, hit.document)
    ranked = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)  # stable
    return [
        ScoredChunk(chunk_id, documents[chunk_id], scores[chunk_id])
        for chunk_id in ranked[: k or config.RETRIEVAL_TOP_K]
    ]


def _run_queries(
    queries: Sequence[str],
    mode: RetrievalMode,
    law_filter: Sequence[LawCode] | None,
    k: int,
) -> list[ScoredChunk]:
    """Run every query in the given mode and fuse all result lists."""
    depth = max(k, config.RETRIEVAL_FETCH_K)
    lists: list[list[ScoredChunk]] = []
    for query in queries:
        if mode in ("vector", "hybrid"):
            lists.append(vector_search(query, law_filter=law_filter, k=depth))
        if mode in ("bm25", "hybrid"):
            lists.append(keyword_search(query, law_filter=law_filter, k=depth))
    return reciprocal_rank_fusion(lists, k=k)


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

    Raises:
        ValueError: If the mode is unknown.

    Related: FR-06 AC2, FR-06 AC3, FR-07 AC1, FR-07 AC2, FR-18 AC1
    """
    chosen = mode or config.RETRIEVAL_MODE
    if chosen not in get_args(RetrievalMode):
        raise ValueError(f"Unknown retrieval mode {chosen!r}; use vector, bm25 or hybrid.")
    selected = cast(RetrievalMode, chosen)
    size = k or config.RETRIEVAL_TOP_K
    law_filter = list(plan.law_filter) if plan.law_filter else None
    chunks = _run_queries(plan.queries_de, selected, law_filter, size)
    fallback = False
    if law_filter and len(chunks) < config.MIN_FILTERED_RESULTS:
        chunks = _run_queries(plan.queries_de, selected, None, size)  # FR-06 AC3
        law_filter, fallback = None, True
    if config.PIN_EXPLICIT_REFERENCES:
        chunks = pin_explicit_references(chunks, plan.queries_de, law_filter, size)
    return RetrievalOutcome(plan, chunks, selected, law_filter, filter_fallback=fallback)


def pin_explicit_references(
    chunks: Sequence[ScoredChunk],
    queries: Sequence[str],
    law_filter: Sequence[LawCode] | None,
    k: int,
) -> list[ScoredChunk]:
    """Move provisions the queries name explicitly to the top of the fused list.

    Experiment D-8: in the spike gate, BGB §§ 195/199 were named in the queries
    but lost in the fusion against similar limitation chunks. At most
    :data:`config.MAX_PINNED_REFERENCES` provisions are pinned (first named
    first); all their chunks move up, even if fusion had not found them. The law
    filter still applies.

    Args:
        chunks: The fused list.
        queries: The German queries of the plan.
        law_filter: The applied filter, or None.
        k: Size of the final list.

    Returns:
        At most *k* chunks: pinned provisions first, then the rest in fused order.

    Related: FR-07 AC3, §12 D-8
    """
    named: list[tuple[str, str]] = []
    for query in queries:
        for match in _REFERENCE.finditer(query):  # in the order the queries name them
            law = (match.group("l1") or match.group("l2")).upper()
            section = (match.group("s1") or match.group("s2")).lower()
            if (law, section) not in named and (not law_filter or law in law_filter):
                named.append((law, section))
    named = named[: config.MAX_PINNED_REFERENCES]
    if not named:
        return list(chunks)[:k]
    pinned = [
        ScoredChunk(_chunk_id(doc), doc, 0.0)
        for ref in named
        for doc in load_corpus()
        if (doc.metadata.get("law"), doc.metadata.get("section")) == ref
    ]
    pinned_ids = {chunk.chunk_id for chunk in pinned}
    rest = [chunk for chunk in chunks if chunk.chunk_id not in pinned_ids]
    return (pinned + rest)[:k]


# ---------------------------------------------------------------------------
# Lookup and rendering (FR-08)
# ---------------------------------------------------------------------------


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
    return next((doc for doc in load_corpus() if _chunk_id(doc) == chunk_id), None)


def format_sources_block(chunks: Sequence[ScoredChunk]) -> str:
    """Wrap the retrieved chunks in the source delimiters of the answer call.

    Args:
        chunks: The chunks to pass to the model.

    Returns:
        The chunks rendered as ``<source id="…">…</source>`` blocks; the system
        prompt declares this content to be data, never instructions.

    Related: FR-08 AC4, FR-22 L4
    """
    return "\n\n".join(
        f'<source id="{chunk.chunk_id}">\n{chunk.document.page_content}\n</source>'
        for chunk in chunks
    )
