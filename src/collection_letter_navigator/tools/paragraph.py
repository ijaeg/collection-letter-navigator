"""FR-14 ``fetch_paragraph``: read one provision out of the knowledge base.

Used to follow a cross-reference inside a retrieved chunk. The text comes from
the committed index, so there is no network call at runtime.

Related: FR-14, FR-04 AC4, FR-10 AC2
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from collection_letter_navigator import retrieval
from collection_letter_navigator.schemas import LawCode, ToolResult
from collection_letter_navigator.tools.contract import not_applicable, tool_result

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "fetch_paragraph"

#: When to use the tool, shown to the model (FR-10 AC1).
DESCRIPTION = (
    "Look up the German text of one section of the BGB, ZPO or RDG in the knowledge base. Use "
    "it only when a source refers to another section that is not among the sources and you "
    "need its wording to answer, e.g. 'nach § 690' inside § 692 ZPO. Needs the law and the "
    "section number without the § sign, e.g. law 'ZPO', section '690'."
)


class FetchParagraphArgs(BaseModel):
    """Arguments of :func:`fetch_paragraph`.

    Related: FR-10 AC1, FR-14
    """

    model_config = ConfigDict(extra="forbid")

    law: LawCode = Field(description="Law the provision belongs to.")
    section: str = Field(description="Section label without the § sign, e.g. '199'.")


def fetch_paragraph(args: FetchParagraphArgs) -> ToolResult:
    """Return the indexed text of one provision.

    Args:
        args: Law and section of the provision.

    Returns:
        A :class:`ToolResult` whose ``result`` holds the chunk ID, the title and
        the German text from the knowledge base. A provision that is not indexed
        yields ``not_applicable_reason`` ("not in the knowledge base").

    Related: FR-14 AC1, FR-14 AC2, FR-10 AC4
    """
    section = re.sub(r"[§\s]", "", args.section).lower()
    # AI: no search here - an exact lookup in the committed index (no network call)
    chunks = [
        doc
        for doc in retrieval.load_corpus()
        if doc.metadata.get("law") == args.law and str(doc.metadata.get("section")) == section
    ]
    reference = f"{args.law} § {section}"
    if not chunks:
        return not_applicable(
            TOOL_NAME,
            f"{reference} is not in the knowledge base; it covers selected sections of the BGB, "
            "ZPO and RDG only.",
        )
    return tool_result(
        TOOL_NAME,
        {
            "provision": reference,
            "title": str(chunks[0].metadata.get("title", "")),
            "chunk_ids": [str(doc.metadata.get("chunk_id")) for doc in chunks],
            "text": "\n".join(doc.page_content for doc in chunks),
        },
        assumptions=["The text is the version in the knowledge base, not necessarily today's."],
        legal_basis=[reference],
    )
