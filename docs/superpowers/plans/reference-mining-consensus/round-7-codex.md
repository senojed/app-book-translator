## BLOCKING

- **Task 12, Step 3 — `valueField.input.onblur`:** synchronous `render()` removes the clicked sibling button during `blur`, before its `click` fires. After typing, actions such as „použít návrh“, „vrátit zpět“, bulk accept, or add relationship can be dropped. Avoid rebuilding during intra-form focus transitions, or coordinate deferred rendering with click dispatch.
- **Task 12, Step 3 — `renderField.canBeReference`:** it depends on current `item.render`. After unlocking a referenced `keep` and selecting the empty option, `canBeReference` becomes false and the revert control disappears, violating reversibility. Compute it solely from fresh reference metadata/classification, as `valueField` does.

## IMPORTANT

- **Task 12, Steps 1–4:** all three tests exercise only GET/POST backend behavior. They pass even if the entire JavaScript implementation in Step 3 is omitted. Add DOM/browser interaction tests covering focus→button click, unlock→empty→revert, suggestion undo, and bulk undo.
- **Tasks 8 and 13, Step 3:** `corpus_fingerprint()` and `load_cache()` can propagate `OSError` from `build_manifest()` after `isdir()` succeeds—for example permission failure or a filesystem race. This can make review return HTTP 500 or make `reference` escape without the required `FatalRunError` diagnostic. Catch filesystem errors: freshness should return `None`; cache loading should return `None` or be converted by the CLI.

## NITS

- **Task 9, Step 3 — `_reference_block` comment:** it still recommends ``shown_cz and ...`` although the code and round-6 fix correctly removed that condition. Rewrite the comment to prevent reintroducing the old bug.

## VERDICT

CHANGES_NEEDED