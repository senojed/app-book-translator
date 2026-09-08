# Round 6 — Claude critique

## Claude's own findings

Žádné nové vlastní nálezy. Ověřil jsem Codexovy body přímým čtením
aktuálního stavu souboru (ne z paměti předchozího kola) - u prvního bodu to
odhalilo, že jsem opravu z kola 5 naplánoval, ale NIKDY skutečně nezapsal.

## On Codex's points

3 BLOCKING, 2 IMPORTANT. Všechny přijaty po ověření.

### Agreed + fixed

- **Task 9: oprava `_reference_block` z kola 5 nebyla aplikována.** Ověřeno
  přímo v souboru - `shown_cz and shown_cz != matched_cz` tam pořád stálo,
  přesně jak Codex tvrdí. Naplánoval jsem tu opravu v kole 5 (je i v mém
  vlastním round-5-claude.md summary), ale Edit jsem nikdy neprovedl - reálná
  chyba na mojí straně procesu, ne jen zapomenutý detail v kódu. *Fix:*
  odstraněna `shown_cz and`, podmínka teď je `shown_cz != matched_cz` (i
  prázdný řetězec se od `matched_cz` liší). Rozšířen existující test
  `test_character_keep_with_blank_cz_is_still_human_decided` o kontrolu
  `"hits" not in harry["reference"]`.
- **Task 12: oprava vratnosti z kola 5 byla neúplná - po skutečné editaci
  `_czUnlocked`/`_renderUnlocked` zůstávalo `true`, ale podmínka pro
  zobrazení tlačítek vyžadovala `stillReference` (provenience ještě
  "reference"), takže po editaci tlačítko "vrátit zpět" zmizelo úplně.**
  Ověřeno trasováním: `canBeReference && stillReference` je `false`, jakmile
  `oninput` přepne provenienci na "human". *Fix:* nová `showLockControls =
  canBeReference && (stillReference || unlocked)` - `unlocked` samo o sobě
  stačí k zobrazení ovládání, nezávisle na tom, jestli editace už proběhla.
- **Task 12: důkaz nebyl živě vázán na hodnotu - zůstával viditelný do
  dalšího `render()`u, u `render` se nekontrolovala hodnota vůbec (zůstal
  viditelný i po přepnutí "keep"→"translate").** Souhlasím a řeším to
  systematicky: PŘEPRACOVAL jsem `valueField`/`renderField` tak, aby
  klikací akce (odemčení, vrátit zpět, použít/zpět u návrhu, změna roletky)
  rovnou volaly `render()` - stejný vzorec, jaký už měly "přijmout všechny"
  a `undo`. Textové psaní (`oninput`) zůstává líné (bez `render()`, aby se
  neztrácel kurzor), ale `input.onblur = () => render()` ho po dopsání
  dorovná - stejný vzorec, jaký formulář od kola 4 používá u editace aliasů.
  Vedlejší efekt: tenhle přechod na `render()`-po-akci ZÁROVEŇ řeší i
  IMPORTANT bod o návrzích u zamčeného pole (viz níž) - obojí byl symptom
  stejné příčiny (ruční, nekonzistentní DOM manipulace místo jednotného
  přepočtu).

### Agreed + fixed (IMPORTANT)

- **Task 12: tlačítka návrhů se u zamčeného pole vůbec nevytvořila, a
  odemčení nevyvolávalo render, takže po odemčení nebyl návrh dostupný, dokud
  nenastala jiná náhodná akce.** Vyřešeno stejnou opravou jako výše - všechny
  klikací akce teď volají `render()`, takže odemčení hned přepočítá i
  viditelnost/dostupnost tlačítek návrhů (`use.disabled = locked || ...`,
  přepočítáno při každém renderu).
- **Task 10: `_seed_one` guard používal `.strip().lower()`, ne
  `textnorm.normalize_key`.** Ověřeno - identita všude jinde v plánu
  (Task 4, 9) stojí na `normalize_key` (NFC + casefold), tenhle guard byl
  jediné místo, které používalo jen `.lower()`. NFC/NFD-jinak zapsaný, ale
  kanonicky stejný text by guard nesloučil. *Fix:* `textnorm.normalize_key`
  na obou stranách porovnání (kanonický i aliasový průchod), přidán import a
  regresní test s NFD aliasem / NFC příchozím jménem.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Šesté kolo - první BLOCKING byla moje vlastní procesní chyba: naplánoval
jsem opravu v kole 5, popsal jsem ji v souhrnu, ale Edit jsem neprovedl.
Zavádím si do dalších kol pravidlo: po každém kole ověřit KAŽDOU plánovanou
opravu greppem v souboru, ne jen podle paměti "tohle jsem přece udělal".

Druhý a třetí BLOCKING spolu s prvním IMPORTANT bodem měly společnou
příčinu - ruční, bodová DOM manipulace (`.hidden=`, `.readOnly=` na
konkrétních uzlech) místo jednotného přepočtu přes `render()`. Místo další
izolované záplaty jsem to řešil systematicky: všechny klikací akce
(odemčení, revert, použití návrhu, změna roletky) teď volají `render()`,
stejně jako to od kola 4 dělá "přijmout všechny"/undo a od kola 4/5 alias
blur. Psaní do textového pole zůstává líné (žádný `render()` na klávesu),
`onblur` ho dorovná. Tohle by měl být konec téhle konkrétní třídy
UI-desync chyb - je teď jen jeden vzorec (akce → render()), ne tři různé
ruční implementace téhož.

Všech 32 Python bloků a 1 JS blok znovu ověřeno strojově.
