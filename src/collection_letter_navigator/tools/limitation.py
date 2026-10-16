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

from collection_letter_navigator.schemas import ToolResult

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "check_limitation"


class LimitationArgs(BaseModel):
    """Arguments of :func:`check_limitation`.

    Related: FR-10 AC1, FR-12
    """

    model_config = ConfigDict(extra="forbid")

    claim_date: date = Field(
        description="Date the claim arose, e.g. the due date of the invoice.",
    )
    knowledge_date: date | None = Field(
        default=None,
        description="Date the creditor learned of the claim; defaults to claim_date.",
    )


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
    raise NotImplementedError("FR-12 AC1: three years from the end of the year (BGB § 199 (1))")


def check_limitation(args: LimitationArgs) -> ToolResult:
    """Estimate whether the regular limitation period has run out.

    Args:
        args: Claim date and optional knowledge date.

    Returns:
        A :class:`ToolResult` whose ``result`` holds the end of the period and
        whether it has passed, never a statement that the claim *is*
        time-barred. ``assumptions`` records that limitation is a defence the
        debtor must raise and, where it applies, that ``claim_date`` was used as
        the knowledge date. ``missing_information`` always asks about payments,
        payment plans and acknowledgments (BGB § 212) and about a served payment
        order (BGB § 204 (1) no. 3); suspension, restart and titled claims
        (BGB § 197) are listed as not covered. Claims arising before
        2002-01-01 yield ``not_applicable_reason``.

    Related: FR-12 AC1, FR-12 AC2, FR-12 AC3, FR-12 AC5, FR-10 AC4, FR-21 AC7
    """
    raise NotImplementedError("FR-12 AC1: estimate the regular limitation period")
