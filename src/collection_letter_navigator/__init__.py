"""Collection Letter Navigator: English guidance on German debt collection letters.

A Streamlit chatbot that triages a German debt collection letter or court payment
order, answers English questions with advanced RAG over German federal law
(BGB, ZPO, RDG) and calls deterministic tools for deadlines, limitation and
default interest.

Related: FR-01, FR-08, FR-10, §1, §9
"""

from __future__ import annotations

#: Package version, kept in sync with the ``version`` field in ``pyproject.toml``.
__version__ = "0.1.0"
