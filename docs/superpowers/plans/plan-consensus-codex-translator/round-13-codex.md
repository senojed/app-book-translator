## IMPORTANT

- Task 2 revision loop / Task 5 fatal handler: `CodexTranslatorFatalError` during `revise_chapter()` propagates before transaction B, so the already complete scene translation in `cz` is discarded. `_cmd_run` only marks the chapter `flagged`; it does not persist `translated_text`. Preserve and commit the last valid `cz` as `flagged` before re-raising the fatal error, and add an integration test for fatal Codex failure during revision.

## VERDICT

CHANGES_NEEDED