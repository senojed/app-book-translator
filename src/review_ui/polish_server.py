"""Lokální web UI pro ruční review stylistického průchodu (`polish`).
Na rozdíl od `server.py` (`review`) tenhle server BĚŽÍ, dokud ho uživatel
nezavře - může rozhodnout jen NĚKTERÉ kapitoly a zbytek nechat na příště.
Viz docs/superpowers/specs/2026-09-11-polish-review-design.md."""
import os
import threading
import uuid
import webbrowser

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src import concordance, glossary, polish_store, state

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

_LOCK_REFRESH_INTERVAL = state._LOCK_STALE_SECONDS // 2   # kolo 2


def _rendered_terms_for(db_path: str, idx: int) -> list:
    """Použito JEN pro DRAFT-vzniklé kapitoly, co ještě nemají uložený
    `rendered_terms` (obranná záloha) - normální cesta je vždy přenášet
    hodnotu z draftu/historie (kolo 18), ne dopočítávat znovu z DB."""
    prior = state.chapter_mentions(db_path, idx)
    return [{"term_id": m["term_id"], "cz_as_used": m["cz_form"],
            "scene_idx": m["scene_idx"]}
           for m in prior if m.get("cz_form") and m.get("source") == "rendered"]


def _stale_info(db_path: str, draft_ch: dict, history_entries: list) -> "dict | None":
    """Spec kolo 3/4 - GET detekuje AKTIVNĚ, ne pasivně přes 409 při retry."""
    row = state.get_chapter(db_path, draft_ch["idx"])
    if row is None:
        return None
    if row["translated_text"] == draft_ch["cz_before"]:
        # DB text SEDÍ s před-stavem draftu - normálně "ještě
        # nerozhodnuto". VÝJIMKA (kolo 6 plán-ping-pongu IMPORTANT):
        # no-op apply (text == cz_before) commitne do DB "kept_original"
        # marker BEZ textové změny - selže-li POTÉ `save_draft`, řádek
        # vypadá jako nerozhodnutý, i když rozhodnutí UŽ proběhlo (retry
        # by přidal DALŠÍ marker). Match se dělá podle `draft_id`, NIKDY
        # podle hashe textu (kolo 10 plán-ping-pongu BLOCKING - stejný
        # `cz_before` se může legitimně opakovat napříč VÍCE nezávislými
        # `polish` běhy na kapitole, co zůstává nestylizovaná; hash by
        # falešně označil ÚPLNĚ NOVÝ, nevyřízený draft jako už vyřízený).
        import main
        already = any(
            f.get("source") == "stylist" and f.get("type") == "kept_original"
            and f.get("draft_id") == draft_ch["draft_id"]
            for f in main._parse_findings(row["notes"]))
        if already:
            return {"stale": True, "reason": "already_committed_kept_original"}
        return None
    # Match podle `draft_id` I `cz_after` (kolo 15 plán-ping-pongu
    # IMPORTANT - dřív jen textová shoda) - jen text by mohl kolidovat s
    # NESOUVISEJÍCÍM starším záznamem (jiný draft, nebo revert) se
    # STEJNÝM výsledným textem, a falešně tvrdit, že DB stav vysvětluje
    # PRÁVĚ TENHLE draft (stejná třída problému jako kolo 10, jen pro
    # větev "text SE liší od cz_before", ne "text SE shoduje").
    matching = [e for e in history_entries
               if e["idx"] == draft_ch["idx"] and e["cz_after"] == row["translated_text"]
               and e.get("draft_id") == draft_ch["draft_id"]]
    if matching:
        return {"stale": True, "reason": "already_committed_has_history"}
    return {"stale": True, "reason": "likely_committed_without_history"}


def _try_load_draft(draft_path: str):
    """`(draft, None)` při úspěchu, `(None, JSONResponse)` při chybě -
    JEDNOTNÁ čitelná 500 pro poškozený `polish.draft.json` napříč VŠEMI
    endpointy (kolo 5 plán-ping-pongu IMPORTANT - dřív jen `apply`
    chytalo tenhle konkrétní případ pro historii, draft se nikde
    nechytal a runtime poškození po startovním preflightu by spadlo
    jako neřízená 500 bez vysvětlení)."""
    try:
        return polish_store.load_draft(draft_path), None
    except polish_store.PolishStoreError as e:
        return None, JSONResponse(
            {"error": f"polish.draft.json je poškozený ({e}) - oprav ho "
                      "ručně (nebo smaž - ztratíš nevyřízené návrhy k review)."},
            status_code=500)


def _try_load_history(history_path: str):
    """Stejný princip jako `_try_load_draft`, pro `polish.history.json`."""
    try:
        return polish_store.load_history(history_path), None
    except polish_store.PolishStoreError as e:
        return None, JSONResponse(
            {"error": f"polish.history.json je poškozený ({e}) - oprav ho "
                      "ručně, žádný zápis neproběhl."},
            status_code=500)


def _annotate_history(db_path: str, full_entries: list, rows: list) -> list:
    """Přidá `can_revert_previous`/`can_revert_original` KE KAŽDÉMU
    vrácenému řádku - server je JEDINÝ zdroj pravdy pro "má tohle
    tlačítko smysl" (kolo 6/20/22 plán-ping-pongu IMPORTANT - UI
    nemá duplikovat chain-walk/no-op logiku, jen vykreslit, co server
    řekl). Počítá se JEN pro řádek, co je SVOJÍ `idx` nejnovější záznam
    (`is` identity - `find_latest` vrací STEJNÝ objekt z `full_entries`,
    ne kopii) - starší řádky v `?idx=N` pohledu dostanou obě `False`
    (UI u nich tlačítka stejně nezobrazuje, ale server je explicitní,
    ne spoléhá na to, že to klient spočítá stejně)."""
    out = []
    for e in rows:
        row = dict(e)
        row["can_revert_previous"] = False
        row["can_revert_original"] = False
        row["stale"] = False
        if polish_store.find_latest(full_entries, e["idx"]) is e:
            current = state.get_chapter(db_path, e["idx"])
            current_text = current["translated_text"] if current else None
            # DB uz nesouhlasi s tim, co historie tvrdi jako posledni
            # aplikovany text (kolo 6 plán-ping-pongu BLOCKING) - typicky
            # kdyz `revert`/`apply` DB commit uspeje, ale nasledny zapis
            # NOVEHO historie-zaznamu selze: historie porad konci STARYM
            # `cz_after`, DB uz ma NOVY text. Draftova `_stale_info` tohle
            # nechyti u revertu, protoze revert zadny draft nevytvari.
            row["stale"] = current_text is not None and current_text != e["cz_after"]
            if row["stale"]:
                row["reason"] = "db_diverged_from_history"
            prev_target = polish_store.resolve_revert_target(full_entries, e["idx"], "previous")
            orig_target = polish_store.resolve_revert_target(full_entries, e["idx"], "original")
            row["can_revert_previous"] = prev_target is not None and prev_target != current_text
            # `orig_target != prev_target` (kolo 2 plán-ping-pongu
            # IMPORTANT - dřív chybělo): u řetězce délky 1 je `original`
            # cíl VŽDY přesně stejný jako `previous` cíl (chain-start ==
            # latest) - obě tlačítka by dělala to samé, spec kolo 19/20
            # chce v tomhle případě jen JEDNO. Tahle podmínka navíc
            # správně potlačí i vzácnou náhodnou shodu textů u delšího
            # řetězce (kdyby k ní došlo, obě tlačítka by STEJNĚ vedla ke
            # stejnému výsledku - potlačení duplicity je tak přesnější
            # kritérium než pouhá "délka řetězce >= 2").
            row["can_revert_original"] = (orig_target is not None
                                          and orig_target != current_text
                                          and orig_target != prev_target)
        out.append(row)
    return out


def build_app(db_path: str, draft_path: str, history_path: str, lock_path: str) -> FastAPI:
    app = FastAPI(title="Book translator - polish review")
    write_lock = threading.Lock()          # kolo 2 - serializuje HTTP requesty
    # Preflight validace OBOU JSON souborů PŘI STARTU (kolo 2
    # plán-ping-pongu BLOCKING) - poškozený draft/historie musí server
    # odmítnout spustit rovnou, ne nechat vybouchnout uprostřed prvního
    # apply/revert requestu (kdy uz může DB commit proběhnout dřív, než
    # se poškození zjistí). `PolishStoreError` odsud propaguje ven -
    # `run_polish_review_server` se prostě nespustí, stejný vzor jako
    # selhání `_snapshot_db` níž.
    polish_store.load_draft(draft_path)
    polish_store.load_history(history_path)
    backup_state = {"done": False, "snapshot_path": db_path + ".pre-polish-review-snapshot"}
    from main import _snapshot_db          # sdílená obecná funkce, ne polish-specifická
    _snapshot_db(db_path, backup_state["snapshot_path"])
    lock_lost = threading.Event()
    # SAMOSTATNÝ event od `lock_lost` (kolo 14 plán-ping-pongu IMPORTANT)
    # - `shutdown` znamená "heartbeat vlákno má SKONČIT", `lock_lost`
    # znamená "zámek jsme ztratili" (gatuje 503 v `_require_lock`). Dřív
    # se heartbeat vlákno při ČISTÉM vypnutí serveru VŮBEC nezastavovalo
    # (jen `daemon=True`, co ho zabije až s CELÝM procesem) - kdyby
    # `server.run()` vrátilo PRÁVĚ v okamžiku, kdy heartbeat mezitím volá
    # `refresh_lock`, mohlo by to zámek OBNOVIT těsně PO tom, co volající
    # (`main()`'s `run_lock`) zavolá `release_lock` - `shutdown.set()` +
    # `heartbeat_thread.join()` v `run_polish_review_server`'s `finally`
    # tenhle race odstraňuje úplně (vlákno je PROKAZATELNĚ zastavené dřív,
    # než funkce vrátí řízení volajícímu).
    shutdown = threading.Event()

    def _heartbeat():
        # `shutdown.wait(...)` (ne `lock_lost.wait`, kolo 14) - `shutdown`
        # se nastaví JAK při zjištěné ztrátě zámku (níž), TAK při čistém
        # vypnutí serveru (`run_polish_review_server`'s `finally`) - JEDNO
        # místo, které vlákno probudí OKAMŽITĚ v obou případech, místo
        # čekání až 3 h na příští periodu.
        while not shutdown.wait(_LOCK_REFRESH_INTERVAL):
            try:
                state.refresh_lock(lock_path)
            except state.LockError:
                lock_lost.set()
                shutdown.set()
                print("POZOR: Zámek ztracen - jiný proces teď zapisuje do DB. "
                      "Ukonči tenhle polish-review (Ctrl-C) a spusť znovu.")

    heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
    heartbeat_thread.start()

    def _require_lock():
        """Synchronní refresh JAKO PRVNÍ krok KAŽDÉHO zápisu (kolo 7) -
        nespoléhat jen na periodický heartbeat, co může zaostávat až 3 h.
        Jednou ztracený zámek je TERMINÁLNÍ stav serveru až do restartu
        (kolo 9 plán-ping-pongu IMPORTANT - dřív by se PO nastavení
        `lock_lost` pořád zkoušelo `refresh_lock` znovu na KAŽDÉM dalším
        requestu; kdyby zámek mezitím zvrtkavěl - cizí proces ho zase
        pustil a NÁŠ soubor náhodou zůstal - mohlo by to nekonzistentně
        střídat 503/200 místo jednou nastaveného, trvalého odmítnutí)."""
        if lock_lost.is_set():
            return False
        try:
            state.refresh_lock(lock_path)
        except state.LockError:
            lock_lost.set()
            shutdown.set()   # probuď heartbeat OKAMŽITĚ (kolo 14), ne až za 3 h
            return False
        return True

    @app.get("/")
    def index():
        return FileResponse(os.path.join(_STATIC, "polish.html"))

    @app.get("/api/polish")
    def get_polish(idx: "int | None" = None):
        draft, err = _try_load_draft(draft_path)
        if err:
            return err
        history_doc, err = _try_load_history(history_path)
        if err:
            return err
        history = history_doc["entries"]
        chapters = []
        for ch in draft["chapters"]:
            row = dict(ch)
            stale = _stale_info(db_path, ch, history)
            row["stale"] = stale is not None
            if stale:
                row["reason"] = stale["reason"]
            chapters.append(row)
        if idx is not None:
            hist_out = [e for e in history if e["idx"] == idx]
        else:
            # Řazení VŽDY podle parsovaného data, nikdy syrového řetězce
            # (spec kolo 5/8 - `isoformat()` vynechává mikrosekundy, když
            # jsou přesně 0, což by lexikografické řazení mohlo rozbít).
            hist_out = sorted(history, key=lambda e: polish_store.parse_z(e["applied_at"]),
                              reverse=True)[:20]
        return {"chapters": chapters, "history": _annotate_history(db_path, history, hist_out)}

    app.state.write_lock = write_lock
    app.state.lock_lost = lock_lost
    app.state.shutdown_heartbeat = shutdown
    app.state.heartbeat_thread = heartbeat_thread
    app.state.require_lock = _require_lock
    app.state.backup_state = backup_state
    app.state.db_path = db_path
    app.state.draft_path = draft_path
    app.state.history_path = history_path
    return app


def run_polish_review_server(db_path: str, draft_path: str, history_path: str,
                             lock_path: str, *, host: str = "127.0.0.1",
                             port: int = 8766) -> int:
    """Vrací VŽDY 0 - žádný CLI krok po `polish-review` nezávisí na tom,
    jestli něco bylo rozhodnuto (spec)."""
    import uvicorn
    app = build_app(db_path, draft_path, history_path, lock_path)
    # CELÝ setup PO `build_app()` (včetně `uvicorn.Server`/`Config`
    # konstrukce) je uvnitř `try/finally` (kolo 14 plán-ping-pongu
    # IMPORTANT - dřív `uvicorn.Server(uvicorn.Config(...))` běželo PŘED
    # `try`, takže by jeho případné selhání PŘESKOČILO finally úplně -
    # heartbeat by zůstal běžet a dočasný snapshot by nikdy neuklidil).
    try:
        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
        url = f"http://{host}:{port}/"
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
        print(f"Polish review UI běží na {url} - zavři okno nebo Ctrl-C, až budeš hotov.")
        try:
            server.run()
        except KeyboardInterrupt:
            pass
    finally:
        # Zastav heartbeat a POČKEJ, až doopravdy skončí (kolo 14
        # plán-ping-pongu IMPORTANT), PŘED návratem řízení volajícímu
        # (`main()`'s `with state.run_lock(...): ... release_lock(...)`
        # na konci) - jinak by heartbeat mohl `refresh_lock` zavolat
        # PRÁVĚ v okamžiku, kdy zámek mezitím uvolní volající, a
        # nechtěně ho znovu publikovat. Krátký timeout jen jako pojistka
        # (`refresh_lock` samo je rychlé - jediný souborový zápis).
        app.state.shutdown_heartbeat.set()
        app.state.heartbeat_thread.join(timeout=5)
        # Nepromovaný dočasný snapshot (žádný apply/revert za celý běh
        # serveru neproběhl) po sobě uklidit - stejný princip jako
        # `_cmd_polish`'s `finally` (kolo 8 IMPORTANT plán-ping-pongu -
        # dřív se tu nic needlídilo).
        backup_state = app.state.backup_state
        if not backup_state["done"]:
            try:
                os.remove(backup_state["snapshot_path"])
            except OSError:
                pass
    return 0
