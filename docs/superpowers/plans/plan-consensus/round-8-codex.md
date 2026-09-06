## BLOCKING

- Task 15, lines 2106 and 2122: `init` is mutating, so it takes `state.run_lock(config.LOCK_PATH)`, but fresh checkout has no `data/` dir. `acquire_lock("data/.lock")` can fail before `init` does anything. Also `init PATH` omits `state.init_db(config.DB_PATH)` before `state.seed_chapters`. Fix: ensure parent dirs before lock, and call `state.init_db` at start of `init` or centrally before DB commands.

- Task 8, lines 1230 and 1275-1276: test expects `"Fů"` vs `"Fůha"` to be `inconsistency`, but defined `stem()` maps both to `"fů"` (`len > 3` → remove 2 chars). Correct implementation per interface will not raise finding. Fix test data to a truly different stem, e.g. canonical `"Fů"` vs used `"Barbar"`.

## IMPORTANT

- Task 14, lines 1854-1855 vs spec lines 155-156: plan says `new_terms` matching existing glossary surface → “přeskoč”; spec says match → “jen mention, ne nový řádek”. Current plan can lose mentions for terms the translator reported as `new_terms` but that resolve to an existing alias/surface. Fix: on match, add explicit mention with resolved `term_id` and `nt["cz"]`.

- Task 12 line 1678 + Task 14 lines 1868-1873 vs spec line 543: `style`/`other` questions with blank `scope_key` are supposed to be remapped to `hash(text)` before DB write, but Task 14 never specifies that normalization. This violates “nikdy NULL/''” and causes bad dedup. Fix: normalize all questions before `commit_chapter_result`.

- Task 15 lines 2078-2096: plan requires all DB mutations in one transaction, but then tells executor to call `glossary.promote`, `glossary.add_accepted_alt`, `state.answer_question`, `state.set_status`, each previously defined as `db_path` helpers with their own `connect`/commit. Atomicity claim is false. Fix: add conn-level helpers or implement `apply_answer` DB phase as one explicit transaction.

- Task 9 line 1355: stale lock takeover via `os.replace(tmp, lock_path)` is not mutually exclusive. Two processes can both observe stale lock, both replace, and both believe they own it. Fix: stale path should delete/unlink then retry the `O_CREAT|O_EXCL` acquire loop; if another process wins, treat as live lock.

## NITS

- Task 16 tests post “valid guide” payload without `terms`. Either require full final shape in tests or explicitly define `validate()` as using `.get(section, [])`.

## VERDICT

CHANGES_NEEDED