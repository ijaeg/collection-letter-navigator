"""Deterministic tools bound to the answer model.

Each tool answers one calculation question, returns the fixed
:class:`ToolResult` contract and refuses rather than guessing when an input
falls outside its supported period or scope.

Related: FR-10, FR-11, FR-12, FR-13, FR-14, §9
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel

from collection_letter_navigator.schemas import ToolResult
from collection_letter_navigator.tools import deadlines, interest, limitation
from collection_letter_navigator.tools.contract import guard_tool_errors, not_applicable


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Everything needed to bind and run one tool.

    Attributes:
        name: Name the model uses to call the tool.
        description: When to use the tool, shown to the model.
        args_schema: Pydantic model of the arguments.
        func: The tool function; takes a validated ``args_schema`` instance.

    Related: FR-10 AC1
    """

    name: str
    description: str
    args_schema: type[BaseModel]
    func: Callable[[Any], ToolResult]


#: The three Must tools, in a stable order (FR-10 AC1).
TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        deadlines.TOOL_NAME,
        deadlines.DESCRIPTION,
        deadlines.ObjectionDeadlineArgs,
        deadlines.calculate_objection_deadline,
    ),
    ToolSpec(
        limitation.TOOL_NAME,
        limitation.DESCRIPTION,
        limitation.LimitationArgs,
        limitation.check_limitation,
    ),
    ToolSpec(
        interest.TOOL_NAME,
        interest.DESCRIPTION,
        interest.DefaultInterestArgs,
        interest.calculate_default_interest,
    ),
)


def invoke_tool(name: str, raw_args: Mapping[str, Any]) -> ToolResult:
    """Validate the model's arguments and run one tool, never raising.

    Args:
        name: Tool name from the model's tool call.
        raw_args: Arguments exactly as the model sent them.

    Returns:
        The tool's result; invalid arguments, an unknown tool name and
        unexpected failures all become ``not_applicable_reason``.

    Related: FR-10 AC2, FR-10 AC3, FR-10 AC6
    """
    spec = next((s for s in TOOL_SPECS if s.name == name), None)
    if spec is None:
        return not_applicable(name, f"There is no tool called {name!r}.")

    @guard_tool_errors(spec.name)
    def run() -> ToolResult:
        # AI: the model's arguments are untrusted - validated here, not by the model
        return spec.func(spec.args_schema.model_validate(dict(raw_args)))

    return run()


def get_tools() -> list[BaseTool]:
    """Build the list of tools bound to the answer model.

    Returns:
        The LangChain tools with their Pydantic argument schemas, in a stable
        order: objection deadline (FR-11), limitation (FR-12), default interest
        (FR-13). The paragraph lookup (FR-14) follows when it is implemented.

    Related: FR-10 AC1
    """
    tools: list[BaseTool] = []
    for spec in TOOL_SPECS:

        def call(_name: str = spec.name, **kwargs: Any) -> dict[str, Any]:
            return invoke_tool(_name, kwargs).model_dump(mode="json")

        # AI: the schema becomes the JSON definition the model sees in bind_tools
        tools.append(
            StructuredTool.from_function(
                func=call,
                name=spec.name,
                description=spec.description,
                args_schema=spec.args_schema,
            )
        )
    return tools
