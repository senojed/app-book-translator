## BLOCKING

- Lines 154–156, 179–188 — Planned fields do not fit the existing guide interface. `merge_draft_and_guide()` reads `suggested` for characters and `suggested_cz` for places/terms; it discards draft `cz`, `render`, and `reference`. Consequently, mined values and evidence never reach the UI. Fix: define the exact draft schema and update `merge_draft_and_guide()` to preserve mined values and metadata, with integration tests from enriched draft through GET/POST.
- Lines 22–23, 69–72, 100, 113, 187 — The safety invariant is violated. An `unverified` model invention is prefilled, existing validation accepts it, and `review` seeds it into the glossary. Merely showing a color does not prevent this. Fix: leave `cz` empty for unverified proposals or require explicit per-item acknowledgement before POST accepts them.
- Lines 92–100, 109–116 — Global corpus occurrence does not verify a translation mapping. Common proposals such as “Rada” may occur frequently for unrelated reasons and become `confirmed`; the same problem affects retained English homographs. “The corpus decides” is therefore false without contextual linkage. Fix: require contextual/aligned evidence, or classify global matches only as candidates requiring expanded human review; never auto-collapse them as confirmed.
- Lines 179–185 — Evidence is not tied to the matched value. The proposed `reference` block lacks the searched/matched Czech form. If an existing `guide.json` overrides draft `cz`, the UI can display one value beside counts gathered for another. Fix: store `matched_cz`/query and recompute or suppress evidence whenever the displayed value differs.

## IMPORTANT

- Lines 134–138, 163–169 — Corpus loading silently tolerates duplicate book numbers and arbitrarily small partial corpora. Dictionary-key collisions may overwrite files, and two surviving books can still produce `confirmed`. Fix: reject duplicate/ambiguous numbering and define a minimum expected corpus/completeness policy.
- Lines 137–138, 193–200 — Cache validity is unspecified. A cache can be reused after changing `--dir`, replacing EPUBs, changing parsing rules, or changing schema. Fix: include schema version, normalized source root, file paths, sizes/mtimes or hashes, and rebuild on mismatch.
- Lines 174–175 — Reruns are neither refreshable nor idempotent. Previously mined nonempty values cannot be updated, stale `reference` metadata can survive corpus changes, and evidence appended to `note` can duplicate indefinitely. Fix: track provenance separately, replace prior mined data atomically, and preserve only human-authored values.
- Lines 83–86, 139–141 — Matching semantics are incomplete: no Unicode normalization, token boundaries, punctuation/whitespace handling, or multiword behavior is defined. Substring counting can inflate evidence. The rule also leaves three-character surfaces ambiguous. Fix: specify normalized, boundary-aware matching and explicit behavior for every length.
- Lines 146–148 — The response format conflicts with the existing parser convention: `extract_json()` only recovers JSON objects, while `propose()` claims a top-level list. Fix: specify an object envelope such as `{"proposals":[...]}` or extend and test the shared parser.
- Lines 151–156 — The surface-to-draft mapping is undefined. Characters use `name_en`, terms use `term_en`, aliases may collide, and the same normalized surface can occur in multiple kinds. Fix: use a stable composite identity such as `(section, normalized primary key)` and define alias handling and duplicate resolution.
- Lines 165–172 — Atomicity covers only the draft, not the report. The plan does not specify write order or cleanup, so a failed/fatal run can leave a fresh report beside an unchanged draft, or vice versa. Fix: generate both temporary artifacts and publish them together, or mark the report with run ID/status and publish only after success.
- Lines 59–62 versus 196–197 — “Does not touch the database at all” contradicts `create_run`/`finish_run`, `llm_calls`, and the cost guard, all of which require SQLite writes. Fix the ownership statement and document exactly which DB tables the command may mutate.
- Lines 202–213 — Tests omit the critical end-to-end invariant: enriched draft → merged GET payload → edited POST → saved guide → glossary seed. Add tests proving metadata survives merging and unverified proposals cannot enter the glossary without explicit confirmation.

## NITS

- Lines 151–153 — `Finding` is written as a set-like literal rather than a concrete dataclass/TypedDict definition; specify exact types and nullable fields.
- Lines 97 and 116 — The cost estimate and thresholds are asserted without measurement provenance. Mark them explicitly as initial estimates.

## VERDICT

CHANGES_NEEDED