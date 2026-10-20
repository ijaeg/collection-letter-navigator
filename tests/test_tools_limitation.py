"""Tests for :mod:`collection_letter_navigator.tools.limitation`.

Reference cases for FR-12 AC4: three years from the end of the year in which
the claim arose and the creditor knew of it (BGB §§ 195, 199 (1)); a part payment
inside the period restarts it (BGB § 212 (1) no. 1).

Related: FR-12, FR-10 AC4, NFR-06
"""

from __future__ import annotations

from datetime import date

import pytest

from collection_letter_navigator.schemas import ToolResult
from collection_letter_navigator.tools import limitation
from collection_letter_navigator.tools.limitation import LimitationArgs

TODAY = date(2026, 10, 19)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """All cases are judged on the same day."""
    monkeypatch.setattr(limitation, "_today", lambda: TODAY)


def run(claim: date, knowledge: date | None = None, ack: date | None = None) -> ToolResult:
    """Call the tool."""
    args = LimitationArgs(claim_date=claim, knowledge_date=knowledge, last_acknowledgment_date=ack)
    return limitation.check_limitation(args)


def end(outcome: ToolResult) -> str:
    """The end of the period from a successful result."""
    assert outcome.result is not None, outcome.not_applicable_reason
    return str(outcome.result["period_end"])


def test_module_imports() -> None:
    """The limitation tool module imports."""
    assert limitation.check_limitation is not None


def test_fr12_ac1_three_years_from_the_end_of_the_claim_year() -> None:
    """A mid-year claim ends three years after that 31 December."""
    assert end(run(date(2023, 6, 15))) == "2026-12-31"


def test_fr12_ac1_claim_on_31_december() -> None:
    """A claim arising on 31 December still counts from that year's end."""
    assert end(run(date(2023, 12, 31))) == "2026-12-31"


def test_fr12_ac1_claim_on_1_january() -> None:
    """A claim arising on 1 January runs almost four calendar years."""
    assert end(run(date(2024, 1, 1))) == "2027-12-31"


def test_fr12_ac1_later_knowledge_date_moves_the_start() -> None:
    """The period starts in the year both conditions are met."""
    assert end(run(date(2024, 11, 10), knowledge=date(2025, 3, 1))) == "2028-12-31"


def test_fr12_ac1_missing_knowledge_date_is_assumed_and_listed() -> None:
    """Without a knowledge date, the claim year is assumed and named."""
    outcome = run(date(2023, 6, 15))
    assert any("assumed to have known" in a and "2023" in a for a in outcome.assumptions)


def test_fr12_ac1_period_that_has_passed_is_reported_as_ended() -> None:
    """A 2021 claim ended on 31 December 2024 – reported as a fact about the period."""
    outcome = run(date(2021, 4, 1))
    assert end(outcome) == "2024-12-31"
    assert outcome.result and outcome.result["regular_period_ended"] is True


def test_fr12_ac2_result_states_limitation_is_a_defence() -> None:
    """The result never says the claim is time-barred by itself."""
    outcome = run(date(2021, 4, 1))
    assert any("defence" in a and "BGB § 214 (1)" in a for a in outcome.assumptions)
    assert "time_barred" not in (outcome.result or {})


def test_fr12_ac2_suspension_restart_and_titled_claims_are_listed() -> None:
    """BGB §§ 204, 212 and 197 appear in the missing information."""
    text = " ".join(run(date(2023, 6, 15)).missing_information)
    for provision in ("BGB § 204", "BGB § 212", "BGB § 197"):
        assert provision in text


def test_fr12_ac5_missing_information_asks_about_payments_and_acknowledgments() -> None:
    """Every result asks the BGB § 212 and § 204 questions."""
    for claim in (date(2021, 4, 1), date(2024, 1, 1)):
        questions = run(claim).missing_information
        assert any("paid" in q and "acknowledged" in q for q in questions)
        assert any("payment order" in q for q in questions)


def test_fr12_ac4_partial_payment_case_is_covered() -> None:
    """A part payment inside the period restarts it: 2022 claim, payment on 2024-09-15."""
    outcome = run(date(2022, 5, 10), ack=date(2024, 9, 15))
    assert end(outcome) == "2027-09-15"
    assert outcome.result and outcome.result["restarted_by_acknowledgment"] is True
    assert outcome.result["regular_period_ended"] is False
    assert any("BGB § 212 (1) no. 1" in a for a in outcome.assumptions)


def test_fr12_ac4_payment_after_the_period_does_not_restart_it() -> None:
    """A payment after the period ended does not revive it, and the tool says so."""
    outcome = run(date(2021, 4, 1), ack=date(2025, 3, 1))
    assert end(outcome) == "2024-12-31"
    assert any("does not restart" in a for a in outcome.assumptions)


def test_fr12_ac3_claim_before_2002_returns_not_applicable() -> None:
    """Claims under the old law produce no result."""
    outcome = run(date(2001, 12, 31))
    assert outcome.result is None
    assert "2002" in (outcome.not_applicable_reason or "")


def test_fr10_ac3_future_claim_date_returns_not_applicable() -> None:
    """A claim date in the future produces no result."""
    assert run(date(2027, 1, 1)).result is None
