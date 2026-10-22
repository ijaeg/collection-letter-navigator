"""Tests for ``eval/run_safety_tests.py``: cases file, automatic checks and the report.

The script lives outside the package, so it is loaded from its file path. The
pipeline is replaced by stubs: no API call.

Related: FR-21 AC8, FR-22, NFR-06
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from types import ModuleType
from typing import Any

from collection_letter_navigator import config, guards
from collection_letter_navigator.answer import AnswerOutcome
from collection_letter_navigator.pipeline import PipelineOutcome
from collection_letter_navigator.retrieval import RetrievalOutcome
from collection_letter_navigator.schemas import AnswerWithSources, RetrievalPlan

TODAY = date(2026, 10, 22)


def _load_script() -> ModuleType:
    path = config.EVAL_DIR / "run_safety_tests.py"
    spec = importlib.util.spec_from_file_location("run_safety_tests", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up while it loads
    spec.loader.exec_module(module)
    return module


ev = _load_script()
CASES: list[dict[str, Any]] = json.loads(
    (config.EVAL_DIR / "safety_cases.json").read_text(encoding="utf-8")
)


def stub_ask(text: str, out_of_scope: bool = False) -> Any:
    """A pipeline stub that applies the real guards and returns a fixed answer."""

    def ask(question: str, triage: Any = None, **_: Any) -> PipelineOutcome:
        guards.assert_no_injection(guards.validate_question(question))
        plan = RetrievalPlan(queries_de=["x"], rationale="x")
        answer = AnswerWithSources(
            answer_en=text, source_chunk_ids=[], used_tools=[], out_of_scope=out_of_scope
        )
        return PipelineOutcome(question, RetrievalOutcome(plan, []), AnswerOutcome(answer))

    return ask


def test_fr21_ac8_at_least_twelve_cases_cover_the_required_situations() -> None:
    """The spec names six situations that must be covered (FR-21 AC8)."""
    assert len(CASES) >= 12
    assert len({c["id"] for c in CASES}) == len(CASES)
    requirements = " ".join(c["requirement"] for c in CASES)
    for needed in ("FR-21 AC4", "FR-21 AC3", "FR-21 AC9", "FR-21 AC7", "FR-22 AC3", "FR-22 AC2"):
        assert needed in requirements


def test_every_check_name_is_known() -> None:
    """A typo in a check name would fail only during the paid run."""
    known = {
        "blocked",
        "answered",
        "no_instruction",
        "no_verdict",
        "referral",
        "out_of_scope",
        "insolvency_administrator",
        "deadline_named",
        "not_answered_from_general_knowledge",
    }
    for case in CASES:
        for name in case["checks"]:
            assert name in known or name.startswith("tool:"), name


def test_injection_cases_are_really_blocked_by_the_guards() -> None:
    """Cases that expect 'blocked' trip L2; the others do not (no API call)."""
    for case in CASES:
        blocked = guards.detect_injection(case["input"]) is not None
        assert blocked == ("blocked" in case["checks"]), case["id"]


def test_instruction_patterns_find_advice_but_not_facts() -> None:
    assert ev.find_instruction("You should pay the amount now.")
    assert ev.find_instruction("File an objection with the court by 28 October.")
    assert ev.find_instruction("You can safely ignore this letter.")
    assert ev.find_instruction("The period ends on 28 October 2026.") is None
    assert ev.find_instruction("The app cannot tell you whether to pay.") is None
    assert ev.find_instruction("You should not ignore the letter.") is None


def test_verdict_patterns_find_verdicts_but_not_rules() -> None:
    assert ev.find_verdict("Your debt is time-barred.")
    assert ev.find_verdict("This is a scam.")
    assert ev.find_verdict("A claim is time-barred only if the debtor raises it.") is None
    assert ev.find_verdict("The regular period ends on 31 December 2025.") is None


def test_blocked_case_passes_without_an_llm_call() -> None:
    case = next(c for c in CASES if c["id"] == "S10")
    result = ev.run_case(case, ask=stub_ask("never used"), today=TODAY)
    assert result.blocked and result.passed
    assert result.answer_text == config.INJECTION_BLOCKED_MESSAGE_EN


def test_out_of_scope_case_needs_flag_and_referral() -> None:
    case = next(c for c in CASES if c["id"] == "S05")
    good = ev.run_case(
        case, stub_ask("Not covered. Contact a debt counselling service.", True), TODAY
    )
    bad = ev.run_case(case, stub_ask("Garnishment limits depend on income.", False), TODAY)
    assert good.passed
    assert not bad.passed and bad.checks == {
        "answered": True,
        "out_of_scope": False,
        "referral": False,
    }


def test_deadline_named_uses_the_triage_date() -> None:
    """Court cases are delivered five days before 'today'; the answer must name the end date."""
    case = next(c for c in CASES if c["id"] == "S02")
    # delivered 2026-10-17 (Saturday) → two weeks → Saturday 31 Oct → Monday 2 November 2026
    named = ev.run_case(case, stub_ask("The period ends on Monday, 2 November 2026."), TODAY)
    missing = ev.run_case(case, stub_ask("There is a two-week period."), TODAY)
    assert named.checks["deadline_named"] and not missing.checks["deadline_named"]


def test_report_lists_every_case_and_the_full_answers() -> None:
    results = [ev.run_case(c, stub_ask("The period ends | soon."), TODAY) for c in CASES[:3]]
    report = ev.render_markdown(results, TODAY)
    assert report.count("\n| S0") == 3
    assert r"ends \| soon" in report  # pipes in answers do not break the table
    assert "## Full answers" in report and "### S01" in report
