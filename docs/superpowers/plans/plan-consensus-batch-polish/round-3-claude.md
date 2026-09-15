# Round 3 — Claude critique

## Claude's own findings

Při opravování Codexových bodů jsem si všiml, že jsem SÁM do vlastních
komentářů dvakrát vepsal poškozený, opakující se text (zjevně vlastní
chyba při psaní, ne obsahová) - opraveno hned při psaní, zmiňuji jen pro
úplnost logu, nejde o Codexův nález.

### NITS
- Vlastní komentáře v `_commit_polish_result`/Task 9 obsahovaly
  nesmyslně opakovaný fragment textu na dvou místech - opraveno na
  srozumitelné vysvětlení.

## On Codex's points

### Agreed + fixed
- **BLOCKING - `btn-save`'s `finally { await loadChapter() }` maže
  rozepsanou práci i po chybě:** ověřeno - `finally` běží VŽDY, i po
  `return` v chybové větvi. Přepsáno - reload proběhne JEN po potvrzeném
  úspěchu, chyba jen odemkne editor a zachová rozepsaný text.
- **BLOCKING - lehká větev (text beze změny) maže `_stylist_marker` a
  cizí nálezy:** ověřeno - přímé SQL UPDATE nahrazovalo `notes` úplně,
  marker (potřebný pro `_already_styled`/`--force`) i nálezy uložené
  JINOU kartou zmizely. Přepsáno na merge podle `id` (markery se nikdy
  nedotknou, protože GET je klientovi nikdy neposílá zpátky).
- **IMPORTANT - no-op podmínka `status=='done' and not raw_findings`
  nesprávná:** souhlas, prázdný seznam nálezů jako platná náhrada
  nefungoval. Nahrazeno skutečným porovnáním výsledného merge stavu s
  aktuálním.
- **IMPORTANT - CAS nechrání SADU nálezů (jen `resolved`):** vyřešeno
  STEJNOU opravou jako lehká větev výš - merge podle `id` nikdy nic
  nemaže, takže karta B's nové nálezy přežijí i zastaralé uložení karty
  A.
- **IMPORTANT - `assign_ids`/`_valid_finding_shape` propustí `id: null`:**
  ověřeno - `setdefault` na PŘÍTOMNÝ, ale `None` klíč nic nezmění.
  Opraveno na `if not f.get("id")`.
- **IMPORTANT - `EDITOR_BUSY` nezamyká checkboxy:** souhlas, přidáno do
  `lockEditor` (dohledání v DOM) i `renderFindings` (nové vykreslení
  respektuje aktuální stav).
- **IMPORTANT - `loadChapter`/`lockEditor` pořád nefunguje vždy:**
  ověřeno na všech třech dílčích bodech - `fetch` bez try/catch,
  `lockEditor` čte `CH.x` i když `CH` je `null`, ovládací prvky aktivní
  před prvním načtením. Opraveno všechny tři (try/catch, null-safe
  `lockEditor`, počáteční `lockEditor(true)` před prvním voláním).
- **IMPORTANT - lehká větev obchází zálohu a chybovou obsluhu:** souhlas,
  přidáno `_backup_db_once` + `try/except` s řízenou 500 odpovědí.
- **IMPORTANT - `renderHistory` zahazuje `e.stale`/`e.reason`:** souhlas,
  starý `polish.html` tohle zobrazoval, nový ho tiše ztratil. Přidán
  zpátky varovný řádek + `.stale-msg` CSS třída (chyběla úplně).
- **NIT - Task 9/Task 15 popisy no-op zastaralé:** opraveno v Task 9
  Interfaces sekci (zbytek gripu nic dalšího nenašel, buď se týkal
  stejného místa pod jiným číslem kroku po mém přečíslování, nebo je
  to už pokryté).
- **NIT - `_polish_one_chapter`'s konzolové hlášky lžou:** souhlas,
  "půjde k ručnímu review" u obou větví je teď nepravdivé. Přidána
  oprava obou `_say` volání do Task 3 (funkce se jinak nemění, jen
  tahle dvě hlášky).

## Claude VERDICT

CHANGES_NEEDED

## Summary for log

Kolo 3 hlavně opravilo regrese, co samo kolo 2 zavedlo (editor mazal
rozepsanou práci PO chybě, lehká větev ztrácela markery/cizí nálezy) -
klasický vzorec "oprava jednoho race conditionu odhalila druhý, co byl
schovaný za ním". `assign_ids`'s `id: null` mezera a chybějící
try/catch v `loadChapter` byly obě reálné, snadno ověřitelné (přečtením
vlastního navrženého kódu) chyby. Merge-podle-id přístup (místo
"přepiš celé pole") se ukázal jako správné řešení pro DVĚ různé
Codexovy stížnosti najednou (marker ztráta i sada-nálezů race) -
jednodušší než dvě samostatné záplaty.
