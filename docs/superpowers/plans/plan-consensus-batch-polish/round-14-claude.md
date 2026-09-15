# Round 14 — Claude critique

## Claude's own findings

Žádné nové nad rámec Codexova seznamu tohle kolo.

## On Codex's points

### Agreed + fixed
- **IMPORTANT #1 - Task 13 Step 7 vs Task 15 Step 1 si odporují ohledně
  `POLISH_DRAFT_PATH`.** Ověřeno čtením main.py:728-744 (`_cmd_init
  --reset`) - `_archive_polish_file(config.POLISH_DRAFT_PATH)` je
  ZÁMĚRNÁ, harmless (no-op když soubor neexistuje) archivace leftover
  souboru z PŘED-migračních instalací, NE přehlédnuté volající místo
  staré draft fronty. Task 13 Step 7 teď tuhle výjimku explicitně
  pojmenovává (a vysvětluje proč `config.POLISH_DRAFT_PATH` konstanta v
  main.py ZŮSTÁVÁ, i když draft fronta jako celek mizí). Task 15 Step 1
  přepsáno z neurčitého "oprav/smaž podle kontextu" na konkrétní pravidlo
  (jediné legitimní přeživší místo = `_cmd_init`, cokoli jiného je
  dořešení zapomenutého z Tasku 13).
- **IMPORTANT #2 - Task 10 `state.create_run(db_path, "polish")` mimo
  `try` - selhání by propadlo jako holý FastAPI 500 bez JSON těla.**
  Ověřeno čtením kódu - potvrzeno, `create_run` byl PŘED `try:` blokem.
  Přesunuto dovnitř, `rid = None` inicializace PŘED `try` umožňuje
  `finally` bloku poznat, jestli run vůbec vznikl (`rid is not None`
  navíc k existující `require_lock()` kontrole před `finish_run`). Nový
  test ověřuje strukturovanou 500 JSON odpověď při `create_run` selhání.
- **IMPORTANT #3 - Task 14 `chapters.html`'s `load()` a export handler
  nemají `try/catch` kolem `fetch` - síťová chyba = nezachycená výjimka
  / navždy visící "Exportuji...".** Ověřeno čtením - potvrzeno, ŽÁDNÝ
  `try/catch` u obou. Opraveno stejným vzorem jako `loadChapter()`
  v editoru (Task 14 Step 2, kolo 3 fix) - `try/catch` kolem `fetch`+
  `.json()`, čitelná chybová hláška při selhání.

## Claude VERDICT

CHANGES_NEEDED (souhlas se všemi 3 IMPORTANT body, plná implementace)

## Summary for log

Kolo 14 opustilo lock-check sérii (kola 10-13) a našlo tři nezávislé,
různorodé mezery - jednu textovou kontradikci mezi dvěma tasky, jednu
chybějící try/except kolem DB zápisu, jednu chybějící try/catch kolem
fetch ve frontendu. Všechny tři reálné a přímočaře opravitelné, žádný
spor/nesouhlas tohle kolo.
