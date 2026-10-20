"""Tests for :mod:`collection_letter_navigator.tools.deadlines`.

Reference cases for FR-11 AC5, checked by hand against a calendar: two weeks
from service, the day of service not counted (BGB § 187 (1)), the end on the
same weekday (BGB § 188 (2)), moved to the next working day (ZPO § 222 (2)).

Related: FR-11, FR-10 AC4, NFR-06
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from collection_letter_navigator.schemas import ToolResult
from collection_letter_navigator.tools import deadlines
from collection_letter_navigator.tools.deadlines import ObjectionDeadlineArgs


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """'Today' is far enough ahead for every reference case."""
    monkeypatch.setattr(deadlines, "_today", lambda: date(2027, 6, 1))


def run(service: date, document: str = "mahnbescheid", state: str | None = None) -> ToolResult:
    """Call the tool with one service date."""
    args = ObjectionDeadlineArgs.model_validate(
        {"document_type": document, "service_date": service, "federal_state": state}
    )
    return deadlines.calculate_objection_deadline(args)


def period_end(outcome: ToolResult) -> str:
    """The end of the period from a successful result."""
    assert outcome.result is not None, outcome.not_applicable_reason
    return str(outcome.result["period_end"])


def test_module_imports() -> None:
    """The deadline tool module imports."""
    assert deadlines.calculate_objection_deadline is not None


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        (date(2026, 10, 12), "2026-10-26"),  # Monday → Monday
        (date(2026, 11, 7), "2026-11-23"),  # Saturday → Saturday → Monday
        (date(2026, 11, 8), "2026-11-23"),  # Sunday → Sunday → Monday
        (date(2026, 12, 11), "2026-12-28"),  # Friday 25.12. → 26.12., weekend → Monday
        (date(2027, 3, 12), "2027-03-30"),  # Good Friday, weekend, Easter Monday → Tuesday
        (date(2026, 12, 23), "2027-01-06"),  # turn of the year
    ],
)
def test_fr11_ac5_reference_cases(service: date, expected: str) -> None:
    """Six hand-checked cases; see the tool brief docs/tools/calculate_objection_deadline.md."""
    assert period_end(run(service)) == expected


def test_fr11_ac1_two_weeks_from_service_on_a_working_day() -> None:
    """The plain case: service on a Monday, period ends two weeks later."""
    assert period_end(run(date(2026, 10, 12))) == "2026-10-26"


def test_fr11_ac1_period_ends_on_saturday() -> None:
    """A period ending on a Saturday runs to the following Monday."""
    outcome = run(date(2026, 11, 7))
    assert period_end(outcome) == "2026-11-23"
    assert any("ZPO § 222 (2)" in a for a in outcome.assumptions)


def test_fr11_ac1_period_ends_on_sunday() -> None:
    """A period ending on a Sunday runs to the following Monday."""
    assert period_end(run(date(2026, 11, 8))) == "2026-11-23"


def test_fr11_ac1_period_ends_on_public_holiday() -> None:
    """A period ending on a nationwide holiday runs to the next working day."""
    assert period_end(run(date(2026, 12, 11))) == "2026-12-28"


def test_fr11_ac1_period_crosses_the_turn_of_the_year() -> None:
    """Service in late December ends in the following January."""
    assert period_end(run(date(2026, 12, 23))) == "2027-01-06"


def test_fr11_ac1_service_day_itself_does_not_count() -> None:
    """Counting starts the day after service (BGB § 187 (1)): Thursday → Thursday."""
    outcome = run(date(2026, 10, 15))
    assert period_end(outcome) == "2026-10-29"
    assert outcome.result and outcome.result["period_end_weekday"] == "Thursday"


def test_fr11_ac2_without_federal_state_only_nationwide_holidays_apply() -> None:
    """The assumption is listed and a state-only holiday does not move the end."""
    outcome = run(date(2026, 12, 23))  # 6 January is a holiday in BY, BW and ST only
    assert period_end(outcome) == "2027-01-06"
    assert any("nationwide" in a for a in outcome.assumptions)


def test_fr11_ac2_federal_state_holiday_moves_the_period_end() -> None:
    """With a federal state given, its holidays are taken into account."""
    outcome = run(date(2026, 12, 23), state="BY")
    assert period_end(outcome) == "2027-01-07"
    assert any("BY" in a for a in outcome.assumptions)


def test_fr11_ac3_mahnbescheid_notes_objection_still_possible() -> None:
    """The result mentions ZPO § 694 (1) for a payment order."""
    outcome = run(date(2026, 10, 12))
    assert outcome.result and outcome.result["procedure"] == "Widerspruch"
    assert outcome.result["strict_deadline"] is False
    assert "ZPO § 694 (1)" in str(outcome.result["note"])


def test_fr11_ac3_vollstreckungsbescheid_notes_strict_period() -> None:
    """The result states that the Einspruch period is strict and asks about service abroad."""
    outcome = run(date(2026, 10, 12), document="vollstreckungsbescheid")
    assert outcome.result and outcome.result["procedure"] == "Einspruch"
    assert outcome.result["strict_deadline"] is True
    assert "ZPO § 339 (1)" in outcome.legal_basis
    assert any("abroad" in m for m in outcome.missing_information)


def test_fr11_ac4_unclear_document_uses_the_stricter_reading() -> None:
    """'unclear' is treated as an enforcement order and says so."""
    outcome = run(date(2026, 10, 12), document="unclear")
    assert outcome.result and outcome.result["strict_deadline"] is True
    assert any("stricter rule" in a for a in outcome.assumptions)


def test_fr11_ac4_triage_date_is_named_as_assumed_date_of_service() -> None:
    """The delivery date appears in the assumptions as the date of service."""
    outcome = run(date(2026, 10, 12))
    assert "2026-10-12 is used as the date of service" in outcome.assumptions[0]


def test_fr10_ac3_future_service_date_returns_not_applicable() -> None:
    """A service date in the future produces no result and says why."""
    outcome = run(date(2027, 7, 1))
    assert outcome.result is None
    assert "future" in (outcome.not_applicable_reason or "")


def test_fr10_ac3_unknown_federal_state_is_rejected_by_the_schema() -> None:
    """Only the 16 state codes are accepted (the runner turns this into a message, FR-10 AC3)."""
    with pytest.raises(ValidationError, match="federal_state"):
        ObjectionDeadlineArgs.model_validate(
            {"document_type": "mahnbescheid", "service_date": "2026-10-12", "federal_state": "XX"}
        )
