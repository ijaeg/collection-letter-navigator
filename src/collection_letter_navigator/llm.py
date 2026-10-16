"""LangChain chat and embedding clients for OpenRouter, with retries and usage.

Everything that talks to OpenRouter goes through this module: the chat model
(FR-20 AC2), the embedding model (D-1), the retry/backoff policy (NFR-02) and
the token/usage bookkeeping the sidebar shows (FR-19). The model-specific
embedding input convention (the e5 ``query: `` / ``passage: `` prefixes) is
applied here and nowhere else (FR-04 AC6).

Related: FR-04 AC6, FR-19, FR-20 AC2, FR-23 AC2, FR-23 AC3, NFR-01, NFR-02,
NFR-03, §5, §12 D-1, §12 D-3
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from collection_letter_navigator import config

#: Kinds of text the embedding model distinguishes by prefix (FR-04 AC6).
EmbeddingInputKind = Literal["query", "passage"]


@dataclass(frozen=True, slots=True)
class LlmUsage:
    """Token counts and cost of a single LLM call.

    Attributes:
        model: Model identifier the call was sent to.
        prompt_tokens: Tokens in the prompt.
        completion_tokens: Tokens in the completion, including reasoning tokens.
        reasoning_tokens: Reasoning tokens, counted inside ``completion_tokens``.
        cost_usd: Cost in USD, or None when prices are unavailable (FR-19 AC2).

    Related: FR-19, NFR-03
    """

    model: str
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    cost_usd: float | None


class LlmCallError(RuntimeError):
    """An OpenRouter call failed in a way the UI must report as a friendly message.

    Related: NFR-02
    """


class LlmLengthError(LlmCallError):
    """The call stopped with ``finish_reason = "length"`` and empty content.

    Related: NFR-03
    """


def load_environment() -> None:
    """Load the gitignored ``.env`` file, if present, into the process environment.

    Returns:
        None.

    Related: FR-23 AC3, NFR-01
    """
    load_dotenv(override=False)  # an exported variable always wins over .env


def get_api_key() -> str:
    """Read the OpenRouter API key from the environment.

    Returns:
        The API key.

    Raises:
        LlmCallError: If the key is unset; the message never contains the key.

    Related: FR-23 AC3, NFR-01
    """
    key = os.getenv(config.OPENROUTER_API_KEY_ENV, "").strip()
    if not key:
        raise LlmCallError(
            f"The environment variable {config.OPENROUTER_API_KEY_ENV} is not set. "
            "Export it or add it to a .env file (see .env.example)."
        )
    return key


class PrefixedEmbeddings(Embeddings):
    """Wrap an embedding client so that every input gets the configured prefix.

    Chroma calls ``embed_documents`` when indexing and ``embed_query`` when
    searching, so wrapping the client is enough to apply the convention of
    FR-04 AC6 everywhere.

    Related: FR-04 AC6
    """

    def __init__(self, inner: Embeddings) -> None:
        self._inner = inner

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed indexed passages (FR-04 AC6)."""
        return self._inner.embed_documents([apply_embedding_prefix(t, "passage") for t in texts])

    def embed_query(self, text: str) -> list[float]:
        """Embed one search query (FR-04 AC6)."""
        return self._inner.embed_query(apply_embedding_prefix(text, "query"))


def build_chat_model(
    model: str | None = None,
    *,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.0,
) -> BaseChatModel:
    """Create the LangChain chat model pointed at OpenRouter.

    Args:
        model: Model identifier; defaults to :data:`config.CHAT_MODEL`.
        reasoning_effort: Reasoning effort; defaults to :data:`config.REASONING_EFFORT`.
        max_tokens: Token ceiling; defaults to :data:`config.MAX_TOKENS`.
        temperature: Sampling temperature; deterministic by default.

    Returns:
        A configured chat model, with provider routing restricted to providers
        without data retention where OpenRouter supports it (D-3).

    Raises:
        LlmCallError: If the API key is missing.

    Related: FR-20 AC2, FR-23 AC4, NFR-03, §12 D-2, §12 D-3
    """
    raise NotImplementedError("FR-20 AC2: build the OpenRouter chat model from config")


def build_embeddings(model: str | None = None) -> Embeddings:
    """Create the LangChain embedding client pointed at OpenRouter.

    Args:
        model: Model identifier; defaults to :data:`config.EMBEDDING_MODEL`.

    Returns:
        An embedding client that applies :func:`apply_embedding_prefix`.

    Raises:
        LlmCallError: If the API key is missing.

    Related: FR-04 AC6, NFR-01, §12 D-1
    """
    client = OpenAIEmbeddings(
        model=model or config.EMBEDDING_MODEL,  # AI: the model that turns text into vectors
        base_url=config.OPENROUTER_BASE_URL,
        api_key=SecretStr(get_api_key()),
        check_embedding_ctx_length=False,  # send raw text, not OpenAI token IDs
        timeout=config.REQUEST_TIMEOUT_SECONDS,
        max_retries=config.MAX_RETRIES,
        model_kwargs={"extra_body": {"provider": config.PROVIDER_PREFERENCES}},  # D-3
    )
    return PrefixedEmbeddings(client)


def apply_embedding_prefix(text: str, kind: EmbeddingInputKind) -> str:
    """Apply the model-specific input convention to one text.

    The e5 family expects ``query: `` before a search query and ``passage: ``
    before an indexed passage. This is the single place that knows about it.

    Args:
        text: The raw text.
        kind: Whether the text is a search query or an indexed passage.

    Returns:
        The text with the prefix the configured embedding model expects.

    Related: FR-04 AC6
    """
    prefix = config.EMBEDDING_QUERY_PREFIX if kind == "query" else config.EMBEDDING_PASSAGE_PREFIX
    return f"{prefix}{text}"


def invoke_with_retry(
    model: BaseChatModel,
    messages: Sequence[BaseMessage],
    **kwargs: Any,
) -> AIMessage:
    """Invoke a chat model, retrying on rate limits and server errors.

    Args:
        model: The chat model to invoke.
        messages: The message sequence to send.
        **kwargs: Extra arguments forwarded to the model (e.g. bound tools).

    Returns:
        The model's reply.

    Raises:
        LlmLengthError: If the call ran out of tokens with empty content.
        LlmCallError: On timeout or after the retry budget is exhausted.

    Related: NFR-02, NFR-03
    """
    raise NotImplementedError("NFR-02: retry 429/5xx with exponential backoff, max 2 retries")


def extract_usage(response: AIMessage, model: str) -> LlmUsage:
    """Read token counts from a model reply and price them.

    Args:
        response: The reply returned by the model.
        model: Model identifier used for the price lookup.

    Returns:
        The usage record; ``cost_usd`` is None when prices are unavailable.

    Related: FR-19 AC1, FR-19 AC2, NFR-03
    """
    raise NotImplementedError("FR-19 AC1: collect prompt, completion and reasoning tokens")


def friendly_error_message(error: Exception) -> str:
    """Turn an exception into an English message that is safe to show.

    The message never contains a stack trace, a prompt or the API key.

    Args:
        error: The exception raised by a call.

    Returns:
        A short English message for the UI.

    Related: FR-23 AC3, NFR-02
    """
    raise NotImplementedError("NFR-02: map errors to friendly messages, never a stack trace")


def log_call(label: str, payload: dict[str, Any]) -> None:
    """Append one call record to the opt-in debug log.

    Does nothing unless ``DEBUG_LOG=1``; the log is gitignored and is used only
    with fictional data.

    Args:
        label: Name of the call, e.g. ``"retrieval_plan"``.
        payload: Serialisable record of the call.

    Returns:
        None.

    Related: FR-23 AC2
    """
    raise NotImplementedError("FR-23 AC2: write the opt-in debug log only when DEBUG_LOG=1")
