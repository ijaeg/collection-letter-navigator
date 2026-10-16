# Collection Letter Navigator

A Streamlit chatbot that explains German debt collection letters and court
payment orders in English. See [`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) for the
full specification; this README follows the sections required by NFR-08 (§10.2).

**Status: scaffold.** Every module is a stub; see `CLAUDE.md` for how the
project is built.

> This app provides general legal information, not legal advice.

## Purpose

TODO: what the app does, for whom, and the problem it solves (§1, §3).

## Screenshots

TODO: triage screen, an answer with legal basis and tool card, the RAG panel.

## Setup

TODO: `uv sync`, `OPENROUTER_API_KEY` in `.env`, `uv run streamlit run app.py`
(NFR-01).

## Usage (including demo cases)

TODO: the triage, the chat, the "Common situations" buttons and the four demo
cases a reviewer can run without own data (FR-03).

## Research and product idea

TODO: the persona, why this domain, and why cross-lingual retrieval is the core
of the product rather than an added feature (§1.1, §3).

## Architecture

TODO: pipeline diagram (§5.2), module map (§9) and dependency direction.

## Design decisions

TODO: the five most important choices and why — among them the embedding model
(D-1), the chat model (D-2), section-based chunking (FR-04 AC2), hybrid search
(FR-07) and one-call vs. two-step tool calling (FR-10 AC8, D-7).

## Retrieval evaluation results

TODO: the R1–R4 results table, the chosen configuration, why it won and at
least one observed weakness (§7.2, §7.5 AC2).

## Tool-calling evaluation

TODO: tool selection and argument accuracy, if the evaluation was run (§7.3).

## Safety and security tests

TODO: summary of `docs/safety_tests.md` (FR-21 AC8).

## Legal information disclaimer and data sources

TODO: the disclaimer, the statute source and snapshot date, the base-rate source
and retrieval date, and the get-help links (FR-21 AC5, AC6, §12 D-5).

## Known limitations

TODO: one labeler without legal training, small dataset, one snapshot of the
law, one model family, and the limits of the R1↔R2 comparison (§7.5 AC3, §12).

## Ideas for improvement

TODO: everything dropped by the cut rule plus the Future Work of §2.2 (§11).

## Traceability

TODO: the table mapping task requirements and review criteria to requirement
IDs (§10.1).

## Tooling and AI assistance

TODO: VS Code, Claude Code, how AI assistance was used and the author's own
share.
