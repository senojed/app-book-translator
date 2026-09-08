## BLOCKING

- Task 2, Step 8: It says a genuine cross-section homonym may remain, but the settled spec forbids all cross-section homonyms and `find_issues()` will continue reporting it. Step 9 can therefore never pass. Remove or rename one occurrence as required by the spec.
- Task 3, Step 1, `test_load_side_failure_drops_whole_book_before_minimum_check`: after one of three pairs fails, only two remain, while `REFERENCE_MIN_CORPUS_BOOKS == 3`. `load_corpus()` correctly raises, contradicting the test’s expected success. Supply four pairs or monkeypatch the minimum to two.
- Task 4, Step 1, `test_punctuation_without_following_space_is_not_sentence_start`: the test asserts `confirm_eligible is False`, but `x.Mab` is explicitly not a sentence start and therefore satisfies the “outside sentence start” requirement. The implementation returns `True`. Fix the assertion and description.
- Task 7, Step 3: `count_en_surface()` NFC-normalizes the primary form before using it as a `per_form` key, but `classify()` and `_finding()` look it up using raw `item["surface"]`. An NFD surface therefore has evidence yet becomes `weak` with `primary_attested=False`. Normalize the lookup key or normalize `SurfaceItem.surface` before resolution; add an end-to-end NFD test.
- Task 12, Step 3, relationship `must_decide`: lines 3204–3208 still copy `md.default` into `answer`. This directly contradicts the spec’s required blank dropdown with the scout suggestion shown separately. Remove default-to-answer initialization.
- Task 12, Steps 1–3: character `cz` uses a plain input. It never displays or applies `lexicographer_suggestion`, and it is not protected for confirmed/weak findings. Use equivalent provenance-aware controls for both character `render` and `cz`.
- Task 12, Step 3, `acceptAllScoutSuggestions()`: the bulk action has no “back” state at all, although the spec requires undoing exactly the fields changed by that action. Implement a tracked change set and a toggle restoring only those values.
- Task 12, Step 3, `valueField()`/`renderField()`: per-item undo is not reliable. Both suggestions share one mutable `before`, and manual input overwrites it. Using both suggestion buttons or editing after applying one loses the pre-action value. Store independent snapshots or allow only one active suggestion state.
- Task 12, Steps 1–4: required UI behavior remains unimplemented: `evidence_only` evidence is never rendered, stale findings have no warning, confirmed findings are not grouped/collapsed, and alias collisions have no warning. The three tests never execute JavaScript, so they cannot detect any of these failures. Implement the requirements and add actual browser/DOM tests.
- Task 14, Step 1: three success-path tests leave `Nevernever.cz` empty. Server validation therefore rejects the POST in `test_proposed_does_not_reach_glossary_without_acceptance` after the claimed human decision, `test_accepted_suggestion_does_reach_glossary`, and `test_confirmed_flows_through_with_evidence`. Fill every unrelated required field or remove `Nevernever` from those fixtures.

## IMPORTANT

- Task 6, Step 3: `propose()` assumes the parsed top level is a dict and every proposal is a dict. A valid JSON list or scalar causes `AttributeError`; malformed rows do likewise. The specified validation contract requires `ValueError`. Validate the envelope, `proposals` list, and every row explicitly.
- Task 8, Step 3: schema validation is still incomplete. `bool` passes checks for integer fields, `per_form[*].case_exact` is neither required nor type-checked, and fingerprint keys/value types are unchecked. Reject booleans for integer fields and validate the complete nested schema.
- Task 9, Step 3: glossary-item matching still uses legacy `normalize()` (`strip().lower()`) rather than `textnorm.normalize_key()`. NFC/NFD or whitespace-equivalent guide and draft keys can fail to merge, producing duplicate rows and losing human precedence. Use `normalize_key()` for character/place/term identity; retain `guide.normalize()` only for relationship semantics.
- Task 12, Step 3: `backed` ignores `provenance`. A human value equal to `matched_cz` is treated as reference-origin and locked. Determine locking from `item.provenance == "reference"` as required by the source-based UI contract.

## VERDICT

CHANGES_NEEDED