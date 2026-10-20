"""FR-12 ``check_limitation``: an estimate of the regular limitation period.

Three years from the end of the year in which the claim arose and the creditor
knew of it (BGB §§ 195, 199 (1)). Limitation is a defence the debtor must
raise, and suspension, restart and titled claims are outside the estimate: the
tool states both every time.

Related: FR-12, FR-10 AC2, FR-21 AC4, §12 D-4
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from collection_letter_navigator import config
from collection_letter_navigator.schemas import ToolResult
from collection_letter_navigator.tools.contract import (
    guard_tool_errors,
    not_applicable,
    tool_result,
)

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "check_limitation"

#: Tool description shown to the model (FR-10 AC1).
DESCRIPTION = (
    "Estimate when the regular three-year limitation period (Verjährung) of a debt ends. Use it "
    "when the user asks whether a debt is too old. Needs the date the claim arose (e.g. the due "
    "date of the invoice) as YYYY-MM-DD; optionally the date of the last part payment or other "
    "acknowledgment of the debt. The result is an estimate, never a statement that the debt is "
    "time-barred."
)

#: Questions asked on every result (FR-12 AC5).
_ALWAYS_ASK = (
    "Has anything been paid, has a payment plan been agreed or has the debt been acknowledged "
    "since the claim arose? Each of these restarts the period (BGB § 212 (1) no. 1).",
    "Was a court payment order (Mahnbescheid) served? Its service suspends the period "
    "(BGB § 204 (1) no. 3).",
    "Is there a court title, e.g. an enforcement order or a judgment? Such claims become "
    "time-barred only after 30 years (BGB § 197 (1) nos. 3, 4) and are not covered here.",
)


class LimitationArgs(BaseModel):
    """Arguments of :func:`check_limitation`.

    Related: FR-10 AC1, FR-12
    """

    model_config = ConfigDict(extra="forbid")

    claim_date: date = Field(
        description="Date the claim arose (YYYY-MM-DD), e.g. the due date of the invoice.",
    )
    knowledge_date: date | None = Field(
        default=None,
        description="Date the creditor learned of the claim and the debtor; default: claim_date.",
    )
    last_acknowledgment_date: date | None = Field(
        default=None,
        description="Date of the last part payment, interest payment or other acknowledgment of "
        "the debt, if the user mentions one.",
    )


def _today() -> date:
    """Today's date; a function so that tests can fix it."""
    return date.today()


def _plus_years(day: date, years: int) -> date:
    """Add whole years; 29 February becomes 28 February (BGB § 188 (3))."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def end_of_limitation_period(claim_date: date, knowledge_date: date | None = None) -> date:
    """Compute the end of the regular three-year period.

    Args:
        claim_date: Date the claim arose.
        knowledge_date: Date the creditor learned of it; defaults to ``claim_date``.

    Returns:
        The last day of the period, counted from the end of the year in which
        both conditions were met (BGB § 199 (1)).

    Related: FR-12 AC1
    """
    start_year = max(claim_date.year, (knowledge_date or claim_date).year)
    return date(start_year + config.LIMITATION_PERIOD_YEARS, 12, 31)


@guard_tool_errors(TOOL_NAME)
def check_limitation(args: LimitationArgs) -> ToolResult:
    """Estimate whether the regular limitation period has run out.

    Args:
        args: Claim date, optional knowledge date and optional date of the last
            acknowledgment (part payment, interest payment, other acknowledgment).

    Returns:
        A :class:`ToolResult` whose ``result`` holds the end of the period and
        whether it has passed, never a statement that the claim *is*
        time-barred. ``assumptions`` records that limitation is a defence the
        debtor must raise and, where it applies, that ``claim_date`` was used as
        the knowledge date. ``missing_information`` always asks about payments,
        payment plans and acknowledgments (BGB § 212) and about a served payment
        order (BGB § 204 (1) no. 3); titled claims (BGB § 197) are listed as not
        covered. An acknowledgment inside the period restarts it (BGB § 212).
        Claims arising before 2002-01-01 yield ``not_applicable_reason``.

    Related: FR-12 AC1, FR-12 AC2, FR-12 AC3, FR-12 AC4, FR-12 AC5, FR-10 AC4, FR-21 AC7
    """
    today = _today()
    if args.claim_date < config.LIMITATION_EARLIEST_CLAIM_DATE:
        return not_applicable(
            TOOL_NAME,
            "Claims that arose before 1 January 2002 fall under the old limitation law, which "
            "this tool does not cover.",
            legal_basis=["BGB § 195"],
        )
    for label, value in (
        ("claim date", args.claim_date),
        ("knowledge date", args.knowledge_date),
        ("acknowledgment date", args.last_acknowledgment_date),
    ):
        if value is not None and value > today:
            return not_applicable(TOOL_NAME, f"The {label} {value.isoformat()} lies in the future.")
    if args.last_acknowledgment_date and args.last_acknowledgment_date < args.claim_date:
        return not_applicable(
            TOOL_NAME, "The acknowledgment date lies before the date the claim arose."
        )

    regular_end = end_of_limitation_period(args.claim_date, args.knowledge_date)
    period_end = regular_end
    assumptions = [
        "Limitation is a defence: it only takes effect if the debtor raises it (BGB § 214 (1)).",
        "Only the regular three-year period is estimated, starting at the end of the year in "
        "which the claim arose and the creditor knew of it (BGB §§ 195, 199 (1)).",
    ]
    if args.knowledge_date is None:
        assumptions.append(
            f"The creditor is assumed to have known of the claim and the debtor in "
            f"{args.claim_date.year}, the year the claim arose."
        )
    restarted = False
    ack = args.last_acknowledgment_date
    if ack is not None and ack <= regular_end:
        restart_end = _plus_years(ack, config.LIMITATION_PERIOD_YEARS)
        restarted = restart_end > regular_end
        period_end = max(regular_end, restart_end)
        assumptions.append(
            f"The acknowledgment on {ack.isoformat()} restarts the period (BGB § 212 (1) no. 1); "
            "a restart never shortens it."
        )
    elif ack is not None:
        assumptions.append(
            f"The acknowledgment on {ack.isoformat()} came after the regular period had ended, "
            "so it does not restart it here. It may still have legal effects that this tool "
            "does not assess."
        )

    return tool_result(
        TOOL_NAME,
        {
            "claim_date": args.claim_date.isoformat(),
            "period_end": period_end.isoformat(),
            "regular_period_ended": today > period_end,
            "restarted_by_acknowledgment": restarted,
        },
        assumptions=assumptions,
        missing_information=list(_ALWAYS_ASK),
        legal_basis=["BGB § 195", "BGB § 199 (1)", "BGB § 212 (1)", "BGB § 214 (1)"],
    )
