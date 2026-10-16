"""Helpers that keep every tool on the same result contract.

A tool either returns a result with its assumptions and legal basis, or it
returns no result and says why. Exceptions never reach the UI: they are turned
into a ``not_applicable_reason`` and shown on the tool card.

Related: FR-10 AC2, FR-10 AC3, FR-10 AC4, FR-10 AC6, §6.2
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from collection_letter_navigator.schemas import ToolResult


def tool_result(
    tool: str,
    result: dict[str, object],
    *,
    assumptions: Sequence[str] = (),
    missing_information: Sequence[str] = (),
    legal_basis: Sequence[str] = (),
) -> ToolResult:
    """Build a successful result.

    Args:
        tool: Name of the tool.
        result: The tool-specific values.
        assumptions: Assumptions the calculation relies on.
        missing_information: Facts that would make the statement firmer.
        legal_basis: Provisions the tool applies.

    Returns:
        A :class:`ToolResult` with ``not_applicable_reason`` unset.

    Related: FR-10 AC2
    """
    raise NotImplementedError("FR-10 AC2: build a ToolResult with result and assumptions")


def not_applicable(
    tool: str,
    reason: str,
    *,
    missing_information: Sequence[str] = (),
    legal_basis: Sequence[str] = (),
) -> ToolResult:
    """Build a result that says why no value could be produced.

    Args:
        tool: Name of the tool.
        reason: Why the tool cannot answer, in plain English.
        missing_information: What the user would have to supply.
        legal_basis: Provisions that make the case out of scope.

    Returns:
        A :class:`ToolResult` with ``result`` set to None.

    Related: FR-10 AC3, FR-10 AC4
    """
    raise NotImplementedError("FR-10 AC4: return no result instead of a wrong result")


def guard_tool_errors[**P](func: Callable[P, ToolResult]) -> Callable[P, ToolResult]:
    """Wrap a tool so that no exception ever reaches the UI.

    Invalid arguments and unexpected failures become a result with
    ``not_applicable_reason`` so that the chat continues.

    Args:
        func: The tool function to wrap.

    Returns:
        The wrapped tool function.

    Related: FR-10 AC3, FR-10 AC6, NFR-02
    """
    raise NotImplementedError("FR-10 AC3: convert tool exceptions into not_applicable_reason")
