## BLOCKING

- [Plan Task 15, lines 1931-1932](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/plans/2026-09-06-book-translator.md:1931): `run` uses `cf jako u scan`, tedy `interactive=False`. Spec says only `scan` hard-stops; `run` must pause/ask on cost guard. Fix: define separate factories: `scan interactive=False`, `run interactive=True`.

- [Plan Task 15, lines 1910 and 1994-2000](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/plans/2026-09-06-book-translator.md:1910): `apply_answer` always calls `glossary.promote(scope_key, ...)` for `term/name`, but tests create blocking `name` questions with nonexistent `cand_a/cand_b`. Answer can be lost or fail. Fix: require every `term/name` question `scope_key` to reference an existing glossary row, or make `apply_answer` create/promote an approved glossary row with known `canonical_en`. Current question shape lacks that surface, so add it.

- [Plan Task 16, lines 2135 and 2191-2194](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/plans/2026-09-06-book-translator.md:2135): `must_decide` validation only checks “has answer”, then saves payload. There is no routing of that answer into `characters/terms/relationships/rules`, and `seed_from_guide` will ignore raw `must_decide`. Human review decisions can be accepted but not affect prompts/glossary. Fix: POST must normalize `must_decide` answers into final guide fields before save, with tests per kind.

## IMPORTANT

- [Plan Task 14, lines 1721-1730](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/plans/2026-09-06-book-translator.md:1721): concordance runs before `new_terms` are added to `glossary_rows`. That means first-pass findings cannot check leaks/inconsistency for newly discovered terms in the same chapter. Fix: build provisional candidate rows before first `check_chapter`, or explicitly state new candidates are exempt until next run.

- [Plan Task 16, lines 2138 and 2200](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/plans/2026-09-06-book-translator.md:2138): CLI `review` reseed and lock are only manual smoke-tested. This is a core state mutation after human gate. Add automated test that monkeypatches `run_review_server` to return 0/1 and asserts reseed happens only on 0 and lock is used.

- [Plan Task 14, line 1750](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/plans/2026-09-06-book-translator.md:1750): `INSERT OR IGNORE` inside `commit_chapter_result` can silently drop a candidate while still inserting mentions/questions for it. That hides data inconsistency. Fix: use plain `INSERT`, or verify row exists and matches expected fields before continuing.

## NITS

- [Plan Task 14, lines 1731-1733](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/plans/2026-09-06-book-translator.md:1731): explicit mention says `cz_form: nt["cz"]` while iterating `new_candidate`; use `candidate["cz"]` or define the paired structure.

- Model ID note: I checked Anthropic model deprecations; `claude-sonnet-5` is listed active as of the crawled docs, so no issue there. Source: https://docs.anthropic.com/en/docs/about-claude/model-deprecations

## VERDICT

CHANGES_NEEDED