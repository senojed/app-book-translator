## IMPORTANT

- [docs/superpowers/specs/2026-09-06-book-translator-design.md:365](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:365) + [381](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:381): Drift detection is circular. `variants` can come from `term_mentions`, but `build_mentions` only records known `cz`/variants. A new inconsistent rendering that is not already in variants will not enter `term_mentions`, so [368](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:368) is false: drift will not catch it later.  
  Fix: define how unknown CZ renderings are discovered. Options: keep LLM `new_terms` for existing `term_en` as `variant`, add explicit translator metadata for used renderings, or accept that drift only checks known forms and remove the stronger claim.

- [docs/superpowers/specs/2026-09-06-book-translator-design.md:143](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:143): “sjednocené do jednoho tvaru” is an interface gap. Critic findings have `severity/cz_excerpt/issue/suggestion`; concordance issues need at least `type`, `term_en`, expected/actual forms, maybe chapter context. Translator revision prompt depends on this shape.  
  Fix: define `Finding` schema, e.g. `{source, type, severity, term_en?, expected?, actual?, cz_excerpt?, issue, suggestion}`.

- [docs/superpowers/specs/2026-09-06-book-translator-design.md:390](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:390): `check_chapter` says candidate inconsistency becomes “otázka”, but pipeline step 7 only persists questions from translator metadata, not concordance.  
  Fix: specify that pipeline converts concordance candidate issues into `questions`, with `kind`, `scope_key`, `guess_answer`, and `severity`.

- [docs/superpowers/specs/2026-09-06-book-translator-design.md:194](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:194): Requeue by `term_mentions` misses affected chapters where the term occurs in EN but no known CZ form was found. Those chapters may need recomputation after a corrected answer, but they are absent from `term_mentions`.  
  Fix: either store EN occurrences separately, or define `term_mentions` rows for omissions, e.g. `cz_form NULL`, and include them in `affected_chapters`.

## NITS

- [docs/superpowers/specs/2026-09-06-book-translator-design.md:455](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:455): `estimated_cost_usd` name conflicts with [457](C:/Users/Honza/Nextcloud/Jan/PROJECTS/book-translator/docs/superpowers/specs/2026-09-06-book-translator-design.md:457), which describes actual usage-based cost. Rename to `cost_usd`, or store both `preflight_estimated_cost_usd` and `actual_cost_usd`.

## VERDICT

CHANGES_NEEDED