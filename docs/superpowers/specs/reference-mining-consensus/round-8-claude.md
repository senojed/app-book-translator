# Round 8 — Claude critique

## Claude's own findings

### BLOCKING

- **Osm kol záplatování rozbilo soudržnost dokumentu.** Pět z šesti Codexových
  nálezů není nová chyba v návrhu, ale zbytek po neúplně provedené předchozí
  opravě: zrušený prefixový algoritmus zůstal na pěti místech, `compound` chybí
  ve `Finding` i v klasifikační tabulce, tok pro složené položky si protiřečí
  ve třech sekcích. Chirurgické zásahy tenhle typ dluhu spíš přidávají.
  *Fix:* konsolidační přepis celého dokumentu s jediným tokem pro každou věc,
  následovaný verifikačním seznamem. Od kola 7 verifikuji jednotlivé náhrady;
  to je nutné, ale nestačí - je třeba kontrolovat i to, že po opravě nikde
  nezůstalo staré tvrzení.

## On Codex's points

### Agreed + fixed

- **Zbytky prefixového algoritmu.** Ověřeno grepem: řádky 51, 319, 619, 644
  pořád předepisují „prefixové porovnání", které kolo 7 výslovně odložilo do
  implementačního plánu. Všechny odstraněny.
- **Klasifikační tabulka odporuje pravidlu o alias-only.** Ověřeno, řádek 264
  tvrdí, že každý `weak` má `cz` předvyplněné. *Oprava:* do `Finding` přibývá
  `primary_attested: bool` a předvyplnění se řídí jím, ne třídou. `weak`
  s doloženým primárním tvarem předvyplní, `weak` jen z aliasu ne.
- **`reference_dir` není propojený.** Přijímám a Codexův postřeh o `--dir` je
  ostrý: jednorázový override by `review` neznal a při výchozím
  `REFERENCE_DIR=""` by označil čerstvou těžbu za zastaralou. *Oprava:*
  `reference.json` nese `source_root` (skutečně použitý kořen) a `review` staví
  otisk z něj, ne z konfigurace. Tím odpadá i potřeba předávat `reference_dir`
  přes tři vrstvy - `build_app` má dál jen `reference_path`. Test „chybějící
  cache ⇒ unknown" se mění na „nedostupný `source_root` ⇒ unknown".
- **Tok pro složené položky si protiřečí.** Ověřeno: text současně mluví
  o rozdělení před těžbou, o zrušení automatického rozdělení a o zachované
  kanonizaci; `compound` navíc chybí ve `Finding.klasifikace` i v tabulce.
  *Oprava:* jediný tok (detekce → `compound` → těžba přeskočí → člověk rozdělí
  ve formuláři), třída doplněna do schématu, tabulky i testů.
- **Ruční split neřeší `must_decide`.** Ověřeno v draftu:
  `scope_key = "naagloshii/skinwalker"` a `"Shagnasty/skinwalker"` tam
  skutečně jsou, takže `apply_must_decide` by složený klíč vložil zpět.
  *Oprava:* rozdělení proběhne **před** `apply_must_decide`; otázka se přemapuje
  na zvolenou variantu nebo zahodí; validace odmítne payload, v němž zůstal
  jakýkoli klíč se `/` nebo `" or "`.
- **Alias guard zahodí ručně vytvořenou položku.** Nejlepší nález kola:
  `Billy` už alias `Billy Borden` je, takže „přidat k aliasům" je no-op a nový
  řádek nevznikne - člověkovo výslovné rozdělení by zmizelo beze stopy.
  *Oprava:* žádné tiché slučování ani tiché přepsání. Kolize povrchu
  s existujícím aliasem je **chyba validace** se srozumitelnou hláškou
  („`Billy` je už alias položky `Billy Borden` - je to táž postava, nebo jiná?")
  a člověk ji vyřeší ve formuláři.

### Agreed (IMPORTANT)

- **Přejímací kritéria matcheru nejsou měřitelná.** „Desítky nesouvisejících
  tvarů" opravdu není podmínka, kterou by šlo odškrtnout. *Oprava:* definován
  eval fixture (≥40 ručně anotovaných dvojic, z toho ≥20 skloňovacích
  a ≥20 zavádějících) a číselný práh: **100 % na množině „nesmí spárovat"
  a ≥90 % na množině „musí spárovat"**, plus povinný výpis zachycených tvarů
  pro 20 vzorových dotazů na skutečném korpusu jako checkpoint před integrací.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Codex 6 blokujících a 1 důležitý, vše přijato a ověřeno. Pět nálezů nejsou nové
chyby, ale zbytky po neúplně provedených opravách z kol 6 a 7 — zrušený
prefixový algoritmus zůstal na pěti místech, `compound` chyběl ve schématu,
tok pro složené položky si protiřečil ve třech sekcích. Spec proto konsolidován
celý místo dalších chirurgických zásahů.

Věcně nejcennější: alias guard z kola 7 by zahodil ručně vytvořenou položku
(`Billy` už alias `Billy Borden` je, takže přidání k aliasům je no-op) — nově je
kolize chybou validace, kterou řeší člověk. A `--dir` override by `review`
neznal, takže by čerstvou těžbu označil za zastaralou; `reference.json` proto
nese `source_root`.

Ověřeno v draftu, že `must_decide` opravdu obsahuje složené klíče
(`naagloshii/skinwalker`, `Shagnasty/skinwalker`).

Matcher dostal měřitelná kritéria: eval fixture ≥40 anotovaných dvojic,
100 % na negativní množině, ≥90 % na pozitivní.
