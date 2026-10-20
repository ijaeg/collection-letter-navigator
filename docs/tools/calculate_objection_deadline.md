# Tool brief: `calculate_objection_deadline` (FR-11)

Computes the last day to object to a court payment order (*Widerspruch* against a *Mahnbescheid*) or to file an *Einspruch* against an enforcement order (*Vollstreckungsbescheid*). It never says whether to object.

## Inputs

| Field | Rule |
|---|---|
| `document_type` | `mahnbescheid`, `vollstreckungsbescheid` or `unclear` |
| `service_date` | a valid date, not in the future |
| `federal_state` | optional; one of the 16 state codes (`BB` … `TH`) |

Anything else (unknown fields, impossible dates, unknown state codes) is returned as `not_applicable_reason` (FR-10 AC3).

## Rule

| Step | Provision (checked against the statute XML, D-4) |
|---|---|
| Two weeks from service | ZPO § 692 (1) no. 3 (payment order); ZPO §§ 700 (1), 339 (1) (enforcement order) |
| The day of service does not count | ZPO § 222 (1), BGB § 187 (1) |
| A period in weeks ends on the weekday with the same name | BGB § 188 (2) |
| Saturday, Sunday or public holiday → next working day | ZPO § 222 (2) |

Public holidays come from the `holidays` package: nationwide only, or nationwide plus the given state.

## Assumptions stated on every result

- The given date is used as the date of service (the day the document was delivered).
- The day of service is not counted.
- Only nationwide holidays count, unless a state is given; legally, the holidays at the court's location matter.
- For `unclear`: the stricter rule of the enforcement order is used.

## Extra notes

- *Mahnbescheid*: after the two weeks, an objection is still possible as long as no enforcement order has been issued (ZPO § 694 (1)).
- *Vollstreckungsbescheid*: the period is strict (*Notfrist*); if service was abroad, it is one month (ZPO § 339 (2)) – asked as missing information.

## No result

- Service date in the future.
- Invalid input (see above).

## Reference cases (tests)

| Service | Weekday | Calculated end | Result | Why |
|---|---|---|---|---|
| 2026-10-12 | Mon | 2026-10-26 | 2026-10-26 | plain case |
| 2026-10-15 | Thu | 2026-10-29 | 2026-10-29 | day of service not counted |
| 2026-11-07 | Sat | 2026-11-21 (Sat) | 2026-11-23 | weekend |
| 2026-11-08 | Sun | 2026-11-22 (Sun) | 2026-11-23 | weekend |
| 2026-12-11 | Fri | 2026-12-25 (holiday) | 2026-12-28 | 25./26.12., weekend |
| 2027-03-12 | Fri | 2027-03-26 (Good Friday) | 2027-03-30 | Easter |
| 2026-12-23 | Wed | 2027-01-06 | 2027-01-06 | turn of the year; nationwide |
| 2026-12-23, `BY` | Wed | 2027-01-06 (holiday in BY) | 2027-01-07 | state holiday |