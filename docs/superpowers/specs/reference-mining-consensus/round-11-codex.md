## BLOCKING

- Stage 0 does not prove that a term was retained. The spec identifies `stole` as a Czech homograph, then classifies lowercase/common-word matches as `weak` and still prefills `cz`. Such an item also skips Stage 1. This can silently seed an incorrect glossary value. Common-word matches must be evidence-only, with empty `cz`, and should remain eligible for Stage 1.
- “Case preserved” contradicts case-insensitive matching for capitalized surfaces. A capitalized English surface can match an unrelated lowercase Czech word and become `confirmed`. Case-insensitive matches cannot safely qualify for automatic prefilling without an additional disambiguation rule.
- The proposed alias-collision validation makes the current draft impossible to save through the described UI. The real draft already contains many conflicts (`Murphy`/`Klish`, `Morgan`/`Donald Morgan`, `Thomas`/`Thomas Raith`, `Will`/`Billy Borden`, etc.), while ordinary canonical names are neither editable nor deletable in the current UI or the proposed UI description. Either add edit/delete controls and reconciliation semantics for every section, or limit the new validation and specify exactly which collisions it covers.

## IMPORTANT

- The stated invariant is false as written. `proposed` and `not_attested` values are not prefilled, but a user may manually copy the displayed model proposal and save it without corpus attestation. Either redefine the invariant as “no unattested model value is automatically prefilled” or enforce provenance during POST.
- Contract B deliberately leaves the algorithm unspecified. Acceptance examples do not tell an implementer how to build it, which tokenizer or morphology library to use, how capitalization is treated, or how matched inflected forms are returned. This design is not executable without another design/measurement phase.
- `books_with_en()` has no matching contract. It is unclear whether it uses Contract A, exact case-sensitive matching, aliases independently, sentence-start filtering, or the CZ-form matcher. This directly affects `E` and therefore every `proposed` classification.
- The compound workflow lacks a payload contract. Undefined points include:
  - Representation and IDs of generated variants.
  - Distribution of aliases, notes, `suggested_cz`, and reference metadata.
  - Whether variant names are editable and how IDs change after edits.
  - How deletion is encoded.
  - How `must_decide.target_id` is represented and validated.
  - Whether temporary IDs survive into `guide.json`.
- The design says automatic splitting is abandoned, but POST still “expands” compound items. Clarify that the browser creates user-approved variant rows and POST only validates them; otherwise this is still automatic splitting.
- `coverage.attempted` is contradictory. One section implies all model submissions are attempted; another uses it exclusively for successful `cz: null` responses. State whether the four coverage arrays are disjoint and define precedence for failed or omitted items.
- `per_form` is untyped, although union-of-ranges, primary thresholds, reporting, and UI depend on it. Define its keys and value schema, including per-book counts/ranges and how overlapping primary/alias matches are represented. Likewise, `matched_en` and `matched_cz` are singular despite potentially multiple matched forms.
- Duplicate draft entries are consolidated only “before mining,” but `merge_sources` still receives the original draft. Multiple original rows can therefore map to one reference ID and reappear twice in the UI. The canonicalized item list must also drive merging, or be persisted explicitly.
- Freshness is underspecified:
  - `corpus_fresh` is shown as a boolean but may equal `unknown`.
  - The draft fingerprint excludes notes even though notes are sent to the lexicographer and can change its proposal.
  - Exact threshold fields, canonical serialization, path normalization, and whether hashing occurs before or after duplicate consolidation are undefined.
- Partial EPUB failure semantics are incomplete. If one side of an initially paired book fails to parse, specify that both sides of that book are removed and that the minimum-pair check runs afterward.
- Prior-result preservation has no clear owner. `resolve()` does not accept prior findings, while `write_reference()` is described as applying the stale/limit state machine. Specify which function loads and validates the previous file and how a corrupt previous file is handled.
- `write_report()` specifies timing but not report contents or ordering. Tests cannot be written without a report contract.
- The glossary guard says a conflict is “reported,” but `_seed_one` and `seed_from_guide` currently return nothing. Define whether this raises, returns structured conflicts, prints, or records them. Also define collision scope across sections and behavior for alias-vs-alias and canonical-vs-canonical collisions.

## OVER-ENGINEERED

- The compound editor, temporary IDs, deletion workflow, and `must_decide` remapping are disproportionate for eleven known bad rows. Manually normalize those rows once before mining, then fix the scout prompt for future scans.
- Per-item stale recovery, four coverage states, three freshness flags, report/run-ID synchronization, and partial batch continuation are excessive for 132 items costing roughly cents. Prefer atomic failure: retain the previous `reference.json`, report the failed batch, and rerun.
- Contract B’s morphology evaluator plus a 40-pair fixture and 20-query manual checkpoint is expensive relative to its effect: Stage 1 never prefills anything. A conservative exact whole-word check, explicitly labelled weak evidence, is sufficient here.
- `reference_report.md` duplicates information already intended for the UI. A console summary is enough unless the report has a concrete audit use.
- The corpus cache and manifest invalidation are reasonable for approximately two million words. The separate reference artifact, merge precedence, evidence display, and glossary collision guard are also proportionate.

## NITS

- `klasifikace` is the only Czech field name in an otherwise English schema. Use `classification`.
- Detection of `" or "` is case- and whitespace-sensitive. Define normalization or restrict the accepted syntax explicitly.
- `REFERENCE_*` fingerprinting would include unrelated path, model, batching, and cache settings if interpreted literally. Enumerate only settings that affect evidence.
- The configured `claude-sonnet-5` identifier is currently active, so the model name itself is not a compatibility problem. [Anthropic model lifecycle](https://docs.anthropic.com/en/docs/about-claude/model-deprecations)

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item