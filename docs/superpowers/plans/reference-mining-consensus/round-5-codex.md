## BLOCKING

- **Task 12, Step 3 — `valueField` / `renderField`:** Unlock state is not durable across `render()`. Unlocking sets `_czProvenance` or `_renderProvenance` to `"human"`. After any unrelated re-render, `backed` becomes false, so the “vrátit zpět předvyplněné” control disappears and the reference original is no longer recoverable through the UI. This affects adding relationships and bulk accept/undo. Persist the reference original and unlocked state on the item; render the revert control from that state and clear it only after reverting.
- **Tasks 8–9, `_finding_is_well_formed` / `_merge_section`:** A type-valid but semantically inconsistent finding such as `classification="proposed", cz="Vymyšleno"` passes `load_reference`; `_merge_section` then treats `cz` as reference-backed and pre-fills it. This directly violates the classification table and core invariant. Validate classification-dependent fields and independently gate prefill to `confirmed`/`weak`.

## IMPORTANT

- **Tasks 9 and 12, `_reference_block` / `valueField`:** Evidence binding and display are inconsistent with the spec. `_reference_block` retains numeric evidence when `shown_cz == ""` because mismatch checking requires `shown_cz` to be truthy. Conversely, when a human value equals `matched_cz`, the backend retains evidence but `valueField` hides it because evidence rendering is coupled to `backed`/reference provenance. Remove the truthiness condition and render retained evidence independently of locking provenance.
- **Task 12, Steps 1 and 4:** The three automated tests do not execute any JavaScript or serialize state produced by the form. They would pass if `valueField`, `renderField`, accept-all, undo, locking, and provenance transitions were entirely broken. Extract state transitions into testable JavaScript reducers or add a lightweight DOM/browser test covering unlock → re-render → revert, individual suggestion undo, bulk undo after manual edits, and serialized payload.
- **Task 12, `aliasCollisionWarnings`:** `owners[key]` stores only one owner, so later aliases overwrite earlier ones. A collision can be missed when the retained owner is the canonical item itself, for example if `Bar` aliases `Foo` and a later `Foo` item also lists `Foo` as its own alias. Store all owners per normalized key and warn whenever any different item owns the alias.

## VERDICT

CHANGES_NEEDED