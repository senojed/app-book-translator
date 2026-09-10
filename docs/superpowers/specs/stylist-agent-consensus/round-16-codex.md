## IMPORTANT

- `def _snapshot_db`, lines 880–911: the 30-second deadline is ineffective for a slow backup because `src.backup()` uses the default `pages=-1`, copying the whole database in one step; the progress callback cannot interrupt that step. Pass a bounded `pages` value, check the deadline between batches, and add a timeout regression test.
- `_polish_rejected`, lines 835–873: set comparison of `(type, term_id, actual)` ignores multiplicity. If the baseline contains one existing leak/inconsistency and styling introduces another occurrence with the same key, it is accepted as unchanged. Compare occurrence counts or richer per-occurrence data before/after.
- Restore procedure, lines 946–961: deleting `-wal`/`-shm` before `os.replace` creates a crash window that can damage the current DB, and it ignores a possible hot `-journal` from the currently used rollback-journal mode. Provide a tested restore function/command that acquires the application lock, handles all journal sidecars safely, and preserves the current DB until replacement succeeds.

## NITS

- Lines 1093 and 1205–1206 still describe snapshot creation as `shutil.copy2`; current code uses `_snapshot_db`.
- `_paragraph_count`, line 372: `split("\n\n")` does not recognize CRLF or whitespace-only blank lines. Normalize newlines or use a blank-line regex.

## VERDICT

CHANGES_NEEDED