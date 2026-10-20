# Tool brief: `calculate_default_interest` (FR-13)

Calculates the maximum statutory default interest a **consumer** can be charged. It does not decide when default began.

## Inputs

| Field | Rule |
|---|---|
| `principal` | EUR, greater than 0, at most 100,000 |
| `start_date` | first day of default – an input, not a finding of the tool |
| `end_date` | optional, defaults to today; not before `start_date` |

## Rule

| Step | Provision (checked against the statute XML, D-4) |
|---|---|
| Rate = base rate + 5 percentage points | BGB § 288 (1) |
| Base rate changes on 1 January and 1 July | BGB § 247 (1) |

- The period is cut at every base-rate change; each part uses the base rate in force then (`data/base_rates.csv`, Deutsche Bundesbank, D-5).
- Interest per part = principal × rate / 100 × days / 365; every day from start to end counts, both included; each part is rounded to cents (half up); the total is the sum of the parts.
- Simple interest on the principal only.

## Assumptions stated on every result

- The start of default is taken as given (BGB § 286 is not applied).
- Consumer rate only; the 9-point rate for businesses (§ 288 (2)) is not applied.
- The day-count convention above.
- The source of the base rates.

## No result

- A date outside the table (currently 2002-01-01 to 2026-12-31).
- End date before start date; principal ≤ 0 or > 100,000.

## Reference cases (tests), calculated by hand

| Principal | From | To | Parts (days × rate) | Total |
|---|---|---|---|---|
| 1,000 € | 2026-01-01 | 2026-06-30 | 181 × 6.27 % = 31.09 | **31.09 €** |
| 1,000 € | 2026-03-01 | 2026-08-31 | 122 × 6.27 % = 20.96; 62 × 6.52 % = 11.08 | **32.04 €** |
| 2,500 € | 2024-11-15 | 2025-02-14 | 47 × 8.37 % = 26.94; 45 × 7.27 % = 22.41 | **49.35 €** |
| 500 € | 2020-01-01 | 2020-12-31 | 182 × 4.12 % = 10.27; 184 × 4.12 % = 10.38 | **20.65 €** |

FR-13 AC5: the values are to be cross-checked once with a public default-interest calculator; a calculator using 366 days in leap years gives a slightly lower value for the 2020 case.