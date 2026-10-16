"""FR-13 ``calculate_default_interest``: the statutory maximum for a consumer.

Base rate (BGB § 247) plus five percentage points (BGB § 288 (1)), applied per
half-year with the base rate in force in that half-year, read from
``data/base_rates.csv``. The tool does not decide *when* default started: the
start date is an input and this is stated in the assumptions.

Related: FR-13, FR-10 AC2, §12 D-4, §12 D-5
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from collection_letter_navigator.schemas import ToolResult

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "calculate_default_interest"


class DefaultInterestArgs(BaseModel):
    """Arguments of :func:`calculate_default_interest`.

    Related: FR-10 AC1, FR-13
    """

    model_config = ConfigDict(extra="forbid")

    principal: float = Field(
        gt=0,
        le=100_000,
        description="Principal claim in EUR, greater than 0 and at most 100,000.",
    )
    start_date: date = Field(
        description="First day of the default period; the tool does not determine it.",
    )
    end_date: date | None = Field(
        default=None,
        description="Last day of the default period; defaults to today.",
    )


class BaseRatePeriod(BaseModel):
    """One row of ``data/base_rates.csv``: a base rate and when it took effect.

    Related: FR-13 AC1, §12 D-5
    """

    model_config = ConfigDict(extra="forbid")

    valid_from: date = Field(description="First day the rate applies, 1 January or 1 July.")
    rate_percent: float = Field(description="Base rate in percent (BGB § 247).")
    source: str = Field(description="Where the value was taken from, with its retrieval date.")


def load_base_rates(path: Path | None = None) -> list[BaseRatePeriod]:
    """Read the base-rate table.

    Args:
        path: CSV file; defaults to :data:`config.BASE_RATES_PATH`.

    Returns:
        The rates, sorted by ``valid_from``.

    Raises:
        FileNotFoundError: If the table is missing.
        ValueError: If a row cannot be parsed.

    Related: FR-13 AC1, §12 D-5
    """
    raise NotImplementedError("FR-13 AC1: read the Bundesbank base rates with source and date")


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
    raise NotImplementedError("FR-13 AC1: split the period at each base-rate change")


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
    raise NotImplementedError("FR-13 AC1: base rate plus 5 points, per half-year period")
