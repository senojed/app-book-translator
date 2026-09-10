## BLOCKING

- **`_backup_db_once` / lines 834, 899–903, 1219–1223:** The claimed pre-`polish` rollback and test are impossible with the shown ordering. `create_run` and guardrail LLM-call records mutate the DB before the lazy backup, so the backup cannot be byte-identical to the DB before invocation; restoring it also leaves the current run unfinished. Fix by creating a temporary SQLite snapshot before `create_run`, promoting it atomically to `.pre-polish-backup` only immediately before the first chapter commit, and deleting it if nothing is committed. Update tests accordingly.

## IMPORTANT

- **`_backup_db_once`, lines 761–778:** `shutil.copy2(db, backup_path)` truncates the previous useful backup before copying. A crash, disk-full condition, or interrupted copy can destroy both the rollback guarantee and the previous backup. Copy to a sibling temporary file, flush/sync it, validate it, then replace the canonical backup atomically. Prefer SQLite’s backup API over raw file copying.

- **`critic.review`, lines 89–136:** Validation remains partly fail-open. A finding such as `{"severity": 0}` or `{}` is silently converted by `_to_finding` into a harmless minor finding. This contradicts the stated rule that malformed critic output is retried and then rejected. Validate required finding fields and enums before conversion; malformed entries must invalidate the whole response.

- **`check_meaning_preserved`, lines 578–582:** `value in (True, False)` accepts JSON integers `0` and `1` because Python booleans compare equal to integers. Thus malformed output can pass validation, including `0` being treated as “no drift.” Require `isinstance(value, bool)` for both fields and add tests for `0`, `1`, `null`, strings, and missing keys.

- **Test plan, lines 965–1166 and 1180–1203:** Safety-critical CLI construction is only manually checked. The fake scripts do not assert `--sandbox read-only`, `--ephemeral`, isolated `-C`, `-m`, or the positional `-`; regressions would pass automated tests. Capture and assert the complete argv in unit tests, while retaining the manual compatibility check against the real CLI.

- **Prose/code consistency, multiple locations:** Several stale statements still describe superseded behavior:
  - Line 724 says baseline concordance receives `[]`; code at lines 810–820 passes `rendered_terms`.
  - Lines 661–662 and 1341–1344 still say missing preflight would end with `status="ok"`; current all-failed behavior is `"fatal"`.
  - Lines 1219–1223 say any nonempty chapter set creates a backup; lazy code creates one only for an accepted change first firstst error?** Actually need fix typo.**. 
  - Lines 1333–1336 describe baseline findings as originating when the chapter became `done`; they are recomputed immediately before styling with the current glossary.
  - Lines 1447–1452 say `check_meaning_preserved` checks only meaning; lines 521–588 now explicitly check register.
  
  Correct these sections so implementation and acceptance criteria do not conflict.

## NITS

- **Lines 349 and 400:** Docstrings still refer to `subprocess.run`; implementation uses `Popen`.
- **Lines 821–824:** Once new concordance findings or `critic_failed` already guarantee rejection, subsequent paid checks can be skipped. Reorder for fail-fast behavior and lower cost.

## VERDICT

CHANGES_NEEDED