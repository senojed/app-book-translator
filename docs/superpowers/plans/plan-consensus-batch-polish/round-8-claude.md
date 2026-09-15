# Round 8 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - opačné pořadí odpovědí: Save/Revert vlastní `loadChapter()`
  GET může na serveru doběhnout PŘED zápisem rozpracovaného resolve, i
  když klientovi resolve odpověď dorazí dřív:** ověřeno logicky - kolo 7
  oprava (dohledání podle `id` v `CURRENT_FINDINGS`) řeší pořadí
  ODPOVĚDÍ na klientovi, ale ne pořadí ZÁPISŮ na serveru. Přidán
  `PENDING_RESOLVE_PROMISES` (Map id → Promise) plněný v `change`
  listeneru checkboxu; `btn-save` handler i `revertChapter()` teď před
  vlastním fetchem čekají `await Promise.all(PENDING_RESOLVE_PROMISES.
  values())`, takže žádné rozpracované resolve nemůže být "předběhnuto"
  jejich vlastním reloadem.

## Claude VERDICT

CONSENSUS (žádné vlastní BLOCKING/IMPORTANT, jediný Codexův bod opraven)

## Summary for log

Třetí kolo v řadě (6, 7, 8) řešící stejnou třídu bugu (zastaralé
reference přes `await` hranice) v `toggleResolved`/Save/Revert - tentokrát
na úrovni pořadí SERVEROVÝCH zápisů, ne jen klientských dat/DOM. Oprava
serializuje Save/Revert vůči rozpracovaným resolve requestům přes
Promise mapu. Claude verdict CONSENSUS - čekáme na Codexovo kolo 9, jestli
potvrdí totéž.
