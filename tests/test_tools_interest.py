"""Tests for :mod:`collection_letter_navigator.tools.interest`.

Reference values for FR-13 AC5, calculated by hand: principal × (base rate + 5)
/ 100 × days / 365, both days counted, each period rounded to cents. Base rates
from data/base_rates.csv (Deutsche Bundesbank).

Related: FR-13, FR-10 AC4, NFR-06
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from collection_letter_navigator.schemas import ToolResult
from collection_letter_navigator.tools import interest
from collection_letter_navigator.tools.interest import DefaultInterestArgs


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """'Today' for the default end date."""
    monkeypatch.setattr(interest, "_today", lambda: date(2026, 10, 19))


def run(principal: float, start: date, end: date | None = None) -> ToolResult:
    """Call the tool."""
    args = DefaultInterestArgs(principal=principal, start_date=start, end_date=end)
    return interest.calculate_default_interest(args)


def total(outcome: ToolResult) -> float:
    """The total interest from a successful result."""
    assert outcome.result is not None, outcome.not_applicable_reason
    return float(outcome.result["total_interest_eur"])


def test_module_imports() -> None:
    """The interest tool module imports."""
    assert interest.calculate_default_interest is not None


def test_d5_base_rate_table_is_complete_and_sourced() -> None:
    """Every half-year since 2002 has a rate and a source (D-5)."""
    rates = interest.load_base_rates()
    assert rates[0].valid_from == date(2002, 1, 1)
    assert (
        len(rates) == (rates[-1].valid_from.year - 2002) * 2 + (rates[-1].valid_from.month > 6) + 1
    )
    assert all("Bundesbank" in rate.source for rate in rates)
    assert {r.valid_from.month for r in rates} == {1, 7}


def test_fr13_ac1_single_half_year_matches_reference_value() -> None:
    """1,000 EUR, 2026-01-01 to 2026-06-30: 181 days at 6.27 % = 31.09 EUR."""
    assert total(run(1000, date(2026, 1, 1), date(2026, 6, 30))) == pytest.approx(31.09)


def test_fr13_ac1_period_spanning_a_base_rate_change() -> None:
    """1,000 EUR, 2026-03-01 to 2026-08-31: 122 days at 6.27 % + 62 days at 6.52 %."""
    outcome = run(1000, date(2026, 3, 1), date(2026, 8, 31))
    periods = outcome.result["periods"] if outcome.result else []
    assert [(p["days"], p["interest_rate_percent"], p["interest_eur"]) for p in periods] == [
        (122, 6.27, 20.96),
        (62, 6.52, 11.08),
    ]
    assert total(outcome) == pytest.approx(32.04)


def test_fr13_ac1_rate_is_base_rate_plus_five_points() -> None:
    """2,500 EUR across the 2025 change: 47 days at 8.37 % + 45 days at 7.27 % = 49.35 EUR."""
    outcome = run(2500, date(2024, 11, 15), date(2025, 2, 14))
    rates = [p["interest_rate_percent"] for p in (outcome.result or {})["periods"]]
    assert rates == [8.37, 7.27]
    assert total(outcome) == pytest.approx(49.35)


def test_fr13_ac1_negative_base_rate_is_handled() -> None:
    """500 EUR in 2020 (base rate -0.88 %): 4.12 %, 182 + 184 days = 20.65 EUR."""
    outcome = run(500, date(2020, 1, 1), date(2020, 12, 31))
    assert {p["interest_rate_percent"] for p in (outcome.result or {})["periods"]} == {4.12}
    assert total(outcome) == pytest.approx(20.65)


def test_fr13_ac2_day_count_convention_is_documented_in_assumptions() -> None:
    """The assumptions name the day-count convention used."""
    outcome = run(1000, date(2026, 1, 1), date(2026, 6, 30))
    assert any("/ 365" in a and "both included" in a for a in outcome.assumptions)


def test_fr13_ac2_result_lists_periods_rates_and_partial_amounts() -> None:
    """The result is itemised, not a single number."""
    period = (run(1000, date(2026, 1, 1), date(2026, 6, 30)).result or {})["periods"][0]
    assert set(period) == {
        "from",
        "to",
        "days",
        "base_rate_percent",
        "interest_rate_percent",
        "interest_eur",
    }


def test_fr13_ac3_start_of_default_is_an_input_not_a_finding() -> None:
    """The assumptions state that BGB § 286 is not applied by the tool."""
    outcome = run(1000, date(2026, 1, 1), date(2026, 6, 30))
    assert any("does not check when default began (BGB § 286)" in a for a in outcome.assumptions)


def test_fr13_end_date_defaults_to_today() -> None:
    """Without an end date, interest runs to 'today'."""
    outcome = run(1000, date(2026, 9, 1))
    assert outcome.result and outcome.result["end_date"] == "2026-10-19"


def test_fr13_ac4_date_outside_the_base_rate_table_returns_not_applicable() -> None:
    """A date the CSV does not cover produces no result."""
    for start, end in (
        (date(2001, 6, 1), date(2002, 6, 1)),
        (date(2026, 11, 1), date(2027, 1, 31)),
    ):
        outcome = run(1000, start, end)
        assert outcome.result is None
        assert "base-rate table covers" in (outcome.not_applicable_reason or "")


def test_fr13_ac4_end_before_start_returns_not_applicable() -> None:
    """Swapped dates are reported back."""
    assert run(1000, date(2026, 6, 1), date(2026, 1, 1)).result is None


def test_fr10_ac3_principal_above_the_limit_is_rejected_by_the_schema() -> None:
    """A principal over 100,000 EUR is refused, not calculated (runner: FR-10 AC3)."""
    with pytest.raises(ValidationError, match="principal"):
        DefaultInterestArgs.model_validate({"principal": 100_001, "start_date": "2026-01-01"})


def test_fr13_ac1_broken_table_row_is_reported(tmp_path: Path) -> None:
    """A malformed CSV row fails loudly when the table is read (D-5)."""
    path = tmp_path / "rates.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["valid_from", "rate_percent", "source"])
        writer.writerow(["2026-01-01", "one point two", "x"])
    with pytest.raises(ValueError):
        interest.load_base_rates(path)
