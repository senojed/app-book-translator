## IMPORTANT

- Task 13 Step 7 / Task 15 Step 1: Plán si odporuje. Task 13 požaduje žádné použití `POLISH_DRAFT_PATH` v `main.py`, ale `_cmd_init` jej stále používá pro archivaci/reset. Task 15 jen neurčitě říká „oprav/smaž podle kontextu“. Explicitně určit úpravu `_cmd_init`, osud existujícího draft souboru a portovat/smazat související reset testy.

- Task 10 Step 3: `state.create_run(db_path, "polish")` je mimo `try`. Selhání SQLite zápisu vrátí neřízenou FastAPI 500 místo JSON chyby a obchází plánovaný error handling. Obalit vytvoření runu, vrátit řízenou chybu a přidat test.

- Task 14 Step 1: `load()` a handler exportu nezachytávají selhání `fetch`. Při síťové chybě zůstane seznam prázdný nebo UI visí na „Exportuji…“ bez vysvětlení. Přidat `try/catch` a uživatelskou chybu, obdobně jako `loadChapter()`.

## VERDICT

CHANGES_NEEDED