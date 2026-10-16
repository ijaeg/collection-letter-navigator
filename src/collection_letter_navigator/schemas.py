"""Pydantic contracts for every structured output and UI state object.

These models are the contract between the LLM calls, the deterministic tools and
the UI. They are implemented in full (not stubbed) because every other module is
written against them.

Related: FR-05, FR-06, FR-08, FR-10, FR-11, FR-12, FR-13, FR-16, §6
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

#: Laws that may appear in a ``RetrievalPlan.law_filter`` (FR-06 AC1).
LawCode = Literal["BGB", "ZPO", "RDG"]

#: Sender categories offered by the triage screen (FR-01 AC1).
SenderType = Literal["creditor", "collection_agency", "court", "not_sure"]

#: Court document types offered when the sender is a court (FR-01 AC2).
CourtDocumentType = Literal["mahnbescheid", "vollstreckungsbescheid", "unclear"]

#: Letter types the Letter Check extraction may return (FR-16 AC4, §6.5).
LetterType = Literal[
    "mahnbescheid",
    "vollstreckungsbescheid",
    "collection_letter",
    "reminder",
    "unknown",
]

#: Sender types the Letter Check extraction may return (FR-16 AC4, §6.5).
LetterSenderType = Literal["court", "collection_agency", "creditor", "lawyer", "unknown"]


class RetrievalPlan(BaseModel):
    """Output of the query-translation call: German queries plus an optional filter.

    Related: FR-05, FR-06, §6.1
    """

    model_config = ConfigDict(extra="forbid")

    queries_de: Annotated[list[str], Field(min_length=1, max_length=4)] = Field(
        description="One to four German legal search queries derived from the English question.",
    )
    law_filter: list[LawCode] | None = Field(
        default=None,
        description="Laws the retrieval is restricted to, or null for an unfiltered search.",
    )
    rationale: str = Field(
        description="One sentence explaining the queries and the filter, shown in the RAG panel.",
    )


class ToolResult(BaseModel):
    """The fixed result structure every deterministic tool returns.

    ``result`` is null whenever the tool cannot produce a value; in that case
    ``not_applicable_reason`` explains why. No result is better than a wrong result.

    Related: FR-10 AC2, FR-10 AC4, §6.2
    """

    model_config = ConfigDict(extra="forbid")

    tool: str = Field(description="Name of the tool that produced this result.")
    result: dict[str, object] | None = Field(
        default=None,
        description="Tool-specific values, e.g. {'deadline': '2026-11-02'}; null if none.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions the calculation relies on, stated in English.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Facts the user would have to supply for a firmer statement.",
    )
    legal_basis: list[str] = Field(
        default_factory=list,
        description="Provisions the tool applies, e.g. 'ZPO § 692 (1) no. 3'.",
    )
    not_applicable_reason: str | None = Field(
        default=None,
        description="Why no result could be produced; set exactly when result is null.",
    )


class AnswerWithSources(BaseModel):
    """Structured final answer of the answer call.

    The model returns chunk IDs only; the German source text shown in the UI is
    looked up in the knowledge base by ID (FR-08 AC2).

    Related: FR-08, FR-09, FR-21 AC7, §6.3
    """

    model_config = ConfigDict(extra="forbid")

    answer_en: str = Field(
        description="The answer in plain English, max. about 250 words.",
    )
    source_chunk_ids: list[str] = Field(
        default_factory=list,
        description="IDs of retrieved chunks the answer relies on; must be retrieved chunks.",
    )
    used_tools: list[str] = Field(
        default_factory=list,
        description="Names of the tools whose results the answer uses.",
    )
    out_of_scope: bool = Field(
        default=False,
        description="True if the question falls outside the app's scope (FR-21 AC7, AC9).",
    )


class TriageResult(BaseModel):
    """Triage answers collected in the UI; no LLM call is involved.

    Related: FR-01 AC6, §6.4
    """

    model_config = ConfigDict(extra="forbid")

    sender: SenderType = Field(description="Who sent the letter, as selected by the user.")
    court_document: CourtDocumentType | None = Field(
        default=None,
        description="Court document type; only set when sender is 'court'.",
    )
    delivered_on: date = Field(
        description="Delivery date, used as the assumed date of service (FR-11 AC4).",
    )


class LetterFacts(BaseModel):
    """Facts extracted from a redacted letter by one LLM call.

    Fields that cannot be found in the letter are null and are never guessed
    (FR-16 AC4).

    Related: FR-16, §6.5
    """

    model_config = ConfigDict(extra="forbid")

    letter_type: LetterType = Field(description="Kind of letter, or 'unknown'.")
    sender_type: LetterSenderType = Field(description="Kind of sender, or 'unknown'.")
    principal_eur: float | None = Field(default=None, description="Principal claim in EUR.")
    interest_eur: float | None = Field(default=None, description="Interest charged in EUR.")
    fees_eur: float | None = Field(default=None, description="Fees charged in EUR.")
    invoice_date: date | None = Field(default=None, description="Date of the original invoice.")
    service_or_receipt_date: date | None = Field(
        default=None,
        description="Date of service (court letter) or receipt (company letter).",
    )
    stated_deadline: date | None = Field(
        default=None,
        description="Deadline stated in the letter; not necessarily a statutory deadline.",
    )
