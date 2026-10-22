"""The answer call: tool-calling loop, structured output and quote fidelity.

One LLM call answers the question from the retrieved chunks and may call the
deterministic tools (FR-10). Afterwards two deterministic checks run before the
answer is shown: cited chunk IDs must belong to this question's retrieval, and
every German quote in the English answer must appear verbatim in a cited chunk
(FR-09).

Related: FR-08, FR-09, FR-10, FR-17 AC1, FR-21 AC2, §5.1, §5.2, §7.4
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from collection_letter_navigator import config, guards, llm, tools
from collection_letter_navigator import retrieval as retrieval_module
from collection_letter_navigator.retrieval import RetrievalOutcome
from collection_letter_navigator.schemas import AnswerWithSources, ToolResult, TriageResult
from collection_letter_navigator.tools import deadlines

#: Answer used when the knowledge base does not support an answer (FR-08 AC3).
NOT_FOUND_EN = (
    "I could not find this in the knowledge base. For help with your situation, contact a "
    "consumer advice centre (Verbraucherzentrale) or a free debt counselling service; the "
    "links are shown below."
)

#: Referral added to every out-of-scope answer (FR-21 AC5, FR-21 AC7).
REFERRAL_EN = (
    "For help with this, contact a free debt counselling service (Schuldnerberatung) or a "
    "consumer advice centre (Verbraucherzentrale); the links are shown below."
)

#: Answer used when an out-of-scope answer has no usable text of its own (FR-21 AC7, AC9).
OUT_OF_SCOPE_EN = (
    "This question is outside what this app covers: it explains debt collection letters and "
    "court payment orders. " + REFERRAL_EN + " If insolvency proceedings are open, your "
    "insolvency administrator (Insolvenzverwalter) is also the right contact."
)

#: Message returned to the model for tool calls beyond the limit (FR-10 AC5).
TOOL_LIMIT_MESSAGE = (
    "Tool call limit reached. Do not call further tools; answer with the results you have."
)

#: Quoted passages: German „…“, English “…” and straight "…" quotation marks (FR-09 AC2).
_QUOTE = re.compile(r"„([^“”\"]+)[“”\"]|“([^”]+)”|\"([^\"]+)\"")

#: Words that mark a passage as German; together with umlauts and ß (FR-09 AC2).
_GERMAN_WORDS = frozenset(
    [
        "der",
        "die",
        "das",
        "den",
        "dem",
        "des",
        "und",
        "oder",
        "ist",
        "sind",
        "wird",
        "werden",
        "kann",
        "nicht",
        "ein",
        "eine",
        "einer",
        "eines",
        "zu",
        "von",
        "mit",
        "auf",
        "für",
        "bei",
        "nach",
        "vor",
        "seit",
        "soweit",
        "wenn",
        "so",
        "dass",
    ]
)

#: Ellipsis marks a model may use inside or around a quote.
_ELLIPSIS = re.compile(r"\s*(?:…|\.\.\.|\[…\]|\(…\))\s*")


@dataclass(slots=True)
class AnswerOutcome:
    """The finished answer plus everything the UI and the metrics need.

    Attributes:
        answer: The structured answer, after the quote check has run.
        tool_results: One result per executed tool call, shown as tool cards.
        dropped_chunk_ids: Cited IDs that were not retrieved and were dropped.
        replaced_quotes: Number of quotes removed by the quote check.
        tool_call_limit_reached: True if the loop stopped at the call limit.
        structured_fallback: True if the final answer needed the extra
            structured-output call (FR-10 AC8).
        usages: Token usage of every LLM call of the answer (FR-19 AC1).

    Related: FR-09 AC1, FR-09 AC3, FR-10 AC5, FR-10 AC8, FR-17 AC1, FR-19 AC1, §7.4
    """

    answer: AnswerWithSources
    tool_results: list[ToolResult] = field(default_factory=list)
    dropped_chunk_ids: list[str] = field(default_factory=list)
    replaced_quotes: int = 0
    tool_call_limit_reached: bool = False
    structured_fallback: bool = False
    usages: list[llm.LlmUsage] = field(default_factory=list)


def _context_block(triage: TriageResult | None) -> str:
    """Render the triage answers for the answer call (FR-01 AC6)."""
    if triage is None:
        return "No triage information."
    lines = [f"Sender: {triage.sender}", f"Delivered on: {triage.delivered_on.isoformat()}"]
    if triage.court_document:
        lines.append(f"Court document: {triage.court_document}")
    return "\n".join(lines)


def build_messages(
    question_en: str,
    retrieval: RetrievalOutcome,
    triage: TriageResult | None = None,
    history: Sequence[BaseMessage] | None = None,
    today: date | None = None,
) -> list[BaseMessage]:
    """Assemble the messages of the answer call.

    The system prompt comes from ``prompts/answer.md`` with today's date filled
    in (FR-10 AC9); question, context and sources are delimited data (FR-08 AC4).

    Related: FR-08 AC4, FR-10 AC9, FR-22 L4, §5.1
    """
    system = llm.load_prompt("answer").replace("{today}", (today or date.today()).isoformat())
    human = "\n".join(
        (
            guards.wrap_untrusted(_context_block(triage), "context"),
            guards.wrap_untrusted(question_en, "question"),
            f"<sources>\n{retrieval_module.format_sources_block(retrieval.chunks)}\n</sources>",
        )
    )
    return [SystemMessage(system), *(history or []), HumanMessage(human)]


def _parse_answer(reply: AIMessage) -> AnswerWithSources | None:
    """Read the structured answer from a final reply, or None if it does not validate."""
    parsed = reply.additional_kwargs.get("parsed")
    if isinstance(parsed, AnswerWithSources):
        return parsed
    try:
        content = reply.content if isinstance(reply.content, str) else json.dumps(reply.content)
        return AnswerWithSources.model_validate_json(content)
    except ValidationError:
        return None


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
    if not retrieval.chunks:  # nothing retrieved: no LLM call, no general knowledge
        return AnswerOutcome(answer=no_sources_answer())
    chat = model or llm.build_chat_model()
    # AI: tools and the structured answer bound together - one call does either (E-8)
    bound = chat.bind_tools(tools.get_tools(), response_format=AnswerWithSources, strict=True)
    messages = build_messages(question_en, retrieval, triage, history)
    messages, tool_results, limit_reached, usages = _loop(bound, messages)

    final = messages[-1]
    parsed = _parse_answer(final) if isinstance(final, AIMessage) else None
    fallback = parsed is None
    if parsed is None:  # FR-10 AC8: one extra structured-output call over the same messages
        structured = chat.with_structured_output(
            AnswerWithSources, method="json_schema", include_raw=True
        )
        raw = llm.call_with_retry(lambda: structured.invoke(messages))  # AI: answer as JSON
        if isinstance(raw, dict) and isinstance(raw.get("raw"), AIMessage):
            usages.append(llm.extract_usage(raw["raw"], config.CHAT_MODEL))
        candidate = raw.get("parsed") if isinstance(raw, dict) else None
        llm.log_call("answer_fallback", {"parsed": candidate is not None})
        if not isinstance(candidate, AnswerWithSources):
            raise llm.LlmCallError("The answer could not be read. Please try again.")
        parsed = candidate

    kept, dropped = validate_source_ids(parsed, retrieval)
    executed = list(dict.fromkeys(result.tool for result in tool_results))
    answer = parsed.model_copy(update={"source_chunk_ids": kept, "used_tools": executed})
    if not kept and not answer.out_of_scope and not tool_results:
        answer = no_sources_answer()  # FR-08 AC3: no supporting source, no answer
    answer, replaced = enforce_quote_fidelity(answer, kept)
    if answer.out_of_scope:
        answer = answer.model_copy(update={"answer_en": ensure_referral(answer.answer_en)})
    else:
        answer = answer.model_copy(
            update={"answer_en": append_deadline_reminder(answer.answer_en, triage)}
        )
    return AnswerOutcome(
        answer=answer,
        tool_results=tool_results,
        dropped_chunk_ids=dropped,
        replaced_quotes=replaced,
        tool_call_limit_reached=limit_reached,
        structured_fallback=fallback,
        usages=usages,
    )


def _call_model(
    model: Runnable[Any, Any], messages: list[BaseMessage], usages: list[llm.LlmUsage]
) -> AIMessage:
    """One answer-call request: retry, record usage, write the opt-in debug log."""
    started = time.perf_counter()
    reply = llm.invoke_with_retry(model, messages)  # AI: the model answers or calls tools
    usage = llm.extract_usage(reply, config.CHAT_MODEL)
    usages.append(usage)
    llm.log_call(
        "answer_call",
        {
            "seconds": round(time.perf_counter() - started, 2),
            "tool_calls": [{"name": c["name"], "args": c.get("args")} for c in reply.tool_calls],
            "content": str(reply.content)[:2000],
            "usage": llm.usage_as_dict(usage),
        },
    )
    return reply


def _loop(
    model: Runnable[Any, Any],
    messages: list[BaseMessage],
) -> tuple[list[BaseMessage], list[ToolResult], bool, list[llm.LlmUsage]]:
    """The tool-calling loop, also returning the usage of every call."""
    results: list[ToolResult] = []
    usages: list[llm.LlmUsage] = []
    limit_reached = False
    while True:
        reply = _call_model(model, messages, usages)
        messages.append(reply)
        if not reply.tool_calls:
            return messages, results, limit_reached, usages
        for call in reply.tool_calls:
            if len(results) >= config.MAX_TOOL_CALLS_PER_QUESTION:
                limit_reached = True  # FR-10 AC5: every call still gets an answer message
                content = json.dumps({"error": TOOL_LIMIT_MESSAGE})
            else:
                # AI: the app runs the tool - the model only asked for it
                result = tools.invoke_tool(call["name"], call.get("args") or {})
                results.append(result)
                content = result.model_dump_json()
                llm.log_call(
                    "tool_call",
                    {"name": call["name"], "args": call.get("args"), "result": result.model_dump()},
                )
            messages.append(ToolMessage(content=content, tool_call_id=call["id"] or ""))
        if limit_reached:
            final = _call_model(model, messages, usages)
            messages.append(final)
            if final.tool_calls:  # still asking for tools: answer them, then stop
                messages.extend(
                    ToolMessage(
                        content=json.dumps({"error": TOOL_LIMIT_MESSAGE}),
                        tool_call_id=c["id"] or "",
                    )
                    for c in final.tool_calls
                )
            return messages, results, limit_reached, usages


def run_tool_calling_loop(
    model: Runnable[Any, Any],
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
    extended, results, limit_reached, _ = _loop(model, messages)
    return extended, results, limit_reached


def no_sources_answer() -> AnswerWithSources:
    """Build the answer used when no retrieved chunk supports an answer.

    Returns:
        An answer stating "I could not find this in the knowledge base", with
        the get-help links and no sources. General knowledge is never used.

    Related: FR-08 AC3, FR-21 AC5
    """
    return AnswerWithSources(answer_en=NOT_FOUND_EN, source_chunk_ids=[], used_tools=[])


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
    retrieved = {chunk.chunk_id for chunk in retrieval.chunks}
    kept: list[str] = []
    dropped: list[str] = []
    for chunk_id in dict.fromkeys(answer.source_chunk_ids):  # duplicates count once
        (kept if chunk_id in retrieved else dropped).append(chunk_id)
    return kept, dropped


def normalise_whitespace(text: str) -> str:
    """Collapse whitespace so that quotes can be compared to the source text.

    Args:
        text: Any text.

    Returns:
        The text with runs of whitespace collapsed to single spaces and the ends
        stripped.

    Related: FR-09 AC2
    """
    return " ".join(text.split())


def extract_german_quotes(answer_text: str) -> list[str]:
    """Find the German quotes inside the English answer text.

    Args:
        answer_text: The English answer.

    Returns:
        The quoted passages that contain German, in order of appearance.

    Related: FR-09 AC2
    """
    quotes = []
    for match in _QUOTE.finditer(answer_text):
        quote = next(group for group in match.groups() if group is not None)
        words = re.findall(r"[a-zäöüß]+", quote.lower())
        # A single quoted term ("Widerspruch") is a name, not a quote of the statute.
        if len(words) >= 3 and (re.search(r"[äöüß]", quote.lower()) or _GERMAN_WORDS & set(words)):
            quotes.append(quote)
    return quotes


def quote_is_grounded(quote: str, chunk_ids: Sequence[str]) -> bool:
    """Check one quote against the cited chunks.

    Args:
        quote: The quoted passage.
        chunk_ids: IDs of the chunks the answer cites.

    Returns:
        True if the normalised quote is a substring of a cited chunk.

    Related: FR-09 AC2
    """
    sources = [
        normalise_whitespace(doc.page_content)
        for doc in (retrieval_module.get_chunk_by_id(chunk_id) for chunk_id in chunk_ids)
        if doc is not None
    ]
    # Every part between ellipses must appear verbatim in one cited chunk.
    parts = [
        normalise_whitespace(part).strip(" .,;:")
        for part in _ELLIPSIS.split(quote)
        if part.strip(" .,;:")
    ]
    return bool(parts) and any(all(part in source for part in parts) for source in sources)


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
    text = answer.answer_en
    replaced = 0
    reference = "(see the legal basis below)"
    if chunk_ids:
        first = retrieval_module.get_chunk_by_id(chunk_ids[0])
        if first is not None:
            reference = f"(see § {first.metadata['section']} {first.metadata['law']} below)"
    for quote in extract_german_quotes(text):
        if quote_is_grounded(quote, chunk_ids):
            continue
        # AI: a quote the model invented is removed, never shown as statute text
        text, count = re.subn(rf"[„“\"]{re.escape(quote)}[“”\"]", reference, text, count=1)
        replaced += count
    return answer.model_copy(update={"answer_en": text}), replaced


def is_out_of_scope_topic(question: str) -> bool:
    """True if the question names a topic that is always out of scope (FR-21 AC7).

    Only for topics the model recognised unreliably: credit-agency (SCHUFA)
    questions (safety test S06). Garnishment and insolvency are left to the
    model, because words like "garnish" also appear in legitimate questions.

    Related: FR-21 AC7
    """
    lowered = question.lower()
    return any(
        re.search(rf"\b{re.escape(term)}\b", lowered) for term in config.OUT_OF_SCOPE_TOPIC_TERMS
    )


def out_of_scope_outcome() -> AnswerOutcome:
    """The fixed refusal with referral, without any LLM call (FR-21 AC5, AC7)."""
    return AnswerOutcome(
        AnswerWithSources(
            answer_en=OUT_OF_SCOPE_EN, source_chunk_ids=[], used_tools=[], out_of_scope=True
        )
    )


def ensure_referral(answer_text: str) -> str:
    """Make sure an out-of-scope answer points to free counselling.

    The model's own "not found" sentence is replaced by a clear out-of-scope
    message, and so is an answer that analyses the case anyway: an out-of-scope
    answer must not cite provisions (safety test S04: the insolvency answer listed
    §§ 201, 204, 205 BGB). Any other text gets the referral appended unless it
    already names counselling or a consumer advice centre.

    Args:
        answer_text: The English answer of an out-of-scope question.

    Returns:
        The answer text with a referral.

    Related: FR-21 AC5, FR-21 AC7, FR-21 AC9
    """
    if answer_text.strip().startswith("I could not find this in the knowledge base"):
        return OUT_OF_SCOPE_EN
    if "§" in answer_text:  # out of scope means no legal analysis (FR-21 AC9)
        return OUT_OF_SCOPE_EN
    lowered = answer_text.lower()
    if "counsel" in lowered or "verbraucherzentrale" in lowered:
        return answer_text
    return f"{answer_text}\n\n{REFERRAL_EN}"


def _date_mentioned(text: str, day: date) -> bool:
    """True if the text names the date in a common English or German format."""
    variants = (
        day.isoformat(),
        day.strftime("%d.%m.%Y"),
        f"{day.day} {day.strftime('%B')} {day.year}",
        f"{day.strftime('%B')} {day.day}, {day.year}",
    )
    return any(variant in text for variant in variants)


def append_deadline_reminder(answer_text: str, triage: TriageResult | None) -> str:
    """Append the one-line deadline reminder to answers about what to do next.

    Args:
        answer_text: The English answer text.
        triage: Triage answers; the reminder is added only for court documents.

    Returns:
        The answer text, with the deadline reminder appended where it applies.

    Related: FR-21 AC2
    """
    if triage is None or triage.sender != "court":
        return answer_text
    args = deadlines.ObjectionDeadlineArgs(
        document_type=triage.court_document or "unclear", service_date=triage.delivered_on
    )
    outcome = deadlines.calculate_objection_deadline(args)
    if outcome.result is None:
        return answer_text
    end = str(outcome.result["period_end"])
    if _date_mentioned(answer_text, date.fromisoformat(end)):  # the answer already names it
        return answer_text
    weekday = outcome.result["period_end_weekday"]
    procedure = outcome.result["procedure"]
    return (
        f"{answer_text}\n\nReminder: assuming the court letter was served on "
        f"{triage.delivered_on.isoformat()}, the period for {procedure} ends on {weekday}, {end}."
    )
