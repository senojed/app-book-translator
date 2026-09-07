## BLOCKING

- **Classification precedence (lines 258–279) contradicts stage-0 rules and tests.** Step 2 maps every attested primary surface to `weak`, so lowercase `stole` and proper names found only case-insensitively never reach `evidence_only`; `weak` then pre-fills them. Step 1 also omits the uppercase and minimum-length requirements. This reintroduces the central false-evidence bug. Restrict `confirmed`/`weak` to eligible uppercase, case-exact primary matches; otherwise run stage 1 and retain `evidence_only` only when it returns `null`.

## IMPORTANT

- **Agent test 6 still says explicit `null` → `unresolved`.** Under the new precedence, `null` must preserve `evidence_only` when stage-0 evidence exists. Qualify the expectation as “no stage-0 evidence → `unresolved`” and add the preservation case.
- **Evidence display rules conflict.** The classification table requires visible evidence for `evidence_only`, but `merge_sources` suppresses numerical evidence whenever blank displayed `cz` differs from `matched_cz`. Since `evidence_only` intentionally leaves `cz` blank, its evidence disappears. Limit that binding check to prefilled `confirmed`/`weak` values or define a separate auxiliary-evidence display rule.
- **Normalization postcondition 6 is not mechanically specified.** The script allegedly verifies that every alias is “identifying,” but no predicate, denylist, or required human acknowledgement is defined. A developer cannot implement a truthful automated check from examples ending in “and similar.”

## NITS

- Line 276 names stage-0 field `matched_en`, while both `Evidence` and `Finding` define `matched_forms`. Use one schema name.
- Define `Finding.source` for final `evidence_only`; the current comment assigns `none` only to `unresolved`.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item