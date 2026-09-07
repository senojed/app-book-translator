## IMPORTANT

- Lines 189–191 vs. 232–235: 1–2-character surfaces now reach stage 1, but `books_with_en` apparently retains the stage-0 minimum length. Therefore `E` is always empty and such items can never become `proposed`. Explicitly search all lengths in `books_with_en`, including 1–2 characters, and add a regression test.
- Lines 288–301 contradict line 296. Precedence gives a non-null model proposal priority over `evidence_only`, while line 296 says an ineligible surface ends “at most `evidence_only`.” Replace it with: ineligible surfaces never become `confirmed`/`weak`; they become `proposed`/`not_attested`, or `evidence_only` when the model returns `null`.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item