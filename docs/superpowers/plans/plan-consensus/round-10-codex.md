## BLOCKING

- Plan Task 14, lines ~1850-1855: `concordance.check_chapter(...)` consumes raw `rendered_terms` before they are verified against final CZ text. Verification happens only later in step 6(a), before commit. This violates spec: hallucinated `cz_as_used` must be dropped before concordance uses it. Otherwise a fake `rendered_terms` entry can trigger bogus inconsistency, revisions, or `flagged`.
  - Fix: normalize/filter `rendered_terms` with `concordance.contains_form(cz, cz_as_used)` before every `check_chapter` call, initial and after each revision. Add a pipeline test: translator reports `cz_as_used="Popelář"` not present in CZ, concordance must not trigger revise/question.

## IMPORTANT

- Task 14, lines ~1863 and ~1899: slug collision handling is unsafe. On `INSERT` collision, plan remaps by `term_id=? OR lower(canonical_en)=lower(?)`. If two different surfaces produce same slug, e.g. punctuation/spacing variants, the plan can silently attach mentions/questions to the wrong glossary row.
  - Fix: remap only when canonical/alias surface actually matches. If `term_id` collision with different canonical, generate deterministic suffixed ID (`cand_slug_2`, etc.) and retry insert.

- Task 15, `init` behavior: `state.seed_chapters` is idempotent insert-only by `idx`. Re-running `init` on a different or shorter book leaves stale chapters and old raw text in DB. That is dangerous for a CLI whose first command is `init <book>`.
  - Fix: either make `init` refuse non-empty DB unless `--force`, or define `init --reset` that clears dependent tables and chapters. Add test for re-init with fewer chapters.

- Task 15, `answer_text` parsing for term/name has no empty-answer validation before `parts[0]`. Empty or whitespace answer becomes an unhelpful `IndexError`/500-style CLI failure.
  - Fix: validate non-empty after splitting and return a controlled error. Add test.

## VERDICT

CHANGES_NEEDED