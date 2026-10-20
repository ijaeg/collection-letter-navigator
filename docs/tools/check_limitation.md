# Tool brief: `check_limitation` (FR-12)

Estimates when the regular limitation period of a claim ends. It never says that a claim *is* time-barred: limitation is a defence the debtor must raise (BGB § 214 (1)).

## Inputs

| Field | Rule |
|---|---|
| `claim_date` | date the claim arose (e.g. due date of the invoice); not before 2002-01-01, not in the future |
| `knowledge_date` | optional; date the creditor learned of the claim and the debtor; defaults to `claim_date` |
| `last_acknowledgment_date` | optional; last part payment, interest payment or other acknowledgment; not before `claim_date`, not in the future |

## Rule

| Step | Provision (checked against the statute XML, D-4) |
|---|---|
| Regular period: three years | BGB § 195 |
| Starts at the end of the year in which the claim arose and the creditor knew of it | BGB § 199 (1) |
| A part payment or other acknowledgment restarts the period | BGB § 212 (1) no. 1 |

- End of the regular period: 31 December of (start year + 3).
- With an acknowledgment inside the period: the period ends three years after the acknowledgment (29 February → 28 February, BGB § 188 (3)). A restart never shortens the period: the later of the two ends counts.
- An acknowledgment after the period has ended does not restart it; the tool says so and does not assess other effects.

## Assumptions stated on every result

- Limitation is a defence (BGB § 214 (1)).
- Only the regular period is estimated (BGB §§ 195, 199 (1)).
- Without `knowledge_date`: the creditor knew of the claim in the year it arose.

## Missing information asked on every result (FR-12 AC5)

- Payments, payment plans or acknowledgments since the claim arose (restart, BGB § 212 (1) no. 1).
- A served court payment order (suspension, BGB § 204 (1) no. 3).
- A court title such as an enforcement order or a judgment (30 years, BGB § 197 (1) nos. 3, 4 – not covered).

## No result

- Claim before 2002-01-01 (old law).
- A date in the future; an acknowledgment before the claim date.

## Reference cases (tests, "today" = 2026-10-19)

| Claim | Knowledge | Acknowledgment | Period end | Ended? |
|---|---|---|---|---|
| 2023-06-15 | – | – | 2026-12-31 | no |
| 2023-12-31 | – | – | 2026-12-31 | no |
| 2024-01-01 | – | – | 2027-12-31 | no |
| 2024-11-10 | 2025-03-01 | – | 2028-12-31 | no |
| 2021-04-01 | – | – | 2024-12-31 | yes |
| 2022-05-10 | – | 2024-09-15 | 2027-09-15 (restart) | no |
| 2021-04-01 | – | 2025-03-01 (after the end) | 2024-12-31 | yes |
| 2001-12-31 | – | – | no result | – |