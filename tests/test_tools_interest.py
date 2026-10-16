"""Tests for :mod:`collection_letter_navigator.tools.interest`.

At least 4 cases against hand-calculated reference values, per FR-13 AC5.

Related: FR-13, FR-10 AC4, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator.tools import interest


def test_module_imports() -> None:
    """The interest tool module imports."""
    assert interest.calculate_default_interest is not None


@pytest.mark.skip(reason="not implemented: FR-13 AC1")
def test_fr13_ac1_single_half_year_matches_reference_value() -> None:
    """A period inside one half-year matches the hand-calculated amount."""


@pytest.mark.skip(reason="not implemented: FR-13 AC1")
def test_fr13_ac1_period_spanning_a_base_rate_change() -> None:
    """Each half-year uses the base rate in force in that half-year."""


@pytest.mark.skip(reason="not implemented: FR-13 AC1")
def test_fr13_ac1_rate_is_base_rate_plus_five_points() -> None:
    """The consumer rate is the base rate plus 5 percentage points."""


@pytest.mark.skip(reason="not implemented: FR-13 AC1")
def test_fr13_ac1_negative_base_rate_is_handled() -> None:
    """A negative base rate still yields the correct consumer rate."""


@pytest.mark.skip(reason="not implemented: FR-13 AC2")
def test_fr13_ac2_day_count_convention_is_documented_in_assumptions() -> None:
    """The assumptions name the day-count convention used."""


@pytest.mark.skip(reason="not implemented: FR-13 AC2")
def test_fr13_ac2_result_lists_periods_rates_and_partial_amounts() -> None:
    """The result is itemised, not a single number."""


@pytest.mark.skip(reason="not implemented: FR-13 AC3")
def test_fr13_ac3_start_of_default_is_an_input_not_a_finding() -> None:
    """The assumptions state that BGB § 286 is not applied by the tool."""


@pytest.mark.skip(reason="not implemented: FR-13 AC4")
def test_fr13_ac4_date_outside_the_base_rate_table_returns_not_applicable() -> None:
    """A date the CSV does not cover produces no result."""


@pytest.mark.skip(reason="not implemented: FR-10 AC3")
def test_fr10_ac3_principal_above_the_limit_returns_not_applicable() -> None:
    """A principal over 100,000 EUR is refused, not calculated."""
