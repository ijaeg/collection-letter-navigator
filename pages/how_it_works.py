"""FR-24: the "How this app works" page, in plain English.

Explains what the app does and does not do, where the legal text comes from and
how answers are checked. Scaffold state: headings and TODO notes only.

Related: FR-24, FR-21 AC1, §12
"""

from __future__ import annotations

import streamlit as st

from collection_letter_navigator.config import DISCLAIMER_EN

st.set_page_config(page_title="How this app works", page_icon="📄")
st.title("How this app works")
st.caption(DISCLAIMER_EN)
st.info("Under construction — this page is a placeholder.")
st.caption(
    "TODO (FR-24 AC1): what the app does and does not do · where the legal text comes from "
    "(FR-04) · how answers are checked: quote check (FR-09) and tool contract (FR-10 AC2) · "
    "the knowledge-base snapshot date (FR-21 AC6) · known limitations (§12)"
)
