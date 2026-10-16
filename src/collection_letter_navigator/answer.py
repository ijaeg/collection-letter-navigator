"""The answer call: tool-calling loop, structured output and quote fidelity.

One LLM call answers the question from the retrieved chunks and may call the
deterministic tools (FR-10). Afterwards two deterministic checks run before the
answer is shown: cited chunk IDs must belong to this question's retrieval, and
every German quote in the English answer must appear verbatim in a cited chunk
(FR-09).

Related: FR-08, FR-09, FR-10, FR-17 AC1, FR-21 AC2, §5.1, §5.2, §7.4
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from collection_letter_navigator.retrieval import RetrievalOutcome
from collection_letter_navigator.schemas import AnswerWithSources, ToolResult, TriageResult


@dataclass(slots=True)
class AnswerOutcome:
    """The finished answer plus everything the UI and the metrics need.

    Attributes:
        answer: The structured answer, after the quote check has run.
        tool_results: One result per executed tool call, shown as tool cards.
        dropped_chunk_ids: Cited IDs that were not retrieved and were dropped.
        replaced_quotes: Number of quotes removed by the quote check.
        tool_call_limit_reached: True if the loop stopped at the call limit.

    Related: FR-09 AC1, FR-09 AC3, FR-10 AC5, FR-17 AC1, §7.4
    """

    answer: AnswerWithSources
    tool_results: list[ToolResult] = field(default_factory=list)
    dropped_chunk_ids: list[str] = field(default_factory=list)
    replaced_quotes: int = 0
    tool_call_limit_reached: bool = False


def answer_question(
    question_en: str,
    retrieval: RetrievalOutcome,
    *,
    triage: TriageResult | None = None,
    history: Sequence[BaseMessage] | None = None,
    model: BaseChatModel | None = None,
) -> AnswerOutcome:
    """Answer one question from the retrieved chunks, using tools where needed.

    Args:
        question_en: The user's question in English.
        retrieval: The chunks retrieved for this question.
        triage: Triage answers passed as context (FR-01 AC6).
        history: Earlier chat turns.
        model: Chat model with the tools bound; defaults to the configured model.

    Returns:
        The checked answer together with the tool results.

    Raises:
        LlmCallError: If the call fails after the retry budget (NFR-02).

    Related: FR-08 AC1, FR-08 AC2, FR-08 AC4, FR-10 AC1, FR-10 AC8, FR-21 AC2
    """
    raise NotImplementedError("FR-08 AC1: answer in English from the retrieved chunks")


def run_tool_calling_loop(
    model: BaseChatModel,
    messages: list[BaseMessage],
) -> tuple[list[BaseMessage], list[ToolResult], bool]:
    """Execute the model's tool calls until it answers or the limit is reached.

    A tool that raises does not end the chat: the failure is recorded and the
    loop continues without that result (FR-10 AC6).

    Args:
        model: Chat model with the tools bound.
        messages: The conversation so far; extended in place by the loop.

    Returns:
        A tuple of the extended messages, the collected tool results and a flag
        that is True if the call limit stopped the loop.

    Related: FR-10 AC1, FR-10 AC3, FR-10 AC5, FR-10 AC6, §5.1
    """
    raise NotImplementedError("FR-10 AC5: run at most 3 tool calls, then stop with a message")


def no_sources_answer() -> AnswerWithSources:
    """Build the answer used when no retrieved chunk supports an answer.

    Returns:
        An answer stating "I could not find this in the knowledge base", with
        the get-help links and no sources. General knowledge is never used.

    Related: FR-08 AC3, FR-21 AC5
    """
    raise NotImplementedError("FR-08 AC3: refuse instead of answering from general knowledge")


def validate_source_ids(
    answer: AnswerWithSources,
    retrieval: RetrievalOutcome,
) -> tuple[list[str], list[str]]:
    """Drop cited chunk IDs that were not retrieved for this question.

    Args:
        answer: The model's structured answer.
        retrieval: The retrieval outcome of this question.

    Returns:
        A tuple of the kept IDs and the dropped IDs; dropped IDs are counted in
        the answer checks (§7.4).

    Related: FR-09 AC1, §7.4
    """
    raise NotImplementedError("FR-09 AC1: drop chunk IDs outside this question's retrieval")


def normalise_whitespace(text: str) -> str:
    """Collapse whitespace so that quotes can be compared to the source text.

    Args:
        text: Any text.

    Returns:
        The text with runs of whitespace collapsed to single spaces and the ends
        stripped.

    Related: FR-09 AC2
    """
    raise NotImplementedError("FR-09 AC2: normalise whitespace before comparing quotes")


def extract_german_quotes(answer_text: str) -> list[str]:
    """Find the German quotes inside the English answer text.

    Args:
        answer_text: The English answer.

    Returns:
        The quoted passages that contain German, in order of appearance.

    Related: FR-09 AC2
    """
    raise NotImplementedError("FR-09 AC2: find quoted German passages in the answer")


def quote_is_grounded(quote: str, chunk_ids: Sequence[str]) -> bool:
    """Check one quote against the cited chunks.

    Args:
        quote: The quoted passage.
        chunk_ids: IDs of the chunks the answer cites.

    Returns:
        True if the normalised quote is a substring of a cited chunk.

    Related: FR-09 AC2
    """
    raise NotImplementedError("FR-09 AC2: verify the quote against the cited chunk text")


def enforce_quote_fidelity(
    answer: AnswerWithSources,
    chunk_ids: Sequence[str],
) -> tuple[AnswerWithSources, int]:
    """Remove every quote that is not backed by a cited chunk.

    A failing quote is replaced by a reference to the provision ("see § … below").

    Args:
        answer: The structured answer, after :func:`validate_source_ids`.
        chunk_ids: IDs of the chunks the answer cites.

    Returns:
        A tuple of the cleaned answer and the number of replaced quotes.

    Related: FR-09 AC3, §7.4
    """
    raise NotImplementedError("FR-09 AC3: replace unverified quotes with a reference")


def append_deadline_reminder(answer_text: str, triage: TriageResult | None) -> str:
    """Append the one-line deadline reminder to answers about what to do next.

    Args:
        answer_text: The English answer text.
        triage: Triage answers; the reminder is added only for court documents.

    Returns:
        The answer text, with the deadline reminder appended where it applies.

    Related: FR-21 AC2
    """
    raise NotImplementedError("FR-21 AC2: remind of the deadline on court-document answers")
