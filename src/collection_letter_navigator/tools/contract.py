"""Helpers that keep every tool on the same result contract.

A tool either returns a result with its assumptions and legal basis, or it
returns no result and says why. Exceptions never reach the UI: they are turned
into a ``not_applicable_reason`` and shown on the tool card.

Related: FR-10 AC2, FR-10 AC3, FR-10 AC4, FR-10 AC6, §6.2
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Sequence

from pydantic import ValidationError

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
    return ToolResult(
        tool=tool,
        result=result,
        assumptions=list(assumptions),
        missing_information=list(missing_information),
        legal_basis=list(legal_basis),
        not_applicable_reason=None,
    )


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
    return ToolResult(
        tool=tool,
        result=None,
        missing_information=list(missing_information),
        legal_basis=list(legal_basis),
        not_applicable_reason=reason,
    )


def describe_validation_error(error: ValidationError) -> str:
    """Turn a Pydantic validation error into one plain English sentence.

    Args:
        error: The validation error raised for the tool arguments.

    Returns:
        A sentence naming each invalid field, e.g. "service_date: Input should
        be a valid date", suitable for the tool card and for the model.

    Related: FR-10 AC3
    """
    problems = "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'input'}: {item['msg']}"
        for item in error.errors()
    )
    return f"The input was not valid ({problems}). Please check the values and ask again."


def guard_tool_errors[**P](
    tool: str,
) -> Callable[[Callable[P, ToolResult]], Callable[P, ToolResult]]:
    """Wrap a tool so that no exception ever reaches the UI.

    Invalid arguments and unexpected failures become a result with
    ``not_applicable_reason`` so that the chat continues.

    Args:
        tool: Name of the tool, written into the fallback result.

    Returns:
        A decorator for the tool function.

    Related: FR-10 AC3, FR-10 AC6, NFR-02
    """

    def decorate(func: Callable[P, ToolResult]) -> Callable[P, ToolResult]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> ToolResult:
            try:
                return func(*args, **kwargs)
            except ValidationError as error:  # FR-10 AC3: invalid arguments
                return not_applicable(tool, describe_validation_error(error))
            except Exception as error:  # FR-10 AC6: the chat goes on without the tool
                return not_applicable(
                    tool, f"The calculation failed unexpectedly ({type(error).__name__})."
                )

        return wrapper

    return decorate
