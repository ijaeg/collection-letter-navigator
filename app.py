"""Streamlit entry point: UI and the TRIAGE to CHAT state machine only.

This module holds no prompt text and no retrieval logic (NFR-05). It lays out
what :mod:`presenter` prepares and sends questions to :func:`pipeline.ask`.

Related: FR-01, FR-02, FR-03, FR-17, FR-19, FR-21, FR-23, NFR-02, NFR-04, NFR-05, §3
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import streamlit as st

from collection_letter_navigator import config, guards, llm, pipeline, presenter, retrieval
from collection_letter_navigator.demo import DEMO_CASES
from collection_letter_navigator.pipeline import PipelineOutcome
from collection_letter_navigator.schemas import (
    CourtDocumentType,
    SenderType,
    ToolResult,
    TriageResult,
)

#: Session-state keys (§3). Everything the user entered lives only here (FR-23 AC2).
STATE_KEY = "app_state"
TRIAGE_KEY = "triage"
MESSAGES_KEY = "messages"
USAGE_KEY = "usage"
PENDING_KEY = "pending_question"
EXAMPLES_KEY = "example_questions"

#: The two screens of the state machine; the Letter Check is a panel in CHAT (§3).
TRIAGE, CHAT = "TRIAGE", "CHAT"

#: Readable names of the tools on the tool cards (FR-17 AC1).
TOOL_TITLES = {
    "calculate_objection_deadline": "Deadline calculation",
    "check_limitation": "Limitation check",
    "calculate_default_interest": "Default interest calculation",
    "fetch_paragraph": "Provision looked up",
}

#: The explanation page (FR-24), linked from the triage and the footer.
HOW_IT_WORKS_PAGE = "pages/how_it_works.py"


def md(text: str) -> str:
    """Escape ``$`` so Streamlit does not render amounts as LaTeX."""
    return text.replace("$", r"\$")


def init_state() -> None:
    """Create the session-state entries on the first run."""
    st.session_state.setdefault(STATE_KEY, TRIAGE)
    st.session_state.setdefault(MESSAGES_KEY, [])
    st.session_state.setdefault(USAGE_KEY, presenter.UsageTotals())
    st.session_state.setdefault(EXAMPLES_KEY, [])


def start_over() -> None:
    """Clear all session data and return to the triage (FR-02 AC4)."""
    st.session_state.clear()
    init_state()


def start_chat(triage: TriageResult, examples: list[str] | None = None) -> None:
    """Store the triage answers and switch to the chat (FR-01 AC6)."""
    st.session_state[TRIAGE_KEY] = triage
    st.session_state[EXAMPLES_KEY] = examples or []
    st.session_state[STATE_KEY] = CHAT


def ask_later(question: str) -> None:
    """Queue a question from a button; it is answered on the next run."""
    st.session_state[PENDING_KEY] = question


# --- Triage -----------------------------------------------------------------------------


def render_triage() -> None:
    """Render the triage questions (FR-01 AC1, AC2, AC4).

    Earlier answers are pre-selected, so the user can change them later.

    Related: FR-01
    """
    st.subheader("1. About your letter")
    st.page_link(HOW_IT_WORKS_PAGE, label="New here? How this app works", icon="ℹ️")
    previous: TriageResult | None = st.session_state.get(TRIAGE_KEY)
    senders = list(config.SENDER_LABELS)
    sender = st.radio(
        "Who sent the letter?",
        senders,
        index=senders.index(previous.sender) if previous else None,
        format_func=config.SENDER_LABELS.__getitem__,
        key="triage_sender",
    )
    delivered = st.date_input(
        "When was it delivered to you?",
        value=previous.delivered_on if previous else date.today(),
        max_value=date.today(),
        format="DD.MM.YYYY",
        help=config.DELIVERY_DATE_HELP_EN,
        key="triage_delivered",
    )
    document = None
    if sender == "court":
        documents = list(config.COURT_DOCUMENT_LABELS)
        preset = previous.court_document if previous and previous.court_document else None
        document = st.radio(
            "Which document is it?",
            documents,
            index=documents.index(preset) if preset else None,
            format_func=config.COURT_DOCUMENT_LABELS.__getitem__,
            key="triage_document",
        )
    if sender == "not_sure":
        st.info(config.NOT_SURE_GUIDE_EN)
        st.warning(config.NOT_SURE_CAUTION_EN)

    ready = sender is not None and (sender != "court" or document is not None)
    if st.button("Continue to the questions", type="primary", disabled=not ready, key="go"):
        assert isinstance(delivered, date)
        start_chat(
            TriageResult(
                sender=cast(SenderType, sender),
                court_document=cast(CourtDocumentType | None, document),
                delivered_on=delivered,
            )
        )
        st.rerun()


# --- Chat -------------------------------------------------------------------------------


def render_deadline_card(triage: TriageResult) -> None:
    """The pinned deadline card for court letters (FR-01 AC3, FR-21 AC2)."""
    card = presenter.deadline_card(triage)
    if card is None:
        return
    with st.container(border=True):
        st.markdown(f"**⏰ {card.headline}**")
        kind = "strict deadline (*Notfrist*)" if card.strict else "deadline"
        st.caption(
            f"This is a {kind}, counted from the delivery date you gave "
            f"({triage.delivered_on.strftime('%d.%m.%Y')}). {card.note}"
        )
        with st.expander("Assumptions behind this date"):
            for line in [*card.assumptions, *card.missing_information]:
                st.markdown(f"- {md(line)}")
        st.caption(help_links())


def help_links() -> str:
    """The get-help links as one Markdown line (FR-21 AC5)."""
    return "Free help: " + " · ".join(f"[{label}]({url})" for label, url in config.GET_HELP_LINKS)


def render_triage_summary(triage: TriageResult) -> None:
    """One line with the triage answers and a button to change them (FR-01 AC4)."""
    sender = config.SENDER_LABELS[triage.sender].split(" (")[0]
    document = (
        f" · {config.COURT_DOCUMENT_LABELS[triage.court_document].split(' –')[0]}"
        if triage.court_document
        else ""
    )
    left, right = st.columns([4, 1])
    left.caption(f"Sender: {sender}{document} · delivered {triage.delivered_on:%d.%m.%Y}")
    if right.button("Change", key="change_triage"):
        st.session_state[STATE_KEY] = TRIAGE
        st.rerun()


def render_legal_basis(chunk_ids: list[str]) -> None:
    """The cited provisions with their German text from the knowledge base (FR-08 AC2)."""
    docs = [doc for doc in map(retrieval.get_chunk_by_id, chunk_ids) if doc is not None]
    if not docs:
        return
    with st.expander(f"Legal basis ({len(docs)})"):
        for doc in docs:
            st.markdown(f"**[{presenter.provision_label(doc)}]({doc.metadata['source_url']})**")
            st.code(doc.page_content, language=None, wrap_lines=True)


def render_tool_card(result: ToolResult) -> None:
    """One tool card: inputs and result, assumptions, missing facts, legal basis (FR-17 AC1)."""
    with st.container(border=True):
        st.markdown(f"**🧮 {TOOL_TITLES.get(result.tool, result.tool)}**")
        if result.result:
            st.markdown(
                "\n".join(
                    f"- {key.replace('_', ' ')}: **{md(display_value(value))}**"
                    for key, value in result.result.items()
                    if key != "text"  # long statute text: shown under "Legal basis" instead
                )
            )
        if result.not_applicable_reason:
            st.warning(result.not_applicable_reason)
        for title, lines in (
            ("Assumptions", result.assumptions),
            ("Missing information", result.missing_information),
        ):
            if lines:
                st.caption(f"**{title}**\n" + "\n".join(f"- {md(line)}" for line in lines))
        pairs = presenter.legal_basis_of(result)
        if pairs:
            with st.expander("Legal basis of this calculation"):
                for reference, doc in pairs:
                    if doc is None:
                        st.markdown(f"- {reference} (not in the knowledge base)")
                    else:
                        st.markdown(f"**[{reference}]({doc.metadata['source_url']})**")
                        st.code(doc.page_content, language=None, wrap_lines=True)


def display_value(value: object) -> str:
    """A tool value as shown on the card: yes/no instead of True/False."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def render_answer(out: PipelineOutcome) -> None:
    """The checked answer with legal basis, tool cards and timing (FR-08, FR-17)."""
    answer = out.answer.answer
    st.markdown(md(answer.answer_en))
    render_legal_basis(answer.source_chunk_ids)
    for result in out.answer.tool_results:
        render_tool_card(result)
    if answer.out_of_scope or not answer.source_chunk_ids:
        st.caption(help_links())
    render_rag_panel(out)
    st.caption(f"Answered in {sum(out.seconds.values()):.1f} s")


def render_rag_panel(out: PipelineOutcome) -> None:
    """How the answer was found: queries, filter, mode and the top chunks (FR-18 AC1)."""
    panel = presenter.rag_panel(out.retrieval)
    with st.expander("How this answer was found"):
        st.markdown("**German search queries**\n" + "\n".join(f"- {md(q)}" for q in panel.queries))
        fallback = " (no hits with the filter, searched without it)" if panel.fallback else ""
        steps = ", ".join(f"{name} {seconds:.1f} s" for name, seconds in out.seconds.items())
        st.caption(
            f"Law filter: {panel.filter_label}{fallback} · {panel.mode_label} · time: {steps}"
        )
        st.caption(f"Why: {md(panel.rationale)}")
        st.table(panel.rows)


def render_message(message: dict[str, Any]) -> None:
    """Replay one chat message from the history (FR-02 AC1)."""
    with st.chat_message(message["role"]):
        if message.get("outcome") is not None:
            render_answer(message["outcome"])
        elif message.get("kind") == "warning":
            st.warning(message["content"])
        elif message.get("kind") == "error":
            st.error(message["content"])
        else:
            st.markdown(md(message["content"]))


def answer_pending(triage: TriageResult) -> None:
    """Answer the queued question with progress labels (FR-02, FR-17 AC2, NFR-02).

    Every error ends the progress indicator with a message; the chat stays usable.
    """
    question = st.session_state.pop(PENDING_KEY, None)
    if not question:
        return
    messages: list[dict[str, Any]] = st.session_state[MESSAGES_KEY]
    user_message = {"role": "user", "content": question}
    messages.append(user_message)
    render_message(user_message)
    turns = [
        (m["question"], m["outcome"].answer.answer.answer_en)
        for m in messages
        if m.get("outcome") is not None
    ]
    reply: dict[str, Any] = {"role": "assistant"}
    with st.chat_message("assistant"):
        status = st.status("Working on your question…", expanded=False)
        try:
            out = pipeline.ask(
                question,
                triage,
                presenter.history_messages(turns),
                progress=lambda label: status.update(label=label),
            )
        except (guards.EmptyInputError, guards.InputTooLongError) as error:
            status.update(label="Not sent", state="error")
            reply.update(kind="warning", content=str(error))
        except guards.InjectionDetectedError as error:
            status.update(label="Blocked", state="error")
            reply.update(kind="warning", content=str(error))
        except llm.LlmCallError as error:
            status.update(label="Something went wrong", state="error")
            reply.update(kind="error", content=llm.friendly_error_message(error))
        else:
            status.update(label="Done", state="complete")
            st.session_state[USAGE_KEY].add(out.usages)
            reply.update(outcome=out, question=question)
    messages.append(reply)
    st.rerun()  # redraw the history and the sidebar totals


def render_chat() -> None:
    """Render the chat screen (FR-02, FR-03 AC2, AC4, FR-17, FR-21 AC2).

    Related: FR-02, FR-03, FR-08, FR-17, FR-21 AC2
    """
    triage: TriageResult = st.session_state[TRIAGE_KEY]
    render_deadline_card(triage)  # pinned at the top, cannot be dismissed
    render_triage_summary(triage)
    if triage.sender == "not_sure":
        st.warning(config.NOT_SURE_CAUTION_EN)

    st.subheader("2. Your questions")
    for message in st.session_state[MESSAGES_KEY]:
        render_message(message)
    answer_pending(triage)

    examples: list[str] = st.session_state[EXAMPLES_KEY]
    if examples:
        st.caption("Example questions for this demo case:")
        for i, question in enumerate(examples):
            st.button(question, key=f"example_{i}", on_click=ask_later, args=(question,))
    with st.expander("Common situations"):
        st.caption("Pick one to ask it in your own words; it is not a recommendation.")
        columns = st.columns(2)
        for i, situation in enumerate(config.COMMON_SITUATIONS):
            columns[i % 2].button(
                situation, key=f"situation_{i}", on_click=ask_later, args=(situation,)
            )

    typed = st.chat_input(
        "Ask a question about your letter", max_chars=config.MAX_QUESTION_CHARACTERS
    )
    if typed:
        ask_later(typed)
        st.rerun()


# --- Sidebar and footer ----------------------------------------------------------------


def render_sidebar() -> None:
    """Demo cases, session usage and knowledge-base dates (FR-03 AC1, FR-19, FR-21 AC6)."""
    with st.sidebar:
        st.header("Collection Letter Navigator")
        st.subheader("Demo cases")
        st.caption("Try the app without a letter of your own. All data is fictional.")
        for case in DEMO_CASES:
            if st.button(case.label, key=f"demo_{case.key}", use_container_width=True):
                start_over()
                start_chat(case.triage(), list(case.questions))
                st.rerun()

        st.subheader("Usage this session")
        usage: presenter.UsageTotals = st.session_state[USAGE_KEY]
        st.metric("Cost (USD)", usage.cost_label)
        st.caption(
            f"{usage.calls} LLM calls · {usage.prompt_tokens:,} prompt tokens · "
            f"{usage.completion_tokens:,} completion tokens "
            f"(incl. {usage.reasoning_tokens:,} reasoning)"
        )

        statutes, base_rate = presenter.knowledge_base_dates()
        st.subheader("Knowledge base")
        st.caption(
            f"German law as of {statutes} (BGB, ZPO, RDG) · base rate table up to "
            f"{base_rate} · model {config.CHAT_MODEL}"
        )
        if st.button("Start over", key="start_over", use_container_width=True):
            start_over()
            st.rerun()


def render_footer() -> None:
    """The permanent footer with the disclaimer and the get-help links (FR-21 AC1, AC5)."""
    st.divider()
    st.caption(config.DISCLAIMER_EN)
    st.caption(help_links())
    st.page_link(HOW_IT_WORKS_PAGE, label="How this app works", icon="ℹ️")


def main() -> None:
    """Run the state machine: TRIAGE, then CHAT (§3).

    Related: FR-01, FR-02 AC4, FR-21 AC1, FR-23 AC1, §3
    """
    st.set_page_config(page_title="Collection Letter Navigator", page_icon="📄")
    llm.load_environment()
    init_state()
    st.title("Collection Letter Navigator")
    st.caption(config.DISCLAIMER_EN)
    st.caption(config.PRIVACY_NOTICE_EN)  # above every input (FR-23 AC1)

    render_sidebar()
    if st.session_state[STATE_KEY] == TRIAGE or TRIAGE_KEY not in st.session_state:
        render_triage()
    else:
        render_chat()
    render_footer()


main()
