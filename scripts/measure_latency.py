"""Measure the answer time per step on the development questions (NFR-04, R-11).

Runs every question of ``eval/dev_questions.json`` through the full pipeline
against the real API and writes one row per question and run to
``eval/latency_<label>.csv``. The test set is never used here (§7.1).

    uv run python scripts/measure_latency.py --label low
    PLAN_REASONING_EFFORT=minimal uv run python scripts/measure_latency.py --label plan-minimal

Cost: about $0.003 per question.

Related: NFR-04, R-11, FR-19 AC1
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from datetime import date
from pathlib import Path

from collection_letter_navigator import config, llm, pipeline
from collection_letter_navigator.schemas import TriageResult

#: Fixed delivery date, so the deadline tool gives the same result on every run.
DELIVERED_ON = date(2026, 10, 14)

FIELDS = [
    "id",
    "run",
    "plan_s",
    "retrieval_s",
    "answer_s",
    "total_s",
    "plan_completion_tokens",
    "plan_reasoning_tokens",
    "answer_calls",
    "answer_completion_tokens",
    "answer_reasoning_tokens",
    "tools",
    "chat_model",
    "plan_reasoning_effort",
    "answer_reasoning_effort",
]


def parse_args() -> argparse.Namespace:
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(description="Measure answer time per step.")
    parser.add_argument("--label", required=True, help="Name of the setting, e.g. 'low'.")
    parser.add_argument("--runs", type=int, default=1, help="Runs per question (default 1).")
    return parser.parse_args()


def triage_for(sender: str) -> TriageResult:
    """Build the triage context of one development question."""
    document = "unclear" if sender == "court" else None
    return TriageResult(sender=sender, court_document=document, delivered_on=DELIVERED_ON)  # type: ignore[arg-type]


def measure(question: dict[str, str], run: int) -> dict[str, object]:
    """Ask one question and return its CSV row."""
    out = pipeline.ask(question["question_en"], triage_for(question["sender"]))
    plan = out.plan_usages
    answer = out.answer.usages
    return {
        "id": question["id"],
        "run": run,
        "plan_s": round(out.seconds.get("plan", 0.0), 1),
        "retrieval_s": round(out.seconds["retrieval"], 1),
        "answer_s": round(out.seconds["answer"], 1),
        "total_s": round(sum(out.seconds.values()), 1),
        "plan_completion_tokens": sum(u.completion_tokens for u in plan),
        "plan_reasoning_tokens": sum(u.reasoning_tokens for u in plan),
        "answer_calls": len(answer),
        "answer_completion_tokens": sum(u.completion_tokens for u in answer),
        "answer_reasoning_tokens": sum(u.reasoning_tokens for u in answer),
        "tools": " ".join(r.tool for r in out.answer.tool_results),
        "chat_model": config.CHAT_MODEL,
        "plan_reasoning_effort": config.PLAN_REASONING_EFFORT,
        "answer_reasoning_effort": config.REASONING_EFFORT,
    }


def main() -> int:
    """Run all development questions and print a summary."""
    args = parse_args()
    llm.load_environment()
    questions = json.loads((config.EVAL_DIR / "dev_questions.json").read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for run in range(1, args.runs + 1):
        for question in questions:
            try:
                row = measure(question, run)
            except llm.LlmCallError as error:
                print(f"{question['id']} run {run}: failed – {error}")
                continue
            rows.append(row)
            print(
                f"{row['id']} run {run}: plan {row['plan_s']:>5} s · retrieval "
                f"{row['retrieval_s']:>4} s · answer {row['answer_s']:>5} s · total "
                f"{row['total_s']:>5} s · tools: {row['tools'] or '-'}"
            )
    path = Path(config.EVAL_DIR) / f"latency_{args.label}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    if rows:
        totals = [float(str(r["total_s"])) for r in rows]
        plans = [float(str(r["plan_s"])) for r in rows]
        over = sum(t > config.TARGET_ANSWER_SECONDS for t in totals)
        print(
            f"\n{len(rows)} runs · total median {statistics.median(totals):.1f} s, "
            f"max {max(totals):.1f} s · plan median {statistics.median(plans):.1f} s, "
            f"max {max(plans):.1f} s · over {config.TARGET_ANSWER_SECONDS} s: {over}"
        )
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
