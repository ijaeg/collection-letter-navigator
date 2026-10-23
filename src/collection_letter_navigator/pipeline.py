"""One question from start to finish: guards, retrieval plan, search, answer.

This is the single entry point the UI calls for a chat question (§5.2). It holds
no UI code and no prompt text; it only wires the steps together, measures their
time and collects what the RAG panel and the tool cards show.

Related: FR-02 AC3, FR-05, FR-06, FR-07, FR-08, FR-10, FR-17, FR-18, FR-19, NFR-04, §5.2
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from collection_letter_navigator import answer, config, guards, llm, retrieval
from collection_letter_navigator.answer import AnswerOutcome
from collection_letter_navigator.retrieval import RetrievalMode, RetrievalOutcome
from collection_letter_navigator.schemas import TriageResult

#: Callback for the progress labels of FR-17 AC2, e.g. ``st.status(...).update``.
ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class PipelineOutcome:
    """Everything one question produced.

    Attributes:
        question_en: The validated question.
        retrieval: The retrieval run, including plan, filter and fallback (FR-18).
        answer: The checked answer with tool results and usage (FR-17, FR-19).
        seconds: Wall-clock seconds per step: ``plan``, ``retrieval``, ``answer``.
        plan_usages: Token usage of the retrieval-plan call (empty without translation).

    Related: FR-17, FR-18, FR-19, NFR-04
    """

    question_en: str
    retrieval: RetrievalOutcome
    answer: AnswerOutcome
    seconds: dict[str, float] = field(default_factory=dict)
    plan_usages: list[llm.LlmUsage] = field(default_factory=list)

    @property
    def usages(self) -> list[llm.LlmUsage]:
        """Usage of every LLM call of this question, plan first (FR-19 AC1)."""
        return [*self.plan_usages, *self.answer.usages]


def ask(
    question_en: str,
    triage: TriageResult | None = None,
    history: Sequence[BaseMessage] | None = None,
    *,
    mode: RetrievalMode | None = None,
    query_translation: bool | None = None,
    k: int | None = None,
    model: BaseChatModel | None = None,
    progress: ProgressCallback | None = None,
    letter_facts: str | None = None,
) -> PipelineOutcome:
    """Answer one chat question.

    The guards run before any LLM call (FR-02 AC3, FR-22); query translation is
    a fixed step unless switched off (FR-05 AC2, AC4).

    Args:
        question_en: The raw question from the chat input.
        triage: Triage answers, passed to plan and answer (FR-01 AC6).
        history: Earlier chat turns.
        mode: Retrieval mode; defaults to :data:`config.RETRIEVAL_MODE`.
        query_translation: Whether to translate; defaults to the config switch.
        k: Number of chunks for the answer; defaults to :data:`config.RETRIEVAL_TOP_K`.
        model: Chat model for plan and answer; defaults to the configured model.
        progress: Receives a short label before each step (FR-17 AC2).
        letter_facts: Facts from a Letter Check in this chat, a source of the answer
            (FR-16 AC6).

    Returns:
        The outcome with retrieval, answer and timings.

    Raises:
        EmptyInputError, InputTooLongError: If the question fails L1 (FR-02 AC2).
        InjectionDetectedError: If L2 finds an injection (FR-22 AC1).
        LlmCallError: If an LLM call fails after retries (NFR-02).

    Related: FR-02 AC3, FR-05 AC2, FR-05 AC4, FR-17 AC2, NFR-04, §5.2
    """
    report = progress or (lambda _label: None)
    question = guards.validate_question(question_en)  # L1: before any LLM call
    guards.assert_no_injection(question)  # L2
    if answer.is_out_of_scope_topic(question):  # e.g. SCHUFA: fixed refusal, no LLM call
        return PipelineOutcome(
            question,
            RetrievalOutcome(retrieval.passthrough_plan(question)),
            answer.out_of_scope_outcome(),
        )
    seconds: dict[str, float] = {}
    plan_usages: list[llm.LlmUsage] = []

    translate = config.QUERY_TRANSLATION_ENABLED if query_translation is None else query_translation
    started = time.perf_counter()
    if translate:
        report("Translating your question into German legal terms…")
        plan = retrieval.create_retrieval_plan(question, triage, model=model, usages=plan_usages)
    else:
        plan = retrieval.passthrough_plan(question)
    seconds["plan"] = time.perf_counter() - started

    report("Searching German law…")
    started = time.perf_counter()
    found = retrieval.retrieve(plan, mode=mode, k=k)
    seconds["retrieval"] = time.perf_counter() - started

    report("Writing the answer…")
    started = time.perf_counter()
    outcome = answer.answer_question(
        question, found, triage=triage, history=history, model=model, letter_facts=letter_facts
    )
    seconds["answer"] = time.perf_counter() - started
    return PipelineOutcome(question, found, outcome, seconds, plan_usages)
