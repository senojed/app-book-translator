# Round 11 — Claude critique

## Claude's own findings

Žádné nové vlastní nálezy. Kolo bez BLOCKING (třetí za sebou), jen 1
IMPORTANT a 1 NIT - oba se týkají oblastí, kterých jsem se dosud dotkl jen
okrajově (Task 2 ruční instrukce, Task 9 guide-only větev).

## On Codex's points

0 BLOCKING, 1 IMPORTANT, 1 NIT. Oba přijaty po ověření.

### Agreed + fixed

- **Task 2 krok 8: ruční instrukce vynechávaly tři pravidla, která spec už
  ustálil.** Ověřeno proti specu: (1) `suggested_cz` u výčtu se má rozdělit
  TÝMŽ oddělovačem a spárovat pozičně, nesedí-li počty, zůstat prázdné -
  dosavadní text řekl jen "varianty dej do aliases", o `suggested_cz` mlčel.
  (2) `bad_scope_key` má TŘI platná řešení (přemapovat / povýšit na
  samostatnou položku / smazat otázku) - dosavadní text zmiňoval jen
  přemapování. (3) pravidlo "alias, který potřebuje vlastní překlad, není
  alias" (`Injun Joe` u `Listens-to-Wind`) v instrukcích úplně chybělo -
  a navíc jsem ověřil, že `check_draft.py` tenhle případ vůbec NEDETEKUJE
  (`weak_alias` chytá jen role/oslovení a krátké tvary, ne alias s vlastní
  otázkou na překlad) - je to čistě lidská kontrola, kterou automat neudělá,
  takže musí být v instrukcích explicitně, ne spoléhat na to, že ji nástroj
  nějak označí. *Fix:* všechny tři doplněny do Step 8.

### Agreed + fixed (NIT)

- **Task 9: guide-only větev `_merge_section` (položka je v `guide.json`,
  ale ne v aktuálním draftu) počítala provenience jen z `g.get("cz")`.**
  Postava s `render="keep"` a prázdným `cz` (platný, uložený stav) by
  dostala `provenance="none"`, ačkoli řádek existuje v `guide.json` a je
  tedy lidské rozhodnutí - přesně ta samá třída chyby, kterou kolo 4 opravilo
  u DRAFTEM spárovaných položek (`human_decided = bool(g)`), jen na druhé
  větvi téže funkce. *Fix:* guide-only řádky teď mají `provenance="human"`
  bezpodmínečně (existence řádku v `guide_map` sama o sobě je důkaz, že ho
  člověk uložil - `validate()` by jinak POST odmítla). Nový test
  `test_guide_only_character_keep_with_blank_cz_is_still_human`.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Jedenácté kolo - třetí za sebou bez BLOCKING, oba nálezy jsou menší a
lokalizované (jedna chybějící větev stejné opravy z kola 4, tři chybějící
detaily v ruční instrukci). Vzorec posledních tří kol (9, 10, 11) ukazuje
plán skutečně konvergující - žádné nové regrese ze zásahů v předchozím kole,
jen dozbývající, čím dál drobnější mezery.

Všech 33 Python bloků a 1 JS blok znovu ověřeno strojově.
