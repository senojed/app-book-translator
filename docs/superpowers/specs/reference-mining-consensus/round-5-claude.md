# Round 5 — Claude critique

## Claude's own findings

### IMPORTANT

- **Fingerprint korpusu nelze při `review` levně spočítat.** Codexův požadavek
  ověřovat všechny tři fingerprinty je správný, ale naivní provedení by při
  každém otevření formuláře načítalo 20 EPUBů (~30 s). *Fix:* korpusový
  fingerprint se porovnává proti manifestu v `REFERENCE_CACHE_PATH`, což je
  levné čtení JSONu. Chybí-li cache, stav je `unknown` (ne „čerstvé").

## On Codex's points

### Agreed + fixed

- **Složené položky v draftu.** Přijímám a mrzí mě to nejvíc z celé oponentury:
  věděl jsem o nich, protože jsem je ve své vlastní úvodní analýze přeskočil
  (`if "/" in s: continue`), a proto mluvil o 121 povrchách místo 132. Do specu
  jsem to nezanesl. Ověřeno, že jich je **11**, například
  `White Court / Red Court / Vampire Courts`, `veil/veiling spell`, `Will/Billy`.
  Bez ošetření by všechny skončily jako `not_attested`, ačkoli `skinwalker` má
  v referencích 58 výskytů. Navíc jsou mezi nimi duplicity v opačném pořadí
  (`skinwalker / naagloshii` i `naagloshii/skinwalker`).
  *Oprava:* kanonizační krok před těžbou - položka se rozdělí na varianty,
  hledá se přes všechny, původní řetězec zůstává jako klíč zpět do draftu.
  Zároveň se opravuje prompt scouta, aby příště jedna položka = jeden povrch.
- **`coverage` neuchová `failed` ani chybějící odpovědi.** Přijímám: po skončení
  příkazu by nešlo odlišit „model řekl neznám" od „dávka spadla". *Oprava:*
  `coverage` nese `attempted`, `failed`, `missing_response`, `skipped_by_limit`.
- **Rozpor v testech.** Ověřeno, řádky 510 a 512 si protiřečí
  („chybějící → `unresolved`" vs. „chybějící `id` → `stale`"). *Oprava:*
  sjednoceno na `stale`, doplněno chování bez předchůdce.
- **`fresh` se kontroluje jen proti draftu.** Přijímám; změněný EPUB nebo
  posunuté prahy by se tvářily jako čerstvý důkaz. *Oprava:* tři samostatné
  příznaky (`draft_fresh`, `corpus_fresh`, `thresholds_fresh`), předvyplnění
  jen když sedí všechny - s levným zdrojem korpusového otisku (viz můj bod výš).

### Disagreed (částečně)

- **„Alias-only nález nesmí předvyplnit `cz` vůbec."** Princip beru - nález
  `Hoss` opravdu neprokazuje, že se `Harry Dresden` píše anglicky. Ale plošný
  zákaz zahodí i případy, kde je inference bezpečná: `Dresden` 976× v deseti
  dílech je velmi silný důkaz, že jméno **nebylo přeloženo**, a u postavy
  `render=keep` znamená `cz = canonical_en` z definice, ne tvrzení o výskytu
  celého řetězce.

  *Rozlišení, které do specu dávám:* předvyplní se jen tehdy, je-li doložený
  tvar **slovem (nebo souvislou posloupností slov) primárního povrchu** -
  `Dresden` ⊂ `Harry Dresden` ano, `Hoss` ne. Nesouvisející alias `cz`
  nepředvyplní. Pokrývá to reálné případy z tohohle draftu a nevzdává se
  vazby hodnoty na důkaz.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex našel 2 blokující a 2 důležité. Nejzávažnější je 11 složených položek
v draftu (`White Court / Red Court / Vampire Courts`), o kterých Claude věděl
z vlastní analýzy, ale nezanesl je do specu - bez kanonizace by všechny skončily
jako nedoložené. Doplněn kanonizační krok a oprava promptu scouta. Dále:
`coverage` nerozlišil selhání od „neznám", testy si protiřečily, a `fresh` se
kontroloval jen proti draftu. U alias-only nálezů Claude Codexův plošný zákaz
předvyplnění **částečně odmítl** a nahradil ho pravidlem „doložený tvar musí být
slovem primárního povrchu". Claude přidal: korpusový fingerprint se musí brát
z cache, jinak by `review` načítal 20 EPUBů.
