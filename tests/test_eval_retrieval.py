"""Tests for ``eval/run_retrieval_eval.py``: metrics, dataset schema and one offline run.

The script lives outside the package, so it is loaded from its file path. The
offline run uses BM25 only and a scripted retrieval plan: no API call.

Related: §7.1, §7.2, §7.5 AC1, NFR-06
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from collection_letter_navigator import config, retrieval
from collection_letter_navigator.schemas import RetrievalPlan


def _load_script() -> ModuleType:
    path = config.EVAL_DIR / "run_retrieval_eval.py"
    spec = importlib.util.spec_from_file_location("run_retrieval_eval", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = _load_script()


def test_hit_rate_counts_any_expected_provision_in_the_top_k() -> None:
    """One expected provision in the top k is a hit (§7.2)."""
    ranked = ["ZPO § 700", "ZPO § 694", "ZPO § 692"]
    assert ev.hit_rate_at_k(ranked, ["ZPO § 692"], 3) == 1.0
    assert ev.hit_rate_at_k(ranked, ["ZPO § 692"], 2) == 0.0


def test_reciprocal_rank_uses_the_first_expected_provision() -> None:
    """MRR looks at the best-ranked expected provision only (§7.2)."""
    ranked = ["BGB § 200", "BGB § 199", "BGB § 195"]
    assert ev.reciprocal_rank(ranked, ["BGB § 195", "BGB § 199"], 10) == pytest.approx(0.5)
    assert ev.reciprocal_rank(ranked, ["BGB § 288"], 10) == 0.0


def test_filter_accuracy_requires_every_expected_law() -> None:
    """A filter is correct only if it allows the law of every expected provision."""
    assert ev.filter_accuracy(["ZPO"], ["ZPO § 222", "BGB § 193"]) == 0.0
    assert ev.filter_accuracy(["ZPO", "BGB"], ["ZPO § 222", "BGB § 193"]) == 1.0
    assert ev.filter_accuracy(None, ["RDG § 13a"]) == 1.0


def test_several_chunks_of_one_section_count_as_one_provision() -> None:
    """BGB-204-1 and BGB-204-2 are both "BGB § 204" (§7.2)."""
    chunks = [retrieval.get_chunk_by_id(i) for i in ("BGB-204-1", "BGB-204-2", "BGB-199")]
    scored = [retrieval.ScoredChunk(d.id or "", d, 1.0) for d in chunks if d is not None]
    assert ev.ranked_provisions(scored) == ["BGB § 204", "BGB § 199"]


def test_dev_questions_match_the_dataset_schema() -> None:
    """The committed development questions pass the schema check of §7.1."""
    questions = ev.load_questions(config.EVAL_DIR / "dev_questions.json")
    assert len(questions) == 10
    assert questions[0]["id"] == "D01"


def test_schema_errors_name_the_question(tmp_path: Path) -> None:
    """A malformed provision is rejected with the question's ID."""
    bad = [
        {
            "id": "X1",
            "question_en": "?",
            "sender": "court",
            "expected": ["§ 692 ZPO"],
            "category": "deadline",
        }
    ]
    path = tmp_path / "q.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="X1: expected"):
        ev.load_questions(path)


def test_offline_run_writes_one_row_per_config_and_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two BM25 configurations over the dev questions, with a scripted plan (§7.5 AC1)."""

    def fake_plan(question_en: str, triage: Any = None, **_: Any) -> RetrievalPlan:
        return RetrievalPlan(queries_de=["Widerspruch Mahnbescheid Frist"], rationale="x")

    monkeypatch.setattr(retrieval, "create_retrieval_plan", fake_plan)
    questions = ev.load_questions(config.EVAL_DIR / "dev_questions.json")
    configs = (("B1", False, "bm25"), ("B2", True, "bm25"))
    rows = ev.evaluate(questions, runs=1, configurations=configs)
    assert len(rows) == 2 * len(questions)
    d01 = next(r for r in rows if r["config"] == "B2" and r["question_id"] == "D01")
    assert d01["hit_at_5"] == 1.0
    summary = {s["config"]: s for s in ev.summarise(rows)}
    assert summary["B2"]["filter_accuracy"] == 1.0
    assert summary["B1"]["filter_accuracy"] is None
