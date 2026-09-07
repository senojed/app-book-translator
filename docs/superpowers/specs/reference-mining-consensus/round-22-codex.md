## IMPORTANT

- Krok 0, postpodmínka 3 a test 8: požadují, aby **každý** `must_decide.scope_key` odkazoval na položku své sekce. Reálný draft však obsahuje `kind: style`; styl není kolekce klíčovaných položek a `apply_must_decide` jeho odpověď přidává do `rules`. Podmínka je tedy nesplnitelná nebo nejednoznačná. Omezit ji na `name`/`place`/`term` a samostatně definovat validaci `relationship`; `style` explicitně vyjmout.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item