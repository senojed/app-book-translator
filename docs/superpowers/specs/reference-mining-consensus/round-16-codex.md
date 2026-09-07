## IMPORTANT

- **Review UI / POST allowlist:** The allowlist drops `note` from characters, places, and terms. This loses scout context and prevents `glossary.seed_from_guide()` from persisting notes, although existing `merge_draft_and_guide()` emits them and `_seed_one()` stores them. Add `note` to those three allowlists and test its end-to-end preservation.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item