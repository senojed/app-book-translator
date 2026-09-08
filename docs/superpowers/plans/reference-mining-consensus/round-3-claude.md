# Round 3 — Claude critique

## Claude's own findings

Před čtením Codexovy kritiky jsem sám ověřil test-count komentáře napříč
plánem (nástroj, ne odhad) - konzistentně jsem je při rychlých editacích
v předchozích kolech neaktualizoval.

### NITS (vlastní, potvrzují se s Codexem)

- Ověřeno strojově (`grep -c "^def test_"` v hranicích každého tasku):
  Task 2 (13, ne 10), Task 3 (13, ne 15 - moje VLASTNÍ chybné přepočítání
  v kole 2/3, ne jen zastaralé číslo). Task 1/4/5/6/7/8 seděla přesně.
  Opraveno všude, ověřeno skriptem znovu po opravě.

## On Codex's points

Codex našel 5 BLOCKING a 3 IMPORTANT, plus 2 NITS. Souhlasím se všemi.

### Agreed + fixed

- **Task 11: `test_get_guide_includes_reference_block` má stejný
  fresh-fixture bug jako Tasky 9/14** (`source_root="/root"`, `corpus: None`)
  - přehlédl jsem ho, protože jsem v kole 1 hledal jen v Taskách 9 a 14, ne
    napříč celým plánem podle vzoru volání. *Fix:* stejný monkeypatch
    `corpus_fingerprint`, jaký mají ostatní.
- **Task 12: `classificationNote()` kontrolovala `!ref.classification`
  DŘÍV než `!ref.fresh`.** Nečerstvý blok nese jen `{fresh: false}` bez
  `classification`, takže první podmínka vždy vrátí `null` a stale větev je
  nedosažitelná. Ověřeno ručním trasováním. *Fix:* přehozeno pořadí,
  `ref.fresh === false` je první a striktní (odlišuje "žádný nález" od
  "nečerstvý nález").
- **Task 12: hromadné "zpět" přepisovalo i ruční úpravy provedené PO
  přijetí návrhů.** Spec (`648`) vyžaduje vrátit jen pole, která akce sama
  změnila. *Fix:* `acceptAllScoutSuggestions` si pamatuje i `applied`
  hodnotu, `undoAcceptAllScoutSuggestions` vrací pole jen tehdy, když je
  pořád na té aplikované hodnotě - jinak ho nechá být.
- **Task 12: ruční editace doloženého pole po odemčení zůstala navždy
  `provenance: "reference"`.** Příští `render()` (vyvolaný třeba jiným
  tlačítkem) by pole znovu zamkl s ručně upravenou hodnotou a předstíral
  důkaz, který už neplatí. *Fix:* `oninput`/`onchange` po odemčení nastaví
  `item.provenance = "human"`; `revert` ho vrátí na `"reference"`.
- **Task 12: po ruční editaci `valueField` zůstala OSTATNÍ tlačítka návrhů
  natrvalo `disabled`.** `oninput` rušil `active`, ale nikdy nevolal
  `useButtons.forEach(b => b.disabled = false)`. *Fix:* přidáno; `useButtons`
  přesunuto před `input.oninput`, aby na něj mělo referenci (odstraněna
  duplicitní pozdější deklarace `const useButtons = []`, což by byl
  `SyntaxError` - ověřeno).

### Agreed + fixed (IMPORTANT)

- **Task 3: `load_cache()` nekontroluje shodu množin klíčů `cz`/`en` ani
  minimum párů.** Platná cache s neshodnými čísly dílů nebo pod
  `REFERENCE_MIN_CORPUS_BOOKS` by obešla párování a kontrolu minima, které
  dělá `load_corpus()`. *Fix:* `set(cz_out) != set(en_out)` a
  `len(cz_out) < config.REFERENCE_MIN_CORPUS_BOOKS` → `None`. Dva nové testy.
- **Task 8: `source` se kontroluje jen jako `str`, ne proti
  `{kept, proposed, none}`.** *Fix:* nová množina `_SOURCES`, kontrola
  doplněna do `_finding_is_well_formed`. Nový test.
- **Task 12: `aliasCollisionWarnings()` používala jen `trim().toLowerCase()`,
  backend `textnorm.normalize_key` dělá NFC + casefold.** Kanonicky stejný,
  ale jinak zapsaný text by unikl varování. *Fix:* nová `normKey()` s
  `.normalize("NFC")` před `trim().toLowerCase()`.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Třetí kolo pokračovalo v očekávaném vzorci - čtyři z pěti BLOCKING byly
regrese z mých vlastních kolo-2 oprav (fresh-fixture zapomenutá v Tasku 11,
tři JS chyby v nově napsaném undo/lock mechanismu). Nejzávažnější: pořadí
podmínek v `classificationNote()` dělalo celou "nečerstvé viditelně
odlišené" funkci mrtvým kódem - psal jsem ji přímo v tomhle kole a hned
udělal logickou chybu, kterou Codex chytil ve stejném kole, ne až
v následujícím (rychlejší zpětná vazba než kolo 1→2).

Věcně nejcennější: odemčení + ruční editace doloženého pole neměnila
`provenance`, takže by se po libovolném dalším `render()` (vyvolaném úplně
jinou akcí) tvářila jako pořád doložená - tichý regres invariantu, který je
celým smyslem Tasku 12.

Test-count nity (Task 2, Task 3) opraveny strojově (skript počítající
`def test_` v hranicích každého tasku), ne odhadem - a rovnou zkontrolovány
napříč VŠEMI tasky (1-8), ne jen těmi dvěma, které Codex zmínil, protože
šlo o stejnou třídu chyby (moje průběžné ruční počítání při editaci).

Všech 32 Python bloků a 1 JS blok znovu ověřeno strojově.
