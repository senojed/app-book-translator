## IMPORTANT

- **Task 2, Step 8:** Manual normalization instructions omit settled rules from the spec. Compound entries must split `suggested_cz` using the same separator and pair values positionally, using blanks when counts differ. Invalid `must_decide.scope_key` values must allow all three resolutions: remap, promote to a standalone item, or delete the question. The current instruction only says to “fix” the key and does not cover aliases requiring their own translation, such as `Injun Joe`. Add these rules explicitly; `find_issues()` cannot validate these semantic decisions afterward.

## NITS

- **Task 9, Step 3, `_merge_section` guide-only loop:** A guide-only character with human `render="keep"` and blank `cz` receives `provenance="none"` because provenance depends solely on `g.get("cz")`. This contradicts the documented meaning that values from `guide.json` are human-originated. Set guide-only rows to `provenance="human"` whenever the guide row exists.

## VERDICT

CHANGES_NEEDED