## IMPORTANT

- **Lines 119–123 vs. 346–347:** normalization forbids all cross-section homonyms, but lexicographer identity explicitly says the same name may exist in `places` and `terms`. Remove the latter allowance or narrow the postcondition.
- **Lines 108–125 vs. 633–636:** the spec says tests enforce all six normalization postconditions, but test 8 omits canonical relationship endpoints, merged abbreviated relationships, cross-section homonyms, identifying aliases, and explicitly parenthesized surfaces. Add these assertions.
- **Lines 28–32 and 153 vs. 526–535:** the global rule says only referenced values are prefilled and neither scout nor lexicographer estimates are prefilled. The later scope explicitly prefills scout estimates for relationships and style. Scope the earlier statements to glossary fields (`cz`/`render` for characters, places, terms).
- **Lines 129–141, 258, 261 and 630:** `evidence_only` proceeds to stage 1, yet each `Finding` has one classification and an explicit `null` becomes `unresolved`. Consequently, no successful full run can retain `evidence_only`, despite UI and end-to-end requirements treating it as a final class. Define classification precedence and whether stage-0 evidence survives a null or stage-1 proposal.
- **Lines 552–553, 561–562 vs. 655–659:** suggestion buttons intentionally put proposed values into fields, but the end-to-end test says they cannot reach the glossary without “manual typing.” Replace that with “explicit user acceptance or manual entry.”

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item