# Round 1 — Claude critique

## Claude's own findings

Nezávislý průchod (před čtením Codexovy kritiky) potvrdil několik ze
stejných tříd problémů (viz "Agreed + fixed" níž — hodně se překrývá,
protože jsem si stejné věci ověřoval přímo v kódu). Vlastní nálezy nad
rámec Codexova seznamu:

### IMPORTANT
- Task 7/8 interní rozpor: dokument tvrdil "spojí `chapters.notes` +
  poslední historii", ale `_commit_polish_result` (Task 5) zapisuje
  STEJNÝ seznam nálezů do obou najednou → zdvojení. Opraveno stejně jako
  Codexův bod "nálezy se násobí" (jsou to dvě strany téhož nálezu, viz
  níž) — sjednoceno na "notes je jediný zdroj", `history_path` parametr
  z `build_findings_report` odstraněn jako mrtvý.

## On Codex's points

### Agreed + fixed
- **BLOCKING - chybí `_snapshot_db` volání (Task 5):** ověřeno přímo v
  `main.py:373-442` (`_backup_db_once` PROMUJE existující soubor,
  nevytváří ho). Přidán `_snapshot_db(db, backup_state["snapshot_path"])`
  hned po vytvoření `backup_state`.
- **BLOCKING - `_VALID_HISTORY_SOURCES` neobsahuje `"polish-batch"`:**
  ověřeno v `src/polish_store.py:20`. Přidán nový Step 3 do Tasku 5,
  rozšiřuje tuple + test.
- **BLOCKING - dávka bez CAS/refresh_lock:** souhlas, dávka na ~50
  kapitolách může běžet hodiny, `_cmd_polish` nemá heartbeat (na rozdíl
  od `polish-review` serveru). Přidán `state.refresh_lock` + CAS kontrola
  PŘED každým commitem v Task 5 smyčce, neshoda → kapitola se přeskočí,
  ne fatal.
- **BLOCKING - nálezy se násobí:** ověřeno - `_commit_polish_result`
  zapisuje STEJNÝ seznam do `notes` i historie zároveň, takže merge při
  čtení (Task 7/8) by zdvojil úplně všechno. Oprava: `notes` je JEDINÝ
  zdroj "aktuálních" nálezů, historie se při čtení už neslučuje (viz
  Task 5/7/8 komentáře). Součást téhle opravy taky řeší dřívější ztrátu
  `run`-fáze nálezů při `polish`/editaci — přijato jako STEJNÉ chování,
  jaké má dnešní `apply` endpoint (přepis, ne merge), ne jako regrese.
- **BLOCKING - `--force`/`_already_styled` marker chybí u nového zápisu:**
  ověřeno v `main.py:100-106`. `_commit_polish_result` teď VŽDY připojí
  `_stylist_marker` (nový param `model_label`), ať volá dávka nebo
  editor - `--force` sémantika funguje pro obě cesty stejně.
- **IMPORTANT (→ zvednuto na BLOCKING) - `app.state.draft_path` zůstává v
  `build_app`:** ověřeno v `src/review_ui/polish_server.py:559`. Přidána
  explicitní instrukce smazat ten řádek v Task 13.
- **BLOCKING - test fixtures neexistují (`_db`, `_make_db_with_one_chapter`):**
  ověřeno v `tests/test_cli.py` (skutečné helpery: `_polish_db`, `_c`,
  `_cf_stub`, `_polish_env`). Všechny výskyty v Taskách 3/4/5/6 přepsány
  na reálné fixtures.
- **BLOCKING - `_polish_env` nepřesměrovává `POLISH_HISTORY_PATH`:**
  ověřeno v `tests/test_cli.py:861-881`. Přidán Step 9 do Tasku 5.
- **IMPORTANT - config reload leak (Task 1):** `importlib.reload` mutuje
  sdílený modul, `monkeypatch` sám nevrátí důsledek reloadu. Testy teď
  mají `try/finally` s `monkeypatch.undo()` + druhým reloadem.
- **IMPORTANT - migrace existujících nálezů bez id:** souhlas - reálná
  DB má nálezy bez `id`/`resolved`. Přidán Step 8 do Tasku 13 (jednorázový
  migrační skript pro `chapters.notes` i historii) + revert endpoint teď
  taky volá `assign_ids`.
- **IMPORTANT - `rendered_terms` ztráta na Task 9 save:** souhlas,
  ověřeno že `commit_chapter_result` PŘEPISUJE `term_mentions` při
  každém commitu → živé čtení by se mohlo postupně zužovat. Save teď
  přednostně bere `rendered_terms` z posledního historie záznamu, na
  živou DB sahá jen bez historie.
- **IMPORTANT - CAS nechrání `resolved`:** souhlas, dva taby scénář je
  reálný. Přidáno: server-side `resolved=True` vždy vyhrává nad
  zastaralým klientským payloadem (jednosměrně - resolve nikdy nezmizí
  kvůli starému save).
- **IMPORTANT - `toggleResolved` skrývá chyby, zkouší dva scope:**
  vyřešeno JEDNODUŠEJI, než Codex navrhoval - protože Task 8 GET už
  nikdy neukazuje historii-nálezy (viz duplicitní-nálezy oprava výš),
  frontend NIKDY nepotřebuje `scope="history"`. Zjednodušeno na jediný
  scope, s właściwým error handling (checkbox se vrátí na starou hodnotu
  při chybě, `resolved` se mění AŽ po potvrzeném úspěchu).
- **IMPORTANT - regenerace není bez zápisů:** souhlas na všech třech
  bodech, ověřeno v kódu (`main.py:56` `_client_factory` natvrdo
  `config.DB_PATH`; `src/llm/client.py:152-169` `interactive=True` volá
  reálný `input()`). Opraveno: `interactive=False`, `require_lock()` bez
  `write_lock` (levná kontrola, ne serializace - zdůvodněno, proč NE
  `write_lock`), testy monkeypatchují `config.DB_PATH`.
- **IMPORTANT - editor dovolí otevřít non-done, save vždy selže:**
  souhlas, rozumný požadavek (přesně scénář ruční opravy `flagged`
  kapitoly z předchozí live session). `_EDITABLE_STATUSES = ("done",
  "flagged", "needs_human", "error")` v obou endpointech (save i
  regenerate), `pending`/`processing` zůstávají vyloučené (nemají
  smysluplný text).
- **IMPORTANT - export obchází `require_lock()`:** souhlas. `POST
  /api/export` teď obalený `write_lock` (serializace proti souběžnému
  save JINÉ kapitoly = konzistentní snímek knihy) + `require_lock()`.
  Plná atomicita zápisu souborů napříč PROCESY zůstává zdokumentované
  zbytkové riziko (stejná třída jako `2026-09-11` spec už přiznává jinde) -
  `write_lock` řeší jediný reálný scénář (jeden server, dva rychlé
  kliky/souběžný save).
- **IMPORTANT - Task 14 ignoruje `skipped`:** opraveno, zobrazuje se v
  toolbar zprávě.
- **IMPORTANT - chybí validace jednotlivých nálezů:** přidána
  `_valid_finding_shape` helper funkce, volaná před `assign_ids`.
- **IMPORTANT - opožděné odpovědi mohou zahodit editaci:** souhlas.
  Přidán `lockEditor()` - textarea i tlačítka se blokují během
  regenerace/uložení, ne jen tlačítko samotné.
- **NIT - `tally['drafted']` v main.py:1234 přežije Task 3:** souhlas,
  bez opravy by Task 3's vlastní Step 9 (`pytest ... Expected: PASS`)
  spadl na `KeyError` dřív, než se k tomu dostane Task 5. Opraveno přímo
  v Tasku 3.
- **NIT - `find_chain_start` sémantika "originálu":** souhlas na
  přesnosti, nesouhlas na "musí se to změnit" - je to ZÁMĚRNĚ převzaté
  chování z `2026-09-11` spec revert tlačítka (řetězec s mezerami je
  edge case, ne bug). Přidána vysvětlující poznámka do Task 8 interface
  popisu, chování beze změny.

### Agreed but already addressed
*(žádné - tohle bylo první kolo, nic už nebylo dřív opravené)*

### Disagreed
*(žádné - všechny Codexovy BLOCKING/IMPORTANT body byly po ověření
platné; NIT o `find_chain_start` přijat jako dokumentační, ne
behaviorální oprava, viz výš)*

## Claude VERDICT

CHANGES_NEEDED (byly - teď opraveno; opravy jsou rozsáhlé, potřebují
další kolo ověření)

## Summary for log

Kolo 1 odhalilo hodně skutečných chyb, hlavně kolem nového `_commit_polish_
result` sdíleného zápisu: chybějící snapshot (dávka by spadla na první
kapitole), nepovolený `source` v historii (DB by se změnila, historie ne),
zdvojené nálezy (notes+historie merge nad STEJNÝMI daty), rozbité `--force`
(chybějící marker), a testovací fixtures, co v souboru vůbec neexistují.
Všechno opraveno přímo v plánu, ověřeno čtením skutečného zdrojového kódu
(main.py, polish_server.py, polish_store.py, src/llm/client.py,
tests/test_cli.py), ne jen podle Codexova tvrzení. Zbývá ověřit kolo 2,
jestli opravy samy nezavedly nový rozpor (hlavně přečíslování kroků v
Tasku 5/13, které bylo rozsáhlé).
