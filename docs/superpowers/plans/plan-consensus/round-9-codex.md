## IMPORTANT

- Task 11 + Task 16: `merge_scout_facts` says conflicts in `characters/places/terms` create `must_decide{kind, scope_key=povrch, question}`, but `kind` for `places` is undefined and `server.apply_must_decide` has no `place` branch. Place conflict from `scan --chunked` either gets lost or is misrouted into `terms`, losing `type=place`. Fix: add explicit `kind:"place"` through scout/review/glossary, or state that place conflicts route to `terms` with `type:"place"` and test it.

- Task 15, `requeue.apply_answer`: for unknown blocking term/name with alternatives (`"Foo | Foa"`), `glossary_ops` uses `("add_approved", scope_key, parts[0])` and then `("add_accepted_alt", tid_or_new, a)`, but `tid_or_new` is not defined before the transaction. `commit_answer` cannot know which new `term_id` to update unless this is specified. Fix: either precompute `term_ + slugify(scope_key)` before building ops, or make `commit_answer` resolve the key after `add_approved` and apply subsequent alt ops to the resolved id. Add a test for blocking answer with alternatives.

- Task 14, step 6: `extra_mentions` for `new_terms` inserts `cz_form=nt["cz"]` as `source:"rendered"` without verifying that this form exists in the final `cz`. Because `new_terms` are cumulative across revisions, stale pre-revision metadata can create false mentions and false drift/requeue signals. Fix: verify `nt["cz"]` against final translation; if absent but the chapter must remain affected for requeue, insert a sentinel mention with `cz_form=NULL` / non-drift source, not a fake rendered form.

- Task 14 atomicity test is too weak. It fails during mention insert but does not include `new_candidates`, so it does not prove “glossary candidates + mentions + questions + chapter update” roll back together, which is the core transaction-B requirement. Fix: include a `new_candidates` row before the bad FK mention and assert it is absent after rollback.

## NITS

- Task 7 tests still save guide objects without `terms`. `load_guide` normalizes this, so it is not fatal, but tests should use the full final shape to avoid normalizing away caller mistakes everywhere.

- Task 11 `must_decide` conflict objects should specify all expected fields (`kind`, `scope_key`, `question`, ideally `default`). Current wording is underspecified for executor implementation and UI rendering.

## VERDICT
CHANGES_NEEDED