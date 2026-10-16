"""Tests for :mod:`collection_letter_navigator.guards`.

Every L2 pattern has its own case here, including the false-positive cases that
keep the patterns narrow (FR-22 AC4).

Related: FR-02 AC2, FR-16 AC1, FR-22, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import guards


def test_module_imports() -> None:
    """The guards module imports."""
    assert guards.detect_injection is not None


@pytest.mark.skip(reason="not implemented: FR-02 AC2")
def test_fr02_ac2_empty_question_is_rejected() -> None:
    """A question that is empty after stripping is rejected."""


@pytest.mark.skip(reason="not implemented: FR-02 AC2")
def test_fr02_ac2_question_over_limit_is_rejected_naming_the_limit() -> None:
    """A question over 1,000 characters is rejected and the message names 1,000."""


@pytest.mark.skip(reason="not implemented: FR-16 AC1")
def test_fr16_ac1_letter_over_limit_is_rejected() -> None:
    """A letter over 6,000 characters is rejected."""


@pytest.mark.skip(reason="not implemented: FR-22 AC4")
def test_fr22_ac4_detects_ignore_previous_instructions() -> None:
    """The phrase "ignore all previous instructions" is detected."""


@pytest.mark.skip(reason="not implemented: FR-22 AC4")
def test_fr22_ac4_detects_system_prompt_request() -> None:
    """A request for the system prompt is detected."""


@pytest.mark.skip(reason="not implemented: FR-22 AC4")
def test_fr22_ac4_detects_you_are_now_role_override() -> None:
    """The role override "you are now ..." is detected."""


@pytest.mark.skip(reason="not implemented: FR-22 AC4")
def test_fr22_ac4_detects_role_tags() -> None:
    """Role tags such as "system:" or "assistant:" are detected."""


@pytest.mark.skip(reason="not implemented: FR-22 AC4")
def test_fr22_ac4_detects_delimiter_imitation() -> None:
    """Text imitating the <source> delimiters is detected."""


@pytest.mark.skip(reason="not implemented: FR-22 AC4")
def test_fr22_ac4_ordinary_letter_mentioning_system_is_not_flagged() -> None:
    """A real letter containing the word "system" passes the guard."""


@pytest.mark.skip(reason="not implemented: FR-22 AC1")
def test_fr22_ac1_detected_injection_blocks_the_llm_call() -> None:
    """A detected injection raises before any model is contacted."""


@pytest.mark.skip(reason="not implemented: FR-22 L4")
def test_fr22_l4_untrusted_text_is_wrapped_and_delimiters_neutralised() -> None:
    """Delimiter imitation inside the text cannot close the wrapper."""
