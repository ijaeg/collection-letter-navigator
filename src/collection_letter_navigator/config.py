"""Central configuration: models, paths, limits, timeouts and feature switches.

Every value the spec names is defined here once, so that switching the model,
the retrieval mode or a limit needs no code change elsewhere (FR-20 AC2).
Secrets are never stored here: only the *name* of the environment variable that
holds the OpenRouter key is a constant (FR-23 AC3).

Related: FR-02, FR-04, FR-05, FR-07, FR-10, FR-13, FR-16, FR-19, FR-20, FR-21,
FR-23, NFR-02, NFR-03, NFR-04, §7.2, §7.3, §12
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths (§9)
# ---------------------------------------------------------------------------

#: Repository root; all other paths are derived from it.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

# The gitignored .env is loaded before any setting below is read, so that values
# in .env (e.g. CHAT_MODEL) take effect; an exported variable always wins (NFR-01).
load_dotenv(PROJECT_ROOT / ".env", override=False)

#: Directory holding the knowledge-base scope, the index and the demo letters.
DATA_DIR: Path = PROJECT_ROOT / "data"

#: Persisted Chroma index, committed to the repository (FR-04 AC4).
INDEX_DIR: Path = DATA_DIR / "index"

#: Snapshot date and embedding model of the committed index (FR-04 AC4, FR-21 AC6).
INDEX_MANIFEST_PATH: Path = INDEX_DIR / "manifest.json"

#: List of provisions that are indexed (FR-04 AC1).
KB_SCOPE_PATH: Path = DATA_DIR / "kb_scope.yaml"

#: Bundesbank base rates with source and retrieval date (FR-13 AC1, D-5).
BASE_RATES_PATH: Path = DATA_DIR / "base_rates.csv"

#: Fictional demo letters for the demo cases (FR-03 AC3).
SAMPLE_LETTERS_DIR: Path = DATA_DIR / "samples" / "letters"

#: Markdown prompt files; no prompt text lives in ``.py`` files (NFR-05).
PROMPTS_DIR: Path = PROJECT_ROOT / "prompts"

#: Evaluation datasets and result CSVs (§7).
EVAL_DIR: Path = PROJECT_ROOT / "eval"

#: Opt-in debug log directory, gitignored (FR-23 AC2).
LOG_DIR: Path = PROJECT_ROOT / "logs"

#: Opt-in JSONL log of LLM calls, used only with fictional data (FR-23 AC2).
DEBUG_LOG_PATH: Path = LOG_DIR / "llm_calls.jsonl"

# ---------------------------------------------------------------------------
# OpenRouter and models (NFR-01, D-1, D-2)
# ---------------------------------------------------------------------------

#: OpenAI-compatible base URL; chat *and* embeddings run through it (NFR-01).
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

#: Name of the environment variable holding the API key; never the key itself.
OPENROUTER_API_KEY_ENV: str = "OPENROUTER_API_KEY"

#: Models endpoint used for price lookup, fetched once per session (FR-19 AC2).
OPENROUTER_MODELS_URL: str = f"{OPENROUTER_BASE_URL}/models"

#: Default chat model, overridable by the ``CHAT_MODEL`` env var (D-2, FR-20 AC2).
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "openai/gpt-5-mini")

#: Default embedding model, overridable by ``EMBEDDING_MODEL`` (D-1, FR-04 AC6).
#: Chosen in the spike (spikes/NOTES.md); fallback: openai/text-embedding-3-small.
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")

#: Prefix before a search query; only e5-style models need one ("query: ") (FR-04 AC6).
EMBEDDING_QUERY_PREFIX: str = os.getenv("EMBEDDING_QUERY_PREFIX", "")

#: Prefix before an indexed passage; only e5-style models need one ("passage: ") (FR-04 AC6).
EMBEDDING_PASSAGE_PREFIX: str = os.getenv("EMBEDDING_PASSAGE_PREFIX", "")

#: OpenRouter provider routing: no training on our data, zero data retention (D-3, FR-23 AC4).
PROVIDER_PREFERENCES: dict[str, object] = {"data_collection": "deny", "zdr": True}

#: Default reasoning effort passed to the chat model (FR-20 AC1, NFR-03).
REASONING_EFFORT: str = os.getenv("REASONING_EFFORT", "low")

#: Reasoning effort of the retrieval-plan call; may be lower than the answer's (R-11, NFR-04).
PLAN_REASONING_EFFORT: str = os.getenv("PLAN_REASONING_EFFORT", REASONING_EFFORT)

#: Token ceiling per call; reasoning tokens count against it (NFR-03).
MAX_TOKENS: int = 4_000

# ---------------------------------------------------------------------------
# Knowledge base and retrieval (FR-04 to FR-07)
# ---------------------------------------------------------------------------

#: Laws that may be indexed and filtered on (FR-04 AC1, FR-06 AC1).
KB_LAWS: tuple[str, ...] = ("BGB", "ZPO", "RDG")

#: Name of the Chroma collection inside :data:`INDEX_DIR`.
CHROMA_COLLECTION_NAME: str = "german_law"

#: A section longer than this many characters is split by subsection (FR-04 AC2).
MAX_CHUNK_CHARACTERS: int = 2_000

#: Number of chunks passed to the answer call (FR-07 AC2).
RETRIEVAL_TOP_K: int = 6

#: Hits fetched per query and retriever before fusion; more than k so that fusion
#: has candidates to choose from (FR-07 AC1).
RETRIEVAL_FETCH_K: int = 20

#: Retrieval mode: ``vector``, ``bm25`` or ``hybrid`` (FR-07 AC4, FR-20 AC1).
RETRIEVAL_MODE: str = os.getenv("RETRIEVAL_MODE", "hybrid")

#: Whether the query-translation step runs; ``off`` also disables the filter (FR-05 AC4, AC5).
QUERY_TRANSLATION_ENABLED: bool = os.getenv("QUERY_TRANSLATION", "on").lower() == "on"

#: Rank constant of the reciprocal rank fusion used to merge result lists (FR-07 AC1).
RRF_K: int = 60

#: Below this many filtered hits the search is retried unfiltered (FR-06 AC3).
MIN_FILTERED_RESULTS: int = 2

#: Provisions a query names explicitly ("§ 199 BGB") are moved to the top of the fused
#: list; on by default since D-8 (development questions, 2026-10-20) (FR-07 AC3).
PIN_EXPLICIT_REFERENCES: bool = os.getenv("PIN_EXPLICIT_REFERENCES", "on").lower() == "on"

#: At most this many explicitly named provisions are pinned (D-8).
MAX_PINNED_REFERENCES: int = 2

#: Official XML source of the statute texts (FR-04 AC1).
GESETZE_IM_INTERNET_BASE_URL: str = "https://www.gesetze-im-internet.de"

# ---------------------------------------------------------------------------
# Input limits and loop bounds (FR-02, FR-08, FR-10, FR-13, FR-16)
# ---------------------------------------------------------------------------

#: Maximum length of a chat question (FR-02 AC2).
MAX_QUESTION_CHARACTERS: int = 1_000

#: Maximum length of a pasted letter (FR-16 AC1).
MAX_LETTER_CHARACTERS: int = 6_000

#: Soft word budget for the English answer (FR-08 AC1).
MAX_ANSWER_WORDS: int = 250

#: Maximum number of tool calls per question (FR-10 AC5).
MAX_TOOL_CALLS_PER_QUESTION: int = 3

#: Smallest principal the interest tool accepts, exclusive (FR-13).
MIN_PRINCIPAL_EUR: float = 0.0

#: Largest principal the interest tool accepts, inclusive (FR-13).
MAX_PRINCIPAL_EUR: float = 100_000.0

# ---------------------------------------------------------------------------
# Legal constants used by the deterministic tools (FR-11 to FR-15)
# ---------------------------------------------------------------------------

#: Objection period for court payment and enforcement orders (FR-11 AC1).
OBJECTION_PERIOD_WEEKS: int = 2

#: Regular limitation period in years (BGB § 195, FR-12 AC1).
LIMITATION_PERIOD_YEARS: int = 3

#: Claims arising before this date fall under old law and are refused (FR-12 AC3).
LIMITATION_EARLIEST_CLAIM_DATE: date = date(2002, 1, 1)

#: Consumer default interest markup over the base rate, in percentage points (FR-13 AC1).
DEFAULT_INTEREST_MARKUP_POINTS: float = 5.0

#: Claims arising before this date are outside the collection-fee rules (FR-15 AC1).
COLLECTION_FEES_EARLIEST_CLAIM_DATE: date = date(2021, 10, 1)

#: Default holiday scope when no federal state is given (FR-11 AC2, D-6).
HOLIDAY_COUNTRY: str = "DE"

# ---------------------------------------------------------------------------
# Error handling, timeouts and responsiveness (NFR-02, NFR-04)
# ---------------------------------------------------------------------------

#: Request timeout for every OpenRouter call, in seconds (NFR-02).
REQUEST_TIMEOUT_SECONDS: int = 60

#: Retries on HTTP 429 and 5xx, with exponential backoff (NFR-02).
MAX_RETRIES: int = 2

#: Base delay of the exponential backoff, in seconds (NFR-02).
RETRY_BACKOFF_SECONDS: float = 1.0

#: Retries when a structured output fails schema validation (NFR-02).
JSON_RETRY_ATTEMPTS: int = 1

#: Target wall-clock time for a typical question, reported in §7.2 (NFR-04).
TARGET_ANSWER_SECONDS: int = 20

#: Whether the opt-in debug log is written; set ``DEBUG_LOG=1`` (FR-23 AC2).
DEBUG_LOG_ENABLED: bool = os.getenv("DEBUG_LOG", "0") == "1"

# ---------------------------------------------------------------------------
# UI texts that must be identical on every screen (FR-21, FR-22, FR-23)
# ---------------------------------------------------------------------------

#: Disclaimer shown on every screen (FR-21 AC1).
DISCLAIMER_EN: str = "This app provides general legal information, not legal advice."

#: Privacy notice shown above every input (FR-23 AC1).
PRIVACY_NOTICE_EN: str = (
    "Your questions and letter text are sent to an LLM provider via OpenRouter for "
    "processing. They are not stored by this app. Personal data in pasted letters is "
    "redacted before sending."
)

#: Message shown when the injection guard blocks a text (FR-22 AC1).
INJECTION_BLOCKED_MESSAGE_EN: str = (
    "Your text contains instructions addressed to an AI. Please remove them."
)

#: Free counselling services shown in the footer and in every refusal (FR-21 AC5).
#: TODO (FR-21 AC5): verify every link is reachable before submission.
GET_HELP_LINKS: tuple[tuple[str, str], ...] = (
    ("Consumer advice centres (Verbraucherzentrale)", "https://www.verbraucherzentrale.de"),
    ("Free debt counselling (Schuldnerberatung)", "https://www.meine-schulden.de"),
)

#: Answer options of "Who sent the letter?" (FR-01 AC1).
SENDER_LABELS: dict[str, str] = {
    "creditor": "The company I owe money to (e.g. a shop, bank, insurer or phone provider)",
    "collection_agency": "A debt collection agency or a law firm collecting for someone else",
    "court": "A court",
    "not_sure": "I'm not sure",
}

#: Answer options of "Which document is it?", one line each (FR-01 AC2).
COURT_DOCUMENT_LABELS: dict[str, str] = {
    "mahnbescheid": "Mahnbescheid – payment order: first court letter, claim not checked",
    "vollstreckungsbescheid": (
        "Vollstreckungsbescheid – enforcement order: issued when no objection was filed"
    ),
    "unclear": "Unclear – I can't tell which of the two it is",
}

#: Help text of the delivery date (FR-01 AC1).
DELIVERY_DATE_HELP_EN: str = (
    "For court letters, use the delivery date written on the envelope. "
    "If you don't know it, use the day you found the letter."
)

#: Guide shown for "not sure" (FR-01 AC4).
NOT_SURE_GUIDE_EN: str = (
    "**How to tell a court letter from a company letter:** a court letter names a court "
    "(*Amtsgericht*) as the sender, usually comes in a yellow envelope with the delivery "
    "date written on it (*Zustellung*), and has a case number (*Geschäftszeichen*). "
    "A collection agency or a company writes on its own letterhead and sets its own "
    "payment date."
)

#: Caution shown for "not sure" (FR-01 AC4).
NOT_SURE_CAUTION_EN: str = (
    "If this is a court document, a two-week deadline may already be running."
)

#: Number of earlier question-answer pairs passed to the answer call (FR-08).
HISTORY_TURNS: int = 3

#: "Common situations" buttons shown below the chat input (FR-03 AC4).
COMMON_SITUATIONS: tuple[str, ...] = (
    "I don't think I owe this",
    "The amount looks too high",
    "I already paid this",
    "I can only pay later",
    "Can I pay in instalments?",
    "The fees look too high",
    "The interest looks too high",
    "Is this debt too old?",
    "Is this letter a scam?",
    "What happens if I do nothing?",
)

# ---------------------------------------------------------------------------
# Evaluation targets (§7.2, §7.3)
# ---------------------------------------------------------------------------

#: Cut-off of the Hit-Rate metric (§7.2).
HIT_RATE_AT_K: int = 5

#: Cut-off of the MRR metric (§7.2).
MRR_AT_K: int = 10

#: Minimum Hit-Rate@5 of the chosen retrieval configuration (§7.2).
HIT_RATE_TARGET: float = 0.80

#: Minimum share of questions whose ``law_filter`` covers every expected law (§7.2).
FILTER_ACCURACY_TARGET: float = 0.90

#: Minimum share of cases with the expected tool call (§7.3).
TOOL_SELECTION_TARGET: float = 0.90

#: Minimum share of tool calls with all expected arguments correct (§7.3).
ARGUMENT_ACCURACY_TARGET: float = 0.80

#: Retrieval configurations compared in the evaluation (§7.2).
RETRIEVAL_CONFIGURATIONS: tuple[tuple[str, bool, str], ...] = (
    ("R1", False, "vector"),
    ("R2", True, "vector"),
    ("R3", False, "hybrid"),
    ("R4", True, "hybrid"),
)

#: Test-set categories, derived from the common situations (§7.1).
EVAL_CATEGORIES: tuple[str, ...] = (
    "deadline",
    "disputed",
    "amount_too_high",
    "already_paid",
    "pay_later",
    "instalments",
    "fees",
    "interest",
    "limitation",
    "legitimacy",
    "ignore_consequences",
    "out_of_scope",
)
