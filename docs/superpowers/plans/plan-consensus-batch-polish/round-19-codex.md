## BLOCKING

- Task 2, `assign_ids()` (lines 287–323) + Task 9 merge (2376–2405): UUIDs are new on every regenerated analysis, so identical findings get different IDs. Save then preserves both forever, duplicating report/UI findings and losing prior `resolved` state. Replace UUID-only identity with a canonical finding fingerprint plus collision ordinal, or reconcile fresh findings to existing IDs before merge; add a regenerate→save→regenerate test proving no duplicate and retained resolution.

## IMPORTANT

- Task 14, save handler (lines 4703–4706): a `fetch` failure is treated as “not saved,” although the server may have committed before the response was lost. Retrying produces 409 and leaves the editor on a stale baseline. Implement an uncertain-write recovery path: read-after-write verification and reload on confirmed commit; otherwise preserve the draft but require an explicit reload/retry decision. Apply the same ambiguity handling to persisted finding resolution.

## VERDICT

CHANGES_NEEDED