## IMPORTANT

- Task 1 / Task 5 eager preflight: Cena se přidává jen pro aktuální hodnotu `CODEX_MODEL` při importu. Změní-li uživatel `CODEX_MODEL`, tabulky cen zůstanou bez nové hodnoty; první `_guard()` pak vyhodí obecný `FatalRunError` až po `begin_chapter()`, kapitola skončí v `processing` a další běh ji tiše vrátí do fronty. Doplň do Codex-translator preflightu kontrolu obou cenových tabulek a vrať `CodexTranslatorFatalError` před frontou; stejnou kontrolu proveď v lazy factory. Přidej regresní test s nepřeceněným modelem.

- Task 6, Step 2: Postup vyžaduje externí `sqlite3` CLI, které v tomto prostředí není dostupné, a projekt ho nemá jako závislost. Manuální ověření je proto neproveditelné podle plánu. Nahraď `.backup` i SQL kontrolu krátkým `python -c` skriptem přes stdlib `sqlite3` (`Connection.backup()` a `SELECT`), nebo explicitně zaveď a ověř závislost na SQLite CLI.

## VERDICT
CHANGES_NEEDED