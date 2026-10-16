"""Tests for :mod:`collection_letter_navigator.llm`.

Related: FR-04 AC6, FR-19, FR-23, NFR-02, NFR-03, NFR-06
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.embeddings import Embeddings

from collection_letter_navigator import config, llm


class RecordingEmbeddings(Embeddings):
    """Fake embedding client that records the texts it receives."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.seen.extend(texts)
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.seen.append(text)
        return [0.0]


def test_module_imports() -> None:
    """The LLM client module imports."""
    assert llm.build_chat_model is not None


def test_fr04_ac6_query_prefix_applied_to_search_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """A search query is embedded with the model's query prefix."""
    monkeypatch.setattr(config, "EMBEDDING_QUERY_PREFIX", "query: ")
    inner = RecordingEmbeddings()
    llm.PrefixedEmbeddings(inner).embed_query("How long do I have?")
    assert inner.seen == ["query: How long do I have?"]


def test_fr04_ac6_passage_prefix_applied_to_indexed_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """An indexed chunk is embedded with the model's passage prefix."""
    monkeypatch.setattr(config, "EMBEDDING_PASSAGE_PREFIX", "passage: ")
    inner = RecordingEmbeddings()
    llm.PrefixedEmbeddings(inner).embed_documents(["§ 692 ZPO Mahnbescheid"])
    assert inner.seen == ["passage: § 692 ZPO Mahnbescheid"]


def test_fr04_ac6_default_model_uses_no_prefix() -> None:
    """The chosen default model (D-1) is embedded without prefixes."""
    assert llm.apply_embedding_prefix("text", "query") == "text"
    assert llm.apply_embedding_prefix("text", "passage") == "text"


def test_d3_embedding_calls_carry_provider_preferences(monkeypatch: pytest.MonkeyPatch) -> None:
    """Embedding requests ask OpenRouter for providers without data retention (D-3)."""
    monkeypatch.setenv(config.OPENROUTER_API_KEY_ENV, "sk-test")
    captured: dict[str, Any] = {}

    class FakeResponse:
        data: list[Any] = []

        def model_dump(self) -> dict[str, Any]:
            return {"data": [{"embedding": [0.1, 0.2]}]}

    def fake_create(**kwargs: Any) -> FakeResponse:
        captured.update(kwargs)
        return FakeResponse()

    embeddings = llm.build_embeddings()
    monkeypatch.setattr(embeddings._inner.client, "create", fake_create)  # type: ignore[attr-defined]
    assert embeddings.embed_query("test") == [0.1, 0.2]
    assert captured["extra_body"] == {"provider": config.PROVIDER_PREFERENCES}
    assert captured["model"] == config.EMBEDDING_MODEL


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


def test_fr23_ac3_missing_api_key_gives_a_friendly_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing key produces a message naming the variable, never a value."""
    monkeypatch.delenv(config.OPENROUTER_API_KEY_ENV, raising=False)
    with pytest.raises(llm.LlmCallError, match=config.OPENROUTER_API_KEY_ENV):
        llm.get_api_key()


@pytest.mark.skip(reason="not implemented: FR-23 AC3")
def test_fr23_ac3_api_key_never_appears_in_error_messages() -> None:
    """A wrong key produces a message that does not contain the key."""


@pytest.mark.skip(reason="not implemented: FR-23 AC2")
def test_fr23_ac2_debug_log_is_silent_unless_enabled() -> None:
    """Without DEBUG_LOG=1 no file is written."""
