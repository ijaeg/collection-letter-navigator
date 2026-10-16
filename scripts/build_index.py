"""Offline script that builds the committed Chroma index.

Run with ``uv run python scripts/build_index.py``. Downloads (or reuses) the
statute XML, chunks the provisions listed in ``data/kb_scope.yaml``, embeds them
and writes the index plus its manifest. Running it twice on the same XML yields
the same chunk IDs and chunk count.

Related: FR-04, FR-21 AC6, NFR-10, §9
"""

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    """Parse the command-line arguments.

    Returns:
        The parsed arguments: scope file, index directory, and whether to force
        a fresh download instead of using the cache.

    Related: FR-04 AC1
    """
    raise NotImplementedError("FR-04 AC1: parse scope path, index path and --refresh")


def main() -> int:
    """Build the knowledge base end to end.

    Returns:
        Process exit code: 0 on success.

    Raises:
        SystemExit: If the scope file or the statute XML cannot be read.

    Related: FR-04 AC1, FR-04 AC4, FR-04 AC5
    """
    raise NotImplementedError("FR-04 AC1: build and persist the knowledge base")


if __name__ == "__main__":
    raise SystemExit(main())
