"""Streamlit entry point: UI and the TRIAGE to CHAT state machine only.

This module holds no prompt text and no retrieval logic (NFR-05); it renders the
screens and delegates to the package. Scaffold state: both screens are
placeholders.

Related: FR-01, FR-02, FR-03, FR-17, FR-19, FR-21, FR-23, FR-24, NFR-05, §3
"""

from __future__ import annotations

import streamlit as st

from collection_letter_navigator.config import DISCLAIMER_EN, GET_HELP_LINKS, PRIVACY_NOTICE_EN

#: Session-state key holding the current screen, ``"TRIAGE"`` or ``"CHAT"`` (§3).
STATE_KEY = "app_state"

#: The two screens of the state machine; the Letter Check is a panel in CHAT (§3).
TRIAGE, CHAT = "TRIAGE", "CHAT"


def render_triage() -> None:
    """Render the triage screen.

    Returns:
        None.

    Related: FR-01, FR-03 AC1, FR-24 AC2
    """
    st.subheader("1. About your letter")
    st.info("Under construction — the triage questions are not implemented yet.")
    st.caption(
        "TODO: sender question (FR-01 AC1) · court document type (FR-01 AC2) · "
        "delivery date (FR-01 AC1) · guidance for 'not sure' (FR-01 AC4) · "
        "store a TriageResult (FR-01 AC6)"
    )


def render_chat() -> None:
    """Render the chat screen.

    Returns:
        None.

    Related: FR-02, FR-03, FR-08, FR-16, FR-17, FR-18, FR-21 AC2
    """
    st.subheader("2. Your questions")
    st.info("Under construction — the chat is not implemented yet.")
    st.caption(
        "TODO: pinned deadline card for court letters (FR-01 AC3, FR-21 AC2) · "
        "chat history (FR-02 AC1) · 'Common situations' buttons (FR-03 AC4) · "
        "answer with legal basis and tool cards (FR-08 AC2, FR-17 AC1) · "
        "RAG panel (FR-18) · Letter Check panel (FR-16)"
    )


def render_sidebar() -> None:
    """Render the sidebar: demo cases, usage and developer settings.

    Returns:
        None.

    Related: FR-03 AC1, FR-19 AC1, FR-20 AC1, FR-21 AC6
    """
    with st.sidebar:
        st.header("Collection Letter Navigator")
        st.info("Under construction.")
        st.caption(
            "TODO: demo cases (FR-03 AC1) · session token usage and cost (FR-19 AC1) · "
            "developer settings (FR-20 AC1) · knowledge-base and base-rate dates (FR-21 AC6)"
        )


def render_footer() -> None:
    """Render the permanent footer with the disclaimer and the get-help links.

    Returns:
        None.

    Related: FR-21 AC1, FR-21 AC5, FR-24 AC2
    """
    st.divider()
    st.caption(DISCLAIMER_EN)
    st.caption(" · ".join(f"[{label}]({url})" for label, url in GET_HELP_LINKS))


def main() -> None:
    """Run the state machine: TRIAGE, then CHAT.

    Returns:
        None.

    Related: FR-01, FR-02 AC4, FR-21 AC1, FR-23 AC1, §3
    """
    st.set_page_config(page_title="Collection Letter Navigator", page_icon="📄")
    st.title("Collection Letter Navigator")
    st.caption(DISCLAIMER_EN)
    st.caption(PRIVACY_NOTICE_EN)

    render_sidebar()

    state = st.session_state.setdefault(STATE_KEY, TRIAGE)
    if state == TRIAGE:
        render_triage()
    else:
        render_chat()

    render_footer()


main()
