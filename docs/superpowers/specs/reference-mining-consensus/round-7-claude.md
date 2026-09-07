# Round 7 — Claude critique

## Claude's own findings

### BLOCKING

- **Dvě opravy z kola 6 se do specu nezapsaly a já to nezkontroloval.**
  `corpus_fresh` (výpočet z disku) a zrušení alias-only předvyplnění zůstaly
  v dokumentu ve staré podobě, protože textová náhrada neseděla na vzor
  změněný v kole 5 a proběhla naprázdno. V shrnutí kola 6 jsem přitom uživateli
  hlásil, že jsou opravené. *Fix:* opravy provést znovu a **každou ověřit
  grepem**; od tohoto kola se každá změna specu kontroluje, ne předpokládá.

- **Třetí neúspěšný pokus specifikovat matcher.** Kolo 5 zavedlo prefix
  `max(4, len-2)` (nezvládl `bílá`/`bílé`), kolo 6 `max(3, len-2)` (změřeno:
  `práh` matchuje 54 tvarů včetně `práce`, `právo`, `prázdný`), a moje dnešní
  varianta s uzavřenou množinou koncovek propadá na `plášť`/`pláště`, protože
  předpoklad „prefix = kmen" u některých slov neplatí. *Fix:* přestat hádat
  algoritmus v designu. Spec nově předepisuje **přejímací kritéria** (konkrétní
  dvojice, které sedět musí a nesmí) a povinnost změřit falešné shody na
  skutečném korpusu; volba algoritmu patří do implementačního plánu.

## On Codex's points

### Agreed + fixed

- **`corpus_fresh` a alias-only rozpor** - viz můj blokující bod výš, jde
  o tytéž nálezy. Ověřeno grepem, že v dokumentu opravdu zůstaly staré verze
  (řádek 447 „porovnává proti manifestu v cache", řádky 586-587 staré pravidlo
  o slově primárního povrchu).
- **Prefixový matcher má falešné shody** - potvrzeno měřením na třech dílech
  referenčního korpusu (270 000 slov): `práh` → 54 tvarů, `rada` → 25 tvarů
  včetně `radost` a `raději`. Řešeno přechodem na přejímací kritéria.
- **`canonical_items` neřeší související data.** Přijímám celé a beru z toho
  důsledek, který Codex nenavrhl, ale plyne z rozsahu problému: automatické
  rozdělování by muselo migrovat `suggested_cz`, aliasy, `must_decide.scope_key`
  i existující `guide.json`, a `apply_must_decide` by původní složený klíč
  vkládal zpět. To je hodně strojvedení kvůli 11 položkám. *Oprava:*
  **automatické rozdělování se ruší.** Složené položky se detekují, dostanou
  třídu `compound`, těžba je přeskočí a **formulář je dá člověku rozdělit
  ručně** ve vlastní sekci. Nic automatického na `guide.json` ani glosář nesahá.
- **Kolize s `glossary._seed_one` přes aliasy.** Ověřeno v draftu: `Billy Borden`
  má aliasy `['Billy', 'Will', 'Will Borden']` a zároveň existuje složená
  položka `Will/Billy`. `_seed_one` páruje přes aliasy a pak přepíše
  `canonical_en`, `cz` i `type`. Ruční rozdělení riziko zmenšuje, ale
  nevylučuje - je to **latentní chyba ve stávajícím kódu**, ne jen v tomhle
  návrhu. *Oprava:* guard v `seed_from_guide` (řádek nalezený jen přes alias se
  nesmí přepsat, když se liší `canonical_en`) + end-to-end test kolize.
- **Freshness nesmí potlačit lidský `guide`.** Přijímám, formulace odporovala
  prioritě `guide > reference > draft`. *Oprava:* výslovně řečeno, že čerstvost
  omezuje **jen hodnoty a důkazy pocházející z `reference`**; uložená lidská
  rozhodnutí platí vždy.
- **`merge_sources` nedostává podklad pro korpusový otisk.** *Oprava:* doplněna
  signatura s `reference_dir`, ze kterého se otisk levně sestaví.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex 4 blokující a 2 důležité. Dva z nich odhalily procesní chybu na straně
Claudea: opravy z kola 6 (corpus_fresh, alias-only) se do specu nezapsaly,
protože textová náhrada neseděla na vzor, a nebylo to ověřeno - v shrnutí kola 6
byly přesto hlášeny jako hotové. Od tohoto kola se každá změna specu ověřuje.

Matcher se specifikuje potřetí neúspěšně; měřením na 270 000 slovech potvrzeno,
že prefix-3 dává `práh` → 54 tvarů. Spec proto přechází z algoritmu na přejímací
kritéria plus povinné měření v implementaci.

Automatické rozdělování složených položek se ruší - migrace suggested_cz, aliasů,
must_decide a guide.json plus kolize s glossary._seed_one přes aliasy
(ověřeno: Billy Borden má alias Billy i Will) je nepřiměřená složitost kvůli
11 položkám. Nově je rozdělí člověk ve formuláři. Doplněn guard proti přepsání
glosářového řádku nalezeného jen přes alias - latentní chyba stávajícího kódu.
