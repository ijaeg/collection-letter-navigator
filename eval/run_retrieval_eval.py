"""Retrieval evaluation: run R1 to R4 over a question set and write the results.

Run with ``uv run python eval/run_retrieval_eval.py``. Every configuration runs
on every question of ``eval/retrieval_questions.json``; the CSV records the
knowledge-base snapshot date, the model names and the settings so that a run can
be reproduced. For the spike gate, run it on the development questions:

    uv run python eval/run_retrieval_eval.py --questions eval/dev_questions.json \\
        --output eval/dev_results.csv

The retrieval plan is created once per question and run, and shared by R2 and
R4, so both configurations search with the same German queries.

Related: §7.2, §7.5, FR-05 AC4, FR-07 AC4, NFR-10
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, get_args

from collection_letter_navigator import config, llm, retrieval
from collection_letter_navigator.ingest import read_manifest
from collection_letter_navigator.schemas import RetrievalPlan, SenderType, TriageResult

#: Expected provisions are written as "BGB § 199" (§7.1).
_PROVISION = re.compile(r"^(BGB|ZPO|RDG) § \d+[a-z]?$")

#: Columns of the results CSV (§7.5 AC1).
FIELDS = (
    "run",
    "config",
    "question_id",
    "category",
    "question_en",
    "query_translation",
    "mode",
    "queries_de",
    "law_filter",
    "filter_fallback",
    "top_provisions",
    "hit_at_5",
    "rr_at_10",
    "filter_ok",
    "plan_seconds",
    "retrieval_seconds",
    "error",
    "snapshot_date",
    "embedding_model",
    "chat_model",
)


def load_questions(path: Path | None = None) -> list[dict[str, object]]:
    """Read the evaluation questions.

    Args:
        path: Dataset file; defaults to ``eval/retrieval_questions.json``.

    Returns:
        The questions, each with ``id``, ``question_en``, ``sender``,
        ``expected`` and ``category``; a missing ``id`` is set to ``Q01``, ``Q02``, …

    Raises:
        FileNotFoundError: If the dataset is missing.
        ValueError: If a question does not match the schema of §7.1.

    Related: §7.1
    """
    source = path or config.EVAL_DIR / "retrieval_questions.json"
    questions = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"{source} must contain a non-empty JSON array.")
    for number, question in enumerate(questions, start=1):
        label = question.get("id", f"#{number}")
        if not str(question.get("question_en", "")).strip():
            raise ValueError(f"{label}: question_en is missing.")
        if question.get("sender") not in get_args(SenderType):
            raise ValueError(f"{label}: unknown sender {question.get('sender')!r}.")
        if question.get("category") not in config.EVAL_CATEGORIES:
            raise ValueError(f"{label}: unknown category {question.get('category')!r}.")
        expected = question.get("expected")
        if not isinstance(expected, list) or not all(
            isinstance(p, str) and _PROVISION.match(p) for p in expected
        ):
            raise ValueError(f"{label}: expected must list provisions like 'BGB § 199'.")
        question.setdefault("id", f"Q{number:02d}")
    return questions


def provision_of(chunk: retrieval.ScoredChunk) -> str:
    """Name the provision a chunk belongs to, e.g. ``"BGB § 204"`` for ``BGB-204-1``."""
    return f"{chunk.document.metadata['law']} § {chunk.document.metadata['section']}"


def ranked_provisions(chunks: list[retrieval.ScoredChunk]) -> list[str]:
    """List the provisions in retrieved order; several chunks of one section count once."""
    return list(dict.fromkeys(provision_of(chunk) for chunk in chunks))


def hit_rate_at_k(ranked: list[str], expected: list[str], k: int) -> float:
    """Compute the Hit-Rate contribution of one question.

    Args:
        ranked: Provisions in retrieved order, e.g. ``["ZPO § 692", ...]``.
        expected: The expected provisions.
        k: Cut-off.

    Returns:
        1.0 if at least one expected provision appears in the top *k*, else 0.0.

    Related: §7.2
    """
    return 1.0 if set(ranked[:k]) & set(expected) else 0.0


def reciprocal_rank(ranked: list[str], expected: list[str], k: int) -> float:
    """Compute the reciprocal rank of the first expected provision.

    Args:
        ranked: Provisions in retrieved order.
        expected: The expected provisions.
        k: Cut-off.

    Returns:
        ``1 / rank`` of the first expected provision in the top *k*, else 0.0.

    Related: §7.2
    """
    for rank, provision in enumerate(ranked[:k], start=1):
        if provision in expected:
            return 1.0 / rank
    return 0.0


def filter_accuracy(law_filter: list[str] | None, expected: list[str]) -> float:
    """Check whether the law filter covers every expected provision.

    Args:
        law_filter: The filter the retrieval plan produced, or None.
        expected: The expected provisions.

    Returns:
        1.0 if every expected law is allowed by the filter, else 0.0. No filter
        excludes nothing and therefore counts as 1.0.

    Related: §7.2, FR-06 AC1
    """
    if law_filter is None:
        return 1.0
    return 1.0 if {p.split(" ")[0] for p in expected} <= set(law_filter) else 0.0


def _triage_for(question: dict[str, Any]) -> TriageResult:
    """Build the triage context of a question; today is the assumed delivery date."""
    return TriageResult(sender=question["sender"], delivered_on=date.today())


def evaluate(
    questions: list[dict[str, Any]],
    *,
    runs: int,
    configurations: tuple[tuple[str, bool, str], ...] = config.RETRIEVAL_CONFIGURATIONS,
) -> list[dict[str, Any]]:
    """Run every configuration on every question, ``runs`` times.

    Args:
        questions: The validated questions.
        runs: Number of repetitions; LLM output varies between runs (§7.2).
        configurations: ``(name, query_translation, mode)`` triples.

    Returns:
        One result row per run, configuration and question.

    Related: §7.2
    """
    manifest = read_manifest()
    common = {
        "snapshot_date": manifest.get("snapshot_date", ""),
        "embedding_model": manifest.get("embedding_model", ""),
        "chat_model": config.CHAT_MODEL,
    }
    depth = max(config.HIT_RATE_AT_K, config.MRR_AT_K)
    needs_plan = any(translate for _, translate, _ in configurations)
    rows: list[dict[str, Any]] = []
    for run in range(1, runs + 1):
        for question in questions:
            plan: RetrievalPlan | None = None
            plan_seconds = 0.0
            plan_error = ""
            if needs_plan:
                started = time.perf_counter()
                try:
                    plan = retrieval.create_retrieval_plan(
                        question["question_en"], _triage_for(question)
                    )
                except llm.LlmCallError as error:
                    plan_error = str(error)
                plan_seconds = time.perf_counter() - started
            for name, translate, mode in configurations:
                row: dict[str, Any] = {
                    "run": run,
                    "config": name,
                    "question_id": question["id"],
                    "category": question["category"],
                    "question_en": question["question_en"],
                    "query_translation": "on" if translate else "off",
                    "mode": mode,
                    **common,
                }
                used = plan if translate else retrieval.passthrough_plan(question["question_en"])
                if used is None:
                    rows.append({**row, "error": plan_error, "hit_at_5": 0.0, "rr_at_10": 0.0})
                    continue
                started = time.perf_counter()
                outcome = retrieval.retrieve(used, mode=mode, k=depth)  # type: ignore[arg-type]
                ranked = ranked_provisions(outcome.chunks)
                expected = question["expected"]
                row.update(
                    queries_de=" | ".join(used.queries_de),
                    law_filter=",".join(outcome.applied_filter or []),
                    filter_fallback=outcome.filter_fallback,
                    top_provisions=" | ".join(ranked[: config.MRR_AT_K]),
                    hit_at_5=hit_rate_at_k(ranked, expected, config.HIT_RATE_AT_K),
                    rr_at_10=reciprocal_rank(ranked, expected, config.MRR_AT_K),
                    filter_ok=filter_accuracy(used.law_filter, expected) if translate else "",
                    plan_seconds=round(plan_seconds, 2) if translate else 0.0,
                    retrieval_seconds=round(time.perf_counter() - started, 2),
                    error="",
                )
                rows.append(row)
            print(f"run {run}: {question['id']} done", file=sys.stderr)
    return rows


def summarise(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate the rows per configuration, with the spread between runs.

    Returns:
        One summary per configuration: Hit-Rate@5, MRR@10, filter accuracy,
        mean latency, and the lowest and highest Hit-Rate@5 of a single run.

    Related: §7.2
    """
    summary = []
    for name in dict.fromkeys(row["config"] for row in rows):
        mine = [row for row in rows if row["config"] == name]
        per_run = [
            statistics.mean(r["hit_at_5"] for r in mine if r["run"] == run)
            for run in sorted({r["run"] for r in mine})
        ]
        filters = [r["filter_ok"] for r in mine if r.get("filter_ok") != ""]
        summary.append(
            {
                "config": name,
                "hit_rate_at_5": statistics.mean(r["hit_at_5"] for r in mine),
                "mrr_at_10": statistics.mean(r["rr_at_10"] for r in mine),
                "filter_accuracy": statistics.mean(filters) if filters else None,
                "seconds": statistics.mean(
                    float(r.get("plan_seconds") or 0) + float(r.get("retrieval_seconds") or 0)
                    for r in mine
                ),
                "hit_rate_min": min(per_run),
                "hit_rate_max": max(per_run),
                "errors": sum(1 for r in mine if r.get("error")),
            }
        )
    return summary


def print_summary(summary: list[dict[str, Any]]) -> None:
    """Print the summary table to the console."""
    print(
        f"\n{'config':<7}{'HR@5':>7}{'min–max':>12}{'MRR@10':>8}{'filter':>8}{'s/q':>6}{'err':>5}"
    )
    for s in summary:
        spread = f"{s['hit_rate_min']:.0%}–{s['hit_rate_max']:.0%}"
        filt = "–" if s["filter_accuracy"] is None else f"{s['filter_accuracy']:.0%}"
        print(
            f"{s['config']:<7}{s['hit_rate_at_5']:>7.0%}{spread:>12}{s['mrr_at_10']:>8.2f}"
            f"{filt:>8}{s['seconds']:>6.1f}{s['errors']:>5}"
        )


def main(argv: list[str] | None = None) -> int:
    """Run every configuration on every question and write the results CSV.

    Returns:
        Process exit code: 0 on success, 1 on a readable error.

    Related: §7.2, §7.5 AC1, NFR-10
    """
    parser = argparse.ArgumentParser(description="Retrieval evaluation R1-R4 (§7.2).")
    parser.add_argument(
        "--questions", type=Path, default=config.EVAL_DIR / "retrieval_questions.json"
    )
    parser.add_argument("--output", type=Path, default=config.EVAL_DIR / "retrieval_results.csv")
    parser.add_argument("--runs", type=int, default=2, help="repetitions (LLM output varies)")
    args = parser.parse_args(argv)

    llm.load_environment()
    try:
        questions = load_questions(args.questions)
        rows = evaluate(questions, runs=args.runs)
    except (FileNotFoundError, ValueError, llm.LlmCallError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print_summary(summarise(rows))
    print(f"\n{len(rows)} rows written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
