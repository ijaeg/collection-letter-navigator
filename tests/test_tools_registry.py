"""Tests for :mod:`collection_letter_navigator.tools`.

Related: FR-10 AC1, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import tools


def test_module_imports() -> None:
    """The tool registry imports."""
    assert tools.get_tools is not None


@pytest.mark.skip(reason="not implemented: FR-10 AC1")
def test_fr10_ac1_registry_exposes_the_three_must_tools() -> None:
    """Deadline, limitation and interest tools are always bound."""


@pytest.mark.skip(reason="not implemented: FR-10 AC1")
def test_fr10_ac1_every_tool_has_a_pydantic_argument_schema() -> None:
    """Each bound tool carries its argument schema for the model."""
