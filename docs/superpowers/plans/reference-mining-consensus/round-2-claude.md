# Round 2 — Claude critique

## Claude's own findings

Po vlastních opravách z kola 1 jsem znovu prošel plán, se zaměřením na místa,
kde by moje vlastní kolo-1 fixy mohly zavést novou nekonzistenci - to je
typicky přesně tam, kde druhé kolo najde nejvíc.

### BLOCKING (vlastní)

- **Task 9: `_merge_section` páruje guide.json a draft přes `guide.normalize`
  (jen strip+lower), ne přes `textnorm.normalize_key` (NFC).** Guide.json
  a draft mohou vzniknout jinou cestou (draft ze scouta, guide.json ruční
  editací v prohlížeči) a nést kanonicky stejný, ale jinak zapsaný Unicode
  text - `normalize()` by je nespároval, vznikly by duplicitní řádky a
  lidské rozhodnutí by se ztratilo. *Fix:* `g_map` i lookup přes
  `textnorm.normalize_key`; `guide.normalize`/`relationship_key` zůstávají
  vyhrazené vztahům. Přidán regresní test
  `test_guide_and_draft_keys_merge_across_nfc_nfd_difference`.

## On Codex's points

Codex našel v tomto kole 7 BLOCKING a 4 IMPORTANT - hlavně vlastní chyby
zavedené MÝMI fixy z kola 1 (typický vzorec druhého kola). Po ověření
souhlasím se všemi.

### Agreed + fixed

- **Task 2, krok 8: `cross_section` doporučení odporuje postpodmínce 5.**
  Ověřeno v specu (`~127`): „žádné homonymum napříč sekcemi" je tvrdý
  požadavek, ne pouhé upozornění - `check_draft.py` ho hlásí jako vadu a bez
  vyřešení `exit 0` nedá. Moje vlastní znění z kola 1 řeklo přesný opak
  ("ponech obě položky"). *Fix:* přepsáno na skutečné dvě možnosti - sloučit,
  nebo jednu přejmenovat (ne závorkou).
- **Task 3: `test_load_side_failure_...` používal 3 páry a
  `REFERENCE_MIN_CORPUS_BOOKS=3`** - po odpadnutí jednoho by zbyly 2, což je
  pod minimem, a `load_corpus()` by zvedl `ValueError` místo návratu, který
  test čekal. *Fix:* 4 páry, po odpadnutí zbydou 3 (přesně na minimu).
- **Task 4: `test_punctuation_without_following_space_is_not_sentence_start`
  měl obrácenou logiku.** Ověřeno ručním trasováním vlastní implementace:
  "x.Mab" NENÍ (opraveným kódem) začátek věty, což je přesně to, co krátký
  povrch (< 5 znaků) potřebuje pro způsobilost - `confirm_eligible` proto
  vychází `True`, ne `False`, jak jsem tvrdil. Přejmenoval jsem i zdůvodnění
  v komentáři testu, ne jen assert.
- **Task 7: `classify()`/`_finding()` hledaly v `ev0.per_form` podle
  syrového `item["surface"]`, ale `count_en_surface` ukládá klíče PO NFC.**
  NFD zápis povrchu by měl reálný důkaz, ale lookup by ho minul a položka by
  vyšla `weak`/`unresolved` s `primary_attested=False`. *Fix:* `unicodedata.
  normalize("NFC", ...)` na `surface` v obou funkcích, plus end-to-end test
  `test_nfd_surface_finds_its_own_nfc_normalized_evidence`.
- **Task 12: vztahová `must_decide` roletka pořád kopírovala `md.default`
  do `answer`** - přímo odporuje spec (`604`: „roletka s prázdnou volbou
  -- vyber --, návrh vedle jako text"). Byl to kus PŮVODNÍHO (nezměněného)
  kódu, který jsem v kole 1 mylně považoval za "beze změny". *Fix:* odstraněn
  auto-výběr, roletka začíná prázdná, návrh zůstává jen jako text pod ní
  (to už tam bylo).
- **Task 12: `cz` u postavy byl obyčejný `<input>` bez zámku a bez
  `lexicographer_suggestion`.** *Fix:* `valueField` rozšířeno o parametr
  `suggestionKeys` (u postavy jen `["lexicographer_suggestion"]`, protože
  `scout_suggestion` tam nese "keep"/"translate", ne text).
- **Task 12: `acceptAllScoutSuggestions` neměla vůbec žádné "zpět".** Spec
  (`648`) to vyžaduje výslovně. *Fix:* funkce teď vrací seznam skutečně
  změněných polí (`{section, i, field, before}`), nová
  `undoAcceptAllScoutSuggestions()` a tlačítko "vrátit zpět přijetí (N)",
  které se objeví jen po použití.
- **Task 12: `valueField`/`renderField` sdílely jedno `before` mezi dvěma
  návrhy a ruční úprava ho tiše přepsala.** Použití obou návrhů po sobě (nebo
  ruční editace po použití jednoho) by ztratilo původní hodnotu. *Fix:*
  aktivní návrh zamyká tlačítko toho druhého (`useButtons.forEach(...
  disabled = true)`), dokud se nevrátí zpět; ruční `oninput` zruší stav
  "aktivní návrh", aby pozdější "zpět" nepřepsalo to, co si člověk mezitím
  dopsal.
- **Task 12: `confirmed` nesbaleno, `not_attested` bez popisku "slabý
  signál", nečerstvé nijak neodlišené, chybí varování při kolizi aliasu.**
  Ověřeno proti spec tabulce (`631-635`). *Fix:* `splitConfirmed()` +
  `<details>` se sumářem a počtem; `classificationNote()` dává text u
  `not_attested` i u nečerstvého nálezu; `aliasCollisionWarnings()` - živá
  (ne DB) obdoba kontroly z `glossary._seed_one` nad obsahem formuláře.
  **Scope rozhodnutí, ne ignorování:** o skutečné DOM/browser testy jsem
  Codexe požádán, ale zavedení Playwright/Selenium infrastruktury je mimo
  rozsah tohoto plánu - ponecháno jako rozšířený ruční vizuální checklist
  (Task 12 krok 5), který teď explicitně pokrývá všech osm nových chování.
- **Task 12/spec: zamykání polí (`backed`) se řídilo shodou hodnoty
  s `matched_cz`, ne polem `provenance`.** Ruční hodnota, která náhodou
  vyjde stejně jako doložený tvar, by se tvářila jako doložená. *Fix:*
  `backed = ref.fresh && item.provenance === "reference" && ...` v obou
  funkcích; přidán server-side regresní test
  `test_human_value_coincidentally_equal_to_matched_cz_stays_human_provenance`,
  který ověřuje datový základ té opravy.
- **Task 14: tři testy nechávaly `Nevernever.cz` prázdné, `validate()`
  vyžaduje neprázdné `cz` u KAŽDÉHO termínu.** POST by vždy skončil 422, ne
  200 jak testy čekaly - `test_confirmed_flows_through_with_evidence` by
  navíc spadl na `FileNotFoundError` při čtení neexistujícího `guide.json`.
  *Fix:* všechny tři doplněny o `Nevernever.cz` před úspěšným POSTem.

### Agreed + fixed (IMPORTANT)

- **Task 6: `propose()` předpokládá, že parsovaný JSON je dict a každý řádek
  `proposals` je dict.** `extract_json` má typový slib `-> dict`, ale za
  běhu vrátí cokoli platné JSON. *Fix:* explicitní `isinstance` kontroly na
  `data`, `data["proposals"]` i každý řádek, s `ValueError`. Tři nové testy.
- **Task 8: validace schématu nekontrolovala `bool` jako zástupný typ pro
  `int`, `per_form[*].case_exact` vůbec, ani tvar `fingerprint`.**
  `isinstance(True, int)` je v Pythonu `True`. *Fix:* `_is_strict_int()`
  vylučuje bool z `hits`/`books`/`cooccurrence`/`per_form[*].hits/books`;
  `case_exact` musí být skutečný bool; nová `_fingerprint_is_well_formed()`
  kontroluje přesnou množinu klíčů a typy. Tři nové testy.

### Disagreed

Nic - všechny Codexovy nálezy po ověření přijaty. U DOM testů (Task 12)
jsem místo slepého souhlasu udělal vědomé škálovací rozhodnutí (viz výše) -
uvádím ho jako "agreed but scoped down", ne jako tiché ignorování.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Druhé kolo potvrdilo očekávaný vzorec: většina nálezů byly chyby zavedené
mými vlastními opravami z kola 1, ne nové věci. Nejzávažnější: Task 12 pořád
nesplňoval polovinu spec tabulky (sbalení `confirmed`, popisek `not_attested`,
odlišení nečerstvého, varování kolize) a vztahová roletka stále kopírovala
scoutův návrh navzdory vlastnímu kolu-1 tvrzení, že "zbytek souboru beze
změny" - ukázalo se to jako mylný předpoklad, ne fakt. Task 14 měl třikrát
stejnou chybu (neúplně vyplněný povinný `cz`), která by první úspěšný test
shodila na `FileNotFoundError`.

Dvě věcně nejcennější opravy: NFC/NFD nesoulad mezi `count_en_surface`
(ukládá klíče po NFC) a `classify()`/`_finding()`/`_merge_section` (hledaly
podle syrového textu) - stejná třída chyby na třech místech, což naznačuje,
že to chtělo jeden systematický průchod, ne tři izolované záplaty. A zamykání
polí v UI podle shody hodnoty místo podle `provenance` - drobný, ale přesně
ten typ chyby, který by tichým způsobem podkopal celý invariant "nedoloženo
se netváří jako doložené".

Všech 32 Python bloků a 1 JS blok znovu ověřeno strojově (parse/compile).
