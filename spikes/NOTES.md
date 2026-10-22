# Spike notes

Record of the spike results and the tuning experiments (Fri 2026-10-16 to Tue 2026-10-20). Feeds the spec (v0.2, v0.2.1).

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

## Spike gate: retrieval on the development questions (Mon 10-19)

Run: `uv run python eval/run_retrieval_eval.py --questions eval/dev_questions.json --output eval/dev_results.csv` – 10 development questions, 2 runs, 4 configurations (§7.2); index snapshot 2026-09-26 (BGB), `qwen/qwen3-embedding-8b`, `openai/gpt-5-mini`; no errors, no filter fallback.

| Config | Query translation | Retrieval | Hit-Rate@5 | Run 1 / run 2 | MRR@10 | Filter accuracy | s / question |
|---|---|---|---|---|---|---|---|
| R1 | off | vector | 80 % | 80 / 80 | 0.53 | – | 0.5 |
| R2 | on | vector | 85 % | 80 / 90 | 0.62 | 100 % | 7.4 |
| R3 | off | hybrid | 60 % | 60 / 60 | 0.49 | – | 0.9 |
| R4 | on | hybrid | **85 %** | 80 / 90 | **0.63** | 100 % | 7.6 |

### Decision

- **Gate passed:** best configuration 85 % ≥ 60 %. No scope reduction (§11).
- **Provisional default: R4** (tie with R2 on Hit-Rate@5, R4 ahead on MRR@10 – winner rule of §7.2). Final choice on the test set (Fri 10-23).

### Observations

- Qwen is strong cross-lingually on its own: the English question finds an expected provision in 8 of 10 cases (R1).
- Query translation adds +5 points Hit-Rate@5 and +0.09 MRR – half a question on 10 questions, not a reliable difference. It costs ≈ 7 s per question (one LLM call), a third of the 20 s budget of NFR-04.
- BM25 only helps with German queries: R3 (English question, hybrid) is worse than R1, because English words add noise to the keyword list.
- Filter accuracy 100 %; the model kept to at most two laws.
- Run-to-run variation as expected from D-3: R2 and R4 differ by one question between runs.

### Misses

- **D05, D06 (limitation):** the expected BGB §§ 195/199 lose against the 25 similar chunks of §§ 194–218, mostly BGB § 200 ("Beginn anderer Verjährungsfristen"). The model even writes "§195 BGB" / "§199 BGB" into the queries; BM25 pins them to rank 1 of its own list, but in the fusion a single first place loses to a chunk that ranks high in all six lists.
- **D10 (instalments):** the queries say "Ratenzahlung", the statute says "Teilleistungen" (BGB § 266); in run 1 § 266 is not retrieved at all.
- **D02 (R1):** the English question finds ZPO § 699 only at rank 6; the translated queries fix it.

### Tuning ideas (development questions only, then decided in spec v0.2)

1. Pin provisions named explicitly in a query **after** the fusion (at most two slots), not only inside the BM25 list. Risk: relies on the model knowing the right section numbers; a wrong number puts a wrong provision on top. Would need a README note as a design decision.
2. Add a short list of lay term → statutory term pairs to `prompts/retrieval_plan.md` (e.g. instalments → Teilleistungen, too old → Verjährung) – general vocabulary, not tied to single questions.

## E-8 Tool calling plus structured answer: one call or two? (Mon 10-19)

Script: `spikes/tools_with_structured_output_check.py`, `openai/gpt-5-mini`, effort low, provider options of D-3; one tool `add_weeks` (two weeks, weekend shift; holidays ignored in the spike); three questions, one run.

- **Variant A (one call):** `bind_tools(tools, response_format=Answer, strict=True)` – the model either requests a tool or returns the final answer as JSON in the same call.
- **Variant B (two steps):** plain tool-calling loop, then one extra call with `with_structured_output(Answer)`.

| Question | A: calls / seconds / tokens | B: calls / seconds / tokens |
|---|---|---|
| Court payment order delivered 2026-10-14 – until when to object? (tool) | 2 / 5.5 / 768 | 3 / 10.9 / 997 |
| What is a Mahnbescheid? (no tool) | 1 / 9.3 / 575 | 2 / 9.2 / 992 |
| Enforcement order came 2026-10-09 – last day for Einspruch? (tool) | 2 / 7.8 / 912 | 3 / 11.0 / 1135 |

- Both variants: 3/3 valid answers; the model called `add_weeks` for both deadline questions and did not calculate itself; both dates correct (2026-10-28, 2026-10-23).
- A saves one LLM call per question: 3–5 s and ≈ 20 % tokens on tool questions. With the retrieval plan (≈ 7 s, spike gate) this keeps a typical question closer to the 20 s of NFR-04.

### Decision

- **FR-10 AC8: variant A (one call).** Safeguard: if the final message does not validate as `AnswerWithSources`, one structured-output call over the same messages follows (variant B as fallback, counted in §7.4).
- Limits: 3 questions, one run, one model. The tool-calling evaluation (§7.3) re-checks this on ≈ 15 cases.

### Findings for `prompts/answer.md` (FR-08, FR-10, FR-21)

- **Recommendations slip in:** "To stop the collection, file a written objection …", "If you want to contest it, file the Einspruch by that date …" → the prompt must state facts ("the period ends on …"), never instructions (FR-21, RDG line).
- **General knowledge:** "What is a Mahnbescheid?" was answered without sources (no retrieval in the spike) → in the app, answers come from the retrieved chunks only (FR-08 AC3).
- **Silent assumption:** "the enforcement order came on …" was used as the date of service without saying so → the tool lists this in `assumptions` (FR-11 AC4), and the answer repeats it.
- Terminology: the model calls an *Einspruch* an "objection" → the answer prompt keeps the German term next to the English one ("objection (Einspruch)").

## D-8 Retrieval tuning on the development questions (Tue 10-20)

Two changes from the spike gate, one per run, each run with 2 repetitions on the 10 development questions; baseline: `eval/dev_results.csv` (Mon 10-19).

- **A – lay-term list:** one line in `prompts/retrieval_plan.md` with lay words and the statutory terms to search for (too old → Verjährung, instalments → Teilleistung, …). Output: `eval/dev_results_d8_prompt.csv`.
- **B – A plus pinned references:** provisions a query names explicitly ("§ 199 BGB") are moved to the top of the fused list, at most two, inside the law filter (`PIN_EXPLICIT_REFERENCES=on`). Output: `eval/dev_results_d8_pin.csv`.

| Run | R2 Hit-Rate@5 (run 1 / 2) | R2 MRR@10 | R4 Hit-Rate@5 (run 1 / 2) | R4 MRR@10 |
|---|---|---|---|---|
| Baseline | 85 % (80 / 90) | 0.62 | 85 % (80 / 90) | 0.63 |
| A | 90 % (90 / 90) | 0.67 | 90 % (90 / 90) | 0.61 |
| B | **100 % (100 / 100)** | **0.80** | **100 % (100 / 100)** | **0.81** |

R1 and R3 (no query translation) are not affected by either change: R1 80 % in all three runs.

### Observations

- **Pinning fixes the limitation questions:** D05 and D06 rank first in both runs. The section numbers the model wrote were correct in these runs (§§ 195, 199, 188, 222); once it named a non-existent "§ 212a", which had no effect because no chunk matches it. The limit of two provisions kept the extra numbers (§§ 212, 212a) out.
- **The lay-term list fixes D10:** the queries now contain "Teilleistung", and BGB § 266 is found in every run.
- **A alone is mixed:** Hit-Rate@5 rises, but R4 MRR drops slightly and D06 is missed once in R4 – within the run-to-run variation of the retrieval plan.
- D04: in one run of B the filter was ZPO only although BGB § 193 is also expected (filter accuracy 95 %); a variation of the plan, not caused by pinning; the question was still hit via ZPO § 222.
- Latency was higher today in all configurations, also in R1 without any LLM call (2–3 s instead of 0.5 s) – provider or network, not the changes.

### Decision

- Rule from spec D-8: keep a change only if Hit-Rate@5 or MRR@10 improves without new misses. **B meets it clearly** (no new miss, +15 points Hit-Rate@5, +0.18 MRR@10); B contains A, so **both changes stay**.
- **`PIN_EXPLICIT_REFERENCES` is on by default** (switch off with `PIN_EXPLICIT_REFERENCES=off`).
- Limits for the README: 10 questions, 2 runs – "100 %" means none of the 10 was missed, not a general result; pinning relies on the model naming correct section numbers (limited to two, inside the filter). The test set decides on Fri 10-23.

## D-9 Retrieval plan with reasoning effort `minimal`, and batched embeddings (Wed 10-21 / Thu 10-22)

**Question:** answers took longer than the 20 s of NFR-04. Where does the time go, and can the plan call be made cheaper without losing retrieval quality?

**Latency on the 10 development questions** (`scripts/measure_latency.py`, one run each, `gpt-5-mini`, answer call always `low`):

| Median (max) | `low` (10-21) | plan `minimal` (10-21) | `low`, batched embeddings (10-22) |
|---|---|---|---|
| Retrieval plan | 7.4 s (11.0) | 2.1 s (11.8) | 4.9 s (8.0) |
| Search | 4.5 s (44.8) | 1.9 s (8.5) | **0.5 s (0.6)** |
| Answer | 15.2 s (26.4) | 9.9 s (19.2) | 8.2 s (13.0) |
| Total | 28.2 s (79.6) | 15.4 s (29.0) | **14.6 s (21.0)** |
| Above 20 s | 8 of 10 | 3 of 10 | 1 of 10 |

- The plan with `minimal` uses no reasoning tokens (64–512 with `low`), so the 4–5 s saving is systematic.
- The answer call ran with the same setting in all three runs and still varied from 8 to 15 s in the median: provider and network variation. Only the search difference in the last column is caused by the code change.

**Retrieval quality with `minimal`** (`eval/dev_results_plan_minimal.csv`, 2 runs, against `eval/dev_results_d8_pin.csv`):

| Config | Hit-Rate@5 `low` → `minimal` | MRR@10 |
|---|---|---|
| R2 | 100 % → 100 % | 0.80 → 0.72 |
| R4 | 100 % → **90 %** | 0.81 → 0.81 |

- New miss in R4: **D01** (objection period of a Mahnbescheid) in both runs; the expected provisions moved to ranks 6–8.
- Cause, visible in the debug log: with `minimal` the plans name section numbers less often (D05 without § 195, D07 without § 288, D08 without § 286) and once the wrong law ("§ 222 BGB" instead of ZPO). Without a named section, pinning (D-8) does not apply.

**Batched embeddings:** the search sent one embedding request per German query, one after the other (up to three round trips; outliers of 14 s and 45 s). Now all queries of a plan go out in one request (`retrieval.embed_queries`, `PrefixedEmbeddings.embed_queries`). The vectors are the same; a test checks one request for three queries and the same hits as the query-by-query search, so the evaluation results stay valid without a new run.

### Decision

- **D-9: the retrieval plan stays at `low`.** `minimal` violates the rule of D-8 (no new misses) on the most important question; `PLAN_REASONING_EFFORT` stays configurable.
- **Batched embeddings are kept** (search median 4.5 s → 0.5 s, no change in results).
- For the README: answer time median ≈ 15 s, but it depends on the provider; occasional answers above 20 s remain a known limitation.

## Open points for the next days

- Sat 10-17: build the index for the BGB and ZPO scope (FR-04) with `qwen/qwen3-embedding-8b`; write the 10 development questions (`eval/dev_questions.json`).
- Sun 10-18: end-to-end spike – confirm D-1 on real chunks (optionally against `openai/text-embedding-3-small`), test E-8 (tools + structured output in one call), test the provider options for embeddings (D-3), measure latency and cost per question.
- Spec v0.2 (Mon 10-19): D-1 decision, NFR-01 guardrail note, `.env.example`/`config.py` (model, empty prefixes), rules for `prompts/retrieval_plan.md`, today's date in the system prompt (FR-10), BM25 directly with `rank-bm25` instead of `langchain-community` (deprecation warning), load `.env` before `config.py` reads environment variables, provider options for data retention (D-3), evaluation runs each question at least twice (§7.2).
- Done: provider options for embeddings (D-3) work – the index was built with them on Fri 10-16. Spike gate passed on Mon 10-19 (see above). E-8 decided on Mon 10-19 (variant A, see above). All spike items are closed; next: spec v0.2.
- D-8 decided on Tue 10-20 (both changes kept, pinning on by default, see above).
- D-9 decided on Wed 10-21 (retrieval plan stays `low`); query embeddings batched on Thu 10-22 (see above).
