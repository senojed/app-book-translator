## BLOCKING

- Task 5, lines 831/852/877: `PipelineLLMClient` imports `state`, but the module is `src.state`. Under `python -m pytest` from repo root this will fail. Fix: use `from src import state` inside methods, or make package layout explicit. Do not rely on `src/state.py` being top-level importable.

- Task 12, line 1446: broken translator metadata is silently converted to empty lists. Spec says broken translator output is recoverable chapter error, not “continue without metadata”. This would silently drop questions/new terms/rendered terms. Fix: invalid `METADATA` must raise `ValueError`; only allow absent optional lists inside valid JSON.

- Task 14, lines 1600/1696: transaction B is underspecified and internally inconsistent. It says one transaction, but uses `glossary.*`, `state.upsert_open_question`, `replace_term_mentions`, `update_chapter`, all of which open their own connections. The later `commit_chapter_result(...)` idea is not in the interface block and does not define how surface matching/candidate insert/questions happen atomically. Fix: define `commit_chapter_result` fully in Interfaces, including candidate surface resolution, mention insert, question upsert, and rollback test that actually forces a mid-transaction failure.

## IMPORTANT

- Task 6, lines 901-902 vs global constraint line 21: seeded `term_id` is specified as `term_` + slug, but global constraint says seeded IDs are just `slug(canonical_en)`. Fix one convention and add a test for newly seeded IDs.

- Task 7/16, lines 992-997 and 1895-1897: final guide shape omits `terms`, while scout and glossary require terms. Review UI POST test also omits `terms`, so scout terms can disappear before `seed_from_guide`. Fix: include `terms` in `load_guide`, merge, validation, POST payload, UI, and seed tests.

- Task 11, line 1370: `merge_scout_facts` says dedup `characters/places/terms` by `name_en`, but scout terms use `term_en`. Tests do not cover terms. Fix: section-specific keys: `characters.name_en`, `places.name_en`, `terms.term_en`; add merge test for terms.

- Task 8, lines 1070/1143 and test lines 1133-1135: drift stemming is too vague and the test can pass while falsely treating “Bílá rada” vs “Bílá radě” as drift. Fix: define normalization for multi-word CZ forms explicitly and assert chapter 2 is not included in drift.

- Task 13, lines 1532-1533: parse-error retry behavior is specified but untested. Fix: add test with invalid JSON then valid JSON, and invalid JSON twice -> `ValueError`.

- Task 15, line 1727: exception handling is ambiguous because `FatalRunError` is an `Exception`. A naive implementation of “except Exception non-fatal” will mark fatal auth/model/cost errors as chapter `error`. Fix: provide explicit catch order: `except FatalRunError: raise`, then recoverable exceptions.

- Task 15, lines 1727 and 1724: scan/run lifecycle says `create_run`/`finish_run`, but fatal paths are not specified. Fix: require `finish_run(..., "fatal")` or equivalent in `finally` for failed commands, otherwise runs can remain open with no ended_at/status.

## NITS

- Task 2 says expected PASS “8 tests”, but the block contains 7 tests.

- Global line 23 mentions `CALIBRATION_CHAPTERS`, but Task 1 config does not define it. Either add it or remove from constraints.

- Ověření aktuálnosti: `claude-sonnet-5` and `$2/$10 MTok` currently match Anthropic docs/pricing, so this part is not a current blocker. Sources: https://platform.claude.com/docs/en/about-claude/pricing and https://platform.claude.com/docs/zh-TW/models/sonnet-5/overview

## VERDICT

CHANGES_NEEDED