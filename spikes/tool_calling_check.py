"""Spike D-7 (part 2): one complete tool-calling round trip with LangChain and OpenRouter.

The model receives a question that needs a date calculation, asks for a tool call, the
script executes the tool and sends the result back, and the model writes the final answer.
The tool is a deliberately simple stand-in for FR-11 (no holiday or weekend rules).

Related: D-7, FR-10, §5.1
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv()

MODEL = os.getenv("CHAT_MODEL", "openai/gpt-5-mini")


@tool
def add_weeks(start_date: str, weeks: int) -> str:
    """Add a number of weeks to a date. start_date must be ISO format YYYY-MM-DD."""
    # AI: the docstring and the type hints become the tool description the model sees.
    end = date.fromisoformat(start_date) + timedelta(weeks=weeks)
    return end.isoformat()


TOOLS = {"add_weeks": add_weeks}

SYSTEM = (
    "You help people understand deadlines in German debt collection letters. "
    "Use the available tools for every date calculation instead of calculating yourself."
)


def make_llm() -> ChatOpenAI:
    """Create the LangChain chat model for OpenRouter."""
    return ChatOpenAI(
        model=MODEL,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        max_tokens=4000,
        timeout=60,
        max_retries=2,
        extra_body={"reasoning": {"effort": "low"}},
    )


def run(llm: ChatOpenAI, question: str) -> str:
    """Run one question through the tool-calling loop and return the final answer."""
    llm_with_tools = llm.bind_tools(list(TOOLS.values()))  # AI: tell the model which tools exist
    messages: list[BaseMessage] = [SystemMessage(SYSTEM), HumanMessage(question)]

    for _ in range(3):  # at most 3 rounds, as in FR-10 AC5
        ai_message = llm_with_tools.invoke(messages)  # AI: model answers OR requests tools
        messages.append(ai_message)
        if not ai_message.tool_calls:  # AI: no tool requested -> this is the final answer
            print(f"Final answer:\n{ai_message.content}")
            return str(ai_message.content)
        for call in ai_message.tool_calls:  # AI: the app (not the model) executes the tool
            print(f"Tool call: {call['name']}({call['args']})")
            result = TOOLS[call["name"]].invoke(call["args"])
            print(f"Tool result: {result}")
            # AI: the result goes back as a "tool" message, linked by the call ID.
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
    return "Stopped after 3 rounds without a final answer."


if __name__ == "__main__":
    run(make_llm(), "A court letter was delivered to me on 2026-10-14. What is two weeks later?")
