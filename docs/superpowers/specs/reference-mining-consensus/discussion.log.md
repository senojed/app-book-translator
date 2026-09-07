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

## Kolo 2 — 2026-09-07

- Codex: `round-2-codex.md` — VERDICT: CHANGES_NEEDED (3 BLOCKING, 7 IMPORTANT, 2 NITS)
- Claude: `round-2-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT)

Nejzávažnější: oprava case-sensitivity z kola 1 vůbec neřešila problém, kvůli
kterému vznikla — české „na stole" je malými písmeny, takže case-sensitive dotaz
na `stole` ho najde stejně. Obecná slova (malé počáteční písmeno) proto nově
nikdy nedosáhnou `confirmed` automaticky. Ověřeno, že `stole` v draftu opravdu je.

Další blokující: pravidlo o vazbě důkazu (`cz == matched_cz`) zabíjelo metadata
právě u `proposed`/`contradicted`, kde je `cz` prázdné záměrně — vazba se nově
vyžaduje jen u tříd s předvyplněnou hodnotou. A UI nemá kudy reference dostat:
`build_app`/`run_review_server` třetí zdroj nemají (ověřeno, main.py:123).

Doplněno: přesný predikát souvýskytu s poměrem, validace odpovědi lexikografa,
odstranění bloků `reference` před uložením guide.json (server.py:129 dnes ukládá
celý payload), sdílená `normalize_key`, celá CLI a config sekce, přebírání
předchozích nálezů u selhané dávky (`stale`), report jako odvoditelný artefakt
s run_id místo lživého tvrzení o atomicitě dvou souborů.

Claude přidal: stupeň 0 nehledá aliasy, a přichází tak o důkazy u jmen, kde
překlad používá zkrácenou podobu (Dresden místo Harry Dresden).

Sporné body: žádné.

