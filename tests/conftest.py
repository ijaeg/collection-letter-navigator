"""Shared fixtures. Every LLM call in the tests runs against a mock.

No test ever reaches OpenRouter: the chat model is replaced by a fake that
returns prepared replies, including prepared tool calls.

Related: NFR-06, FR-10, §7.4
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from collection_letter_navigator import retrieval
from collection_letter_navigator.retrieval import RetrievalOutcome, ScoredChunk
from collection_letter_navigator.schemas import RetrievalPlan


class FakeChatModel:
    """Scripted stand-in for a LangChain chat model.

    ``replies`` are returned by ``invoke`` in order (plain answers or tool calls);
    ``structured`` maps a Pydantic schema to the values that
    ``with_structured_output(schema).invoke`` returns in order. A reply that is
    an exception is raised instead. Every call is recorded in ``calls``.
    """

    def __init__(
        self,
        replies: Sequence[AIMessage | Exception] = (),
        structured: dict[type, list[Any]] | None = None,
    ) -> None:
        self.replies = list(replies)
        self.structured = {key: list(values) for key, values in (structured or {}).items()}
        self.calls: list[tuple[str, list[BaseMessage]]] = []
        self.bound_tools: list[Any] = []
        self.bind_kwargs: dict[str, Any] = {}

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> FakeChatModel:
        self.bound_tools = list(tools)
        self.bind_kwargs = kwargs
        return self

    def invoke(self, messages: list[BaseMessage], **_: Any) -> AIMessage:
        self.calls.append(("invoke", list(messages)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def with_structured_output(self, schema: type, **kwargs: Any) -> Any:
        model = self

        class Structured:
            def invoke(self, messages: list[BaseMessage], **_: Any) -> Any:
                model.calls.append((f"structured:{schema.__name__}", list(messages)))
                value = model.structured[schema].pop(0)
                if kwargs.get("include_raw"):
                    return {"raw": AIMessage(content=""), "parsed": value, "parsing_error": None}
                return value

        return Structured()


def tool_call(name: str, args: dict[str, Any], call_id: str = "call_1") -> AIMessage:
    """An AI message that asks for one tool call."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def final_answer(text: str, ids: list[str], out_of_scope: bool = False) -> AIMessage:
    """An AI message carrying the structured answer as JSON."""
    payload = {
        "answer_en": text,
        "source_chunk_ids": ids,
        "used_tools": [],
        "out_of_scope": out_of_scope,
    }
    return AIMessage(
        content=json.dumps(payload),
        usage_metadata={
            "input_tokens": 900,
            "output_tokens": 120,
            "total_tokens": 1020,
            "output_token_details": {"reasoning": 64},
        },
    )


@pytest.fixture
def mock_chat_model() -> type[FakeChatModel]:
    """Provide the class of the scripted chat model; each test sets up its replies.

    Related: NFR-06, FR-10 AC1, NFR-02
    """
    return FakeChatModel


@pytest.fixture
def mock_retrieved_chunks() -> RetrievalOutcome:
    """Provide a retrieval outcome with real chunks from the committed index.

    Related: NFR-06, FR-08 AC2, FR-09 AC1
    """
    plan = RetrievalPlan(queries_de=["Widerspruch Mahnbescheid Frist"], rationale="Test.")
    chunks = []
    for chunk_id in ("ZPO-692", "ZPO-694", "BGB-195"):
        doc = retrieval.get_chunk_by_id(chunk_id)
        assert doc is not None
        chunks.append(ScoredChunk(chunk_id, doc, 1.0))
    return RetrievalOutcome(plan, chunks)
