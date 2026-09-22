# Book Translator

> ⚠️ **Work in progress** — personal project, not production quality. API may change without notice.

*[Česká verze](README.md)*

Multi-agent CLI translator for books EN→CZ. Pipeline: scout → translator → critic →
reviewer, orchestrated in code. State lives in SQLite, so a run can be interrupted
and resumed at any time.

Design and rationale: [`docs/superpowers/specs/2026-09-06-book-translator-design.md`](docs/superpowers/specs/2026-09-06-book-translator-design.md).
Before a first real run, go through [`docs/pilot-checklist.md`](docs/pilot-checklist.md).

## Install

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...        # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-..."
```

Python 3.11+.

## Run phases

```bash
python main.py init book.epub     # book -> chapters into DB (status pending)
python main.py scan               # scout goes through the book -> data/guide.draft.json
python tools/check_draft.py                   # sanity-check the draft (report-only)
python main.py reference --dir "<path to references>"   # mine terminology
python main.py review             # web UI: confirm/edit the guide -> data/guide.json
python main.py run                # translation loop over chapters
python main.py questions          # questions raised during the run
python main.py answer 7 "White Council"   # answer -> glossary/rule + recompute chapters
python main.py status             # chapter status overview
python main.py export             # finished chapters -> output/book_cz.txt
```

Useful variants:

- `init book.epub --reset` - discards existing book state and loads a new one
- `scan --chunked` - when the book doesn't fit into a single scout call
- `run --retry-flagged [IDX...]` - returns flagged chapters to the queue (resets review rounds)
- `export --only-done` - only clean chapters (skipped ones are still printed to stdout)
- `answer 7 "White Council | White Councils"` - first form is canonical, the rest are approved alternatives

## Terminology from previous volumes

If you have previous volumes of a series in both EN and CZ, `reference` mines
established translations from them. The folder needs `EN/` and `CZ/`
subfolders with files numbered by volume.

First run `tools/check_draft.py` - it reports what's broken in the scout's draft
(enumerations instead of a single term, duplicate entities, questions pointing nowhere).
It changes nothing; you fix it by hand in `data/guide.draft.json`.

In the form: only what's **evidenced** in a professional translation is pre-filled,
with proof next to it ("112x in 8 volumes"). Model guesses wait next to an empty
field behind a "use suggestion" button.

## Chapter states

| Marker | State | Meaning |
|---|---|---|
| `..` | pending | waiting for translation |
| `~~` | processing | currently being processed (stuck ones get reset to pending by the next `run`) |
| `OK` | done | translated, no open findings |
| `!!` | flagged | a serious finding survived `MAX_REVIZE` rounds - translation exists, but review it |
| `??` | needs_human | translator hit something it can't decide without you (`questions`) |
| `XX` | error | technical error; a normal `run` retries it |

`run` picks up `pending` and `error`. `flagged` and `needs_human` are skipped -
`answer` and `run --retry-flagged` respectively bring them back into play. No chapter blocks the batch.

## Where things live

- `data/` (gitignored) - `state.sqlite3`, `guide.json`, `guide.draft.json`, run lock
- `output/` (gitignored) - `book_cz.txt`
- `config.py` - model IDs, token prices, thresholds, `MAX_REVIZE`, `MAX_SPEND_USD`

The term glossary lives in SQLite (not JSON), so writing it and committing a chapter
are one transaction. The guide (`guide.json`) is a file - a human edits it via the review UI.

## Money

Every call is logged into the `llm_calls` table (tokens + cost). A cost guard
estimates the price before each call; if `MAX_SPEND_USD` is exceeded, `run`
asks for a new cap, `scan` stops hard.

```sql
SELECT agent, COUNT(*), SUM(cost_usd) FROM llm_calls GROUP BY agent;
```

## Tests

```bash
python -m pytest
```

Tests never touch the API - agents are tested via `FakeLLMClient`, the pipeline via
monkeypatched agents.

## Archive

`pokus-1/` is a previous attempt (a complete skeleton, never run against the API).
Don't touch it, it's kept only as reference.
