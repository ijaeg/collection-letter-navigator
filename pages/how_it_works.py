"""FR-24: the "How this app works" page, in plain English.

Explains what the app does and does not do, where the legal text comes from,
how answers are checked, the knowledge-base date and the known limitations.
The page holds text only; dates come from :mod:`presenter`.

Related: FR-24, FR-21 AC1, FR-21 AC6, §12
"""

from __future__ import annotations

import streamlit as st

from collection_letter_navigator import config, presenter

st.set_page_config(page_title="How this app works", page_icon="📄")
st.title("How this app works")
st.caption(config.DISCLAIMER_EN)

statutes, base_rate = presenter.knowledge_base_dates()

st.header("What the app does")
st.markdown(
    """
- It explains German rules on **debt collection letters** and **court payment orders**
  (*Mahnbescheid*, *Vollstreckungsbescheid*) in English.
- It calculates three things with fixed rules instead of letting an AI guess:
  the **objection deadline** of a court letter, whether a debt may be **too old**
  (limitation), and the **maximum default interest**.
- Every answer shows the **German legal text** it is based on, so you or an adviser
  can check it.
"""
)

st.header("What the app does not do")
st.markdown(
    """
- It gives **legal information, not legal advice**. It never tells you whether to
  pay, object or ignore a letter.
- It does not cover wage garnishment and enforcement (*Pfändung*), personal
  insolvency, claims between businesses or credit-agency (SCHUFA) disputes.
- It does not store your questions. Close the tab or press **Start over** and they
  are gone.
"""
)

st.header("Where the legal text comes from")
st.markdown(
    f"""
- Sections of the **BGB** (Civil Code), **ZPO** (Code of Civil Procedure) and **RDG**
  (Legal Services Act) from the official site
  [gesetze-im-internet.de]({config.GESETZE_IM_INTERNET_BASE_URL}), as of **{statutes}**.
- The base interest rate (*Basiszinssatz*) from the **Deutsche Bundesbank**; the table
  in the app runs up to the rate valid from **{base_rate}**.
- Law changes after these dates are not included.
"""
)

st.header("How an answer is made and checked")
st.markdown(
    """
1. **Safety check:** questions that try to give the AI instructions are blocked before
   anything is sent.
2. **German search terms:** an AI model turns your English question into German legal
   search terms and picks the relevant law.
3. **Search:** the app looks for the closest sections of the law (open *How this answer
   was found* below an answer to see the search terms and results).
4. **Answer:** the AI model answers **only from these sections** and calls a calculation
   tool where a date or an amount is needed. Each tool lists its **assumptions** and the
   information it is missing.
5. **Checks in code:** every cited section must really have been found, and every German
   quote in the answer must appear word for word in the law; otherwise it is removed.
   If nothing relevant is found, the app says so instead of answering from general
   knowledge.
"""
)

st.header("Known limitations")
st.markdown(
    """
- The search finds a relevant section for most, but not all, questions: on a test set
  of 23 questions, 96 % of the runs found an expected section among the top five.
- Deadlines use the delivery date you enter as the date of service and only nationwide
  public holidays; a holiday in the court's federal state can move the end by a day.
- The AI model can still word things imperfectly, and its answers vary a little between
  runs. Treat every answer as a starting point and check important deadlines with a
  counselling service.
"""
)

st.header("Free help")
st.markdown("\n".join(f"- [{label}]({url})" for label, url in config.GET_HELP_LINKS))
