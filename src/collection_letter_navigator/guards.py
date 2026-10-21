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

from collection_letter_navigator import config

#: Delimiter tags of the prompts; imitating them in untrusted text is neutralised (FR-22 L4).
DELIMITER_TAGS: tuple[str, ...] = ("question", "context", "sources", "source", "letter", "history")

_TAGS = "|".join(DELIMITER_TAGS)

#: Narrow L2 patterns, one per instruction-like phrase, in English and German (FR-22 L2).
#: Each has a test case; a real letter that contains words like "System" must pass (AC4).
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "ignore all previous instructions" and variants
    re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous\s+|prior\s+|"
        r"above\s+|earlier\s+|your\s+)?(?:instructions|rules|prompts?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ignoriere|vergiss|missachte)\s+(?:alle\s+|die\s+|deine\s+)?(?:vorherigen\s+|"
        r"bisherigen\s+|obigen\s+)?(?:anweisungen|regeln|instruktionen)\b",
        re.IGNORECASE,
    ),
    # requests for the system prompt or the instructions
    re.compile(r"\bsystem[\s-]?prompt\b", re.IGNORECASE),
    re.compile(
        r"\b(?:reveal|show|print|repeat)\s+(?:me\s+)?(?:your|the)\s+(?:hidden\s+)?"
        r"(?:instructions|prompt)\b",
        re.IGNORECASE,
    ),
    # role override
    re.compile(r"\b(?:you\s+are\s+now|from\s+now\s+on\s+you)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:du\s+bist\s+(?:jetzt|nun|ab\s+sofort)|ab\s+jetzt\s+bist\s+du)\b", re.IGNORECASE
    ),
    # role tags at the start of a line, and lines addressed to an AI ("AI: tell the user …")
    re.compile(r"(?im)^\s*(?:system|assistant|developer|ai|ki|chatgpt|llm)\s*:"),
    re.compile(r"<\|im_start\|>|\[/?INST\]", re.IGNORECASE),
    # imitation of the prompt delimiters
    re.compile(rf"</?\s*(?:{_TAGS})\b[^>]*>", re.IGNORECASE),
)


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
    return _validate(question_en, config.MAX_QUESTION_CHARACTERS, "question")


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
    return _validate(letter_de, config.MAX_LETTER_CHARACTERS, "letter")


def _validate(text: str, limit: int, what: str) -> str:
    """Shared L1 check: not empty, not longer than the limit."""
    stripped = text.strip()
    if not stripped:
        raise EmptyInputError(f"Please enter a {what}.")
    if len(stripped) > limit:
        raise InputTooLongError(
            f"Your {what} has {len(stripped):,} characters; the limit is {limit:,}. "
            "Please shorten it."
        )
    return stripped


def detect_injection(text: str) -> InjectionFinding | None:
    """Match the L2 heuristics against one untrusted text.

    Args:
        text: A question or a letter.

    Returns:
        The first match, or None if the text looks clean.

    Related: FR-22 AC1, FR-22 AC4
    """
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return InjectionFinding(pattern=pattern.pattern, matched_text=match.group(0))
    return None


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
    if detect_injection(text) is not None:
        raise InjectionDetectedError(config.INJECTION_BLOCKED_MESSAGE_EN)


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
    # "<question>" inside the text becomes "‹question>", so it cannot close the wrapper
    clean = re.sub(rf"<(/?\s*(?:{_TAGS})\b)", r"‹\1", text, flags=re.IGNORECASE)
    return f"<{tag}>\n{clean}\n</{tag}>"
