"""Tests for :mod:`collection_letter_navigator.tools.limitation`.

At least 6 cases, per FR-12 AC4.

Related: FR-12, FR-10 AC4, NFR-06
"""

from __future__ import annotations

import pytest

from collection_letter_navigator.tools import limitation


def test_module_imports() -> None:
    """The limitation tool module imports."""
    assert limitation.check_limitation is not None


@pytest.mark.skip(reason="not implemented: FR-12 AC1")
def test_fr12_ac1_three_years_from_the_end_of_the_claim_year() -> None:
    """A mid-year claim ends three years after that 31 December."""


@pytest.mark.skip(reason="not implemented: FR-12 AC1")
def test_fr12_ac1_claim_on_31_december() -> None:
    """A claim arising on 31 December still counts from that year's end."""


@pytest.mark.skip(reason="not implemented: FR-12 AC1")
def test_fr12_ac1_claim_on_1_january() -> None:
    """A claim arising on 1 January runs almost four calendar years."""


@pytest.mark.skip(reason="not implemented: FR-12 AC1")
def test_fr12_ac1_later_knowledge_date_moves_the_start() -> None:
    """The period starts in the year both conditions are met."""


@pytest.mark.skip(reason="not implemented: FR-12 AC1")
def test_fr12_ac1_missing_knowledge_date_is_assumed_and_listed() -> None:
    """Without a knowledge date, claim_date is assumed and named."""


@pytest.mark.skip(reason="not implemented: FR-12 AC2")
def test_fr12_ac2_result_states_limitation_is_a_defence() -> None:
    """The result never says the claim is time-barred by itself."""


@pytest.mark.skip(reason="not implemented: FR-12 AC2")
def test_fr12_ac2_suspension_restart_and_titled_claims_are_listed() -> None:
    """BGB §§ 204, 212 and 197 appear as not covered."""


@pytest.mark.skip(reason="not implemented: FR-12 AC5")
def test_fr12_ac5_missing_information_asks_about_payments_and_acknowledgments() -> None:
    """Every result asks the BGB § 212 and § 204 questions."""


@pytest.mark.skip(reason="not implemented: FR-12 AC4")
def test_fr12_ac4_partial_payment_case_is_covered() -> None:
    """A case with a partial payment is flagged as a possible restart."""


@pytest.mark.skip(reason="not implemented: FR-12 AC3")
def test_fr12_ac3_claim_before_2002_returns_not_applicable() -> None:
    """Claims under the old law produce no result."""
