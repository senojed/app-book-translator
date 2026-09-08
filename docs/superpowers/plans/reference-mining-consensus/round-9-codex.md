## IMPORTANT

- **Task 12, Step 3 — `undoAcceptAllScoutSuggestions`:** Bulk undo restores values but leaves `_czActiveKey` / `_renderActive` and their `Before` values intact. Concrete failure: bulk-accept a character’s scout `render`; click its still-visible per-field “použít návrh” (same value); bulk-undo; the per-field button remains “zpět” and restores the supposedly undone bulk value. Clear per-field active undo state for every field reverted by bulk undo, or disable applying a suggestion already equal to the current value. Add a regression test for this sequence.

- **Task 12, Steps 1/4:** `tests/test_review_ui_fields.py` does not execute any Task 12 JavaScript. All three tests exercise backend merge/validation and would pass if the entire replacement `<script>` were omitted. The spec-required locking, suggestion undo, bulk accept/undo, stale-state reconciliation, relationship selector, and blur/click behavior therefore have no automated regression coverage. Extract state transitions into testable pure JavaScript or add browser tests; at minimum automate the bulk/per-field composition cases that repeatedly regressed in prior rounds.

## VERDICT

CHANGES_NEEDED