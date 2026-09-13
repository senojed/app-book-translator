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


def _stale_info(row: "dict | None", draft_ch: dict, history_entries: list) -> "dict | None":
    """Spec kolo 3/4 - GET detekuje AKTIVNĚ, ne pasivně přes 409 při retry.
    `row` (kolo polish-ui-v2 IMPORTANT) - dřív si funkce sama volala
    `state.get_chapter`, takže `get_polish` otvíralo DB spojení PODRUHÉ
    jen kvůli `raw_text` pro EN sloupec. Volající teď kapitolu načte
    JEDNOU a předá řádek sem - žádná duplicitní DB práce."""
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
            db_row = state.get_chapter(db_path, ch["idx"])
            # `raw_text` (kolo polish-ui-v2) - anglický originál pro třetí
            # UI panel. `db_row` může být `None`, když kapitola mezitím
            # zmizela z DB (stejná hrana, co uz `_stale_info` řeší níž) -
            # `None` je pak i výsledný `raw_text`, ne pád na chybějícím klíči.
            row["raw_text"] = db_row["raw_text"] if db_row else None
            stale = _stale_info(db_row, ch, history)
            row["stale"] = stale is not None
            if stale:
                row["reason"] = stale["reason"]
            chapters.append(row)
        if idx is not None:
            hist_out = [e for e in history if e["idx"] == idx]
        else:
            # Řazení VŽDY podle (parsovaného data, POZICE v poli), nikdy
            # jen podle syrového řetězce (spec kolo 5/8 - `isoformat()`
            # vynechává mikrosekundy, když jsou přesně 0, což by
            # lexikografické řazení mohlo rozbít) ANI jen podle
            # parsovaného data samotného (code review nález IMPORTANT -
            # dva záznamy stejného idx mohou mít IDENTICKÝ `applied_at`
            # string - časové rozlišení není dost jemné - a `sorted`
            # je STABILNÍ, takže by shodné klíče nechal v PŮVODNÍM
            # pořadí; `_annotate_history` níž ale "nejnovější" určuje
            # přes `find_latest`, co je definuje VÝHRADNĚ podle POZICE
            # v poli, nikdy podle času - kdyby se dvě řazení touhle
            # tiebreak logikou rozešla, `history[0]` by ukázal STARŠÍ
            # záznam BEZ revert tlačítek, zatímco skutečně nejnovější
            # (anotovaný tlačítky) by skončil níž). Pozice v `history`
            # je tak SOUČÁSTÍ klíče, ne jen záložní - `find_latest`'s
            # "nejnovější" napodobuje přesně.
            hist_out = sorted(enumerate(history),
                              key=lambda p: (polish_store.parse_z(p[1]["applied_at"]), p[0]),
                              reverse=True)
            hist_out = [e for _, e in hist_out][:20]
        return {"chapters": chapters, "history": _annotate_history(db_path, history, hist_out)}

    @app.post("/api/polish/apply")
    def post_apply(payload: dict):
        idx_raw, text = payload.get("idx"), payload.get("text")
        # `type(x) is int` NE `isinstance` (kolo 3 plán-ping-pongu
        # BLOCKING - `bool` je podtřída `int`, `isinstance(True, int)`
        # je `True`; `idx: true` by se choval jako `idx: 1`). Tahle
        # kontrola zůstává PŘED zámkem - je to levná kontrola TVARU
        # requestu, ne rozhodnutí závislé na stavu, žádný důvod držet
        # kvůli ní `write_lock`.
        if type(idx_raw) is not int or not isinstance(text, str):
            return JSONResponse({"error": "idx musí být int, text musí být str"},
                                status_code=400)
        idx = idx_raw
        # CELÉ rozhodnutí - ověření zámku, čtení draftu, existence
        # položky, CAS, zápis - je JEDNA atomická operace (kolo 3 + kolo
        # 4 plán-ping-pongu BLOCKING): draft se dřív četl MIMO
        # `write_lock` (kolo 3 - souběžný `discard` mohl proběhnout
        # MEZI čtením a získáním zámku, CAS na DB text to nezachytí).
        # `require_lock()` se dřív volalo PŘED `write_lock` (kolo 4) -
        # čekání na `write_lock` (drží ho jiný request) mohlo trvat
        # dost dlouho, že by MEZITÍM mohl zestárnout zámek napříč
        # procesy a ověření z PŘED čekáním by bylo zastaralé. Ověření
        # JAKO PRVNÍ krok UVNITŘ zámku dělá kontrolu platnou přesně v
        # okamžiku, kdy se s ní skutečně pracuje.
        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            draft, err = _try_load_draft(draft_path)
            if err:
                return err
            ch = next((c for c in draft["chapters"] if c["idx"] == idx), None)
            if ch is None:
                return JSONResponse({"error": "kapitola už není ve frontě - "
                                              "zkontroluj, jestli mezitím neproběhla "
                                              "v jiné kartě"}, status_code=404)
            row = state.get_chapter(db_path, idx)
            if (row is None or row["translated_text"] != ch["cz_before"]
                    or row["status"] != "done"):
                return JSONResponse(
                    {"error": "kapitola se mezitím změnila mimo tenhle review - "
                              "pravděpodobně `answer`/nová revize; zkontroluj "
                              "aktuální text, případně spusť `polish` znovu"},
                    status_code=409)

            import main   # lazy - main.py nikdy neimportuje tenhle modul na top-levelu
            changed = text != ch["cz_before"]
            if not changed:
                # Idempotentní zkrácení PŘED jakýmkoli DB zápisem (kolo 9
                # plán-ping-pongu IMPORTANT) - GET/UI (kolo 6) UŽ tenhle
                # stav DETEKUJE (`already_committed_kept_original`), ale
                # samotný endpoint by bez týhle kontroly no-op apply
                # ZNOVU commitnul a přidal DRUHÝ `kept_original` marker.
                # Match podle `ch["draft_id"]`, NIKDY podle hashe textu
                # (kolo 10 plán-ping-pongu BLOCKING - stejný `cz_before`
                # se může legitimně opakovat napříč VÍCE nezávislými
                # `polish` běhy; hash by falešně přeskočil komit pro
                # ÚPLNĚ NOVÝ, nevyřízený draft) - když marker se STEJNÝM
                # `draft_id` UŽ existuje, TOHLE rozhodnutí bylo dřív
                # potvrzeno, zbývá jen dokončit úklid draftu.
                already = any(
                    f.get("source") == "stylist" and f.get("type") == "kept_original"
                    and f.get("draft_id") == ch["draft_id"]
                    for f in main._parse_findings(row["notes"]))
                if already:
                    draft["chapters"] = [c for c in draft["chapters"] if c["idx"] != idx]
                    try:
                        polish_store.save_draft(draft_path, draft)
                    except Exception as e:
                        return JSONResponse(
                            {"error": f"Zápis draftu selhal ({type(e).__name__}: "
                                      f"{e}) - rozhodnutí bylo dřív potvrzeno, jen "
                                      "se nepovedlo odebrat z fronty, zkus to znovu."},
                            status_code=500)
                    return {"ok": True}

            # Historie se NAČTE (a tím i validuje) PŘED jakýmkoli zápisem
            # do DB (kolo 2 plán-ping-pongu BLOCKING - dřív se `load_
            # history` volalo AŽ PO `commit_chapter_result`: poškozená
            # historie by pak nechala DB už změněnou, ale request by
            # spadl s nezachyceným `PolishStoreError` a draft by zůstal
            # viset pending bez historie). Startovní preflight v `build_
            # app` tohle pokrývá pro "poškozeno PŘED spuštěním serveru" -
            # tady navíc pro "poškozeno AŽ za běhu" (ruční zásah do
            # souboru mezitím).
            history, err = _try_load_history(history_path)
            if err:
                return err

            en = row["raw_text"]
            glossary_rows = glossary.all_terms(db_path)
            mentions = concordance.build_mentions(en, text, glossary_rows, ch["rendered_terms"])
            # Marker VŽDY popisuje `text` (co SKUTEČNĚ šlo do knihy),
            # NIKDY `cz_before`/`styled` (kolo 3 plán-ping-pongu IMPORTANT
            # - dřív `_stylist_marker(ch["cz_before"], ...)` popisoval
            # PŮVODNÍ text, ne uložený - auditní hash/délka by neseděly
            # s tím, co reálně skončilo v DB, zvlášť při ruční editaci).
            marker = (main._stylist_marker(text, draft["codex_model"]) if changed
                      else main._kept_original_marker(text, draft["codex_model"], ch["draft_id"]))
            findings = ch["findings"] + [marker]

            # Záloha + DB commit OBALENÉ (kolo 12 plán-ping-pongu IMPORTANT
            # - dřív bez ošetření propadly jako neřízená 500). `commit_
            # chapter_result` je JEDNA SQLite transakce (`src/state.py` -
            # "Výjimka kdekoli uvnitř = nic se necommitne"), takže selhání
            # TADY znamená JISTOTU, ne domněnku, že se DB nezměnila -
            # bezpečné vrátit jasné "text NEBYL uložen, zkus znovu".
            import json as _json
            try:
                main._backup_db_once(db_path, app.state.backup_state)
                state.commit_chapter_result(
                    db_path, idx, translated_text=text,
                    revision_rounds=row["revision_rounds"],   # z ŽIVÉ DB (kolo 2), ne z draftu
                    notes_json=_json.dumps(findings, ensure_ascii=False), status="done",
                    new_candidates=[], mentions=mentions, questions=[])
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text NEBYL uložen - záloha/DB commit selhal "
                              f"({type(e).__name__}: {e}) - zkus to znovu."},
                    status_code=500)

            # DB commit VÝŠ už proběhl a je NEODVOLATELNÝ - selhání
            # NÍŽE (disk plný, práva) je jiná třída chyby než selhání
            # PŘED commitem (kolo 5 plán-ping-pongu IMPORTANT - dřív se
            # tenhle rozdíl nikde neřekl, request by dostal obyčejnou
            # 500 bez vysvětlení, že kniha SE ZMĚNILA). `GET /api/polish`
            # (kolo 3/4 detekce) tenhle konkrétní stav sama najde příští
            # načtení stránky (DB už neodpovídá draftu/historii), takže
            # nejde o TICHOU korupci - jen o hůř formulovanou 500 bez
            # tyhle opravy.
            try:
                if changed:
                    history["entries"].append({
                        "idx": idx, "applied_at": polish_store.utc_now_z(),
                        "cz_before": ch["cz_before"], "cz_after": text,
                        "styled_by_codex": ch["styled"], "title": ch["title"],
                        "findings": findings, "rendered_terms": ch["rendered_terms"],
                        "source": "polish-review", "draft_id": ch["draft_id"]})
                    polish_store.save_history(history_path, history)

                draft["chapters"] = [c for c in draft["chapters"] if c["idx"] != idx]
                polish_store.save_draft(draft_path, draft)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text SE ULOŽIL do knihy úspěšně, ale zápis "
                              f"do historie/draftu selhal ({type(e).__name__}: "
                              f"{e}) - načti stránku znovu, `polish-review` "
                              "detekuje nesoulad a nabídne úklid přes "
                              "`discard`."}, status_code=500)
        return {"ok": True}

    @app.post("/api/polish/revert")
    def post_revert(payload: dict):
        idx_raw = payload.get("idx")
        # `type(x) is int` NE `isinstance` (kolo 3 plán-ping-pongu
        # BLOCKING - `bool` je podtřída `int`). Levná kontrola tvaru,
        # zůstává PŘED zámkem stejně jako u `apply`.
        if type(idx_raw) is not int:
            return JSONResponse({"error": "idx musí být int"}, status_code=400)
        idx = idx_raw
        to = payload.get("to", "previous")
        if to not in ("previous", "original"):
            return JSONResponse({"error": "to musí být previous/original"}, status_code=400)

        # CELÉ rozhodnutí - ověření zámku, draft-pending kontrola,
        # načtení historie, výpočet cíle, CAS, zápis - je JEDNA
        # atomická operace pod STEJNÝM zámkem (kolo 3 + kolo 4
        # plán-ping-pongu BLOCKING - stejný princip jako u `apply` výš,
        # včetně přesunu `require_lock()` dovnitř, ať čekání na
        # `write_lock` samo neudělá kontrolu zastaralou).
        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            draft, err = _try_load_draft(draft_path)
            if err:
                return err
            if any(c["idx"] == idx for c in draft["chapters"]):
                return JSONResponse(
                    {"error": "kapitola má nevyřízený draft z novějšího `polish` "
                              "běhu - nejdřív ho vyřeš (ulož nebo zahoď), pak zkus "
                              "revert znovu"}, status_code=409)

            history, err = _try_load_history(history_path)
            if err:
                return err
            entries = history["entries"]
            latest = polish_store.find_latest(entries, idx)
            if latest is None:
                return JSONResponse({"error": "kapitola nemá historii"}, status_code=404)
            target = polish_store.resolve_revert_target(entries, idx, to)

            row = state.get_chapter(db_path, idx)
            if row is None or row["translated_text"] != latest["cz_after"] or row["status"] != "done":
                return JSONResponse(
                    {"error": "kapitola se mezitím změnila mimo tenhle review"},
                    status_code=409)
            if target == row["translated_text"]:
                return {"ok": True, "noop": True}   # kolo 22 - žádný zápis

            import main
            en = state.get_chapter(db_path, idx)["raw_text"]
            glossary_rows = glossary.all_terms(db_path)
            mentions = concordance.build_mentions(en, target, glossary_rows, latest["rendered_terms"])
            # DB audit marker musí ukazovat, KTERÝ konkrétní historie-
            # záznam revert vysvětluje (review nález IMPORTANT) - dřív
            # jen slovní popis bez identifikace záznamu; `idx` je pozice
            # v `entries` (`is` identita, ne `==`, stejný princip jako
            # `_annotate_history`'s `find_latest(...) is e` výš - pole
            # DB `idx` znamená kapitolu, ne historii, proto tenhle
            # samostatný název).
            target_entry = latest if to == "previous" else polish_store.find_chain_start(entries, idx)
            entry_pos = next(i for i, e in enumerate(entries) if e is target_entry)
            note = (f"vráceno na verzi před poslední stylizací (historie "
                    f"idx={entry_pos}, applied_at={target_entry['applied_at']})"
                    if to == "previous" else
                    f"vráceno na verzi před JAKOUKOLI stylizací (historie "
                    f"idx={entry_pos}, applied_at={target_entry['applied_at']})")
            findings = concordance.check_chapter(en, target, glossary_rows,
                                                 latest["rendered_terms"]) + [main._revert_marker(note)]

            # Záloha + DB commit OBALENÉ (kolo 12 plán-ping-pongu IMPORTANT
            # - stejný princip jako u `apply` výš: `commit_chapter_result`
            # je JEDNA SQLite transakce, selhání tu tedy znamená JISTOTU,
            # ne domněnku, že se DB nezměnila).
            import json as _json
            try:
                main._backup_db_once(db_path, app.state.backup_state)
                state.commit_chapter_result(
                    db_path, idx, translated_text=target,
                    revision_rounds=row["revision_rounds"],   # ze ŽIVÉ DB (kolo 1 plán-ping-pongu IMPORTANT), ne natvrdo 0
                    notes_json=_json.dumps(findings, ensure_ascii=False), status="done",
                    new_candidates=[], mentions=mentions, questions=[])
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text NEBYL vrácen - záloha/DB commit selhal "
                              f"({type(e).__name__}: {e}) - zkus to znovu."},
                    status_code=500)

            # Stejný princip jako u `apply` výš (kolo 5 plán-ping-pongu
            # IMPORTANT) - DB commit už proběhl, selhání zápisu historie
            # NÍŽE je odlišná třída chyby, co si zaslouží jasnou zprávu.
            # `polish-review` DETEKUJE nesoulad (kolo 6 plán-ping-pongu
            # BLOCKING - dřív tohle tvrzení bylo nepravdivé: draftová
            # `_stale_info` revert vůbec nezachytí, protože revert žádný
            # draft nevytváří; `_annotate_history` teď navíc porovnává
            # DB text s `cz_after` NEJNOVĚJŠÍHO historie-záznamu a
            # označí ho `stale: true, reason: "db_diverged_from_history"`).
            try:
                history["entries"].append({
                    "idx": idx, "applied_at": polish_store.utc_now_z(),
                    "cz_before": row["translated_text"], "cz_after": target,
                    "styled_by_codex": "", "title": latest["title"], "findings": findings,
                    "rendered_terms": latest["rendered_terms"], "source": "revert",
                    # Čerstvé vlastní ID (kolo 15 plán-ping-pongu IMPORTANT) -
                    # revert nemá žádný vlastní draft, ale `draft_id` je teď
                    # POVINNÉ pole historie-schématu; unikátní hodnota tu
                    # zajistí, že tenhle záznam NIKDY nekoliduje se ŽÁDNÝM
                    # draftem v `_stale_info`'s `already_committed_has_
                    # history` matchi (ten porovnává PROTI `draft_ch["draft_id"]`).
                    "draft_id": uuid.uuid4().hex})
                polish_store.save_history(history_path, history)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text SE VRÁTIL v knize úspěšně, ale zápis do "
                              f"historie selhal ({type(e).__name__}: {e}) - "
                              "načti stránku znovu, `polish-review` detekuje "
                              "nesoulad."}, status_code=500)
        return {"ok": True}

    @app.post("/api/polish/discard")
    def post_discard(payload: dict):
        idx_raw = payload.get("idx")
        # `type(x) is int` NE `isinstance` (kolo 3 plán-ping-pongu
        # BLOCKING - `bool` je podtřída `int`). Levná kontrola tvaru,
        # zůstává PŘED zámkem.
        if type(idx_raw) is not int:
            return JSONResponse({"error": "idx musí být int"}, status_code=400)
        idx = idx_raw
        # `require_lock()` UVNITŘ zámku (kolo 4 plán-ping-pongu BLOCKING,
        # stejný princip jako u apply/revert výš).
        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            draft, err = _try_load_draft(draft_path)
            if err:
                return err
            draft["chapters"] = [c for c in draft["chapters"] if c["idx"] != idx]
            # discard NIKDY nesahá na DB - selhání zápisu draftu tu tedy
            # NENÍ post-commit třída chyby jako u apply/revert, ale pořád
            # by bez ošetření propadlo jako neřízená 500 (kolo 8
            # plán-ping-pongu IMPORTANT - dřív žádný try/except).
            try:
                polish_store.save_draft(draft_path, draft)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Zápis draftu selhal ({type(e).__name__}: {e}) - "
                              "kapitola zůstává ve frontě, zkus to znovu."},
                    status_code=500)
        return {"ok": True}

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
        except (KeyboardInterrupt, SystemExit):
            # `SystemExit` (code review nález IMPORTANT) - uvicorn 0.44
            # volá `sys.exit(1)` uvnitř `Server.startup()`, když se
            # nepodaří nabindovat port (adresa už obsazená apod.); bez
            # tyhle větve by `SystemExit` propagoval MIMO tuhle funkci a
            # porušil garanci "vrací VŽDY 0" ze spec (`finally` níž by
            # sice ještě proběhl, ale samotný `return 0` už ne).
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
