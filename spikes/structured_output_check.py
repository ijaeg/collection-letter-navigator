"""Spike D-7 (part 1): structured output with LangChain against OpenRouter.

Turns three English lay questions into a `RetrievalPlan` (German search queries plus an
optional law filter). The prompt is inline because this is a throwaway spike; in the app,
prompts live in prompts/*.md (NFR-05).

Related: D-7, FR-05, FR-06, §6.1
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()

#: Default chat model candidate (D-2).
MODEL = os.getenv("CHAT_MODEL", "openai/gpt-5-mini")


class RetrievalPlan(BaseModel):
    """Format of §6.1: what to search for, and where."""

    queries_de: list[str] = Field(
        min_length=1, max_length=4, description="German legal search queries"
    )
    law_filter: list[Literal["BGB", "ZPO", "RDG"]] | None = Field(
        default=None, description="Laws to search in; null = search all"
    )
    rationale: str = Field(description="One sentence explaining the plan")


SYSTEM = (
    "You turn an English question about a German debt collection letter into a search plan "
    "for a database of German statutes (BGB, ZPO, RDG). Write 1-4 short German search queries "
    "using German legal terms (e.g. Mahnbescheid, Widerspruch, Verjährung, Verzugszinsen, "
    "Inkassodienstleister). Set law_filter only if you are confident which laws apply."
)

QUESTIONS = [
    "I got a letter from the court. How long do I have to object?",
    "My phone bill is from 2021. Is it too old to be collected?",
    "The collection agency did not say who they work for. Do they have to tell me?",
]


def make_llm() -> ChatOpenAI:
    """Create the LangChain chat model for OpenRouter."""
    return ChatOpenAI(
        model=MODEL,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        max_tokens=4000,  # reasoning tokens count against this budget (NFR-03)
        timeout=60,
        max_retries=2,
        extra_body={
            "reasoning": {"effort": "low"},
            "provider": {"data_collection": "deny", "zdr": True},
        },  # AI: reasoning effort, OpenRouter format
    )


def run(llm: ChatOpenAI) -> list[RetrievalPlan]:
    """Ask for a RetrievalPlan per question and print it."""
    # AI: LangChain sends the Pydantic model as JSON schema and parses the answer back.
    planner = llm.with_structured_output(RetrievalPlan, method="json_schema")
    plans = []
    for question in QUESTIONS:
        plan = planner.invoke([SystemMessage(SYSTEM), HumanMessage(question)])  # AI: the call
        plans.append(plan)
        print(f"Q: {question}\n   queries: {plan.queries_de}\n   filter:  {plan.law_filter}")
        print(f"   why:     {plan.rationale}\n")
    return plans


if __name__ == "__main__":
    run(make_llm())
