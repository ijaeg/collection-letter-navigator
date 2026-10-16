"""Tests for :mod:`collection_letter_navigator.config`.

Related: FR-04 AC2, FR-07 AC2, FR-20 AC2, §9
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import config


def test_module_imports() -> None:
    """The configuration module imports and exposes its constants."""
    assert config.RETRIEVAL_TOP_K == 6
    assert config.MAX_CHUNK_CHARACTERS == 2_000


@pytest.mark.skip(reason="not implemented: FR-20 AC2")
def test_fr20_ac2_chat_model_overridable_by_environment() -> None:
    """CHAT_MODEL in the environment replaces the default model."""


@pytest.mark.skip(reason="not implemented: FR-05 AC4")
def test_fr05_ac4_query_translation_switch_read_from_environment() -> None:
    """QUERY_TRANSLATION=off disables the query-translation step."""


@pytest.mark.skip(reason="not implemented: FR-23 AC3")
def test_fr23_ac3_api_key_is_not_a_configuration_value() -> None:
    """Only the name of the key variable is a constant, never the key itself."""
