## BLOCKING

- **Task 7, `test_merge_keeps_human_decisions`**
  Problem: test contradicts interface above it. Interface says new draft character gets `render: draft.suggested`; test allows `render` missing/empty for `NewGuy`. Earlier test also expects draft `suggested` → `render`.
  Fix: change test to expect `newguy["render"] == "translate"` or change interface/spec consistently. Current plan is internally inconsistent.

- **Task 11 + Task 15 `scan --chunked`**
  Problem: `scout.chunk_chapters()` is specified for objects with `.raw_text`, but Task 15 passes `chs = state.chapters_by_status(...)`, i.e. dict/sqlite rows consumed as `c["raw_text"]` elsewhere. `scan --chunked` will fail on real CLI.
  Fix: either make `chunk_chapters` accept both dict and object (`raw = ch["raw_text"] if isinstance(ch, dict) else ch.raw_text`) or change Task 15 to pass wrapper objects/texts.

- **Task 16 `POST /api/guide` validation order**
  Problem: plan says `validate` before `apply_must_decide`. A `must_decide` relationship answer `"foo"` passes “nonempty answer”, then `apply_must_decide` writes `{address:"foo"}` after validation. Invalid `guide.json` can be saved.
  Fix: validate must_decide answers by kind before apply, then run full schema validation again after apply; or apply first, then validate final payload.

## IMPORTANT

- **Task 11 test block**
  Problem: `tests/test_scout.py` code fence is not closed before Step 2. This is easy for a worker to copy incorrectly and makes the plan markdown structurally broken.
  Fix: add closing ``` after `test_chunk_chapters_greedy_packs_under_limit`.

- **Task 14 critic failure status**
  Problem: interface says critic nonfatal failure sets `status="flagged"` with pseudo-finding `action:"note"`, but generic status rule says `flagged` only when `has_revise_triggers(findings)` remains true. With `action:"note"`, naive implementation will mark `done`.
  Fix: add explicit `critic_failed = True` flag in algorithm and status rule: `flagged if critic_failed or has_revise_triggers(findings)`; add test.

- **Task 15 `scan` broken scout output**
  Problem: spec says broken scout output is fatal. Plan only maps `OutputTruncated` to `FatalRunError`; `ValueError` from `scan_book` will bubble as uncaught exception with stacktrace. Lifecycle ends as fatal, but UX/error handling is inconsistent.
  Fix: in `scan`, catch `(OutputTruncated, ValueError)` and raise `FatalRunError` with actionable message.

- **Task 16 must_decide routing coverage**
  Problem: tests only cover `term`. No tests for `name`, `relationship`, `style/other`, nor replacement/update of existing rows. These are exactly the branches that can corrupt guide shape.
  Fix: add focused tests for each kind, including invalid relationship answer and update existing term/name instead of duplicate append.

## VERDICT

CHANGES_NEEDED