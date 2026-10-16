# Spike notes

Record of the spike results (Fri 2026-10-16 to Sun 2026-10-18). Feeds spec v0.2.

## D-1 Embedding model (Fri 10-16)

### Availability with the course API key

The OpenRouter key is provided by Turing College. Its workspace guardrails restrict which models can be used; they cannot be changed by the student.

| Model | Available |
|---|---|
| `intfloat/multilingual-e5-large` | no – blocked by guardrail (`model-ignored-by-guardrail`, HTTP 404) |
| `google/gemini-embedding-001` | no |
| `openai/text-embedding-3-small` | yes |
| `openai/text-embedding-3-large` | yes |
| `qwen/qwen3-embedding-8b` | yes |
| `mistralai/mistral-embed-2312` | yes |

### Cross-lingual check

Script: `spikes/embedding_check.py`. Four simplified German legal statements (paraphrases, not statute text) and four English lay questions; each question should be closest to its matching statement. Run without input prefixes (`QUERY_PREFIX="" PASSAGE_PREFIX=""`); raw output in `spikes/embedding_*.txt`.

Margin = score of the correct statement minus score of the runner-up (per question). Absolute scores are not comparable between models (each model has its own scale), so models are compared by their margins.

| Model | Top-1 | Smallest margin | Mean margin | Dimensions |
|---|---|---|---|---|
| `qwen/qwen3-embedding-8b` | 4/4 | **0.070** | 0.159 | 4096 |
| `openai/text-embedding-3-small` | 4/4 | 0.031 | 0.108 | 1536 |
| `mistralai/mistral-embed-2312` | 4/4 | 0.031 | 0.055 | 1024 |
| `openai/text-embedding-3-large` | 3/4 | miss | 0.167 | 3072 |

### Observations

- The hardest question for every model was "My phone bill is from 2021. Is it too old to be collected?" (expected: BGB § 195). The lay phrase "too old" shares little with "Verjährungsfrist". Qwen separates it best (margin 0.070 vs. 0.031 for the next models); `text-embedding-3-large` misses it.
- `mistral-embed-2312` gets all four right, but its scores are compressed (0.65–0.78), which leaves little room once many similar chunks compete.
- Hypothesis for Sunday: query translation (FR-05) should help most on lay phrasings like "too old".

### Limits of this check

- Only 4 pairs with short paraphrases; real chunks are longer and more similar to each other.
- One run per model; no instruction prompt for Qwen3 (supported by the model, possible tuning knob later).

### Decision

- **Embedding model: `qwen/qwen3-embedding-8b`, without input prefixes.**
- **Fallback: `openai/text-embedding-3-small`** (switch via `EMBEDDING_MODEL`).
- To be confirmed on Sun 10-18 with the 10 development questions on the real statute chunks; if time allows, build the index once more with the fallback model and compare.
- Consequences for spec v0.2: D-1 (decision, e5 removed), NFR-01 (a reviewer's key must allow the embedding model – note in the README setup), `.env.example` and `config.py` (model, empty prefixes), FR-04 AC6 (prefix handling stays configurable).

## D-7 LangChain interfaces (Fri 10-16)

- Structured output (`with_structured_output`, method `json_schema`, `openai/gpt-5-mini`, effort low): **works** – 3/3 valid RetrievalPlans.
- Example (Q1 "court letter, how long to object?"): queries `Mahnbescheid Widerspruch Frist 14 Tage ZPO`, `Einspruch Vollstreckungsbescheid Frist 2 Wochen ZPO`; filter `["ZPO"]`.
- Findings for `prompts/retrieval_plan.md` (FR-05, FR-06):
  - `rationale` came back in German → require English (NFR-09, shown in the RAG panel).
  - Filter too broad when unsure (Q2: all three laws = no filter) → rule "at most two laws, otherwise null"; measured as filter accuracy (§7.2).
  - Case facts leak into queries ("Handyrechnung", "Telekommunikationsvertrag") → rule "statutory terms only, no facts of the user's case".
  - Up to 4 queries per question; 2–3 are probably enough → check in Sunday's spike.
  - Queries contain section numbers ("§195 BGB") → useful for BM25 (FR-07).
- Tool calling (`bind_tools` + ToolMessage loop): **works** – model requested `add_weeks({'start_date': '2026-10-14', 'weeks': 2})` with correctly typed arguments, the script executed it, the model answered from the result ("2026-10-28") instead of calculating itself.
- Observations: a tool question needs 2 LLM calls (+1 for query translation) → check latency against NFR-04 (20 s) and cost on Sunday. Spike answer is terse; the real prompt structures it via the tool contract (result, assumptions, missing information). Still open: E-8 (tools + structured output in one call) → Sunday.
- Relative dates: "delivered last Tuesday" was resolved to 2026-10-13 (correct for Fri 2026-10-16) although no date was in the prompt – the provider apparently injects the current date. The model stated its assumption. Not reliable or testable → the app passes today's date explicitly in the system prompt; tools receive absolute dates only; the model states how it resolved a relative date or asks back (new AC for FR-10 in spec v0.2).

## D-3 Data retention routing (Fri 10-16)

- Option found in the OpenRouter docs: provider routing via `extra_body={"provider": {"data_collection": "deny", "zdr": True}}` – only providers that do not collect data for training and do not retain prompts (zero data retention).
- Course guardrails: the same workspace guardrails also hold data policy settings (see the D-1 error message); they cannot be changed with the course key.
- Tested in a call: **yes** – `structured_output_check.py` with both options succeeds for `openai/gpt-5-mini` (no "0 endpoints … data policy" error), so at least one eligible provider exists and the restriction is applied.
- Side finding: results vary between runs (Q2 filter `BGB, ZPO, RDG` at midday vs. `BGB` now, Q3 the other way round) → §7.2 runs each question at least twice and reports the spread.
- Not yet covered: embedding calls → pass the same provider options via `model_kwargs={"extra_body": ...}`, test on Sun 10-18.
- **Decision:** both options on by default for all chat calls (FR-23 AC4), set once in `llm.py`/`config.py`; embeddings to follow after Sunday's test.

## Open points for the next days

- Sat 10-17: build the index for the BGB and ZPO scope (FR-04) with `qwen/qwen3-embedding-8b`; write the 10 development questions (`eval/dev_questions.json`).
- Sun 10-18: end-to-end spike – confirm D-1 on real chunks (optionally against `openai/text-embedding-3-small`), test E-8 (tools + structured output in one call), test the provider options for embeddings (D-3), measure latency and cost per question.
- Spec v0.2 (Mon 10-19): D-1 decision, NFR-01 guardrail note, `.env.example`/`config.py` (model, empty prefixes), rules for `prompts/retrieval_plan.md`, today's date in the system prompt (FR-10), BM25 directly with `rank-bm25` instead of `langchain-community` (deprecation warning), load `.env` before `config.py` reads environment variables, provider options for data retention (D-3), evaluation runs each question at least twice (§7.2).
