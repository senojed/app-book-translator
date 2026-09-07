# Round 22 — Claude critique

Jediný nález, správný. Poprvé v této sérii to **není důsledek předchozí
opravy** - spirála „oprava rozbije něco jiného" se uzavřela.

## On Codex's points

### Agreed + fixed

- **Postpodmínka 3 byla u otázek typu `style` nesplnitelná.** Požadoval jsem,
  aby každý `must_decide.scope_key` ukazoval na položku ve své sekci, ale styl
  není kolekce klíčovaných položek - `apply_must_decide` jeho odpověď přidává
  do `rules`, takže klíč na nic ukazovat nemusí. Draft takové otázky má dvě
  (`nicknames`, `Binder_dialect`). Podmínka rozdělena podle druhu otázky:
  `name`/`place`/`term` ukazují na položku, `relationship` má tvar `a|b`
  s kanonickými konci, `style` je vyjmutý.

## Claude's own findings

Žádné.

## Claude VERDICT

CONSENSUS
