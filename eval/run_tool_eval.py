"""Tool-calling evaluation: expected tool and arguments per case.

Run with ``uv run python eval/run_tool_eval.py``. Every case goes through the
real pipeline (search plan, retrieval, answer call with tools), so the model
decides about tools exactly as in the app. Measures how often the model calls
the expected tool (or none) and how often the arguments are right, and writes
``eval/tool_results.csv``. Cost: about $0.003 per case and run.

Related: §7.3, FR-10, NFR-10
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from collection_letter_navigator import config, llm, pipeline
from collection_letter_navigator.schemas import TriageResult

#: Tolerance for amounts in the argument comparison (EUR).
AMOUNT_TOLERANCE = 0.01

FIELDS = [
    "run",
    "id",
    "question_en",
    "expected_tool",
    "called_tools",
    "selection_ok",
    "expected_args",
    "actual_args",
    "args_ok",
    "error",
    "chat_model",
]


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """Read the tool-calling cases.

    Args:
        path: Dataset file; defaults to ``eval/tool_cases.json``.

    Returns:
        The cases, each with a question, the expected tool (or null for "no
        tool") and the expected arguments.

    Raises:
        FileNotFoundError: If the dataset is missing.

    Related: §7.1, §7.3
    """
    file = path or config.EVAL_DIR / "tool_cases.json"
    cases: list[dict[str, Any]] = json.loads(file.read_text(encoding="utf-8"))
    return cases


def score_tool_selection(actual: list[str], expected: str | None) -> float:
    """Score the tool choice of one case.

    Args:
        actual: Names of the tools the model called, in order (empty if none).
        expected: Tool the case expects, or None for "no tool".

    Returns:
        1.0 if the expected tool was called (or, for "no tool", no tool at all),
        else 0.0.

    Related: §7.3
    """
    if expected is None:
        return 1.0 if not actual else 0.0
    return 1.0 if expected in actual else 0.0


def _same(actual: object, expected: object) -> bool:
    """Compare one argument: amounts with a tolerance, everything else as text."""
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        try:
            return abs(float(str(actual)) - float(expected)) <= AMOUNT_TOLERANCE
        except ValueError:
            return False
    return str(actual) == str(expected)


def score_arguments(actual: dict[str, Any], expected: dict[str, Any]) -> float:
    """Score the arguments of one tool call.

    Only the expected arguments are compared; extra arguments the model adds
    (such as an end date that defaults to today) do not count against it.

    Args:
        actual: Arguments the model passed.
        expected: Arguments the case expects.

    Returns:
        1.0 if every expected argument matches, else 0.0.

    Related: §7.3
    """
    return 1.0 if all(_same(actual.get(k), v) for k, v in expected.items()) else 0.0


def triage_for(case: dict[str, Any]) -> TriageResult:
    """The triage context of one case."""
    return TriageResult(
        sender=case["sender"],
        court_document=case.get("court_document"),
        delivered_on=date.fromisoformat(case["delivered_on"]),
    )


def evaluate_case(
    case: dict[str, Any],
    run: int,
    ask: Callable[..., pipeline.PipelineOutcome] = pipeline.ask,
) -> dict[str, Any]:
    """Ask one case and score the tool call (one CSV row).

    Related: §7.3
    """
    row: dict[str, Any] = {
        "run": run,
        "id": case["id"],
        "question_en": case["question_en"],
        "expected_tool": case["expected_tool"] or "none",
        "expected_args": json.dumps(case["expected_args"]),
        "chat_model": config.CHAT_MODEL,
    }
    try:
        out = ask(case["question_en"], triage_for(case))
    except Exception as error:  # a failed case is recorded, the run goes on
        row.update(error=str(error), called_tools="", selection_ok=0.0, args_ok="", actual_args="")
        return row
    calls = out.answer.tool_calls
    names = [call["name"] for call in calls]
    row["called_tools"] = " ".join(names) or "none"
    row["selection_ok"] = score_tool_selection(names, case["expected_tool"])
    match = next((c for c in calls if c["name"] == case["expected_tool"]), None)
    row["actual_args"] = json.dumps(match["args"], default=str) if match else ""
    row["args_ok"] = score_arguments(match["args"], case["expected_args"]) if match else ""
    row["error"] = ""
    return row


def summarise(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Tool selection accuracy over all rows, argument accuracy over the matched calls."""
    selection = [float(r["selection_ok"]) for r in rows]
    arguments = [float(r["args_ok"]) for r in rows if r.get("args_ok") not in ("", None)]
    return {
        "selection_accuracy": sum(selection) / len(selection) if selection else 0.0,
        "argument_accuracy": sum(arguments) / len(arguments) if arguments else 0.0,
        "tool_calls_scored": float(len(arguments)),
    }


def main(argv: list[str] | None = None) -> int:
    """Run every case and report the two metrics.

    Returns:
        Process exit code: 0 on success.

    Related: §7.3, NFR-10
    """
    parser = argparse.ArgumentParser(description="Tool-calling evaluation (§7.3).")
    parser.add_argument("--cases", type=Path, default=config.EVAL_DIR / "tool_cases.json")
    parser.add_argument("--output", type=Path, default=config.EVAL_DIR / "tool_results.csv")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args(argv)
    llm.load_environment()
    rows = []
    for run in range(1, args.runs + 1):
        for case in load_cases(args.cases):
            row = evaluate_case(case, run)
            rows.append(row)
            mark = "ok " if row["selection_ok"] == 1.0 and row["args_ok"] in ("", 1.0) else "CHECK"
            print(
                f"{mark} {row['id']} run {run}: expected {row['expected_tool']}, "
                f"called {row['called_tools']} {row['actual_args']} {row['error']}"
            )
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    s = summarise(rows)
    print(
        f"\nTool selection accuracy: {s['selection_accuracy']:.0%} (target ≥ 90 %) · "
        f"argument accuracy: {s['argument_accuracy']:.0%} over "
        f"{int(s['tool_calls_scored'])} calls (target ≥ 80 %) · written: {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
