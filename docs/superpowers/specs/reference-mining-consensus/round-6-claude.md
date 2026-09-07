# Round 6 — Claude critique

## Claude's own findings

### IMPORTANT

- **Rozdělení složených položek musí vidět i formulář, nejen těžba.** Rozdělím-li
  `White Court / Red Court / Vampire Courts` na tři položky jen uvnitř těžby,
  UI dál ukáže jeden řádek z draftu a tři nálezy nebude mít kam pověsit. *Fix:*
  kanonizace se vytáhne do sdílené `guide.canonical_items(draft)`, kterou volá
  těžba **i** `merge_sources`. Formulář pak zobrazí tři řádky, každý s vlastním
  polem. Draft na disku zůstává beze změny.

## On Codex's points

### Agreed + fixed

- **Kanonizace byla datově chybná.** Přijímám celé. `White Court / Red Court /
  Vampire Courts` nejsou aliasy jedné entity - jsou to tři různé dvory a každý
  potřebuje vlastní překlad. Totéž `Flickum bicus / Forzare / Aparturum` (tři
  různá zaklínadla). Slévat je do jedné položky s jedním `cz` je věcná chyba,
  ne jen kosmetika. Navíc jsem chtěl současně sloučit obrácené duplicity a
  zachovat oba původní řetězce jako klíče, což nejde.

  *Oprava, jednodušší než původní návrh:* **každý výčet se rozdělí na samostatné
  položky**, žádné slučování podle interpunkce. Synonyma (`skinwalker /
  naagloshii`) tím dostanou dva řádky - a to je správně, ne redundantně: jsou to
  dva různé anglické povrchy, které se v textu vyskytují a oba potřebují záznam,
  aby je concordance uměla najít. Obrácené duplicity se rozpadnou na tytéž
  položky a splynou přirozeně přes `id`.

- **Alias-only předvyplnění - beru zpět svou námitku z kola 5.** Codexův
  protiargument je silnější: výskyt `Dresden` nedokládá tvar `Harry Dresden`,
  protože překlad může příjmení ponechat a křestní jméno počeštit. A rozhodující
  je pro mě praktická stránka: `weak` položka je ve formuláři rozbalená i
  s důkazem („976× v 10 dílech"), takže ji člověk doplní za dvě vteřiny. Cena za
  nepředvyplnění je nulová, cena za špatné předvyplnění je chybný termín
  protažený celou knihou. *Oprava:* alias-only nález nepředvyplní `cz` ani
  `render`; slouží jen jako zobrazený důkaz. Pravidlo o „slově primárního
  povrchu" se ze specu odstraňuje.

- **Prefixový matcher neuměl skloňovat.** Ověřeno spuštěním - pravidlo
  `max(4, len-2)` nespáruje ani `bílá`/`bílé`, ani `rada`/`radě`, takže
  deklarovaná podpora skloňování byla prázdné tvrzení. *Oprava:*
  `max(3, len(slovo) - 2)`, slova kratší než 3 znaky přesně. Ověřeno, že
  `bílá`↔`bílé`, `rada`↔`radě`, `plášť`↔`pláště`, `rada`↔`radami` sedí,
  a `bílá`/`bída` ani `rada`/`rana` **ne**. Oba směry mají povinný test.

- **`corpus_fresh` porovnával dva historické údaje.** Přijímám: otisk uložený
  v `reference.json` proti manifestu uloženému v téže cache neodhalí, že se
  EPUBy mezitím změnily. *Oprava:* při `review` se manifest sestaví **znovu
  z disku** (`os.stat` - cesty, velikosti, mtime), EPUBy se neparsují. Zůstává
  levné a měří to skutečný stav.

- **NITS** - počet povrchů opraven (54+59+19 = 132, dřívější 121 bylo po
  vyloučení složených položek); příklad schématu nese všechny tři příznaky
  čerstvosti místo jednoho `fresh`.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex 2 blokující a 2 důležité, vše přijato — včetně vrácení sporu z kola 5.
Kanonizace složených položek byla datově chybná: `White Court / Red Court /
Vampire Courts` jsou tři různé entity, ne aliasy, takže se výčty nově rozdělují
na samostatné položky bez slučování. Alias-only nález nepředvyplní nic (Claude
svou námitku z kola 5 stáhl - `Dresden` nedokládá `Harry Dresden` a nic se
nezíská, protože `weak` je ve formuláři stejně rozbalený). Prefixový matcher
z kola 5 nefungoval na skloňování, ověřeno spuštěním; opraven na
`max(3, len-2)`. `corpus_fresh` se nově počítá z disku, ne z cache.
Claude přidal: rozdělení výčtů musí vidět i formulář, proto sdílená
`guide.canonical_items()` volaná těžbou i `merge_sources`.
