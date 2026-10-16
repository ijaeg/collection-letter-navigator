"""Tool-calling evaluation: expected tool and arguments per case.

Run with ``uv run python eval/run_tool_eval.py``. Measures how often the model
calls the expected tool (or none) and how often the arguments are right.

Related: §7.3, FR-10, NFR-10
"""

from __future__ import annotations

from pathlib import Path


def load_cases(path: Path | None = None) -> list[dict[str, object]]:
    """Read the tool-calling cases.

    Args:
        path: Dataset file; defaults to ``eval/tool_cases.json``.

    Returns:
        The cases, each with a question, the expected tool (or "no tool") and
        the expected arguments.

    Raises:
        FileNotFoundError: If the dataset is missing.

    Related: §7.1, §7.3
    """
    raise NotImplementedError("§7.1: read the tool-calling cases")


def score_tool_selection(actual: str | None, expected: str | None) -> float:
    """Score the tool choice of one case.

    Args:
        actual: Tool the model called, or None if it called none.
        expected: Tool the case expects, or None for "no tool".

    Returns:
        1.0 on a match, else 0.0.

    Related: §7.3
    """
    raise NotImplementedError("§7.3: score tool selection accuracy")


def score_arguments(actual: dict[str, object], expected: dict[str, object]) -> float:
    """Score the arguments of one tool call.

    Args:
        actual: Arguments the model passed.
        expected: Arguments the case expects.

    Returns:
        1.0 if every expected argument matches, else 0.0.

    Related: §7.3
    """
    raise NotImplementedError("§7.3: score argument accuracy")


def main() -> int:
    """Run every case and report the two metrics.

    Returns:
        Process exit code: 0 on success.

    Related: §7.3, NFR-10
    """
    raise NotImplementedError("§7.3: run the tool-calling evaluation")


if __name__ == "__main__":
    raise SystemExit(main())
