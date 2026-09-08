## BLOCKING

- **Task 3, Step 3 (`load_corpus`, lines 863–874):** `manifest` is captured only after EPUB parsing. If a file changes after being parsed but before `build_manifest`, the returned corpus contains old text with the new manifest. Task 13 then persists that manifest and `review` can incorrectly mark findings as fresh. Capture the manifest before loading, compare it with a second manifest afterward, and fail/retry if they differ. Add a regression test simulating a change during loading.

- **Task 2, Steps 7 and 10:** Both commits attempt `git add data/...`, but the actual repository ignores the entire `data/` directory. These commands fail without `-f`, so the prescribed execution cannot complete. Decide explicitly whether these runtime files should remain local—in which case remove the commits—or intentionally version them and adjust `.gitignore`/use `git add -f`.

## IMPORTANT

- **Task 12, Step 3 (`invalidateAcceptAllChange`, `valueField`, `renderField`):** Every `onChange` invalidates the bulk-accept undo record, including programmatic “use suggestion” and its own “back” action. Sequence: bulk-accept scout value → use an individual suggestion → undo that suggestion. The field returns to the bulk-applied value, but bulk undo can no longer restore the original empty value. This violates the spec’s reversible-action invariant. Invalidate bulk history only on direct manual edits, or implement composable per-field history; add this sequence to the browser checklist or automated JS tests.

## VERDICT

CHANGES_NEEDED