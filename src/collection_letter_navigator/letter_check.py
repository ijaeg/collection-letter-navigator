"""Letter Check: redaction, fact extraction and the derived tool checklist.

The user pastes the German letter; personal data is replaced by placeholders
*before* any LLM call and shown as a preview the user must confirm. Only then
does one call extract a :class:`LetterFacts` object, the matching tools run on
the extracted facts, and the result is rendered as "Points worth checking".

Related: FR-16, FR-21 AC2, FR-22, FR-23 AC1, §6.5
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel

from collection_letter_navigator.schemas import LetterFacts, ToolResult, TriageResult

#: Redaction rules as ``(name, pattern)`` pairs; the name becomes the placeholder
#: prefix, e.g. ``IBAN`` yields ``<IBAN_1>`` (FR-16 AC2).
#: TODO (FR-16 AC2, AC7): add one rule per personal-data class (IBAN, e-mail,
#: phone, case number, customer number, street/postcode line), each with a test;
#: amounts, dates and deadlines must survive redaction.
REDACTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = ()


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


def redact(letter_de: str) -> RedactionResult:
    """Replace personal data in the letter with placeholders.

    IBANs, e-mail addresses, phone numbers, case and customer numbers and
    street/postcode lines are replaced; amounts, dates and deadlines are kept
    because the tools need them.

    Args:
        letter_de: The validated letter text.

    Returns:
        The redacted text and the placeholder map, for the preview.

    Related: FR-16 AC2, FR-16 AC7, FR-23 AC1
    """
    raise NotImplementedError("FR-16 AC2: redact personal data before any LLM call")


def extract_letter_facts(
    redacted_text: str,
    *,
    model: BaseChatModel | None = None,
) -> LetterFacts:
    """Extract the structured facts from the redacted letter.

    Fields that cannot be found are null and are never guessed.

    Args:
        redacted_text: The confirmed, redacted letter text.
        model: Chat model to use; defaults to the configured model.

    Returns:
        The extracted facts.

    Raises:
        LlmCallError: If the call fails or the output never validates.

    Related: FR-16 AC3, FR-16 AC4, FR-22 L4
    """
    raise NotImplementedError("FR-16 AC4: extract LetterFacts, null for anything not found")


def plan_tool_calls(
    facts: LetterFacts,
    triage: TriageResult | None = None,
) -> list[tuple[str, dict[str, object]]]:
    """Decide which tools the extracted facts call for.

    For example a letter type of ``mahnbescheid`` calls the objection deadline
    tool with the service date from the letter.

    Args:
        facts: The extracted facts.
        triage: Triage answers, used to fill gaps in the facts.

    Returns:
        One ``(tool_name, arguments)`` pair per tool to run.

    Related: FR-16 AC5, FR-16 AC7
    """
    raise NotImplementedError("FR-16 AC5: map LetterFacts to the matching tool calls")


def build_checklist(
    facts: LetterFacts,
    tool_results: Sequence[ToolResult],
) -> list[ChecklistItem]:
    """Turn the facts and tool results into "Points worth checking".

    Args:
        facts: The extracted facts.
        tool_results: Results of the tools planned by :func:`plan_tool_calls`.

    Returns:
        The checklist, each point carrying its source; no point recommends an
        action.

    Related: FR-16 AC5, FR-21 AC4
    """
    raise NotImplementedError("FR-16 AC5: build the checklist, each point with its source")
