"""Tests for :mod:`collection_letter_navigator.llm`.

Related: FR-04 AC6, FR-19, FR-23, NFR-02, NFR-03, NFR-06
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import openai
import pytest
from conftest import FakeChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage

from collection_letter_navigator import config, llm

REQUEST = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")


def status_error(cls: type[openai.APIStatusError], code: int, message: str = "x") -> Exception:
    """Build an OpenAI status error as the SDK raises it."""
    return cls(message, response=httpx.Response(code, request=REQUEST), body=None)


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


def test_fr20_ac2_chat_model_uses_config_and_provider_preferences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chat model comes from config and carries reasoning effort and D-3 routing."""
    monkeypatch.setenv(config.OPENROUTER_API_KEY_ENV, "sk-test")
    model: Any = llm.build_chat_model()
    assert model.model_name == config.CHAT_MODEL
    assert model.max_tokens == config.MAX_TOKENS
    assert model.temperature is None  # gpt-5 models reject other temperatures
    assert model.extra_body == {
        "reasoning": {"effort": config.REASONING_EFFORT},
        "provider": config.PROVIDER_PREFERENCES,
    }


def test_nfr05_prompts_are_read_from_markdown_files() -> None:
    """Prompt text comes from prompts/*.md, never from Python code (NFR-05)."""
    text = llm.load_prompt("retrieval_plan")
    assert text.startswith("You build search plans")
    with pytest.raises(FileNotFoundError):
        llm.load_prompt("does_not_exist")


def test_nfr02_retries_on_rate_limit_then_succeeds() -> None:
    """An HTTP 429 is retried with backoff and the second attempt is returned."""
    waits: list[float] = []
    model = FakeChatModel([status_error(openai.RateLimitError, 429), AIMessage(content="ok")])
    reply = llm.invoke_with_retry(model, [HumanMessage("hi")], sleep=waits.append)
    assert reply.content == "ok"
    assert waits == [config.RETRY_BACKOFF_SECONDS]


def test_nfr02_gives_up_after_two_retries_with_friendly_message() -> None:
    """After the retry budget the caller gets a friendly error, not a traceback."""
    waits: list[float] = []
    model = FakeChatModel([status_error(openai.InternalServerError, 502) for _ in range(3)])
    with pytest.raises(llm.LlmCallError, match="HTTP 502"):
        llm.invoke_with_retry(model, [HumanMessage("hi")], sleep=waits.append)
    assert waits == [1.0, 2.0]  # exponential backoff, max. 2 retries


def test_nfr02_timeout_produces_friendly_message() -> None:
    """A timeout after 60 s ends the call with a message the UI can show."""
    model = FakeChatModel([openai.APITimeoutError(request=REQUEST) for _ in range(3)])
    with pytest.raises(llm.LlmCallError, match="within 60 seconds"):
        llm.invoke_with_retry(model, [HumanMessage("hi")], sleep=lambda _: None)


def test_nfr02_client_errors_are_not_retried() -> None:
    """A rejected key is reported at once; retrying would not help."""
    model = FakeChatModel([status_error(openai.AuthenticationError, 401)])
    with pytest.raises(llm.LlmCallError, match="API key was rejected"):
        llm.invoke_with_retry(model, [HumanMessage("hi")], sleep=lambda _: None)
    assert len(model.calls) == 1


def test_nfr03_length_finish_reason_with_empty_content_is_reported() -> None:
    """finish_reason='length' with empty content raises LlmLengthError."""
    reply = AIMessage(content="", response_metadata={"finish_reason": "length"})
    with pytest.raises(llm.LlmLengthError, match="token budget"):
        llm.invoke_with_retry(FakeChatModel([reply]), [HumanMessage("hi")])


def test_fr19_ac1_usage_includes_reasoning_tokens() -> None:
    """Reasoning tokens are counted inside the completion tokens."""
    reply = AIMessage(
        content="x",
        usage_metadata={
            "input_tokens": 900,
            "output_tokens": 120,
            "total_tokens": 1020,
            "output_token_details": {"reasoning": 64},
        },
        response_metadata={"token_usage": {"cost": 0.00042}},
    )
    usage = llm.extract_usage(reply, "openai/gpt-5-mini")
    assert (usage.prompt_tokens, usage.completion_tokens, usage.reasoning_tokens) == (900, 120, 64)
    assert usage.cost_usd == pytest.approx(0.00042)
    assert llm.extract_usage(AIMessage(content="x"), "m").cost_usd is None


def test_fr23_ac3_missing_api_key_gives_a_friendly_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing key produces a message naming the variable, never a value."""
    monkeypatch.delenv(config.OPENROUTER_API_KEY_ENV, raising=False)
    with pytest.raises(llm.LlmCallError, match=config.OPENROUTER_API_KEY_ENV):
        llm.get_api_key()


def test_fr23_ac3_api_key_never_appears_in_error_messages() -> None:
    """A wrong key produces a message that does not contain the key."""
    secret = "sk-or-v1-0123456789abcdef"
    error = status_error(openai.AuthenticationError, 401, f"Invalid key {secret}")
    message = llm.friendly_error_message(error)
    assert secret not in message
    assert config.OPENROUTER_API_KEY_ENV in message


def test_fr23_ac2_debug_log_is_silent_unless_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Without DEBUG_LOG=1 no file is written; with it, one JSON line per call."""
    log = tmp_path / "logs" / "llm_calls.jsonl"
    monkeypatch.setattr(config, "LOG_DIR", log.parent)
    monkeypatch.setattr(config, "DEBUG_LOG_PATH", log)
    monkeypatch.setattr(config, "DEBUG_LOG_ENABLED", False)
    llm.log_call("answer", {"tokens": 1})
    assert not log.exists()
    monkeypatch.setattr(config, "DEBUG_LOG_ENABLED", True)
    llm.log_call("answer", {"tokens": 1})
    assert json.loads(log.read_text(encoding="utf-8"))["label"] == "answer"
