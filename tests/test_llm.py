"""Tests for :mod:`collection_letter_navigator.llm`.

Related: FR-04 AC6, FR-19, FR-23, NFR-02, NFR-03, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator import llm


def test_module_imports() -> None:
    """The LLM client module imports."""
    assert llm.build_chat_model is not None


@pytest.mark.skip(reason="not implemented: FR-04 AC6")
def test_fr04_ac6_query_prefix_applied_to_search_text() -> None:
    """A search query is embedded with the model's query prefix."""


@pytest.mark.skip(reason="not implemented: FR-04 AC6")
def test_fr04_ac6_passage_prefix_applied_to_indexed_text() -> None:
    """An indexed chunk is embedded with the model's passage prefix."""


@pytest.mark.skip(reason="not implemented: NFR-02")
def test_nfr02_retries_on_rate_limit_then_succeeds() -> None:
    """An HTTP 429 is retried with backoff and the second attempt is returned."""


@pytest.mark.skip(reason="not implemented: NFR-02")
def test_nfr02_gives_up_after_two_retries_with_friendly_message() -> None:
    """After the retry budget the caller gets a friendly error, not a traceback."""


@pytest.mark.skip(reason="not implemented: NFR-02")
def test_nfr02_timeout_produces_friendly_message() -> None:
    """A timeout after 60 s ends the call with a message the UI can show."""


@pytest.mark.skip(reason="not implemented: NFR-03")
def test_nfr03_length_finish_reason_with_empty_content_is_reported() -> None:
    """finish_reason='length' with empty content raises LlmLengthError."""


@pytest.mark.skip(reason="not implemented: FR-19 AC1")
def test_fr19_ac1_usage_includes_reasoning_tokens() -> None:
    """Reasoning tokens are counted inside the completion tokens."""


@pytest.mark.skip(reason="not implemented: FR-23 AC3")
def test_fr23_ac3_api_key_never_appears_in_error_messages() -> None:
    """A missing or wrong key produces a message that does not contain the key."""


@pytest.mark.skip(reason="not implemented: FR-23 AC2")
def test_fr23_ac2_debug_log_is_silent_unless_enabled() -> None:
    """Without DEBUG_LOG=1 no file is written."""
