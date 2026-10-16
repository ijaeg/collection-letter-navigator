"""FR-14 ``fetch_paragraph``: read one provision out of the knowledge base.

Used to follow a cross-reference inside a retrieved chunk. The text comes from
the committed index, so there is no network call at runtime.

Related: FR-14, FR-04 AC4, FR-10 AC2
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from collection_letter_navigator.schemas import LawCode, ToolResult

#: Name the model uses to call this tool (FR-10 AC1).
TOOL_NAME = "fetch_paragraph"


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
    raise NotImplementedError("FR-14 AC1: read the provision from the committed index")
