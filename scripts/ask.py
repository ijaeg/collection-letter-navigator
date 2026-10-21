"""Ask the pipeline one question from the terminal (developer smoke test).

Shows what the UI will show later: the German queries and the filter, the
retrieved chunks, the tool calls, the checked answer with its sources, the
checks of FR-09, the token usage and the time per step. Use only fictional data.

    uv run python scripts/ask.py "A court payment order came on 14 October 2026. \\
        Until when can I object?" --sender court --document mahnbescheid \\
        --delivered 2026-10-14

Related: §5.2, FR-08, FR-09, FR-10, FR-17, FR-18, FR-19, NFR-04
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from collection_letter_navigator import guards, llm, pipeline, retrieval
from collection_letter_navigator.schemas import TriageResult


def parse_args() -> argparse.Namespace:
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(description="Ask one question (developer smoke test).")
    parser.add_argument("question")
    parser.add_argument(
        "--sender", choices=["creditor", "collection_agency", "court", "not_sure"], default=None
    )
    parser.add_argument(
        "--document", choices=["mahnbescheid", "vollstreckungsbescheid", "unclear"], default=None
    )
    parser.add_argument("--delivered", type=date.fromisoformat, default=date.today())
    parser.add_argument("--mode", choices=["vector", "bm25", "hybrid"], default=None)
    return parser.parse_args()


def main() -> int:
    """Run one question and print every intermediate result."""
    args = parse_args()
    llm.load_environment()
    triage = None
    if args.sender:
        document = args.document if args.sender == "court" else None
        triage = TriageResult(
            sender=args.sender, court_document=document, delivered_on=args.delivered
        )
    try:
        out = pipeline.ask(args.question, triage, mode=args.mode, progress=print)
    except (guards.EmptyInputError, guards.InputTooLongError, guards.InjectionDetectedError) as e:
        print(f"Blocked: {e}")
        return 1
    except llm.LlmCallError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    plan = out.retrieval.plan
    print("\n== Retrieval plan ==")
    for query in plan.queries_de:
        print(f"  query: {query}")
    print(f"  filter: {out.retrieval.applied_filter} (fallback: {out.retrieval.filter_fallback})")
    print(f"  why: {plan.rationale}")
    print("\n== Retrieved chunks ==")
    for chunk in out.retrieval.chunks:
        print(f"  {chunk.chunk_id:<12} {chunk.score:.4f}  {chunk.document.metadata.get('title')}")
    print("\n== Tools ==")
    for result in out.answer.tool_results or []:
        print(f"  {result.tool}: {result.result or result.not_applicable_reason}")
        for assumption in result.assumptions:
            print(f"    assumes: {assumption}")
    if not out.answer.tool_results:
        print("  (none)")
    a = out.answer.answer
    print("\n== Answer ==")
    print(a.answer_en)
    print(
        f"\n  sources: {a.source_chunk_ids}  tools: {a.used_tools}  out of scope: {a.out_of_scope}"
    )
    print("\n== Legal basis (from the knowledge base) ==")
    for chunk_id in a.source_chunk_ids:
        doc = retrieval.get_chunk_by_id(chunk_id)
        if doc is not None:
            print(f"  {doc.page_content[:160]}…")
    print("\n== Checks ==")
    print(f"  dropped chunk IDs: {out.answer.dropped_chunk_ids}")
    print(f"  replaced quotes:   {out.answer.replaced_quotes}")
    print(f"  tool limit:        {out.answer.tool_call_limit_reached}")
    print(f"  structured fallback call: {out.answer.structured_fallback}")
    tokens = sum(u.prompt_tokens + u.completion_tokens for u in out.answer.usages)
    print(f"  answer calls: {len(out.answer.usages)}, tokens: {tokens}")
    print("  seconds: " + ", ".join(f"{k} {v:.1f}" for k, v in out.seconds.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
