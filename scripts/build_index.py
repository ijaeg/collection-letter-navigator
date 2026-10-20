"""Offline script that builds the committed Chroma index.

Run with ``uv run python scripts/build_index.py``. Downloads (or reuses) the
statute XML, chunks the provisions listed in ``data/kb_scope.yaml``, embeds them
and writes the index plus its manifest. Running it twice on the same XML yields
the same chunk IDs and chunk count.

Related: FR-04, FR-21 AC6, NFR-10, §9
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document

from collection_letter_navigator import config, ingest, llm


def parse_args() -> argparse.Namespace:
    """Parse the command-line arguments.

    Returns:
        The parsed arguments: scope file, index directory, whether to force
        a fresh download, and whether to stop after chunking (no embedding).

    Related: FR-04 AC1
    """
    parser = argparse.ArgumentParser(description="Build the Chroma index (FR-04).")
    parser.add_argument("--scope", type=Path, default=config.KB_SCOPE_PATH)
    parser.add_argument("--index-dir", type=Path, default=config.INDEX_DIR)
    parser.add_argument("--refresh", action="store_true", help="download the XML again")
    parser.add_argument("--dry-run", action="store_true", help="chunk only, do not embed")
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="rewrite manifest.json for the unchanged index, without embedding",
    )
    return parser.parse_args()


def main() -> int:
    """Build the knowledge base end to end.

    Returns:
        Process exit code: 0 on success, 1 on a readable error.

    Related: FR-04 AC1, FR-04 AC4, FR-04 AC5
    """
    args = parse_args()
    llm.load_environment()
    try:
        scope = ingest.load_kb_scope(args.scope)
        chunks = ingest.build_chunks(scope, refresh=args.refresh)
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not chunks:
        print("Error: the scope selects no sections; fill kb_scope.yaml first.", file=sys.stderr)
        return 1
    per_law = Counter(chunk.metadata["law"] for chunk in chunks)
    longest = max(chunks, key=lambda c: len(c.page_content))
    print(f"{len(chunks)} chunks: " + ", ".join(f"{law} {n}" for law, n in per_law.items()))
    print(f"Longest chunk: {longest.id} ({len(longest.page_content)} characters)")
    if args.dry_run:
        return 0
    if args.manifest_only:
        return rewrite_manifest(chunks, args.index_dir)

    started = time.perf_counter()
    try:
        ingest.write_index(chunks, args.index_dir)
    except (RuntimeError, llm.LlmCallError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    ingest.write_manifest(chunks, args.index_dir)
    print(f"Index written to {args.index_dir} in {time.perf_counter() - started:.1f} s")
    return 0


def rewrite_manifest(chunks: list[Document], index_dir: Path) -> int:
    """Rewrite the manifest of an unchanged index, keeping model and build time.

    Refuses if the chunks differ from the indexed ones, because then the index
    itself must be rebuilt.

    Returns:
        Process exit code: 0 on success, 1 if the index would have to be rebuilt.

    Related: FR-04 AC4, NFR-10
    """
    try:
        old = ingest.read_manifest(index_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if old.get("chunk_ids") != [str(chunk.id) for chunk in chunks]:
        print("Error: the chunks differ from the indexed ones; rebuild the index.", file=sys.stderr)
        return 1
    ingest.write_manifest(
        chunks,
        index_dir,
        embedding_model=str(old["embedding_model"]),
        built_at=str(old["built_at"]),
    )
    print(f"Manifest rewritten in {index_dir} (index unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
