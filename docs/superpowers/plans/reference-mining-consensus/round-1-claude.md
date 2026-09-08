# Round 1 — Claude critique

## Claude's own findings

Nezávisle jsem prošel celý plán (3123 řádků) a ověřil ho proti skutečnému
kódu (`src/ingest.py`, `src/review_ui/server.py`, `src/review_ui/static/index.html`,
`src/guide.py`, `src/glossary.py`, `tests/test_review_ui.py`) a proti specu.
Nálezy se z velké části kryjí s Codexem - u každého uvádím, kde jsem to
ověřil vlastním trasováním kódu, ne jen přečtením.

### BLOCKING (vlastní, potvrzují se s Codexem)

- **Task 3: `test_documents_joined_with_separator_and_without_titles` padá
  proti skutečnému `ingest._load_epub`** - ověřeno čtením `src/ingest.py:66`:
  `soup.get_text(separator="\n")` nerozlišuje nadpis od těla, takže
  `Chapter.raw_text` obsahuje i text `<h1>`. *Fix:* nová `_strip_leading_title`
  v `_load_side`, odstraňuje `chapter.title`, pokud text raw_text jím začíná
  (syntetický titul "Kapitola N" se v textu nevyskytuje, takže se nic
  neodstraní tam, kde nadpis chybí).
- **Tasky 3-5: chybí NFC normalizace** - spec (`351`) výslovně říká "Hledá se
  v surovém textu po NFC", plán normalizoval jen `textnorm.normalize_key`
  (identitu), ne text ke hledání. *Fix:* `unicodedata.normalize("NFC", ...)`
  na text při `_load_side` a na `surface`/`aliases`/`form` ve všech třech
  hledacích funkcích, plus regresní test NFD dotaz → NFC korpus.
- **Task 4: `_at_sentence_start` nevyžaduje mezeru za interpunkcí** - spec
  (`202`) říká "první nebílý znak po `.`/`!`/`?`/`…` **s bílým znakem**".
  Ověřeno ručním trasováním: `"x.Mab"` (překlep bez mezery) by prošlo jako
  začátek věty. *Fix:* sleduje se, zda smyčka přeskočila alespoň jeden bílý
  znak, `\x00` (oddělovač dokumentů) je výjimka.
- **Task 4: `test_document_separator_counts_as_sentence_start` je chybný** -
  ověřeno ručním trasováním obou výskytů "Bob": oba jsou po interpunkci/
  odděl. dokumentů, tedy OBA na začátku věty → `confirm_eligible` musí být
  `False`, test ale čekal `True`. *Fix:* rozdělen na dva testy - čistě po
  DOC_SEP (False) a DOC_SEP + druhý výskyt uprostřed věty (True).
- **Task 7: prahy `confirmed`/`weak` počítané z `ev0.hits`/`ev0.books`, což
  je sjednocení primárního tvaru A ALIASŮ** - spec (`208-211`) říká výhradně
  primární tvar. Postavil jsem konkrétní repro: primární tvar 1 výskyt v 1
  dílu (pod prahem), alias `Dresden` má 6 výskytů ve 2 dílech - staré API by
  vrátilo `confirmed`, ačkoli primární tvar sám o sobě doložen není. *Fix:*
  `classify()` dostává `surface` navíc a čte `ev0.per_form[surface]`.
- **Task 8: `load_reference` nevaliduje TYPY polí, jen jejich přítomnost** -
  poškozený `hits` jako string by prošel a spadl by až na frontendu. *Fix:*
  `_FIELD_TYPES` mapa + rekurzivní kontrola `per_form`/`books`/`cooccurrence`.
- **Task 9: `_fresh_fp` v testech vždy dá `fresh=False`** - ověřeno
  trasováním `_is_fresh`: `corpus_fingerprint("/root")` volá
  `build_manifest` na neexistující cestu → `None`, a `_is_fresh` vrací
  `current_corpus is not None and ...` → vždy `False`. Všechny testy
  očekávající předvyplnění by padly. *Fix:* `_fresh_fp` monkeypatchuje
  `reference_mine.corpus_fingerprint` na pevnou hodnotu; totéž v Tasku 14
  `_setup`.
- **Task 9: nečerstvá reference dál ukazuje `classification` a
  `lexicographer_suggestion`** - spec (`524`) výslovně: "s výjimkou nečerstvé
  reference, kde se nezobrazuje nic než poznámka". *Fix:* `_reference_block`
  vrací při `not fresh` jen `{"fresh": False}`; `lex_suggestion` v
  `_merge_section` gatováno `fresh`.
- **Task 11: existující test `test_must_decide_relationship_routes_and_
  rejects_invalid_answer` touhle změnou spadne** - ověřeno čtením
  `tests/test_review_ui.py:86-95`: odpověď na vztahovou otázku vloží řádek do
  `relationships` přes `apply_must_decide`, a nová kontrola
  `_check_relationships_reviewed` běží PO ní - bez `relationships_reviewed`
  v `_post`u by první assert (`200`) dostal `422`. *Fix:* sdílený `_post`
  helper posílá `relationships_reviewed: True` ve výchozím payloadu.
- **Task 12: JS funkce `valueField`/`acceptAllScoutSuggestions` nikdy
  nejsou zapojené do `render()`** - ověřeno přečtením celého skutečného
  `index.html` (182 řádků): stávající vykreslování postav/míst/termínů je
  přímo v `render()`, plán definoval nové funkce vedle, ale nikdy je tam
  nevolal. Navíc `acceptAllScoutSuggestions` zapisovala u postav do `cz`
  místo do `render`, a "zpět" u návrhu vždy nastavovalo `""` místo hodnoty
  před použitím návrhu. *Fix:* přepsán celý `<script>` - nová `renderField`
  pro postavy (pracuje s `render`, ne `cz`), `valueField` opraveno na
  uzávěr `before`, `render()` obě funkce skutečně volá, přidán checkbox
  `relationships_reviewed` a tlačítko "přijmout všechny scoutovy návrhy".
- **Tasky 12 a 14: testy čekají 200 s prázdným `cz` u termínu** - ověřeno
  čtením `src/review_ui/server.py:70-90` (`validate()`, beze změny touto
  specifikací): prázdné `cz` u termínu/místa vrací chybu vždy, bez ohledu na
  původ. Plán tuhle validaci nemění, testy jí ale odporovaly. *Fix:*
  přepsány na správné chování - prázdné `cz` blokuje uložení úplně (422,
  `guide.json` nevznikne); teprve vlastní rozhodnutí člověka (jiné než návrh
  modelu) projde a do glosáře se dostane JEHO hodnota.

### IMPORTANT (vlastní)

- **Task 10: `_seed_one` skončí na první aliasové shodě, i když pozdější
  řádek odpovídá kanonicky** - ověřeno: SELECT bez `ORDER BY` vrací řádky v
  pořadí vložení; je-li aliasový řádek starší než kanonický, jednoprůchodový
  kód s `break` na první shodě nahlásí konflikt místo použití správného
  kanonického řádku. *Fix:* dva průchody - nejdřív všechny kanonické shody,
  teprve pak aliasové.
- **Chybí `SurfaceItem`/`Finding` jako skutečné `TypedDict`** - Interfaces
  bloky je slibovaly, kód je nedefinoval. *Fix:* přidány do `reference_mine.py`.

## On Codex's points

### Agreed + fixed

Všech 13 BLOCKING bodů z Codexovy kritiky přijato a opraveno - u každého jsem
navíc sám ověřil chybu v kódu/testu dřív, než jsem sáhl na opravu (viz výše,
kde se kryje s mým vlastním nálezem). Konkrétně navíc oproti mým nálezům:

- **Task 2: `find_issues` nekontroluje duplicitní kanonický klíč ani
  duplicitní vztah, `scope_key` u vztahu nekontroluje přesný tvar
  `guide.relationship_key(a, b)`.** Přidány `duplicate_key`,
  `duplicate_relationship` kategorie a kontrola `scope == guide.
  relationship_key(a, b)`. Plus čtyři nové testy.
- **Task 2: chybí skutečná normalizace `data/guide.draft.json`.** Přidány
  kroky 7-10: záloha, ruční oprava kategorie po kategorii (s návodem, co
  dělat s každou), ověření `check_draft.py` exit 0, commit.
- **Task 3: `load_cache` nevaliduje strukturu, poškozený JSON dá
  KeyError/ValueError místo `None`.** Přidána typová validace + 2 testy.
- **Task 3: chybí test selhání jedné strany dvojice.** Přidán
  `test_load_side_failure_drops_whole_book_before_minimum_check`.
- **Task 4: "velké písmeno" = "není malé" pustí i číslici/interpunkci.**
  Opraveno na `surface[:1].isupper()`, přidán regresní test.
- **Task 9: priorita lidských dat špatně** - `g.get("aliases") or d.get(...)`
  znemožní smazat všechny aliasy (prázdný seznam je falsy), `note` se bere
  vždy z draftu, i když ho člověk upravil v guide.json. *Fix:* kontrola
  přítomnosti klíče (`"aliases" in g`), ne pravdivostní hodnoty. Dva nové
  testy (`test_human_can_remove_all_aliases`,
  `test_human_edited_note_survives_next_merge`).
- **Task 13: chyby `load_draft`/`save_cache`/`write_reference` mimo obecný
  převod na `FatalRunError`.** `load_draft` zabaleno zvlášť; `resolve()` a
  `write_reference()` sloučeny do JEDNOHO try/except, takže selhání zápisu
  dostane stejnou atomickou zprávu jako selhání těžby; `save_cache` selhání
  je nefatální (cache je jen zrychlení).
- **Task 14: chybí explicitní pokrytí `evidence_only`/`not_attested`.**
  Přidány dva testy.
- **NITS:** cenový test kontroluje i `PRICE_OUT_PER_MTOK` (ověřeno, klíč v
  `config.py` existuje); `weak_alias` stripuje před kontrolou velikosti
  písmene; atomický zápis `reference.json` používá `tempfile.mkstemp` místo
  pevného `path + ".tmp"`, s úklidem při chybě.

### Agreed but already addressed

Žádné - první kolo, nic nebylo řešeno dřív.

### Disagreed

Nic. Všechny Codexovy nálezy jsem po ověření přijal.

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

První kolo, oba kritici nezávisle. Codex: 13 BLOCKING, 6 IMPORTANT, 3 NITS.
Claude vlastní analýza (kód `src/ingest.py`, `src/review_ui/server.py`,
`src/review_ui/static/index.html`, `src/guide.py`, `src/glossary.py`,
`tests/test_review_ui.py` přečteny celé, ne jen greppnuté) našla stejných 11
BLOCKING nezávisle plus 2 vlastní IMPORTANT. Shoda je vysoká - důvod: spec po
23 kolech je pevný, chyby jsou v převodu specu do konkrétního kódu/testů, ne
v architektuře.

Opraveno v plánu: title-stripping v korpusu, NFC normalizace hledání,
`_at_sentence_start` vyžaduje mezeru po interpunkci, `confirmed`/`weak` prahy
jen z primárního tvaru (ne union s aliasy), plná typová validace
`reference.json`, oprava fresh-fixture v testech (Task 9 i 14), skutečné
potlačení nečerstvé reference (ne jen čísel, ale i klasifikace/návrhu),
oprava existujícího testu rozbitého novým `relationships_reviewed`, celý JS
formulář v Tasku 12 přepsán tak, aby nové funkce byly opravdu zapojené do
`render()`, kontrakt validace prázdného `cz` sjednocen se skutečným
(neměněným) `server.validate()`, dvouprůchodové hledání v glosáři (kanonická
shoda má vždy přednost před aliasovou bez ohledu na pořadí řádků), přidány
`TypedDict` definice. Všech 32 Python bloků a 1 JS blok v plánu ověřeno
syntakticky (parsováno/zkompilováno strojově, ne jen přečteno).

Nejzávažnější nález (můj i Codexův nezávisle): Task 12 definoval JS funkce
`valueField`/`acceptAllScoutSuggestions`, ale plán je nikdy nezapojil do
skutečného vykreslování - bez opravy by celý smysl Tasku 12 (nic
nedoloženého se nepředvyplní, každá akce je vratná) zůstal jen v nepoužitém
kódu vedle starého. Druhý nejzávažnější: fresh-fixture bug v Tasku 9 a 14 by
způsobil, že VŠECHNY testy očekávající předvyplnění z reference by padaly -
"fresh" bylo tiše vždy `False`.
