"""Letter Check: redaction, fact extraction and the derived tool checklist.

The user pastes the German letter; personal data is replaced by placeholders
*before* any LLM call and shown as a preview the user must confirm. Only then
does one call extract a :class:`LetterFacts` object, the matching tools run on
the extracted facts, and the result is rendered as "Points worth checking".

Related: FR-16, FR-21 AC2, FR-22, FR-23 AC1, §6.5
"""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from collection_letter_navigator import config, guards, llm, tools
from collection_letter_navigator.schemas import LetterFacts, ToolResult, TriageResult
from collection_letter_navigator.tools import deadlines, interest, limitation

#: Words before a number that mark it as a case or file number (FR-16 AC2).
_CASE_LABELS = r"Aktenzeichen|Az\.|Geschäftszeichen|Gesch\.-Z\.|Gz\."

#: Words before a number that mark it as a customer, contract or invoice number.
_CUSTOMER_LABELS = (
    r"Kundennummer|Kunden-Nr\.|Kd\.-Nr\.|Vertragsnummer|Vertrags-Nr\.|Rechnungsnummer|"
    r"Rechnungs-Nr\.|Rechnung Nr\.|Forderungsnummer|Mitgliedsnummer|"
    r"Unser Zeichen|Ihr Zeichen|Referenz"
)

#: Redaction rules as ``(name, pattern)`` pairs; the name becomes the placeholder
#: prefix, e.g. ``IBAN`` yields ``<IBAN_1>`` (FR-16 AC2). If a pattern has a group
#: named ``value``, only that group is replaced and the label before it stays, so
#: the model still knows what kind of number it was. Amounts, dates and deadlines
#: are not matched by any rule; the tools need them.
REDACTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    (
        "CASE_NO",
        re.compile(rf"(?i:{_CASE_LABELS})\s*:?\s*(?P<value>[A-Z0-9][A-Z0-9 ./-]*[A-Z0-9])"),
    ),
    (
        "CUSTOMER_NO",
        re.compile(rf"(?i:{_CUSTOMER_LABELS})\s*:?\s*(?P<value>[A-Z0-9][A-Z0-9./-]*[A-Z0-9])"),
    ),
    (
        "POSTCODE_CITY",  # before PHONE: postcodes such as 04109 start with 0
        re.compile(r"\b\d{5} (?!EUR\b|Euro\b)[A-ZÄÖÜ][a-zäöüß]+(?:[ -][A-ZÄÖÜ][a-zäöüß]+)*"),
    ),
    ("PHONE", re.compile(r"(?:\+49|0049|(?<![\d.,])0)[ /-]?\d{2,5}(?:[ /-]?\d{2,}){1,4}")),
    (
        "BIRTH_DATE",
        re.compile(r"(?:geb\.|geboren am)\s*(?P<value>\d{1,2}\.\d{1,2}\.\d{4})", re.IGNORECASE),
    ),
    (
        "STREET",
        re.compile(
            r"\b[A-ZÄÖÜ][\wäöüß.-]*(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|"
            r"ufer|chaussee) \d+ ?[a-z]?\b"
        ),
    ),
    (
        "NAME",
        re.compile(
            r"\b(?:Herrn?|Frau)\s+(?:Dr\.\s+)?"
            r"(?P<value>[A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+)?)"
        ),
    ),
)


@dataclass(slots=True)
class RedactionResult:
    """The redacted letter and what was replaced, for the preview.

    Attributes:
        redacted_text: The letter with placeholders instead of personal data.
        placeholders: Mapping from placeholder to the rule that produced it;
            the original values are never persisted.

    Related: FR-16 AC2, FR-16 AC3, FR-23 AC2
    """

    redacted_text: str
    placeholders: dict[str, str] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        """How many values each rule replaced, for the preview (FR-16 AC3)."""
        totals: dict[str, int] = {}
        for rule in self.placeholders.values():
            totals[rule] = totals.get(rule, 0) + 1
        return totals


@dataclass(slots=True)
class ChecklistItem:
    """One point of the "Points worth checking" list.

    Attributes:
        title: Short English heading of the point.
        detail: The explanation, derived from a tool result or a provision.
        legal_basis: Provisions the point rests on.
        tool: Name of the tool the point came from, or None.

    Related: FR-16 AC5, FR-17 AC1
    """

    title: str
    detail: str
    legal_basis: list[str] = field(default_factory=list)
    tool: str | None = None


@dataclass(slots=True)
class LetterCheckOutcome:
    """Everything one Letter Check produced, for the chat and the tool cards.

    Attributes:
        facts: The extracted facts.
        tool_results: One result per tool that ran on the facts.
        checklist: The "Points worth checking".
        usages: Token usage of the extraction call (FR-19 AC1).
        seconds: Wall-clock seconds of the whole check.

    Related: FR-16 AC4, AC5, AC6
    """

    facts: LetterFacts
    tool_results: list[ToolResult] = field(default_factory=list)
    checklist: list[ChecklistItem] = field(default_factory=list)
    usages: list[llm.LlmUsage] = field(default_factory=list)
    seconds: float = 0.0


def redact(letter_de: str) -> RedactionResult:
    """Replace personal data in the letter with placeholders.

    IBANs, e-mail addresses, phone numbers, case and customer numbers,
    street/postcode lines, names after "Herr"/"Frau" and birth dates are
    replaced; amounts, dates and deadlines are kept because the tools need them.
    The same value gets the same placeholder every time it occurs.

    Args:
        letter_de: The validated letter text.

    Returns:
        The redacted text and the placeholder map, for the preview.

    Related: FR-16 AC2, FR-16 AC7, FR-23 AC1
    """
    text = letter_de
    placeholders: dict[str, str] = {}
    for name, pattern in REDACTION_RULES:
        seen: dict[str, str] = {}

        has_value = "value" in pattern.groupindex

        def replace(
            match: re.Match[str],
            name: str = name,
            seen: dict[str, str] = seen,
            has_value: bool = has_value,
        ) -> str:
            value = match.group("value") if has_value else match.group(0)
            if value.startswith("<"):  # already a placeholder
                return match.group(0)
            if value not in seen:
                seen[value] = f"<{name}_{len(seen) + 1}>"
                placeholders[seen[value]] = name
            if not has_value:
                return seen[value]
            start, end = match.span("value")
            offset = match.start()
            whole = match.group(0)
            return whole[: start - offset] + seen[value] + whole[end - offset :]

        text = pattern.sub(replace, text)
    return RedactionResult(text, placeholders)


def prepare_letter(letter_de: str) -> RedactionResult:
    """Validate, guard and redact a pasted letter; nothing is sent anywhere yet.

    Args:
        letter_de: The raw letter text from the text area.

    Returns:
        The redaction for the preview (FR-16 AC3).

    Raises:
        EmptyInputError, InputTooLongError: If the letter fails L1 (FR-16 AC1).
        InjectionDetectedError: If the letter contains instructions to an AI (FR-22).

    Related: FR-16 AC1, FR-16 AC2, FR-22 AC3
    """
    letter = guards.validate_letter(letter_de)  # L1: 6,000 characters
    guards.assert_no_injection(letter)  # L2, on the original text
    return redact(letter)


def extract_letter_facts(
    redacted_text: str,
    *,
    model: BaseChatModel | None = None,
    usages: list[llm.LlmUsage] | None = None,
) -> LetterFacts:
    """Extract the structured facts from the redacted letter.

    Fields that cannot be found are null and are never guessed.

    Args:
        redacted_text: The confirmed, redacted letter text.
        model: Chat model to use; defaults to the configured model.
        usages: If given, the token usage of the call is appended (FR-19 AC1).

    Returns:
        The extracted facts.

    Raises:
        LlmCallError: If the call fails or the output never validates.

    Related: FR-16 AC3, FR-16 AC4, FR-22 L4
    """
    chat = model or llm.build_chat_model()
    # AI: structured output - one call, the schema of LetterFacts decides the fields
    extractor = chat.with_structured_output(LetterFacts, method="json_schema", include_raw=True)
    messages = [
        SystemMessage(llm.load_prompt("letter_extraction")),
        HumanMessage(guards.wrap_untrusted(redacted_text, "letter")),
    ]
    last_error: Exception | None = None
    for _ in range(1 + config.JSON_RETRY_ATTEMPTS):
        try:
            reply: Any = llm.call_with_retry(lambda: extractor.invoke(messages))
            parsed = reply.get("parsed") if isinstance(reply, dict) else reply
            raw = reply.get("raw") if isinstance(reply, dict) else None
            if usages is not None and isinstance(raw, AIMessage):
                usages.append(llm.extract_usage(raw, config.CHAT_MODEL))
            facts = LetterFacts.model_validate(parsed)
            llm.log_call("letter_extraction", {"facts": facts.model_dump(mode="json")})
            return facts
        except ValidationError as error:  # schema violated: one retry (NFR-02)
            last_error = error
        except llm.LlmCallError:
            raise
        except Exception as error:  # anything else the client raises
            raise llm.LlmCallError(
                f"The letter could not be read: {llm.friendly_error_message(error)}"
            ) from error
    raise llm.LlmCallError(f"The letter could not be read: {last_error}")


def _default_start(invoice_date: date) -> date:
    """First day of default, assumed 30 days after the invoice (BGB § 286 (3))."""
    return invoice_date + timedelta(days=31)


def plan_tool_calls(
    facts: LetterFacts,
    triage: TriageResult | None = None,
) -> list[tuple[str, dict[str, object]]]:
    """Decide which tools the extracted facts call for.

    - A court letter with a service date → objection deadline (FR-11). Without a
      date in the letter, the delivery date from the triage is used.
    - An invoice date → limitation check (FR-12).
    - Principal, interest charged and an invoice date → maximum default interest
      (FR-13), from 30 days after the invoice to the date of the letter.

    A tool whose inputs are missing is not planned; nothing is guessed.

    Args:
        facts: The extracted facts.
        triage: Triage answers, used to fill the service date of a court letter.

    Returns:
        One ``(tool_name, arguments)`` pair per tool to run.

    Related: FR-16 AC5, FR-16 AC7
    """
    calls: list[tuple[str, dict[str, object]]] = []
    if facts.letter_type in ("mahnbescheid", "vollstreckungsbescheid"):
        served = facts.service_or_receipt_date or (
            triage.delivered_on if triage and triage.sender == "court" else None
        )
        if served is not None:
            calls.append(
                (
                    deadlines.TOOL_NAME,
                    {"document_type": facts.letter_type, "service_date": served.isoformat()},
                )
            )
    if facts.invoice_date is not None:
        calls.append((limitation.TOOL_NAME, {"claim_date": facts.invoice_date.isoformat()}))
    if facts.principal_eur and facts.interest_eur is not None and facts.invoice_date is not None:
        args: dict[str, object] = {
            "principal": facts.principal_eur,
            "start_date": _default_start(facts.invoice_date).isoformat(),
        }
        if facts.service_or_receipt_date is not None:
            args["end_date"] = facts.service_or_receipt_date.isoformat()
        calls.append((interest.TOOL_NAME, args))
    return calls


def _eur(amount: float) -> str:
    return f"{amount:,.2f} €"


def build_checklist(
    facts: LetterFacts,
    tool_results: Sequence[ToolResult],
) -> list[ChecklistItem]:
    """Turn the facts and tool results into "Points worth checking".

    Every point states a fact or a rule with its source; no point recommends an
    action (FR-21 AC4).

    Args:
        facts: The extracted facts.
        tool_results: Results of the tools planned by :func:`plan_tool_calls`.

    Returns:
        The checklist, each point carrying its source.

    Related: FR-16 AC5, FR-21 AC4
    """
    items: list[ChecklistItem] = []
    by_tool = {result.tool: result for result in tool_results}

    deadline = by_tool.get(deadlines.TOOL_NAME)
    if deadline and deadline.result:
        res = deadline.result
        kind = "strict deadline (Notfrist)" if res.get("strict_deadline") else "deadline"
        items.append(
            ChecklistItem(
                "Court deadline",
                f"The period for {res['procedure']} ends on {res['period_end_weekday']}, "
                f"{res['period_end']} – a {kind}, counted from the service date "
                f"{res['service_date']}.",
                list(deadline.legal_basis),
                deadlines.TOOL_NAME,
            )
        )
    elif facts.letter_type in ("mahnbescheid", "vollstreckungsbescheid"):
        items.append(
            ChecklistItem(
                "Court deadline",
                "This looks like a court document, but no date of service was found. The "
                "two-week period runs from the date of service written on the envelope.",
                ["ZPO § 692 (1) no. 3", "ZPO § 339 (1)"],
            )
        )

    if facts.stated_deadline is not None and facts.sender_type != "court":
        items.append(
            ChecklistItem(
                "Payment date in the letter",
                f"The letter names {facts.stated_deadline.isoformat()}. This date is set by the "
                "sender; it is not a statutory deadline.",
            )
        )

    limit = by_tool.get(limitation.TOOL_NAME)
    if limit and limit.result:
        status = (
            "has ended in this estimate"
            if limit.result.get("regular_period_ended")
            else "has not ended"
        )
        items.append(
            ChecklistItem(
                "Age of the claim",
                f"Counting from the invoice date {limit.result['claim_date']}, the regular "
                f"three-year period ends on {limit.result['period_end']} and {status}. A "
                "payment, acknowledgment or court step can change this; limitation only "
                "takes effect if the debtor raises it.",
                list(limit.legal_basis),
                limitation.TOOL_NAME,
            )
        )

    rate = by_tool.get(interest.TOOL_NAME)
    if rate and rate.result and facts.interest_eur is not None:
        maximum = float(str(rate.result["total_interest_eur"]))
        comparison = "more than" if facts.interest_eur > maximum + 0.005 else "not more than"
        items.append(
            ChecklistItem(
                "Interest",
                f"The letter charges {_eur(facts.interest_eur)} interest. The statutory maximum "
                f"for a consumer from {rate.result['start_date']} to {rate.result['end_date']} "
                f"is {_eur(maximum)}, so the amount is {comparison} that maximum. Default is "
                "assumed to start 30 days after the invoice; an earlier reminder can move it.",
                list(rate.legal_basis),
                interest.TOOL_NAME,
            )
        )

    if facts.fees_eur is not None and facts.fees_eur > 0:
        items.append(
            ChecklistItem(
                "Collection fees",
                f"The letter charges {_eur(facts.fees_eur)} in fees. A creditor can claim "
                "collection costs only up to what a lawyer could charge; the app does not "
                "calculate this limit.",
                ["RDG § 13e", "RDG § 13f"],
            )
        )

    if facts.sender_type == "collection_agency":
        items.append(
            ChecklistItem(
                "Information the agency must give",
                "A registered collection agency must state the creditor, the reason for the "
                "claim, an interest calculation and the type and reason of its costs, and must "
                "name its supervisory authority. Missing items can be requested.",
                ["RDG § 13a (1)", "RDG § 13a (2)"],
            )
        )
    return items


def facts_summary(facts: LetterFacts) -> str:
    """One English paragraph with the extracted facts, added to the chat context (FR-16 AC6)."""
    parts = [f"Letter type: {facts.letter_type}", f"sender: {facts.sender_type}"]
    for label, value in (
        ("principal", facts.principal_eur),
        ("interest", facts.interest_eur),
        ("fees", facts.fees_eur),
    ):
        if value is not None:
            parts.append(f"{label}: {_eur(value)}")
    for label, day in (
        ("invoice date", facts.invoice_date),
        ("date of service or receipt", facts.service_or_receipt_date),
        ("payment date stated in the letter", facts.stated_deadline),
    ):
        if day is not None:
            parts.append(f"{label}: {day.isoformat()}")
    return (
        "Facts from the user's letter (redacted, extracted by the Letter Check): "
        + "; ".join(parts)
        + "."
    )


def run_letter_check(
    redacted_text: str,
    triage: TriageResult | None = None,
    *,
    model: BaseChatModel | None = None,
) -> LetterCheckOutcome:
    """Extract the facts, run the matching tools and build the checklist.

    Called only after the user confirmed the redacted preview (FR-16 AC3).

    Raises:
        LlmCallError: If the extraction fails after retries (NFR-02).

    Related: FR-16 AC4, AC5, AC6
    """
    started = time.perf_counter()
    usages: list[llm.LlmUsage] = []
    facts = extract_letter_facts(redacted_text, model=model, usages=usages)
    # AI: deterministic tools on the extracted facts - no further LLM call
    results = [tools.invoke_tool(name, args) for name, args in plan_tool_calls(facts, triage)]
    return LetterCheckOutcome(
        facts,
        results,
        build_checklist(facts, results),
        usages,
        time.perf_counter() - started,
    )
