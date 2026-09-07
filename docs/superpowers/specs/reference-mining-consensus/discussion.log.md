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

## Kolo 3 — 2026-09-07

- Codex: `round-3-codex.md` — VERDICT: CHANGES_NEEDED (4 BLOCKING, 6 IMPORTANT, 2 NITS)
- Claude: `round-3-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní BLOCKING, 1 IMPORTANT)

Nejcennější námitka: třída `contradicted` byla věcně chybná. Čeština skloňuje,
takže nenalezení jednoho konkrétního tvaru návrh nevyvrací — přejmenováno na
`not_attested` a hledání na CZ straně se nově opře o existující
`concordance.find_form_occurrences` (kmenové porovnání), místo aby se stavěla
vlastní morfologie.

Další blokující: agregace aliasů dvojitě počítala překryvy (`Dresden` uvnitř
`Harry Dresden`) a nález aliasu se vydával za doložení primárního tvaru; identita
přes `term_en` nerozliší stejné jméno v `places` a `terms` (nově `id =
sekce/klíč`); `write_reference` neuměl odlišit selhanou dávku od `unresolved`
a `--limit` by smazal položky mimo limit; a délkové pravidlo si protiřečilo
s vlastním testem `Mab`.

Postavy obcházely invariant: validace dovoluje prázdné `cz` při `render=keep`,
UI má `keep` jako výchozí a seed pak vloží anglické jméno. Nově vyžadována
aktivní volba.

Claude přidal blokující rozpor ve vlastní tabulce hranic (`reference.py` neměl
znát `guide`, ale volat `guide.normalize_key`) — řeší nový `src/textnorm.py`.
A upřesnil, že `--limit` se smí týkat jen stupně 1; stupeň 0 je zdarma.

Spec přepsán celý — po třech kolech se sekce rozcházely.

Sporné body: žádné.

## Kolo 4 — 2026-09-07

- Codex: `round-4-codex.md` — VERDICT: CHANGES_NEEDED (3 BLOCKING, 7 IMPORTANT)
- Claude: `round-4-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT)

Zrušeno rozhodnutí z kola 3. `concordance.find_form_occurrences` se pro doložení
termínů použít nedá, ověřeno spuštěním:
  form_key("Bílá rada") == form_key("Bída rana")   → True
  find_form_occurrences("Byl to Za-Lord.", "Za-Lord") → []
Kmen zkracuje "bílá" i "bída" na "bí", "rada" i "rana" na "ra"; tokenizace přes
\w+ rozseká Za-Lord na pomlčce. Pro drift v jedné kapitole to stačí, pro doložení
v milionovém korpusu ne. `reference.py` dostává vlastní matcher se dvěma
kontrakty (přesný pro stupeň 0, prefixový pro stupeň 1), `concordance` zůstává
beze změny.

Další blokující: normalize_key vždy casefolduje, takže "case-sensitive hledání"
na normalizovaném textu bylo nemožné — normalizace nově slouží jen k identitě,
hledá se v surovém textu. `reference_path` musí být keyword-only (třetí poziční
parametr build_app je on_saved, server.py:108). `id` z draftu nejsou zaručeně
unikátní — scan_book duplicity nekontroluje, dedup je jen ve scan_chunks.

Důležité: write_reference dostal úplný stavový automat včetně nálezů stupně 0;
chybějící id v odpovědi modelu se nově liší od explicitního null (stale vs
unresolved); fresh:false nesmí předvyplňovat vůbec; prahy confirmed se počítají
jen z primárního tvaru; UI fallback `c.render || "keep"` (index.html:111) se ruší
ve prospěch prázdné volby; report se generuje z finálního slitého payloadu.

Claude přidal: částečný běh přes --limit se tvářil jako úplný, doplněno `coverage`.

Sporné body: žádné.

## Kolo 5 — 2026-09-07

- Codex: `round-5-codex.md` — VERDICT: CHANGES_NEEDED (2 BLOCKING, 2 IMPORTANT)
- Claude: `round-5-claude.md` — VERDICT: CHANGES_NEEDED (1 vlastní IMPORTANT,
  1 částečný nesouhlas)

Nejzávažnější: draft obsahuje 11 složených položek (`White Court / Red Court /
Vampire Courts`, `veil/veiling spell`, `Will/Billy`), které nejsou jedním
povrchem. Přesné hledání by je nikdy nenašlo a všechny by skončily jako
not_attested, ačkoli samotný skinwalker má 58 výskytů. Claude o nich věděl
z vlastní úvodní analýzy (přeskakoval je podmínkou na "/"), ale do specu je
nezanesl. Doplněn kanonizační krok + oprava promptu scouta. Mezi položkami jsou
i duplicity v opačném pořadí (skinwalker/naagloshii vs naagloshii/skinwalker).

Dále: `coverage` neuchovával failed ani missing_response, takže po skončení
příkazu nešlo odlišit "model řekl neznám" od "dávka spadla"; testy si
protiřečily (řádky 510 a 512); `fresh` se kontroloval jen proti draftu, ačkoli
fingerprint zahrnuje i korpus a prahy — nově tři samostatné příznaky.

ČÁSTEČNÝ NESOUHLAS: Codex chtěl u alias-only nálezů zakázat předvyplnění `cz`
plošně. Claude přijal princip, ale nahradil plošný zákaz pravidlem "doložený tvar
musí být slovem primárního povrchu" (Dresden ⊂ Harry Dresden ano, Hoss ne).
Důvod: 976 výskytů "Dresden" v deseti dílech je silný důkaz nepřeloženého jména
a u postavy render=keep znamená cz=canonical_en z definice.

Claude přidal: korpusový fingerprint se musí brát z cache manifestu, jinak by
review kvůli formuláři načítal 20 EPUBů (~30 s).

