"""Tests for ``eval/run_tool_eval.py`` and the recorded tool calls. No API call.

Related: §7.3, FR-10, NFR-06
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from types import ModuleType
from typing import Any

from conftest import FakeChatModel, final_answer, tool_call

from collection_letter_navigator import answer, config, pipeline
from collection_letter_navigator.schemas import RetrievalPlan
from collection_letter_navigator.tools import deadlines


def _load_script() -> ModuleType:
    path = config.EVAL_DIR / "run_tool_eval.py"
    spec = importlib.util.spec_from_file_location("run_tool_eval", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ev = _load_script()


def test_cases_cover_every_tool_and_no_tool() -> None:
    """About 15 cases, each tool at least twice, and questions that need no tool (§7.1)."""
    cases = ev.load_cases()
    assert 12 <= len(cases) <= 20 and len({c["id"] for c in cases}) == len(cases)
    expected = [c["expected_tool"] for c in cases]
    for tool in (
        "calculate_objection_deadline",
        "check_limitation",
        "calculate_default_interest",
    ):
        assert expected.count(tool) >= 2
    assert expected.count(None) >= 4
    for case in cases:
        date.fromisoformat(case["delivered_on"])
        assert (case["expected_tool"] is None) == (case["expected_args"] == {})


def test_selection_score() -> None:
    assert ev.score_tool_selection(["check_limitation"], "check_limitation") == 1.0
    assert (
        ev.score_tool_selection(["fetch_paragraph", "check_limitation"], "check_limitation") == 1.0
    )
    assert ev.score_tool_selection([], "check_limitation") == 0.0
    assert ev.score_tool_selection([], None) == 1.0
    assert ev.score_tool_selection(["check_limitation"], None) == 0.0


def test_argument_score_compares_expected_keys_with_amount_tolerance() -> None:
    expected = {"principal": 600, "start_date": "2026-02-01"}
    assert (
        ev.score_arguments(
            {"principal": 600.0, "start_date": "2026-02-01", "end_date": "x"}, expected
        )
        == 1.0
    )
    assert ev.score_arguments({"principal": "600.004", "start_date": "2026-02-01"}, expected) == 1.0
    assert ev.score_arguments({"principal": 601, "start_date": "2026-02-01"}, expected) == 0.0
    assert ev.score_arguments({"start_date": "2026-02-01"}, expected) == 0.0


def test_answer_outcome_records_the_tool_calls_of_the_model() -> None:
    """The evaluation reads what the model asked for, including the arguments."""
    plan = RetrievalPlan(queries_de=["Widerspruch Frist"], law_filter=["ZPO"], rationale="x")
    args = {"document_type": "mahnbescheid", "service_date": "2026-10-14"}
    model = FakeChatModel(
        [tool_call(deadlines.TOOL_NAME, args), final_answer("Ends 2026-10-28.", ["ZPO-692"])],
        structured={RetrievalPlan: [plan]},
    )
    out = pipeline.ask("Until when can I object?", mode="bm25", model=model)
    assert out.answer.tool_calls == [{"name": deadlines.TOOL_NAME, "args": args}]
    assert isinstance(out.answer, answer.AnswerOutcome)


def test_evaluate_case_scores_one_row() -> None:
    """One case through a stubbed pipeline gives a complete CSV row."""
    case = ev.load_cases()[0]

    def ask(question: str, triage: Any = None, **_: Any) -> Any:
        plan = RetrievalPlan(
            queries_de=["Widerspruch Mahnbescheid Frist"], law_filter=["ZPO"], rationale="x"
        )
        model = FakeChatModel(
            [tool_call(deadlines.TOOL_NAME, case["expected_args"]), final_answer("ok", [])],
            structured={RetrievalPlan: [plan]},
        )
        return pipeline.ask(question, triage, mode="bm25", model=model)

    row = ev.evaluate_case(case, 1, ask=ask)
    assert (row["selection_ok"], row["args_ok"], row["error"]) == (1.0, 1.0, "")
    assert ev.summarise([row]) == {
        "selection_accuracy": 1.0,
        "argument_accuracy": 1.0,
        "tool_calls_scored": 1.0,
    }
