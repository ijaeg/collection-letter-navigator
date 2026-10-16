"""Retrieval evaluation: run R1 to R4 over the test set and write the results.

Run with ``uv run python eval/run_retrieval_eval.py``. Every configuration runs
on every question of ``eval/retrieval_questions.json``; the CSV records the
knowledge-base snapshot date, the model names and the settings so that a run can
be reproduced.

Related: §7.2, §7.5, FR-05 AC4, FR-07 AC4, NFR-10
"""

from __future__ import annotations

from pathlib import Path


def load_questions(path: Path | None = None) -> list[dict[str, object]]:
    """Read the evaluation questions.

    Args:
        path: Dataset file; defaults to ``eval/retrieval_questions.json``.

    Returns:
        The questions, each with ``question_en``, ``sender``, ``expected`` and
        ``category``.

    Raises:
        FileNotFoundError: If the dataset is missing.
        ValueError: If a question does not match the schema of §7.1.

    Related: §7.1
    """
    raise NotImplementedError("§7.1: read the retrieval test set")


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
    raise NotImplementedError("§7.2: Hit-Rate@k over the expected provisions")


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
    raise NotImplementedError("§7.2: MRR@k over the expected provisions")


def filter_accuracy(law_filter: list[str] | None, expected: list[str]) -> float:
    """Check whether the law filter covers every expected provision.

    Args:
        law_filter: The filter the retrieval plan produced, or None.
        expected: The expected provisions.

    Returns:
        1.0 if every expected law is allowed by the filter, else 0.0.

    Related: §7.2, FR-06 AC1
    """
    raise NotImplementedError("§7.2: filter accuracy against the expected laws")


def main() -> int:
    """Run every configuration on every question and write the results CSV.

    Returns:
        Process exit code: 0 on success.

    Related: §7.2, §7.5 AC1, NFR-10
    """
    raise NotImplementedError("§7.2: run R1-R4 and write eval/retrieval_results.csv")


if __name__ == "__main__":
    raise SystemExit(main())
