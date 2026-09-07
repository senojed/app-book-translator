# Round 12 — Claude critique (zkouška proveditelnosti)

Formát: Codex měl ze specu napsat první tři úkoly implementačního plánu a vést
si seznam všeho, co musel dohadovat. Mezery v zadání se pozná při psaní kódu,
ne při kritice.

Výsledek: 10 dohadů (2 zásadní), 2 rozpory se stávajícím kódem.

## Nejzávažnější nález celé oponentury

**Můj invariant byl jedenáct kol v rozporu s tím, co nástroj už dnes dělá.**
Ověřeno v kódu:

```python
guide.py:92    "render": g.get("render") or d.get("suggested") or "keep"
guide.py:111   "cz":     g.get("cz") or d.get("suggested_cz") or ""
```

Formulář **už teď předvyplňuje scoutovy odhady** - model něco navrhne, formulář
to nabídne, uložením to jde do glosáře jako závazné. Přesně to, o čem jsem
psal, že tomu invariant „žádná nedoložená hodnota se nepředvyplní" brání.
Invariant jsem ale formuloval jen pro těžbu, takže rozpor zůstal skrytý -
ani deset kol oponentury ho nenašlo, protože všichni posuzovali těžbu
izolovaně, ne proti chování formuláře.

*Oprava:* invariant přeformulován na **„odhad se nikdy nesmí tvářit jako
důkaz"** - každá předvyplněná hodnota nese viditelnou provenienci. Návrh
lexikografa se nepředvyplňuje právě proto, že by v témže poli byl
nerozeznatelný od hodnoty podložené referencemi; scoutův návrh předvyplněný
zůstává, ale označený jako odhad.

Jestli má zmizet i předvyplňování scoutových návrhů, **spec nerozhoduje** -
je to volba mezi bezpečností a ~59 ručně vypsanými termíny a patří člověku.
Zaneseno jako otevřená otázka.

## On Codex's points

### Agreed + fixed (zásadní dohady)

- **Vstup `resolve()`** - „seznam povrchů" nestačí, nález i lexikograf potřebují
  `id`, sekci, aliasy a poznámku. Doplněn typ `SurfaceItem` a řečeno, že jeho
  sestavení z draftu je věc `_cmd_reference`, ne `resolve`.
- **Rozhraní normalizačního kroku** - spec říkal „rozhoduje člověk, skript nic
  nemění" a zároveň „výsledkem je nový draft se zálohou", což je rozpor.
  Určeno: skript je **report-only**, člověk upraví draft ručně, záloha
  `data/guide.draft.pre-reference.json`. Interaktivní nástroj ani soubor
  s deklarativními rozhodnutími se nestaví - je to jednorázová operace na 26
  řádcích.

### Agreed + fixed (ostatní dohady)

- **Spojování dokumentů** - určeno `Chapter.raw_text` bez `Chapter.title`
  (tituly bývají jen „Chapter 1" a zkreslily by počty výskytů), oddělovač
  `"\n\x00\n"`.
- **Nečíslované EPUBy** - přeskočit s varováním; chybou je jen duplicitní
  rozpoznané číslo.
- **Zúžení bílých znaků** - upřesněno: NFC → `casefold` → sekvence bílých znaků
  na jednu ASCII mezeru → `strip`.
- **Čas v manifestu** - `st_mtime_ns`, ne desetinné `st_mtime`.
- **Formát reportu a název zálohy** - určeny.

### Agreed + fixed (rozpory s kódem)

- **`extract_json` prý neumí seznam** - moje tvrzení, ověřeno jako nepravdivé:
  `json.loads` vrátí i top-level seznam. Objektová obálka zůstává, ale
  ze správného důvodu: regexový fallback při ukecaném modelu hledá `\{.*\}`,
  takže seznam by se z textu s okolním povídáním nevytáhl.
- **Předvyplňování ze scout draftu** - viz nejzávažnější nález výše.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Zkouška proveditelnosti našla to, co deset kol kritiky minulo: invariant specu
byl v rozporu s chováním, které nástroj má už dnes — guide.py:92 a :111
předvyplňují scoutovy modelové odhady do formuláře a odtud do glosáře.
Invariant přeformulován na "odhad se nikdy nesmí tvářit jako důkaz"; otázka,
jestli zrušit i předvyplňování scoutových návrhů, předána člověku.

Dále doplněn chybějící typ vstupu do resolve(), určeno rozhraní normalizačního
kroku (report-only), kontrakt spojování dokumentů a několik drobností. Opraveno
nepravdivé tvrzení o extract_json.
