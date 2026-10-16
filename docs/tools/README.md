# Tool briefs

One page per deterministic tool, written **before** the tool is implemented
(D-4). A brief records the inputs, the rule with its provisions, the
assumptions the tool states, and the cases in which it returns no result.

TODO (D-4): write one brief per tool, verified against the statute text and
public consumer guides.

| Tool | Requirement | Brief |
|---|---|---|
| `calculate_objection_deadline` | FR-11 | TODO `calculate_objection_deadline.md` |
| `check_limitation` | FR-12 | TODO `check_limitation.md` |
| `calculate_default_interest` | FR-13 | TODO `calculate_default_interest.md` |
| `fetch_paragraph` | FR-14 | TODO `fetch_paragraph.md` |
| `check_collection_fees` | FR-15 | TODO `check_collection_fees.md` — the brief is the **precondition** for implementing the tool at all; without it, fee questions are answered from the knowledge base without a calculation. |

Every brief contains:

- **Inputs** — with their validation rules (FR-10 AC3).
- **Rule** — the calculation and the provisions it rests on (FR-10 AC2).
- **Assumptions** — what the tool states on every result (FR-10 AC7).
- **No result** — the inputs that yield `not_applicable_reason` (FR-10 AC4).
- **Reference cases** — the hand-calculated values the unit tests use.
