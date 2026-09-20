## IMPORTANT

- Task 3, Step 3, `PipelineLLMClient.complete()` around `_guard()`: `except FatalRunError` wraps all guard failures for a Codex inner client, not only the intended missing-price failure. This misclassifies cancelled/failed cost guard (and future `LockLostError`) as `CodexTranslatorFatalError`, causing Task 5 to flag the chapter as a Codex backend failure. Fix: introduce/catch a dedicated missing-price exception from `_price()` only; add a test that a Codex run hitting a normal cost-guard stop remains plain `FatalRunError`.

- Task 5, Step 3, `except CodexTranslatorFatalError`: it redacts `detail` for `chapters.notes`, then bare-raises the original exception. The outer handler prints unredacted `str(e)` to console/log capture. This violates the stated Codex-error redaction rule for errors created outside `CodexLLMClient` (notably lazy preflight). Fix: re-raise a new `CodexTranslatorFatalError(detail)` after updating the chapter, preserving the original as `__cause__`; test captured console output with `STYLIST_REPORT_REJECTED_TEXT=False`.

## VERDICT

CHANGES_NEEDED