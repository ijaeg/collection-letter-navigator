# Evaluation datasets

The datasets are written **before** prompts and retrieval settings are tuned
(§7.1). `dev_questions.json` is used for tuning; `retrieval_questions.json` is
the test set and is used only for the final runs.

| File | Content |
|---|---|
| `dev_questions.json` | 10 development questions, used in the spike and for tuning. Not part of the test set. |
| `retrieval_questions.json` | 20–25 English lay questions, written after the spike and never used for tuning. |
| `tool_cases.json` | ≈ 15 questions with the expected tool and arguments (or "no tool"). |
| `letters/` | 6–8 fictional letters with annotated `LetterFacts` (§6.5). |
| `retrieval_results.csv` | Output of `run_retrieval_eval.py`: 4 configurations × all questions. |

## Schema of the question files (§7.1)

Each file is a JSON array of objects:

| Field | Type | Meaning |
|---|---|---|
| `question_en` | string | The question in English, written as a lay person would ask it. |
| `expected` | array of strings | The provisions the retrieval should find, e.g. `["ZPO § 692", "ZPO § 694"]`. |
| `category` | string | One of the categories below, derived from the "common situations" (FR-03 AC4). |
| `sender` | string | Triage sender for this question: `creditor`, `collection_agency`, `court` or `not_sure` (§6.4). |

```json
[
  {
    "question_en": "I got a letter from a court. How long do I have to object?",
    "expected": ["ZPO § 692", "ZPO § 222"],
    "category": "deadline",
    "sender": "court"
  }
]
```

### Categories

`deadline` · `disputed` · `amount_too_high` · `already_paid` · `pay_later` ·
`instalments` · `fees` · `interest` · `limitation` · `legitimacy` ·
`ignore_consequences` · `out_of_scope`

At least 2 questions for each of the first six, 1 for each of the others.

## Ground truth

The expected provisions are set by the author (no legal training) and
cross-checked against the statute text and public consumer guides. Those guides
are reference only and are never copied into the knowledge base. The limits of
this are stated in the README (§7.5 AC3, R-7).

TODO (§7.1): fill `dev_questions.json` (Sat 10-17), then
`retrieval_questions.json` and `tool_cases.json` (Mon 10-19 onwards).
