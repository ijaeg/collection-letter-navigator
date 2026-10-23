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

import json
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

import openai
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
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

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed several search queries in one request (R-11, NFR-04).

        Uses the batch endpoint, so three queries cost one round trip instead
        of three; the vectors are the same as from :meth:`embed_query`.
        """
        return self._inner.embed_documents([apply_embedding_prefix(t, "query") for t in texts])


def model_id(model: object) -> str:
    """The OpenRouter model identifier behind a chat model, for usage and pricing.

    Follows LangChain's ``bound`` wrappers (``bind_tools``); test fakes without a
    model name count as the configured model.

    Related: FR-19 AC1, FR-20 AC1
    """
    for _ in range(5):
        name = getattr(model, "model_name", None)
        if isinstance(name, str) and name:
            return name
        model = getattr(model, "bound", None)
        if model is None:
            break
    return config.CHAT_MODEL


def build_chat_model(
    model: str | None = None,
    *,
    reasoning_effort: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """Create the LangChain chat model pointed at OpenRouter.

    Args:
        model: Model identifier; defaults to :data:`config.CHAT_MODEL`.
        reasoning_effort: Reasoning effort; defaults to :data:`config.REASONING_EFFORT`.
        max_tokens: Token ceiling; defaults to :data:`config.MAX_TOKENS`.
        temperature: Sampling temperature; None leaves the provider default,
            because reasoning models such as ``gpt-5-mini`` reject other values.

    Returns:
        A configured chat model, with provider routing restricted to providers
        without data retention where OpenRouter supports it (D-3).

    Raises:
        LlmCallError: If the API key is missing.

    Related: FR-20 AC2, FR-23 AC4, NFR-03, §12 D-2, §12 D-3
    """
    return ChatOpenAI(
        model=model or config.CHAT_MODEL,  # AI: the chat model that answers and plans
        base_url=config.OPENROUTER_BASE_URL,
        api_key=SecretStr(get_api_key()),
        max_completion_tokens=max_tokens or config.MAX_TOKENS,  # AI: reasoning tokens count too
        temperature=temperature,
        timeout=config.REQUEST_TIMEOUT_SECONDS,
        max_retries=0,  # retries happen in invoke_with_retry, so they can be tested (NFR-02)
        extra_body={
            "reasoning": {"effort": reasoning_effort or config.REASONING_EFFORT},
            "provider": config.PROVIDER_PREFERENCES,  # D-3: no training, zero data retention
        },
    )


def load_prompt(name: str) -> str:
    """Read one prompt file from ``prompts/``.

    All prompt text lives in Markdown files, never in ``.py`` files (NFR-05).

    Args:
        name: File name without extension, e.g. ``"retrieval_plan"``.

    Returns:
        The prompt text.

    Raises:
        FileNotFoundError: If the prompt file does not exist.

    Related: NFR-05, §5
    """
    return (config.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


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


#: Errors worth a retry: rate limits, server errors, timeouts, broken connections (NFR-02).
_RETRYABLE = (
    openai.RateLimitError,
    openai.InternalServerError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)


def call_with_retry[T](call: Callable[[], T], *, sleep: Callable[[float], None] = time.sleep) -> T:
    """Run one LLM request, retrying on rate limits, server errors and timeouts.

    Args:
        call: The request, e.g. ``lambda: model.invoke(messages)``.
        sleep: Wait function between attempts; replaced in tests.

    Returns:
        Whatever the request returns.

    Raises:
        LlmCallError: With a friendly message, after at most
            :data:`config.MAX_RETRIES` retries or at once for errors a retry
            cannot fix (e.g. a rejected key).

    Related: NFR-02
    """
    attempt = 0
    while True:
        try:
            return call()  # AI: one request to OpenRouter
        except _RETRYABLE as error:
            if attempt >= config.MAX_RETRIES:
                raise LlmCallError(friendly_error_message(error)) from error
            sleep(config.RETRY_BACKOFF_SECONDS * 2**attempt)  # 1 s, 2 s, ...
            attempt += 1
        except openai.OpenAIError as error:  # auth, bad request, ...: retrying does not help
            raise LlmCallError(friendly_error_message(error)) from error


def invoke_with_retry(
    model: Runnable[Any, Any],
    messages: Sequence[BaseMessage],
    *,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> AIMessage:
    """Invoke a chat model, retrying on rate limits and server errors.

    Args:
        model: The chat model to invoke, possibly with tools bound.
        messages: The message sequence to send.
        sleep: Wait function between attempts; replaced in tests.
        **kwargs: Extra arguments forwarded to the model.

    Returns:
        The model's reply.

    Raises:
        LlmLengthError: If the call ran out of tokens with empty content.
        LlmCallError: On timeout or after the retry budget is exhausted.

    Related: NFR-02, NFR-03
    """
    reply = call_with_retry(lambda: model.invoke(list(messages), **kwargs), sleep=sleep)
    if not isinstance(reply, AIMessage):
        raise LlmCallError("The model returned an unexpected reply.")
    finish = reply.response_metadata.get("finish_reason")
    if finish == "length" and not reply.content and not reply.tool_calls:
        raise LlmLengthError(friendly_error_message(LlmLengthError()))
    return reply


def extract_usage(response: AIMessage, model: str) -> LlmUsage:
    """Read token counts from a model reply and price them.

    Args:
        response: The reply returned by the model.
        model: Model identifier used for the price lookup.

    Returns:
        The usage record; ``cost_usd`` is None when prices are unavailable.

    Related: FR-19 AC1, FR-19 AC2, NFR-03
    """
    usage: dict[str, Any] = dict(response.usage_metadata or {})
    details = usage.get("output_token_details") or {}
    token_usage = response.response_metadata.get("token_usage") or {}
    cost = token_usage.get("cost")  # OpenRouter reports the cost when usage accounting is on
    return LlmUsage(
        model=model,
        prompt_tokens=int(usage.get("input_tokens", 0)),
        completion_tokens=int(usage.get("output_tokens", 0)),
        reasoning_tokens=int(details.get("reasoning", 0)),
        cost_usd=float(cost) if isinstance(cost, int | float) else None,
    )


def friendly_error_message(error: Exception) -> str:
    """Turn an exception into an English message that is safe to show.

    The message never contains a stack trace, a prompt or the API key.

    Args:
        error: The exception raised by a call.

    Returns:
        A short English message for the UI.

    Related: FR-23 AC3, NFR-02
    """
    if isinstance(error, LlmLengthError):
        return (
            "The model ran out of its token budget before answering. Please ask a shorter or "
            "more specific question."
        )
    if isinstance(error, LlmCallError):
        return str(error)
    if isinstance(error, openai.AuthenticationError | openai.PermissionDeniedError):
        return (
            f"The API key was rejected. Check {config.OPENROUTER_API_KEY_ENV} (see .env.example)."
        )
    if isinstance(error, openai.RateLimitError):
        return "The model service is busy (rate limit). Please wait a moment and try again."
    if isinstance(error, openai.APITimeoutError):
        return (
            f"The model did not answer within {config.REQUEST_TIMEOUT_SECONDS} seconds. "
            "Please try again."
        )
    if isinstance(error, openai.APIConnectionError):
        return "The model service could not be reached. Check the internet connection."
    if isinstance(error, openai.APIStatusError):
        return f"The model service reported an error (HTTP {error.status_code}). Please try again."
    return "Something went wrong while contacting the model. Please try again."


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
    if not config.DEBUG_LOG_ENABLED:
        return
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now().isoformat(timespec="seconds"), "label": label, **payload}
    with config.DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def usage_as_dict(usage: LlmUsage) -> dict[str, Any]:
    """Serialise a usage record, e.g. for the debug log or the UI.

    Related: FR-19 AC1, FR-23 AC2
    """
    return asdict(usage)
