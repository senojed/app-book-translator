## IMPORTANT

- **Task 12, Step 6 — `test_bulk_undo_clears_active_suggestion_flag`:** The test never sets `_renderActive = true`, so its final assertion passes even if both cleanup lines are removed from `undoAcceptAllScoutSuggestions`. It does not reproduce the claimed round-9 sequence: after bulk accept, simulate clicking the individual suggestion by setting `_renderBefore` and `_renderActive`, then bulk-undo and assert the flag is cleared. Add equivalent coverage for `_czActiveKey`.

- **Task 12, Step 3 — reference revert handlers:** `valueField.revert.onclick` and `renderField.revert.onclick` restore the reference value but do not clear `_czActiveKey` / `_renderActive`. Sequence: unlock a referenced field → apply a suggestion → revert to the reference → unlock again. The suggestion button incorrectly remains in “zpět” state and can restore the pre-suggestion value, undoing the explicit reference revert. Clear the corresponding active flag when reverting and add regression coverage.

## NITS

- **Task 12, Step 6 — `_JS_SOURCE`:** It is not byte-for-byte identical to the production block; production comments are omitted. The executable statements currently match, but nothing detects future drift. Either describe it as an executable-code copy or extract/evaluate the functions from `index.html` in the test.

- **Task 12, Step 5 — stale-reference visual check:** Changing thresholds and rerunning `reference` creates a fresh matching fingerprint. To test staleness, generate `reference.json`, then change a threshold and open `review` without rerunning `reference`.

## VERDICT

CHANGES_NEEDED