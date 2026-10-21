"""Tests for :mod:`collection_letter_navigator.presenter` and :mod:`~.demo`.

No test calls OpenRouter; the legal-basis tests read the committed index.

Related: FR-01 AC3, FR-03, FR-17 AC1, FR-19 AC1, FR-21 AC6, R-12, NFR-06
"""

from __future__ import annotations

from datetime import date

from langchain_core.messages import AIMessage, HumanMessage

from collection_letter_navigator import config, demo, presenter, retrieval
from collection_letter_navigator.llm import LlmUsage
from collection_letter_navigator.schemas import TriageResult
from collection_letter_navigator.tools import limitation

DELIVERED = date(2026, 10, 14)


def test_fr01_ac3_court_payment_order_gets_a_deadline_card() -> None:
    """The card uses the delivery date as date of service (FR-11 AC4)."""
    triage = TriageResult(sender="court", court_document="mahnbescheid", delivered_on=DELIVERED)
    card = presenter.deadline_card(triage)
    assert card is not None
    assert (card.procedure, card.period_end, card.strict) == (
        "Widerspruch",
        date(2026, 10, 28),
        False,
    )
    assert card.headline == "The period for Widerspruch ends on Wednesday, 28 October 2026."


def test_fr01_ac3_unclear_document_takes_the_stricter_reading() -> None:
    """For 'unclear', the card shows the strict Einspruch period and says so."""
    triage = TriageResult(sender="court", court_document="unclear", delivered_on=DELIVERED)
    card = presenter.deadline_card(triage)
    assert card is not None and card.strict and card.procedure == "Einspruch"
    assert any("stricter" in line for line in card.assumptions)


def test_fr01_ac5_no_deadline_card_for_other_senders() -> None:
    """Company letters and 'not sure' get no card."""
    for sender in ("creditor", "collection_agency", "not_sure"):
        triage = TriageResult(sender=sender, delivered_on=DELIVERED)  # type: ignore[arg-type]
        assert presenter.deadline_card(triage) is None
    assert presenter.deadline_card(None) is None


def test_r12_references_map_to_chunk_ids() -> None:
    """Subsection chunks are preferred; unknown provisions give None."""
    assert presenter.chunk_id_for_reference("BGB § 199 (1)") == "BGB-199"
    assert presenter.chunk_id_for_reference("BGB § 204 (1) no. 3") == "BGB-204-1"
    assert presenter.chunk_id_for_reference("RDG § 13a (1)") == "RDG-13a-1"
    assert presenter.chunk_id_for_reference("ZPO § 9999") is None
    assert presenter.chunk_id_for_reference("not a reference") is None


def test_r12_tool_card_shows_the_tools_legal_basis() -> None:
    """The limitation tool's provisions come with their German text (smoke test Q3)."""
    result = limitation.check_limitation(limitation.LimitationArgs(claim_date=date(2022, 3, 15)))
    pairs = presenter.legal_basis_of(result)
    assert [ref for ref, _ in pairs] == result.legal_basis
    assert all(doc is not None for _, doc in pairs)


def test_fr08_ac2_provision_label() -> None:
    """The heading names section, subsection, law and title."""
    doc = retrieval.get_chunk_by_id("RDG-13a-1")
    assert doc is not None
    assert presenter.provision_label(doc).startswith("§ 13a (1) RDG – Darlegungs-")


def test_fr19_ac1_usage_totals_add_tokens_and_cost() -> None:
    """Tokens are summed; calls without a known cost are counted separately."""
    totals = presenter.UsageTotals()
    usages = [
        LlmUsage("m", 1000, 200, 64, 0.001),
        LlmUsage("m", 2000, 300, 128, None),
    ]
    totals.add(usages, cost_of=lambda u: u.cost_usd)
    assert (totals.calls, totals.prompt_tokens, totals.completion_tokens) == (2, 3000, 500)
    assert totals.cost_label == "$0.0010 (without 1 calls)"
    assert presenter.UsageTotals().cost_label == "$0.0000"


def test_fr19_ac2_cost_unavailable_when_no_call_has_a_price() -> None:
    """If no price is known at all, the sidebar says so instead of showing $0."""
    totals = presenter.UsageTotals()
    totals.add([LlmUsage("m", 10, 5, 0, None)], cost_of=lambda u: None)
    assert totals.cost_label == "cost unavailable"


def test_fr21_ac6_knowledge_base_dates() -> None:
    """The sidebar dates come from the index manifest and the base-rate table."""
    snapshot, base_rate = presenter.knowledge_base_dates()
    assert date.fromisoformat(snapshot) and date.fromisoformat(base_rate)
    assert base_rate >= "2026-07-01"


def test_history_keeps_the_last_turns_and_wraps_questions() -> None:
    """Older turns are dropped; questions are delimited as untrusted data (FR-22 L4)."""
    turns = [(f"question {i}", f"answer {i}") for i in range(5)]
    messages = presenter.history_messages(turns)
    assert len(messages) == 2 * config.HISTORY_TURNS
    assert isinstance(messages[0], HumanMessage) and isinstance(messages[1], AIMessage)
    assert "<history>" in str(messages[0].content) and "question 2" in str(messages[0].content)


def test_fr03_ac1_four_demo_cases_with_two_or_three_questions() -> None:
    """Court, agency, 'not sure' and off-topic/injection cases exist (FR-03 AC1, AC2)."""
    senders = {case.sender for case in demo.DEMO_CASES}
    assert len(demo.DEMO_CASES) >= 4 and {"court", "collection_agency", "not_sure"} <= senders
    assert all(2 <= len(case.questions) <= 3 for case in demo.DEMO_CASES)
    assert any(
        "Ignore all previous instructions" in q for c in demo.DEMO_CASES for q in c.questions
    )


def test_fr03_demo_court_deadline_lies_ahead() -> None:
    """The court demo's delivery date is relative to today, so its card never expires."""
    case = next(c for c in demo.DEMO_CASES if c.sender == "court")
    today = date(2026, 10, 22)
    card = presenter.deadline_card(case.triage(today))
    assert card is not None and card.period_end > today
