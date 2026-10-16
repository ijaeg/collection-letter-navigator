"""FR-11 ``calculate_objection_deadline``: the last day to object in court.

Two weeks from service (ZPO §§ 692 (1) no. 3, 700 (1), 339 (1)), counted with
ZPO § 222 and BGB §§ 187 (1), 188 (2); a period ending on a Saturday, Sunday or
public holiday runs to the next working day (ZPO § 222 (2)). The tool never
says whether to object, only when the period ends and what it assumed.

Related: FR-11, FR-01 AC3, FR-10 AC2, FR-21 AC2, §12 D-4, §12 D-6
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from collection_letter_navigator.schemas import CourtDocumentType, ToolResult

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "calculate_objection_deadline"


class ObjectionDeadlineArgs(BaseModel):
    """Arguments of :func:`calculate_objection_deadline`.

    Related: FR-10 AC1, FR-11
    """

    model_config = ConfigDict(extra="forbid")

    document_type: CourtDocumentType = Field(
        description="Which court document was served; 'unclear' uses the stricter reading.",
    )
    service_date: date = Field(
        description="Date the document was served, not in the future.",
    )
    federal_state: str | None = Field(
        default=None,
        description="German federal state code for public holidays, e.g. 'SN'; optional.",
    )


def is_working_day(day: date, federal_state: str | None = None) -> bool:
    """Decide whether a day counts as a working day for ZPO § 222 (2).

    Args:
        day: The day to check.
        federal_state: Federal state code, or None for nationwide holidays only.

    Returns:
        False for Saturdays, Sundays and public holidays, True otherwise.

    Related: FR-11 AC1, FR-11 AC2, §12 D-6
    """
    raise NotImplementedError("FR-11 AC1: Saturdays, Sundays and holidays are not working days")


def next_working_day(day: date, federal_state: str | None = None) -> date:
    """Move a day forward to the next working day, if needed.

    Args:
        day: The calculated end of the period.
        federal_state: Federal state code, or None for nationwide holidays only.

    Returns:
        ``day`` itself if it is a working day, otherwise the next working day.

    Related: FR-11 AC1, FR-11 AC2
    """
    raise NotImplementedError("FR-11 AC1: move the period end to the next working day")


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
    raise NotImplementedError("FR-11 AC1: two weeks from service under ZPO § 222")
