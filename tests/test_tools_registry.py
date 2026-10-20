"""Tests for :mod:`collection_letter_navigator.tools`.

Related: FR-10 AC1, NFR-06
"""

from __future__ import annotations

from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel

from collection_letter_navigator import tools


def test_module_imports() -> None:
    """The tool registry imports."""
    assert tools.get_tools is not None


def test_fr10_ac1_registry_exposes_the_three_must_tools() -> None:
    """Deadline, limitation and interest tools are always bound, in a stable order."""
    assert [tool.name for tool in tools.get_tools()] == [
        "calculate_objection_deadline",
        "check_limitation",
        "calculate_default_interest",
    ]


def test_fr10_ac1_every_tool_has_a_pydantic_argument_schema() -> None:
    """Each bound tool carries its argument schema and a description for the model."""
    for tool in tools.get_tools():
        assert isinstance(tool.args_schema, type) and issubclass(tool.args_schema, BaseModel)
        assert len(tool.description) > 80
        definition = convert_to_openai_tool(tool, strict=True)["function"]
        assert definition["parameters"]["additionalProperties"] is False


def test_fr10_ac1_bound_tool_returns_the_contract_as_json() -> None:
    """Calling the LangChain tool gives the ToolResult as a JSON-ready dict."""
    tool = tools.get_tools()[0]
    output = tool.invoke({"document_type": "mahnbescheid", "service_date": "2026-10-14"})
    assert output["tool"] == "calculate_objection_deadline"
    assert output["result"]["period_end"] == "2026-10-28"
