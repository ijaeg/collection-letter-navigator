# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this project is

**Collection Letter Navigator** — a Streamlit chatbot for people in Germany who
do not read German well and have received a letter from a debt collection agency
(*Inkasso*) or a court payment order (*Mahnbescheid*). The user asks in English;
the app triages the letter, answers with advanced RAG over German federal law
(BGB, ZPO, RDG), calls deterministic tools for deadlines, limitation and default
interest, and shows the verbatim German provision as evidence.

It gives **legal information, not legal advice**. It never tells the user
whether to pay.

Turing College, AI Engineering Sprint 2. Python 3.13, uv, LangChain against
OpenRouter, Chroma, BM25, Pydantic.

## The spec is the source of truth

[`PRODUCT_SPEC.md`](PRODUCT_SPEC.md) (v0.1.2) defines everything: functional
requirements `FR-01`–`FR-24` with acceptance criteria, non-functional
requirements `NFR-01`–`NFR-10`, the structured formats in §6, the evaluation in
§7 and the code structure in §9.

- Read the relevant FR and its ACs **before** writing code for it.
- Every commit message, docstring, test name and TODO names the requirement IDs
  it belongs to. A docstring without a `Related:` line is incomplete.
- Priorities are `Must` > `Should` > `Could`. Do not implement a `Could` while a
  `Must` is open.
- If the code and the spec disagree, the spec wins — or the spec is changed
  first, in its own commit.

## Commands

**uv only.** Never run bare `pip`, `python` or `pytest`; there is no activated
virtualenv.

```bash
uv sync                                  # install, including dev dependencies
uv run streamlit run app.py              # run the app (needs OPENROUTER_API_KEY)
uv run python scripts/build_index.py     # build the knowledge base (FR-04)
uv run python eval/run_retrieval_eval.py # retrieval evaluation (§7.2)
uv run python eval/run_tool_eval.py      # tool-calling evaluation (§7.3)

uv run pytest                            # tests with coverage (NFR-06)
uv run ruff check .                      # lint (NFR-07)
uv run ruff format .                     # format (NFR-07)
uv run mypy src                          # type check (NFR-07)

uv add <package>                         # add a runtime dependency
uv add --dev <package>                   # add a dev dependency
```

All four checks must pass before a pull request.

## Architecture and dependency direction

```text
app.py · pages/              UI and the TRIAGE → CHAT state machine only
  ↓
answer.py · letter_check.py  orchestration: tool-calling loop, quote check, redaction
  ↓
retrieval.py · tools/        retrieval plan, hybrid search, deterministic tools
  ↓
llm.py · ingest.py · guards.py · pricing.py
  ↓
schemas.py · config.py       contracts and constants; depend on nothing in the package
```

Dependencies point **downwards only**. `schemas.py` and `config.py` import
nothing from the package; `app.py` is imported by nothing.

- `config.py` — every model name, limit, timeout and feature switch, defined
  once (FR-20 AC2).
- `schemas.py` — the Pydantic models of §6. They are the contract; change them
  deliberately.
- `prompts/*.md` — all prompt text.
- `tests/` — one file per module, test names carry the requirement ID.

## Invariants

These hold for every change. Breaking one is a bug, not a trade-off.

1. **OpenRouter only.** One API key, for chat *and* embeddings (NFR-01). No
   second provider account, no local model at runtime. Base URL and model names
   come from `config.py`.
2. **No prompt text in `.py` files.** Prompts live in `prompts/*.md` and are
   loaded by file name (NFR-05). `app.py` additionally contains no retrieval
   logic.
3. **Privacy.** Questions and letter text stay in `st.session_state`; they are
   never written to disk and never logged, except through the opt-in
   `DEBUG_LOG=1` log, which is gitignored and used only with fictional data
   (FR-23 AC2). Personal data in pasted letters is redacted *before* the first
   LLM call, with a preview the user confirms (FR-16 AC2, AC3). The API key
   never appears in the repository, the UI or an error message (FR-23 AC3).
4. **Tests mock every LLM call.** No test reaches OpenRouter; the chat model
   comes from the `mock_chat_model` fixture (NFR-06).
5. **English only** in the UI, the docs and the code. The only German is quoted
   legal text and German terms that are explained in English (NFR-09).
6. **Grounded answers.** The displayed German source text is read from the
   knowledge base by chunk ID, never written by the model (FR-08 AC2); cited IDs
   are validated and German quotes are checked against the sources (FR-09).
7. **No result beats a wrong result.** A tool outside its supported period or
   scope returns `not_applicable_reason`, never a guess (FR-10 AC4).
8. **No stack trace in the UI.** Errors, timeouts and tool failures become
   friendly messages and leave the chat usable (NFR-02, NFR-04).
9. **Information, not advice.** No recommendation on whether to pay, object or
   ignore; refusals always carry the get-help links (FR-21).

## Conventions

- **Commits:** lowercase imperative, with the requirement IDs in the subject.
  `add objection deadline tool (FR-11)`, `fix quote check whitespace handling
  (FR-09 AC2)`. Keep one commit to one concern.
- **Branches:** feature branches off `main`, named
  `feature/<short-description>`. Never commit to `main` directly.
- **Pull requests:** every change goes through a PR and is merged with a merge
  commit. The PR body names the requirement IDs and the ACs it satisfies.
- **Docstrings:** Google style with `Args`, `Returns` and `Raises`, ending with
  a `Related:` line naming the requirement IDs. Every module starts with
  `from __future__ import annotations` and a module docstring that ends in the
  same way. Module-level constants get a `#:` comment.
- **Types:** full annotations; `uv run mypy src` must be clean.
- **Line length:** 100 (ruff).
- **Scaffold stubs:** an unimplemented function raises
  `NotImplementedError("FR-xx: <short description>")`. Do not silently return a
  placeholder value.
- **Spikes:** throwaway scripts live in `spikes/` and are kept as a record; they
  are not imported by the package and are not held to these conventions.
