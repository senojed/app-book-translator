## IMPORTANT

- `_backup_db_once` – popsaná obnova není bezpečná pro WAL režim. Po `os.replace(tmp_path, db)` mohou zůstat novější `db-wal`/`db-shm`, které obnovený stav změní nebo poškodí. Oprava: definovat a otestovat obnovu včetně sidecarů, případně použít SQLite backup API i pro restore.
- `_snapshot_db` – `sqlite3.Connection.backup()` nemá časový limit; při dlouhodobě zamčené DB může příkaz viset neomezeně. Oprava: deadline přes `progress` callback a regresní test se zamčeným zdrojem.
- Tabulka chybových stavů, ř. 1686 – „Jen `fluency`/stylistické nálezy → přijato“ odporuje `_polish_rejected`, který odmítá každý kritikův `action=="revise"`, tedy i kritický `fluency` nález. Oprava: uvést, že se přijímají pouze `action=="note"` nálezy, a přidat test kritického `fluency`.

## NITS

- Test zálohy, ř. 1565 – požadavek na bytovou shodu s původním hlavním DB souborem není vhodný pro WAL režim, který má nový mechanismus podporovat. Ověřovat logický obsah, integritu a nepřítomnost změn z aktuálního běhu.
- Ř. 1061 a 1173 stále popisují aktuální operaci jako `shutil.copy2`; kód už používá `_snapshot_db`.
- Rozhodnutí kolo 9, ř. 1959, stále bez označení nahrazení tvrdí, že aktuální snapshot vytváří `shutil.copy2`. Doplnit explicitní poznámku o nahrazení v kole 14.
- `critic.review()` docstring, ř. 65, tvrdí, že chyba vždy vytvoří `flagged` kapitolu. V `polish` vede k výsledku `rejected` bez změny statusu kapitoly.

## VERDICT

CHANGES_NEEDED