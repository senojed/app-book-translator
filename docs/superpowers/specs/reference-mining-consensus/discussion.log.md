# Plan-consensus - discussion log

- Plán: `docs/superpowers/specs/2026-09-07-reference-mining-design.md`
- Start: 2026-09-07
- Max kol: 10

## Kolo 1 — 2026-09-07

- Codex: `round-1-codex.md` — VERDICT: CHANGES_NEEDED (4 BLOCKING, 9 IMPORTANT, 2 NITS)
- Claude: `round-1-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní BLOCKING, 3 vlastní IMPORTANT)

Codex našel 4 blokující body, všechny ověřeny proti kódu a přijaty: merge_draft_and_guide
zahazuje vytěžená pole (guide.py:93,111), neověřený návrh by se přes review dostal do
glosáře, globální výskyt v korpusu neprokazuje překladový vztah, důkaz nebyl svázán
s hodnotou. Claude přidal blokující bod, který Codex minul: opakovaný `scan` přepíše
draft celý (main.py:105) a těžbu tiše smaže.

Zásadní změny ve specu: výsledek těžby se stěhuje z draftu do vlastního
`data/reference.json`; `confirmed` smí vzniknout jen z deterministického stupně 0;
neověřené návrhy nechávají `cz` prázdné (invariant vynucen mechanicky, ne kázní);
přibyl test souvýskytu přes EN stranu; `merge_draft_and_guide` se rozšiřuje na
`merge_sources` se třemi zdroji.

Sporné body: žádné.

