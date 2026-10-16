"""Deterministic tools bound to the answer model.

Each tool answers one calculation question, returns the fixed
:class:`ToolResult` contract and refuses rather than guessing when an input
falls outside its supported period or scope.

Related: FR-10, FR-11, FR-12, FR-13, FR-14, §9
"""

from __future__ import annotations

from langchain_core.tools import BaseTool


def get_tools() -> list[BaseTool]:
    """Build the list of tools bound to the answer model.

    Returns:
        The LangChain tools with their Pydantic argument schemas, in a stable
        order: objection deadline (FR-11), limitation (FR-12), default interest
        (FR-13) and, if enabled, paragraph lookup (FR-14).

    Related: FR-10 AC1
    """
    raise NotImplementedError("FR-10 AC1: bind the deterministic tools to the answer model")
