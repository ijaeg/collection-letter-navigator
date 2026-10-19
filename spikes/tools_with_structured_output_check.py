"""Spike E-8 (FR-10 AC8): tool calling plus structured final answer - one call or two?

Variant A ("one call"): the tools are bound together with ``response_format``; the
model either requests a tool or returns the final answer as JSON in the same call.
Variant B ("two steps"): a plain tool-calling loop, then one extra call with
``with_structured_output`` that turns the conversation into the final answer.

For each variant and question the script prints whether a valid answer came back,
which tools ran, the number of LLM calls, the seconds and the tokens. The prompt
is inline because this is a throwaway spike; in the app, prompts live in prompts/.

Run with ``uv run python spikes/tools_with_structured_output_check.py``.

Related: E-8, FR-10 AC8, D-7, §6.3
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field, ValidationError

from collection_letter_navigator import llm

MAX_TOOL_CALLS = 3  # FR-10 AC5


class Answer(BaseModel):
    """Reduced version of AnswerWithSources (§6.3) for the spike."""

    answer_en: str = Field(description="The answer in plain English, two or three sentences.")
    used_tools: list[str] = Field(description="Names of the tools whose results were used.")


@tool
def add_weeks(start_date: str, weeks: int) -> str:
    """Add whole weeks to a date given as YYYY-MM-DD and return the resulting date.

    If the result falls on a Saturday or Sunday, the next Monday is returned.
    """
    end = date.fromisoformat(start_date) + timedelta(weeks=weeks)
    while end.weekday() >= 5:  # simplified ZPO § 222 (2), holidays ignored in the spike
        end += timedelta(days=1)
    return f"{end.isoformat()} ({end.strftime('%A')})"


TOOLS = {"add_weeks": add_weeks}

SYSTEM = (
    f"Today is {date.today().isoformat()}. You explain German debt collection letters in plain "
    "English. Never calculate dates yourself: use the add_weeks tool. The objection period for a "
    "court payment order (Mahnbescheid) and an enforcement order (Vollstreckungsbescheid) is two "
    "weeks from service. Answer in two or three sentences."
)

QUESTIONS = [
    "A court payment order was delivered to me on 14 October 2026. Until when can I object?",
    "What is a Mahnbescheid?",
    "The enforcement order came on 2026-10-09. What is the last day for an Einspruch?",
]


def _tokens(message: Any) -> int:
    """Total tokens of one reply, if the provider reported them."""
    usage = getattr(message, "usage_metadata", None) or {}
    return int(usage.get("total_tokens", 0))


def _run_tools(reply: Any, messages: list[BaseMessage], used: list[str]) -> None:
    """Execute the requested tool calls and append the results as tool messages."""
    for call in reply.tool_calls:
        used.append(call["name"])
        result = TOOLS[call["name"]].invoke(call["args"])  # AI: the app runs the tool
        messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))


def variant_one_call(question: str) -> dict[str, Any]:
    """Tools and the structured answer in the same call (FR-10 AC8, first option)."""
    model = llm.build_chat_model().bind_tools(  # type: ignore[attr-defined]
        list(TOOLS.values()), response_format=Answer, strict=True
    )
    messages: list[BaseMessage] = [SystemMessage(SYSTEM), HumanMessage(question)]
    used: list[str] = []
    calls = tokens = 0
    started = time.perf_counter()
    while True:
        reply = model.invoke(messages)  # AI: one call - tool request or final JSON
        calls += 1
        tokens += _tokens(reply)
        messages.append(reply)
        if reply.tool_calls and len(used) < MAX_TOOL_CALLS:
            _run_tools(reply, messages, used)
            continue
        break
    parsed = reply.additional_kwargs.get("parsed")
    try:
        answer = parsed if isinstance(parsed, Answer) else Answer.model_validate_json(reply.content)
        ok, text = True, answer.answer_en
    except (ValidationError, ValueError, TypeError) as error:
        ok, text = False, f"no valid answer: {error}"
    return _result("A one call", ok, text, used, calls, tokens, started)


def variant_two_steps(question: str) -> dict[str, Any]:
    """Tool loop first, then one structured-output call (FR-10 AC8, second option)."""
    chat = llm.build_chat_model()
    model = chat.bind_tools(list(TOOLS.values()))
    messages: list[BaseMessage] = [SystemMessage(SYSTEM), HumanMessage(question)]
    used: list[str] = []
    calls = tokens = 0
    started = time.perf_counter()
    while len(used) < MAX_TOOL_CALLS:
        reply = model.invoke(messages)  # AI: step 1 - may request tools
        calls += 1
        tokens += _tokens(reply)
        messages.append(reply)
        if not reply.tool_calls:
            break
        _run_tools(reply, messages, used)
    final = chat.with_structured_output(Answer, method="json_schema", include_raw=True)
    raw = final.invoke(messages)  # AI: step 2 - final answer as JSON
    calls += 1
    tokens += _tokens(raw["raw"])
    answer = raw.get("parsed")
    ok = isinstance(answer, Answer)
    text = answer.answer_en if isinstance(answer, Answer) else f"no valid answer: {raw}"
    return _result("B two steps", ok, text, used, calls, tokens, started)


def _result(
    name: str, ok: bool, text: str, used: list[str], calls: int, tokens: int, started: float
) -> dict[str, Any]:
    """Collect and print the measurements of one run."""
    seconds = time.perf_counter() - started
    print(f"  {name:<12} ok={ok!s:<5} tools={used} calls={calls} {seconds:.1f}s {tokens} tok")
    print(f"               {text}")
    return {"variant": name, "ok": ok, "tools": used, "calls": calls, "seconds": seconds}


if __name__ == "__main__":
    llm.load_environment()
    for question in QUESTIONS:
        print(f"Q: {question}")
        for variant in (variant_one_call, variant_two_steps):
            try:
                variant(question)
            except Exception as error:  # a spike reports, it does not crash
                print(f"  {variant.__name__}: failed with {type(error).__name__}: {error}")
        print()
