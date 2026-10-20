"""FR-13 ``calculate_default_interest``: the statutory maximum for a consumer.

Base rate (BGB § 247) plus five percentage points (BGB § 288 (1)), applied per
half-year with the base rate in force in that half-year, read from
``data/base_rates.csv``. The tool does not decide *when* default started: the
start date is an input and this is stated in the assumptions.

Related: FR-13, FR-10 AC2, §12 D-4, §12 D-5
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from collection_letter_navigator import config
from collection_letter_navigator.schemas import ToolResult
from collection_letter_navigator.tools.contract import (
    guard_tool_errors,
    not_applicable,
    tool_result,
)

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "calculate_default_interest"

#: Tool description shown to the model (FR-10 AC1).
DESCRIPTION = (
    "Calculate the maximum statutory default interest (Verzugszinsen) a consumer can be charged: "
    "base rate plus 5 percentage points, per half-year. Use it when the user asks whether the "
    "interest in a letter is too high. Needs the principal in EUR and the first day of default "
    "as YYYY-MM-DD; the end date defaults to today. The tool does not decide when default began."
)

#: Days per year in the day-count convention (FR-13 AC2).
DAYS_PER_YEAR = 365


class DefaultInterestArgs(BaseModel):
    """Arguments of :func:`calculate_default_interest`.

    Related: FR-10 AC1, FR-13
    """

    model_config = ConfigDict(extra="forbid")

    principal: float = Field(
        gt=config.MIN_PRINCIPAL_EUR,
        le=config.MAX_PRINCIPAL_EUR,
        description="Principal claim in EUR, greater than 0 and at most 100,000.",
    )
    start_date: date = Field(
        description="First day of the default period (YYYY-MM-DD); the tool does not determine it.",
    )
    end_date: date | None = Field(
        default=None,
        description="Last day of the default period (YYYY-MM-DD); defaults to today.",
    )


class BaseRatePeriod(BaseModel):
    """One row of ``data/base_rates.csv``: a base rate and when it took effect.

    Related: FR-13 AC1, §12 D-5
    """

    model_config = ConfigDict(extra="forbid")

    valid_from: date = Field(description="First day the rate applies, 1 January or 1 July.")
    rate_percent: float = Field(description="Base rate in percent (BGB § 247).")
    source: str = Field(description="Where the value was taken from, with its retrieval date.")


def _today() -> date:
    """Today's date; a function so that tests can fix it."""
    return date.today()


def load_base_rates(path: Path | None = None) -> list[BaseRatePeriod]:
    """Read the base-rate table.

    Args:
        path: CSV file; defaults to :data:`config.BASE_RATES_PATH`.

    Returns:
        The rates, sorted by ``valid_from``.

    Raises:
        FileNotFoundError: If the table is missing.
        ValueError: If a row cannot be parsed or the table is empty.

    Related: FR-13 AC1, §12 D-5
    """
    source = path or config.BASE_RATES_PATH
    with source.open(encoding="utf-8", newline="") as handle:
        rows = [BaseRatePeriod.model_validate(row) for row in csv.DictReader(handle)]
    if not rows:
        raise ValueError(f"{source} contains no base rates.")
    return sorted(rows, key=lambda row: row.valid_from)


def _covered_until(rates: list[BaseRatePeriod]) -> date:
    """Last day covered by the table: the end of the half-year of the latest rate."""
    last = rates[-1].valid_from
    return date(last.year, 6, 30) if last.month < 7 else date(last.year, 12, 31)


def split_into_rate_periods(
    start_date: date,
    end_date: date,
    rates: list[BaseRatePeriod],
) -> list[tuple[date, date, float]]:
    """Cut the default period at every base-rate change.

    Args:
        start_date: First day of the default period.
        end_date: Last day of the default period.
        rates: The base-rate table.

    Returns:
        One ``(from, to, rate_percent)`` triple per half-year segment.

    Raises:
        ValueError: If a date lies outside the range covered by ``rates``.

    Related: FR-13 AC1, FR-13 AC4
    """
    first, last = rates[0].valid_from, _covered_until(rates)
    if start_date < first or end_date > last:
        raise ValueError(
            f"The base-rate table covers {first.isoformat()} to {last.isoformat()} only."
        )
    segments = []
    for index, rate in enumerate(rates):
        valid_to = (
            rates[index + 1].valid_from - timedelta(days=1) if index + 1 < len(rates) else last
        )
        seg_start, seg_end = max(start_date, rate.valid_from), min(end_date, valid_to)
        if seg_start <= seg_end:
            segments.append((seg_start, seg_end, rate.rate_percent))
    return segments


def _cents(value: Decimal) -> Decimal:
    """Round to cents, half up."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@guard_tool_errors(TOOL_NAME)
def calculate_default_interest(args: DefaultInterestArgs) -> ToolResult:
    """Calculate the maximum statutory default interest for a consumer.

    Args:
        args: Principal, start date and optional end date.

    Returns:
        A :class:`ToolResult` whose ``result`` lists the periods, rates and
        partial amounts plus the total. ``assumptions`` documents the day-count
        convention and that the start of default is an input, not a finding of
        the tool. A date outside the range covered by ``base_rates.csv`` yields
        ``not_applicable_reason``.

    Related: FR-13 AC1, FR-13 AC2, FR-13 AC3, FR-13 AC4, FR-10 AC2, FR-10 AC4
    """
    end_date = args.end_date or _today()
    if end_date < args.start_date:
        return not_applicable(TOOL_NAME, "The end date lies before the start date.")
    rates = load_base_rates()
    try:
        segments = split_into_rate_periods(args.start_date, end_date, rates)
    except ValueError as error:
        return not_applicable(
            TOOL_NAME,
            f"{error} Interest for other dates cannot be calculated with it.",
            legal_basis=["BGB § 247"],
        )

    principal = Decimal(str(args.principal))
    markup = Decimal(str(config.DEFAULT_INTEREST_MARKUP_POINTS))
    periods = []
    total = Decimal("0")
    for seg_start, seg_end, base_rate in segments:
        days = (seg_end - seg_start).days + 1  # both days count
        rate = Decimal(str(base_rate)) + markup  # BGB § 288 (1): base rate + 5 points
        amount = _cents(principal * rate / Decimal(100) * Decimal(days) / Decimal(DAYS_PER_YEAR))
        total += amount
        periods.append(
            {
                "from": seg_start.isoformat(),
                "to": seg_end.isoformat(),
                "days": days,
                "base_rate_percent": float(base_rate),
                "interest_rate_percent": float(rate),
                "interest_eur": float(amount),
            }
        )
    return tool_result(
        TOOL_NAME,
        {
            "principal_eur": float(principal),
            "start_date": args.start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "periods": periods,
            "total_interest_eur": float(total),
        },
        assumptions=[
            f"Default is assumed to start on {args.start_date.isoformat()}; the tool does not "
            "check when default began (BGB § 286).",
            "Consumer rate: base rate plus 5 percentage points (BGB § 288 (1)); the higher rate "
            "for businesses (§ 288 (2)) is not applied.",
            f"Day count: every day from start to end date counts, both included; interest per "
            f"day = principal × rate / {DAYS_PER_YEAR}. Each period is rounded to cents.",
            "Simple interest on the principal only, no interest on interest.",
            f"Base rates from {rates[-1].source}.",
        ],
        missing_information=[
            "The date on which default actually began, e.g. the date of the first reminder "
            "after the due date (BGB § 286)."
        ],
        legal_basis=["BGB § 288 (1)", "BGB § 247"],
    )
