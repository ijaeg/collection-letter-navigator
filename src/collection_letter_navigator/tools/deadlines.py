"""FR-11 ``calculate_objection_deadline``: the last day to object in court.

Two weeks from service (ZPO §§ 692 (1) no. 3, 700 (1), 339 (1)), counted with
ZPO § 222 and BGB §§ 187 (1), 188 (2); a period ending on a Saturday, Sunday or
public holiday runs to the next working day (ZPO § 222 (2)). The tool never
says whether to object, only when the period ends and what it assumed.

Related: FR-11, FR-01 AC3, FR-10 AC2, FR-21 AC2, §12 D-4, §12 D-6
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

import holidays
from pydantic import BaseModel, ConfigDict, Field

from collection_letter_navigator import config
from collection_letter_navigator.schemas import CourtDocumentType, ToolResult
from collection_letter_navigator.tools.contract import (
    guard_tool_errors,
    not_applicable,
    tool_result,
)

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "calculate_objection_deadline"

#: Federal state codes accepted for public holidays (FR-11 AC2, D-6).
FederalState = Literal[
    "BB", "BE", "BW", "BY", "HB", "HE", "HH", "MV", "NI", "NW", "RP", "SH", "SL", "SN", "ST", "TH"
]

#: Tool description shown to the model (FR-10 AC1).
DESCRIPTION = (
    "Compute the last day of the two-week period to object to a German court payment order "
    "(Mahnbescheid, objection = Widerspruch) or to file an Einspruch against an enforcement order "
    "(Vollstreckungsbescheid). Use it whenever the user asks until when they can react to a "
    "court document. Needs the date of service as YYYY-MM-DD; use 'unclear' if the document "
    "type is unknown."
)


class ObjectionDeadlineArgs(BaseModel):
    """Arguments of :func:`calculate_objection_deadline`.

    Related: FR-10 AC1, FR-11
    """

    model_config = ConfigDict(extra="forbid")

    document_type: CourtDocumentType = Field(
        description="Which court document was served; 'unclear' uses the stricter reading.",
    )
    service_date: date = Field(
        description="Date the document was served (YYYY-MM-DD), not in the future.",
    )
    federal_state: FederalState | None = Field(
        default=None,
        description="German federal state code for public holidays, e.g. 'SN'; optional.",
    )


def _today() -> date:
    """Today's date; a function so that tests can fix it."""
    return date.today()


def is_working_day(day: date, federal_state: str | None = None) -> bool:
    """Decide whether a day counts as a working day for ZPO § 222 (2).

    Args:
        day: The day to check.
        federal_state: Federal state code, or None for nationwide holidays only.

    Returns:
        False for Saturdays, Sundays and public holidays, True otherwise.

    Related: FR-11 AC1, FR-11 AC2, §12 D-6
    """
    if day.weekday() >= 5:  # Saturday or Sunday
        return False
    public = holidays.country_holidays(config.HOLIDAY_COUNTRY, subdiv=federal_state, years=day.year)
    return day not in public


def next_working_day(day: date, federal_state: str | None = None) -> date:
    """Move a day forward to the next working day, if needed.

    Args:
        day: The calculated end of the period.
        federal_state: Federal state code, or None for nationwide holidays only.

    Returns:
        ``day`` itself if it is a working day, otherwise the next working day.

    Related: FR-11 AC1, FR-11 AC2
    """
    while not is_working_day(day, federal_state):
        day += timedelta(days=1)
    return day


@guard_tool_errors(TOOL_NAME)
def calculate_objection_deadline(args: ObjectionDeadlineArgs) -> ToolResult:
    """Compute the last day to object to a court payment or enforcement order.

    Args:
        args: Document type, service date and optional federal state.

    Returns:
        A :class:`ToolResult` whose ``result`` holds the end of the period, with
        the counting rules and the holiday scope in ``assumptions``. For
        ``mahnbescheid`` the result notes that an objection remains possible
        while no enforcement order has been issued (ZPO § 694 (1)); for
        ``vollstreckungsbescheid`` that the period is strict. A service date in
        the future yields ``not_applicable_reason``.

    Related: FR-11 AC1, FR-11 AC2, FR-11 AC3, FR-11 AC4, FR-10 AC2, FR-10 AC3
    """
    if args.service_date > _today():
        return not_applicable(
            TOOL_NAME,
            f"The service date {args.service_date.isoformat()} lies in the future.",
            missing_information=["The date on which the document was actually delivered."],
        )
    strict = args.document_type != "mahnbescheid"  # 'unclear' takes the stricter reading
    # BGB § 187 (1): the day of service does not count; § 188 (2): a period in weeks ends
    # on the weekday that has the same name as the day of service, two weeks later.
    calculated_end = args.service_date + timedelta(weeks=config.OBJECTION_PERIOD_WEEKS)
    period_end = next_working_day(calculated_end, args.federal_state)  # ZPO § 222 (2)

    assumptions = [
        f"{args.service_date.isoformat()} is used as the date of service (the day the document "
        "was delivered).",
        "The day of service is not counted; the two weeks end on the same weekday two weeks "
        "later (BGB §§ 187 (1), 188 (2)).",
    ]
    if args.federal_state:
        assumptions.append(
            f"Public holidays of {args.federal_state} are taken into account; legally, the "
            "holidays at the court's location matter."
        )
    else:
        assumptions.append(
            "Only nationwide public holidays are taken into account; a holiday in the federal "
            "state of the court could move the end of the period by a day."
        )
    if period_end != calculated_end:
        assumptions.append(
            f"The period would end on {calculated_end.strftime('%A')}, "
            f"{calculated_end.isoformat()}, which is not a working day, so it ends on the next "
            "working day (ZPO § 222 (2))."
        )
    if args.document_type == "unclear":
        assumptions.append(
            "The document type is unclear, so the stricter rule for an enforcement order "
            "(Vollstreckungsbescheid) is used."
        )

    if strict:
        procedure = "Einspruch"
        note = (
            "The two-week period for an Einspruch is a strict deadline (Notfrist); it cannot be "
            "extended (ZPO §§ 700 (1), 339 (1))."
        )
        legal_basis = [
            "ZPO § 700 (1)",
            "ZPO § 339 (1)",
            "ZPO § 222",
            "BGB § 187 (1)",
            "BGB § 188 (2)",
        ]
        missing = [
            "Was the document served abroad? Then the period is one month (ZPO § 339 (2)).",
        ]
    else:
        procedure = "Widerspruch"
        note = (
            "After the two weeks, an objection is still possible as long as no enforcement order "
            "has been issued (ZPO § 694 (1))."
        )
        legal_basis = [
            "ZPO § 692 (1) no. 3",
            "ZPO § 694 (1)",
            "ZPO § 222",
            "BGB § 187 (1)",
            "BGB § 188 (2)",
        ]
        missing = []
    missing.append("The exact date of service, if it differs from the date used here.")

    return tool_result(
        TOOL_NAME,
        {
            "document_type": args.document_type,
            "procedure": procedure,
            "service_date": args.service_date.isoformat(),
            "period_end": period_end.isoformat(),
            "period_end_weekday": period_end.strftime("%A"),
            "strict_deadline": strict,
            "note": note,
        },
        assumptions=assumptions,
        missing_information=missing,
        legal_basis=legal_basis,
    )
