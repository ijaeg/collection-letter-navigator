"""Tests for :mod:`collection_letter_navigator.tools.deadlines`.

At least 8 date cases, per FR-11 AC5.

Related: FR-11, FR-10 AC4, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator.tools import deadlines


def test_module_imports() -> None:
    """The deadline tool module imports."""
    assert deadlines.calculate_objection_deadline is not None


@pytest.mark.skip(reason="not implemented: FR-11 AC1")
def test_fr11_ac1_two_weeks_from_service_on_a_working_day() -> None:
    """The plain case: service on a Monday, period ends two weeks later."""


@pytest.mark.skip(reason="not implemented: FR-11 AC1")
def test_fr11_ac1_period_ends_on_saturday() -> None:
    """A period ending on a Saturday runs to the following Monday."""


@pytest.mark.skip(reason="not implemented: FR-11 AC1")
def test_fr11_ac1_period_ends_on_sunday() -> None:
    """A period ending on a Sunday runs to the following Monday."""


@pytest.mark.skip(reason="not implemented: FR-11 AC1")
def test_fr11_ac1_period_ends_on_public_holiday() -> None:
    """A period ending on a nationwide holiday runs to the next working day."""


@pytest.mark.skip(reason="not implemented: FR-11 AC1")
def test_fr11_ac1_period_crosses_the_turn_of_the_year() -> None:
    """Service in late December ends in the following January."""


@pytest.mark.skip(reason="not implemented: FR-11 AC1")
def test_fr11_ac1_service_day_itself_does_not_count() -> None:
    """Counting starts the day after service (BGB § 187 (1))."""


@pytest.mark.skip(reason="not implemented: FR-11 AC2")
def test_fr11_ac2_without_federal_state_only_nationwide_holidays_apply() -> None:
    """The assumption is listed and a state-only holiday does not move the end."""


@pytest.mark.skip(reason="not implemented: FR-11 AC2")
def test_fr11_ac2_federal_state_holiday_moves_the_period_end() -> None:
    """With a federal state given, its holidays are taken into account."""


@pytest.mark.skip(reason="not implemented: FR-11 AC3")
def test_fr11_ac3_mahnbescheid_notes_objection_still_possible() -> None:
    """The result mentions ZPO § 694 (1) for a payment order."""


@pytest.mark.skip(reason="not implemented: FR-11 AC3")
def test_fr11_ac3_vollstreckungsbescheid_notes_strict_period() -> None:
    """The result states that the Einspruch period is strict."""


@pytest.mark.skip(reason="not implemented: FR-11 AC4")
def test_fr11_ac4_unclear_document_uses_the_stricter_reading() -> None:
    """'unclear' is treated as an enforcement order and says so."""


@pytest.mark.skip(reason="not implemented: FR-11 AC4")
def test_fr11_ac4_triage_date_is_named_as_assumed_date_of_service() -> None:
    """The delivery date from the triage appears in the assumptions."""


@pytest.mark.skip(reason="not implemented: FR-10 AC3")
def test_fr10_ac3_future_service_date_returns_not_applicable() -> None:
    """A service date in the future produces no result and says why."""
