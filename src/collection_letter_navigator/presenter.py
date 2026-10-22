"""What the UI shows, prepared without Streamlit so it can be tested.

``app.py`` only lays these values out on the screen (NFR-05). This module
builds the deadline card, the legal basis of a tool card, the session's token
and cost totals and the knowledge-base dates.

Related: FR-01 AC3, FR-08 AC2, FR-17 AC1, FR-19 AC1, FR-21 AC2, FR-21 AC6, R-12
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import cache

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from collection_letter_navigator import config, guards, pricing, retrieval
from collection_letter_navigator.llm import LlmUsage
from collection_letter_navigator.retrieval import RetrievalOutcome
from collection_letter_navigator.schemas import ToolResult, TriageResult
from collection_letter_navigator.tools import deadlines

#: Matches one provision as the tools write it, e.g. "BGB § 199 (1)" or "ZPO § 222".
_REFERENCE = re.compile(r"^(BGB|ZPO|RDG) § (\d+[a-z]?)(?: \((\d+)\))?")


@dataclass(frozen=True, slots=True)
class DeadlineCard:
    """The pinned deadline card for a court letter (FR-01 AC3).

    Attributes:
        procedure: ``Widerspruch`` or ``Einspruch``.
        period_end: Last day of the period.
        weekday: English weekday of ``period_end``.
        strict: True for a strict deadline (*Notfrist*).
        note: The tool's note on what happens after the period.
        assumptions: The tool's assumptions, shown below the date.
        missing_information: What could change the date.

    Related: FR-01 AC3, FR-11, FR-21 AC2
    """

    procedure: str
    period_end: date
    weekday: str
    strict: bool
    note: str
    assumptions: list[str]
    missing_information: list[str]

    @property
    def headline(self) -> str:
        """One line with the end of the period, stated as a fact (FR-21 AC4)."""
        return (
            f"The period for {self.procedure} ends on {self.weekday}, "
            f"{self.period_end.day} {self.period_end:%B %Y}."
        )


def deadline_card(triage: TriageResult | None) -> DeadlineCard | None:
    """Build the deadline card for a court letter, or None for any other sender.

    The delivery date is used as the assumed date of service; for ``unclear``
    the tool takes the stricter reading and says so in its assumptions.

    Args:
        triage: The triage answers.

    Returns:
        The card, or None if the sender is not a court or the tool cannot
        compute a date.

    Related: FR-01 AC3, FR-01 AC5, FR-11 AC4
    """
    if triage is None or triage.sender != "court":
        return None
    outcome = deadlines.calculate_objection_deadline(
        deadlines.ObjectionDeadlineArgs(
            document_type=triage.court_document or "unclear", service_date=triage.delivered_on
        )
    )
    if outcome.result is None:
        return None
    result = outcome.result
    return DeadlineCard(
        procedure=str(result["procedure"]),
        period_end=date.fromisoformat(str(result["period_end"])),
        weekday=str(result["period_end_weekday"]),
        strict=bool(result["strict_deadline"]),
        note=str(result.get("note") or ""),
        assumptions=list(outcome.assumptions),
        missing_information=list(outcome.missing_information),
    )


def chunk_id_for_reference(reference: str) -> str | None:
    """Map a provision such as ``"BGB § 199 (1)"`` to a chunk ID in the knowledge base.

    A subsection chunk (``BGB-204-1``) is preferred; otherwise the whole
    section (``BGB-199``) is used.

    Returns:
        The chunk ID, or None if the provision is not in the knowledge base.

    Related: R-12, FR-17 AC1
    """
    match = _REFERENCE.match(reference.strip())
    if match is None:
        return None
    law, section, subsection = match.groups()
    candidates = [f"{law}-{section}-{subsection}"] if subsection else []
    candidates.append(f"{law}-{section}")
    for candidate in candidates:
        if retrieval.get_chunk_by_id(candidate) is not None:
            return candidate
    return None


def legal_basis_of(result: ToolResult) -> list[tuple[str, Document | None]]:
    """The provisions a tool relied on, with the German text where it is indexed.

    This fills the "Legal basis" of a tool card even when the provisions were
    not among the retrieved chunks (smoke test, limitation question).

    Returns:
        One ``(reference, document or None)`` pair per entry of ``legal_basis``.

    Related: R-12, FR-17 AC1, FR-08 AC2
    """
    pairs: list[tuple[str, Document | None]] = []
    for reference in result.legal_basis:
        chunk_id = chunk_id_for_reference(reference)
        pairs.append((reference, retrieval.get_chunk_by_id(chunk_id) if chunk_id else None))
    return pairs


@dataclass(slots=True)
class UsageTotals:
    """Token and cost totals of the session, shown in the sidebar (FR-19 AC1).

    Attributes:
        calls: Number of LLM calls.
        prompt_tokens: Prompt tokens of all calls.
        completion_tokens: Completion tokens, including reasoning tokens.
        reasoning_tokens: Reasoning tokens (already inside ``completion_tokens``).
        cost_usd: Sum of all calls whose cost is known.
        calls_without_cost: Calls whose cost could not be determined.

    Related: FR-19 AC1, FR-19 AC2
    """

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float = 0.0
    calls_without_cost: int = field(default=0)

    def add(
        self,
        usages: Sequence[LlmUsage],
        cost_of: Callable[[LlmUsage], float | None] = pricing.cost_of,
    ) -> None:
        """Add the usage of one question's LLM calls."""
        for usage in usages:
            self.calls += 1
            self.prompt_tokens += usage.prompt_tokens
            self.completion_tokens += usage.completion_tokens
            self.reasoning_tokens += usage.reasoning_tokens
            cost = cost_of(usage)
            if cost is None:
                self.calls_without_cost += 1
            else:
                self.cost_usd += cost

    @property
    def cost_label(self) -> str:
        """The cost as shown in the sidebar, or "cost unavailable" (FR-19 AC2)."""
        if self.calls and self.calls_without_cost == self.calls:
            return "cost unavailable"
        label = f"${self.cost_usd:.4f}"
        return (
            f"{label} (without {self.calls_without_cost} calls)"
            if self.calls_without_cost
            else label
        )


@cache
def knowledge_base_dates() -> tuple[str, str]:
    """Snapshot date of the statutes and date of the newest base rate (FR-21 AC6).

    Returns:
        ``(statutes snapshot date, latest base rate valid from)``, both ISO dates.

    Related: FR-21 AC6, FR-04, D-5
    """
    manifest = json.loads(config.INDEX_MANIFEST_PATH.read_text(encoding="utf-8"))
    with config.BASE_RATES_PATH.open(encoding="utf-8", newline="") as handle:
        latest = max(row["valid_from"] for row in csv.DictReader(handle))
    return str(manifest["snapshot_date"]), latest


def provision_label(doc: Document) -> str:
    """Heading of a legal-basis entry, e.g. "§ 13a (1) RDG – Darlegungs- …" (FR-08 AC2)."""
    meta = doc.metadata
    subsection = f" ({meta['subsection']})" if meta.get("subsection") else ""
    return f"§ {meta['section']}{subsection} {meta['law']} – {meta['title']}"


def history_messages(turns: Sequence[tuple[str, str]]) -> list[BaseMessage]:
    """Earlier question-answer pairs as chat messages for the answer call.

    Only the last :data:`config.HISTORY_TURNS` pairs are kept; earlier questions
    are wrapped as untrusted data, like the current one (FR-22 L4).

    Args:
        turns: ``(question, answer)`` pairs, oldest first.

    Returns:
        Alternating human and AI messages.

    Related: FR-08, FR-22, §5.1
    """
    messages: list[BaseMessage] = []
    for question, answer_text in turns[-config.HISTORY_TURNS :]:
        messages.append(HumanMessage(guards.wrap_untrusted(question, "history")))
        messages.append(AIMessage(answer_text))
    return messages


#: Readable names of the retrieval modes in the RAG panel (FR-18 AC1).
MODE_LABELS = {
    "vector": "vector search",
    "bm25": "keyword search (BM25)",
    "hybrid": "hybrid search",
}


@dataclass(frozen=True, slots=True)
class RagPanel:
    """What the RAG process panel shows for one answer (FR-18 AC1).

    Attributes:
        queries: The German search queries (or the English question without translation).
        rationale: The plan's one-line reason for queries and filter.
        filter_label: The applied law filter, e.g. "ZPO", or "none".
        fallback: True if the filtered search was retried without filter (FR-06 AC3).
        mode_label: The retrieval mode in plain words.
        rows: One row per retrieved chunk: rank, provision, chunk ID, fused score.

    Related: FR-18 AC1, FR-06 AC3, FR-07 AC2
    """

    queries: list[str]
    rationale: str
    filter_label: str
    fallback: bool
    mode_label: str
    rows: list[dict[str, object]]


def rag_panel(found: RetrievalOutcome) -> RagPanel:
    """Prepare the RAG process panel of one answer.

    Args:
        found: The retrieval run of the answer.

    Returns:
        The panel content; the score is the fused RRF score (higher is better).

    Related: FR-18 AC1
    """
    rows: list[dict[str, object]] = []
    for rank, chunk in enumerate(found.chunks, start=1):
        meta = chunk.document.metadata
        subsection = f" ({meta['subsection']})" if meta.get("subsection") else ""
        rows.append(
            {
                "rank": rank,
                "provision": f"§ {meta.get('section', '?')}{subsection} {meta.get('law', '')}",
                "title": meta.get("title", ""),
                "chunk": chunk.chunk_id,
                "score": round(chunk.score, 4),
            }
        )
    return RagPanel(
        queries=list(found.plan.queries_de),
        rationale=found.plan.rationale,
        filter_label=", ".join(found.applied_filter) if found.applied_filter else "none",
        fallback=found.filter_fallback,
        mode_label=MODE_LABELS.get(found.mode, found.mode),
        rows=rows,
    )
