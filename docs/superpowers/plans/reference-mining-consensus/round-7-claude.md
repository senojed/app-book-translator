# Round 7 — Claude critique

## Claude's own findings

Do promptu pro Codexe jsem tohle kolo sám vložil konkrétní podezření (blur
mažící DOM uprostřed click-sekvence u sousedního tlačítka), které jsem si
všiml při psaní kola 6, ale nechal neopravené jako "mimo rozsah". Codex ho
nezávisle potvrdil jako BLOCKING - beru to jako svůj vlastní nález, který
jsem měl řešit rovnou v kole 6, ne odkládat.

## On Codex's points

2 BLOCKING, 1 IMPORTANT, 1 NIT. Všechny přijaty po ověření.

### Agreed + fixed

- **Task 12: `input.onblur = () => render()` může smazat sousední tlačítko
  z DOM uprostřed sekvence mousedown→mouseup→click, takže klik na "použít
  návrh"/"vrátit zpět"/"přijmout všechny" po psaní může proběhnout naprázdno.**
  Standardní příčina: posun focusu z inputu na tlačítko vyvolá `blur` PŘED
  dokončením kliku na tom tlačítku; synchronní `render()` v `blur` handleru
  vymění DOM strom (včetně cílového tlačítka) dřív, než `click` stihne
  doběhnout na původním uzlu. *Fix:* `input.onblur = () => setTimeout(() =>
  render(), 0)` - odloženo o jeden tick, takže click na PŮVODNÍM tlačítku
  stihne proběhnout dřív, než se cokoli přestaví. Stejná oprava u
  `al.onblur` (pole aliasů postavy) - stejná třída rizika, Codex ji
  nezmínil explicitně, ale je to identický vzorec zavedený ve stejném kole.
- **Task 12: `renderField`'s `canBeReference` závisela na AKTUÁLNÍ hodnotě
  `item.render`, ne na stabilních metadatech reference.** Ověřeno: po
  odemčení doloženého `render="keep"` a výběru prázdné volby `""` (falsy) by
  `canBeReference` spadla na `false`, a s ní `showLockControls` - tlačítko
  "vrátit zpět" by zmizelo, přestože jde přesně o probíhající editaci, kterou
  má umožnit vrátit. `valueField` tuhle chybu nemá, protože stojí na
  `ref.matched_cz` (neměnné metadatě), ne na `item.cz`. *Fix:* `canBeReference`
  u `renderField` teď stojí jen na `ref.fresh` + `classification` (bez
  `&& item.render`) - `_merge_section` u postavy s confirmed/weak nálezem
  vždy nastaví `ref_render = "keep"`, takže tahle dvojice sama o sobě
  znamená "reference by tu měla keep", nezávisle na tom, co tam teď zrovna
  je vybráno.

### Agreed + fixed (IMPORTANT)

- **Tasky 8/13: `corpus_fingerprint()` a `load_cache()` mohou propagovat
  `OSError` z `build_manifest()` i PO úspěšném `isdir()`** (soubor mezitím
  zmizel, oprávnění, síťový disk - TOCTOU race). `corpus_fingerprint` se volá
  z `guide._is_fresh()` uvnitř `GET /api/guide` - nezachycená výjimka by
  znamenala HTTP 500 místo srozumitelného "nevím, ber jako nečerstvé".
  `load_cache()` volá `build_manifest()` znovu na konci (porovnání s
  uloženým manifestem) - stejné riziko. *Fix:* obě obalena `try/except
  OSError: return None` - "nevím" je legitimní odpověď obou kontraktů. Dva
  nové testy.

### Agreed + fixed (NIT)

- **Task 9: komentář nad opraveným `_reference_block` doporučoval PŘESNÝ
  opak toho, co dělá kód pod ním** ("`shown_cz and ...`, ne jen `shown_cz !=
  matched_cz`" - fakticky návod, jak bug vrátit zpátky). Přepsáno tak, aby
  jasně řeklo, co NEDĚLAT a proč, ne aby to znělo jako doporučení.

### Disagreed

Nic.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Sedmé kolo - poprvé jsem do promptu pro Codexe vložil vlastní, dosud
neopravené podezření (blur/click race) a nechal ho nezávisle ověřit, místo
abych ho buď potichu ignoroval, nebo opravoval bez ověření. Ukázalo se jako
reálné a BLOCKING.

Druhý BLOCKING (`renderField`'s `canBeReference` na mutable `item.render`)
je varianta STEJNÉ třídy chyby, kterou `valueField` už v kole 5 vyřešil
použitím stabilního `ref.matched_cz` - `renderField` prošel analogickou
opravou ve stejném kole, ale s jinou (méně stabilní) závislostí, protože
`render` nemá ekvivalent `matched_cz` a já jsem místo odvození "vždy keep"
z metadat nechal kontrolu viset na aktuální hodnotě pole.

IMPORTANT bod (OSError z build_manifest) je první nález v celé oponentuře
o chybové cestě na úrovni souborového systému, ne o datovém modelu nebo UI
stavu - jiná kategorie rizika, správně odchycená až v pozdějším kole, kdy
se pozornost přirozeně přesunula z UI logiky na okolní infrastrukturu.

Všech 32 Python bloků a 1 JS blok znovu ověřeno strojově, test-count
komentáře znovu skriptem přes všechny tasky.
