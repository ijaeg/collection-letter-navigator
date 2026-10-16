"""Input validation and prompt-injection heuristics (layers L1, L2 and L4).

L1 checks length and emptiness before any LLM call, L2 matches narrow regex
patterns for instruction-like text, and L4 wraps untrusted text in delimiters
that the system prompts declare to be data. Every L2 pattern has its own test
case in ``tests/test_guards.py`` (FR-22 AC4).

Related: FR-02 AC2, FR-02 AC3, FR-16 AC1, FR-22, §5.1
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Narrow L2 patterns, one per instruction-like phrase (FR-22 L2).
#: TODO (FR-22 AC4): add one pattern per phrase listed in §4.6, each with a test
#: case, keeping them narrow enough that a real letter containing "system" passes.
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = ()


class InputTooLongError(ValueError):
    """A question or letter exceeds its configured character limit.

    Related: FR-02 AC2, FR-16 AC1, FR-22 L1
    """


class EmptyInputError(ValueError):
    """A question or letter is empty after stripping whitespace.

    Related: FR-02 AC2, FR-22 L1
    """


class InjectionDetectedError(ValueError):
    """The text contains instructions addressed to an AI.

    Related: FR-22 AC1
    """


@dataclass(frozen=True, slots=True)
class InjectionFinding:
    """One L2 match, used for the block message and for the safety tests.

    Attributes:
        pattern: The pattern that matched.
        matched_text: The matched span, used only for test reporting.

    Related: FR-22 AC1, FR-22 AC4
    """

    pattern: str
    matched_text: str


def validate_question(question_en: str) -> str:
    """Check a chat question before any LLM call.

    Args:
        question_en: The raw question from ``st.chat_input``.

    Returns:
        The stripped question.

    Raises:
        EmptyInputError: If the question is empty.
        InputTooLongError: If it exceeds :data:`config.MAX_QUESTION_CHARACTERS`;
            the message names the limit.

    Related: FR-02 AC2, FR-22 L1
    """
    raise NotImplementedError("FR-02 AC2: reject empty questions and name the 1,000 char limit")


def validate_letter(letter_de: str) -> str:
    """Check a pasted letter before redaction.

    Args:
        letter_de: The raw letter text.

    Returns:
        The stripped letter text.

    Raises:
        EmptyInputError: If the letter is empty.
        InputTooLongError: If it exceeds :data:`config.MAX_LETTER_CHARACTERS`.

    Related: FR-16 AC1, FR-22 L1
    """
    raise NotImplementedError("FR-16 AC1: enforce the 6,000 character letter limit")


def detect_injection(text: str) -> InjectionFinding | None:
    """Match the L2 heuristics against one untrusted text.

    Args:
        text: A question or a letter.

    Returns:
        The first match, or None if the text looks clean.

    Related: FR-22 AC1, FR-22 AC4
    """
    raise NotImplementedError("FR-22 AC1: match narrow injection patterns")


def assert_no_injection(text: str) -> None:
    """Block the LLM call if the text contains instructions addressed to an AI.

    Args:
        text: A question or a letter.

    Returns:
        None.

    Raises:
        InjectionDetectedError: If :func:`detect_injection` matches; the UI shows
            :data:`config.INJECTION_BLOCKED_MESSAGE_EN`.

    Related: FR-02 AC3, FR-16 AC1, FR-22 AC1
    """
    raise NotImplementedError("FR-22 AC1: block the call when an injection is detected")


def wrap_untrusted(text: str, tag: str) -> str:
    """Wrap untrusted text in delimiters for the L4 prompt hardening.

    Args:
        text: The untrusted text (question, letter or retrieved chunk).
        tag: Delimiter tag, e.g. ``"question"``, ``"letter"`` or ``"source"``.

    Returns:
        The text inside the delimiters, with any imitation of the delimiters in
        the text neutralised.

    Related: FR-08 AC4, FR-22 L4
    """
    raise NotImplementedError("FR-22 L4: wrap untrusted text and neutralise delimiter imitation")
