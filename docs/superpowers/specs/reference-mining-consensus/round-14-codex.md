## BLOCKING

- Step 0 does not normalize all `must_decide.scope_key` values. The real draft has at least nine non-relationship keys that do not match any canonical item in their declared section: `Injun Joe`, `the Ostentatiatory`, `Shagnasty/skinwalker`, `grasshopper_nickname`, `Warden`, `Za-Lord's Militia`, `grasshopper (Molly's nickname)`, `the Nevernever`, `Mouse (pes)`. The spec mentions only two. Current `apply_must_decide()` inserts a new row when matching fails, so these create duplicates or wrong-section entities. Require every post-normalization scope key to resolve exactly once or be explicitly converted into a standalone item.

- The normalization scope misses malformed relationships. The draft contains endpoints `Billy/Will`, `Gatekeeper/Rashid`, `Will/Georgia`, and `Rashid/Gatekeeper`; some represent duplicate relationships, while `Will/Georgia` combines two people. Relationship names cannot be edited or deleted in the current UI. Step 0 must report and manually resolve these before the proposed “relationships checked” confirmation can be meaningful.

- Alias semantics remain unresolved. `Injun Joe` is an alias of `Listens-to-Wind`, but its `must_decide` requires an independently translated rendering. A glossary row has only one `cz` value for the canonical surface and all aliases; making `Injun Joe` separate would then trigger the proposed alias-collision guard. The design must define alias-specific translations or require such translatable nicknames/titles to be removed from aliases and represented separately.

## IMPORTANT

- POST cleanup is incomplete. Items carry sibling fields `provenance`, `scout_suggestion`, and `lexicographer_suggestion`, but the spec removes only `reference` blocks before saving. Those transient fields would remain in `guide.json`, contradicting the stated clean human model. Define an allowlisted persisted schema or strip all merge/UI metadata.

- `Finding.source` permits only `kept | proposed`, but `unresolved` findings can arise without either source, especially surfaces under three characters. Add `none`, make the field nullable, or define valid semantics for every classification.

- Freshness behavior contradicts itself: lines 410–412 say stale reference data shows only a stale-run notice, while lines 415–416 say classification and proposal are always displayed. Specify whether stale lexicographer proposals and classifications are exposed.

- The mandatory relationship-review checkbox has no defined payload field, server validation, or removal-before-save behavior. Without that contract, implementations may either fail to enforce it or pollute `guide.json`.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item