"""Shared fixtures. Every LLM call in the tests runs against a mock.

No test ever reaches OpenRouter: the chat model is replaced by a fake that
returns prepared replies, including prepared tool calls.

Related: NFR-06, FR-10, §7.4
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest


@pytest.fixture
def mock_chat_model() -> Any:
    """Provide a LangChain chat model stand-in with scripted replies.

    The fake supports the three things the pipeline needs: a structured output
    reply (`RetrievalPlan`, `AnswerWithSources`, `LetterFacts`), a reply that
    carries tool calls, and a failure mode for the error-handling tests.

    Returns:
        A chat model stand-in whose replies the test sets up.

    Related: NFR-06, FR-10 AC1, NFR-02
    """
    raise NotImplementedError("NFR-06: provide a mocked LangChain chat model")


@pytest.fixture
def mock_retrieved_chunks() -> Sequence[Any]:
    """Provide a small set of retrieved chunks with stable IDs.

    Returns:
        Scored chunks used by the answer, quote-check and tool-loop tests.

    Related: NFR-06, FR-08 AC2, FR-09 AC1
    """
    raise NotImplementedError("NFR-06: provide fixed retrieved chunks for the answer tests")
