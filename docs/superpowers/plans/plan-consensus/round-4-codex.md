## BLOCKING

- Plan 1751: `critic.review` errors are to be caught and converted to `flagged`, but `FatalRunError` can also come from critic client calls. If swallowed, auth/model/cost fatal errors become chapter-level `flagged` and `run` continues incorrectly. Fix: in pipeline, catch `FatalRunError` before critic recoverable handling and re-raise. Add test: monkeypatch `critic.review` to raise `FatalRunError`; assert `process_chapter` propagates and chapter is not `flagged`.

## IMPORTANT

- Plan 853-855, 857-880: `_price()` returns `0.0` for unknown model. That disables cost guard silently for typo/new model. Fix: unknown model in either price dict must raise `FatalRunError`; add test.

- Plan 878-880: cost guard parses user ceiling with `float(ans)` directly. Invalid input raises `ValueError`, which later can be treated as chapter recoverable error, not fatal/cost stop. Fix: validate input and either reprompt or raise `FatalRunError`. Add test for `confirm=lambda _: "abc"`.

- Plan 1972, 2094-2104: export coverage is too thin. Spec requires flagged chapters with `[!! REVIDOVAT: ...]`, missing `needs_human`/`error` warnings, `export --only-done`, and read-only behavior. Current test only checks one missing pending chapter. Add tests for flagged marker, `--only-done`, stdout warning/list, and DB unchanged.

- Plan 2249-2270: review reseed negative-path test is ineffective. It runs `review` with rc=1 after a successful reseed but asserts nothing, so it cannot prove “no reseed on failure”. Fix: use a fresh DB or add a new term in failed run and assert it was not seeded; assert return code is `1`.

## NITS

- Plan 1963: `except (OutputTruncated, ValueError, Exception)` is equivalent to `except Exception`. Keep explicit branches if different notes/status are desired, otherwise use `except Exception`.

- Plan 2142-2143 / 2249-2270: after adding the CLI review test in Task 16, the plan should explicitly rerun `tests/test_cli.py`, not only commit.

## VERDICT

CHANGES_NEEDED