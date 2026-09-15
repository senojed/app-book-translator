"""Jednorázová migrace - doplní `id`/`resolved` do existujících nálezů
v `chapters.notes` a `polish.history.json` (vznikly před Task 2, kdy
`assign_ids` ještě neexistovalo). Spusť JEDNOU, ručně, PŘED prvním
ostrým použitím nové `polish-review` UI:

    python scripts/migrate_findings_ids.py

Ne trvalý CLI příkaz - po úspěšném spuštění smazatelný. Viz plán
docs/superpowers/plans/2026-09-14-batch-polish-reader-workflow.md,
Task 13 Step 8."""
import sys; sys.path.insert(0, ".")
import json
import os
import shutil
import config
import main
from src import findings, polish_store, state


def _valid_entries(raw):
    """Stejná tolerance jako `main._parse_findings` - ne-dict prvky
    se PŘESKOČÍ (nespadnou), ne odmítnou celý seznam. Použitelné jen
    pro `chapters.notes` (čte se syrovým `json.loads`, žádná schema
    validace před tím) - `polish.history.json` prochází `polish_store.
    load_history`'s PŘÍSNOU validací PŘED tímhle skriptem, viz níž."""
    return [f for f in raw if isinstance(f, dict)]


state.acquire_lock(config.LOCK_PATH)   # žádný jiný mutující příkaz souběžně
try:
    # Historie SE ZKOUŠÍ NAČÍST JAKO PRVNÍ - selže-li (poškozený JSON,
    # nebo netolerovatelná položka uvnitř `findings`, co `load_history`'s
    # schema validace odmítne DŘÍV, než tenhle skript dostane šanci ji
    # ošetřit), NIC se zatím nezapsalo - žádný poloviční stav. Neúspěch =
    # ruční oprava souboru, pak skript spustit znovu.
    history = None
    history_entries_before = None
    if os.path.exists(config.POLISH_HISTORY_PATH):
        try:
            history = polish_store.load_history(config.POLISH_HISTORY_PATH)
        except polish_store.PolishStoreError as e:
            print(f"STOP - {config.POLISH_HISTORY_PATH} se nedá načíst "
                 f"({e}) - oprav ho ručně, pak spusť skript znovu. "
                 "Nic se zatím NEZAPSALO.")
            raise SystemExit(1)
        history_entries_before = json.dumps(history["entries"], ensure_ascii=False)

    # `main._snapshot_db` (SQLite `Connection.backup()` API), NE
    # `shutil.copy2` - prostý souborový copy může zachytit DB UPROSTŘED
    # zápisu (nekonzistentní kopie) a neumí WAL/SHM sidecar soubory.
    #
    # PEVNÉ jméno zálohy by DRUHÉ spuštění (po neúspěšném prvním pokusu)
    # PŘEPSALO zálohu z PRVNÍHO běhu - `if not os.path.exists(...)` =
    # zapiš zálohu jen JEDNOU.
    #
    # Zápis PŘÍMO na `backup_path` riskuje, že PŘERUŠENÍ uprostřed
    # (výpadek, Ctrl-C, OOM kill) nechá na disku NEÚPLNÝ, ale EXISTUJÍCÍ
    # soubor - zapiš na DOČASNOU cestu, ověř, a teprve PAK atomicky
    # přejmenuj (`os.replace`).
    backup_path = config.DB_PATH + ".pre-findings-migration-backup"
    if not os.path.exists(backup_path):
        tmp_backup_path = backup_path + ".tmp"
        if os.path.exists(tmp_backup_path):
            os.remove(tmp_backup_path)   # úklid po dřívějším přerušení
        try:
            main._snapshot_db(config.DB_PATH, tmp_backup_path)
            os.replace(tmp_backup_path, backup_path)
        except (OSError, TimeoutError) as e:
            try:
                os.remove(tmp_backup_path)
            except OSError:
                pass
            print(f"STOP - záloha DB selhala ({type(e).__name__}: {e}) - "
                 "MIGRACE SE NESPOUŠTÍ, dokud se nedá udělat bezpečná "
                 "záloha. Nic se zatím NEZAPSALO.")
            raise SystemExit(1)
        print(f"Záloha DB: {backup_path}")
    else:
        print(f"Záloha DB už existuje ({backup_path}) - zachovávám PŮVODNÍ "
             "(nejspíš druhé spuštění po dřívějším neúspěchu).")

    with state.connect(config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT idx, notes FROM chapters WHERE notes IS NOT NULL").fetchall()
        changed = 0
        for row in rows:
            try:
                parsed = json.loads(row["notes"])
            except ValueError:
                print(f"  přeskočeno (neplatný JSON) - kapitola {row['idx']}")
                continue
            if not isinstance(parsed, list) or not parsed:
                continue
            valid = _valid_entries(parsed)
            if len(valid) != len(parsed):
                print(f"  POZOR - kapitola {row['idx']}: "
                     f"{len(parsed) - len(valid)} ne-dict položek přeskočeno")
            before = json.dumps(valid, ensure_ascii=False)
            findings.assign_ids(valid)
            after = json.dumps(valid, ensure_ascii=False)
            if after != before or len(valid) != len(parsed):
                conn.execute("UPDATE chapters SET notes=?, "
                            "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                            (after, row["idx"]))
                changed += 1
        print(f"chapters.notes migrováno: {changed}")

    if history is not None:
        history_backup_path = config.POLISH_HISTORY_PATH + ".pre-findings-migration-backup"
        try:
            if not os.path.exists(history_backup_path):
                tmp_history_backup = history_backup_path + ".tmp"
                if os.path.exists(tmp_history_backup):
                    os.remove(tmp_history_backup)
                shutil.copy2(config.POLISH_HISTORY_PATH, tmp_history_backup)
                os.replace(tmp_history_backup, history_backup_path)
        except OSError as e:
            print(f"POZOR - chapters.notes SE ÚSPĚŠNĚ migrovalo, ale "
                 f"záloha historie selhala ({type(e).__name__}: {e}) - "
                 "historie se NEZAPISUJE (bez zálohy je to riskantní). "
                 "Oprav příčinu a SPUSŤ SKRIPT ZNOVU - je idempotentní.")
            raise SystemExit(1)
        for entry in history["entries"]:
            findings.assign_ids(entry["findings"])   # `load_history` UŽ zaručilo list[dict]
        if json.dumps(history["entries"], ensure_ascii=False) != history_entries_before:
            try:
                polish_store.save_history(config.POLISH_HISTORY_PATH, history)
            except Exception as e:
                # `chapters.notes` výš UŽ JE zapsané - tenhle zápis selhal
                # AŽ POTOM. ŽÁDNÝ automatický rollback `chapters.notes`
                # zpátky ze zálohy - `_valid_entries`/`assign_ids` čistí
                # jen garbage (ne-dict položky, netypované hodnoty), co
                # by stejně zůstaly nepoužitelné - žádný legitimní nález
                # se tím neztrácí. Bezpečná oprava je PROSTĚ SKRIPT
                # SPUSTIT ZNOVU (notes migrace podruhé je no-op).
                print(f"POZOR - chapters.notes SE ÚSPĚŠNĚ migrovalo (viz "
                     f"'chapters.notes migrováno' výš), ale zápis historie "
                     f"selhal ({type(e).__name__}: {e}). Tohle NENÍ "
                     "poškozený/nekonzistentní stav - id v chapters.notes "
                     "zůstávají platná. Oprav příčinu (místo na disku, "
                     "práva k zápisu apod.) a SPUSŤ SKRIPT ZNOVU - je "
                     "idempotentní, notes migrace podruhé nic nezmění, "
                     "historie se zkusí zapsat znovu. Zálohy pro ruční "
                     f"obnovu (jen kdybys to přesto chtěl vrátit): "
                     f"{backup_path}, {history_backup_path}")
                raise SystemExit(1)
            print("historie záznamů migrována")
        else:
            print("historie: beze změny (všechny záznamy už měly id)")
finally:
    state.release_lock(config.LOCK_PATH)
