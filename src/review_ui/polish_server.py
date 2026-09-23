"""Lokální web UI pro ruční review stylistického průchodu (`polish`).
Na rozdíl od `server.py` (`review`) tenhle server BĚŽÍ, dokud ho uživatel
nezavře - může rozhodnout jen NĚKTERÉ kapitoly a zbytek nechat na příště.
Viz docs/superpowers/specs/2026-09-11-polish-review-design.md."""
import json
import os
import threading
import uuid
import webbrowser

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src import concordance, findings, findings_report, glossary, polish_store, state

_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

_LOCK_REFRESH_INTERVAL = state._LOCK_STALE_SECONDS // 2   # kolo 2


def _try_load_history(history_path: str):
    """`(history, None)` při úspěchu, `(None, JSONResponse)` při chybě -
    JEDNOTNÁ čitelná 500 pro poškozený `polish.history.json` napříč
    VŠEMI endpointy."""
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
            # kdyz `revert`/save DB commit uspeje, ale nasledny zapis
            # NOVEHO historie-zaznamu selze: historie porad konci STARYM
            # `cz_after`, DB uz ma NOVY text.
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


def build_app(db_path: str, history_path: str, lock_path: str) -> FastAPI:
    app = FastAPI(title="Book translator - polish review")
    write_lock = threading.Lock()          # kolo 2 - serializuje HTTP requesty
    # Preflight validace historie PŘI STARTU (kolo 2 plán-ping-pongu
    # BLOCKING) - poškozená historie musí server odmítnout spustit
    # rovnou, ne nechat vybouchnout uprostřed prvního save/revert
    # requestu (kdy uz může DB commit proběhnout dřív, než se poškození
    # zjistí). `PolishStoreError` odsud propaguje ven - `run_polish_
    # review_server` se prostě nespustí, stejný vzor jako selhání
    # `_snapshot_db` níž.
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
        return FileResponse(os.path.join(_STATIC, "chapters.html"))

    @app.get("/editor")
    def editor_page():
        return FileResponse(os.path.join(_STATIC, "editor.html"))

    @app.get("/api/chapters")
    def get_chapters():
        import main
        rows = state.chapters_by_status(
            db_path, ("pending", "processing", "done", "flagged",
                     "needs_human", "error"))
        out = []
        for row in sorted(rows, key=lambda r: r["idx"]):
            notes_findings = main._parse_findings(row["notes"])
            out.append({"idx": row["idx"], "title": row["title"],
                       "status": row["status"],
                       "unresolved_findings": findings.count_unresolved(notes_findings),
                       "updated_at": row["updated_at"]})
        return {"chapters": out}

    @app.get("/api/chapter/{idx}")
    def get_chapter_detail(idx: int):
        import main
        row = state.get_chapter(db_path, idx)
        if row is None:
            return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
        history, err = _try_load_history(history_path)
        if err:
            return err
        entries = history["entries"]
        latest = polish_store.find_latest(entries, idx)
        chain_start = polish_store.find_chain_start(entries, idx)
        # `notes` je JEDINÝ zdroj "aktuálních" nálezů (viz `build_findings_
        # report` docstring, Task 7) - `_commit_polish_result` zapisuje
        # STEJNÝ seznam do notes i do historie zároveň, sloučení by
        # zdvojilo každý nález.
        notes_findings = [f for f in main._parse_findings(row["notes"])
                          if not findings.is_marker(f)]
        own_history = [e for e in entries if e["idx"] == idx]
        return {
            "idx": row["idx"], "title": row["title"], "raw_text": row["raw_text"],
            "translated_text": row["translated_text"], "status": row["status"],
            "draft_text": row["draft_text"], "draft_updated_at": row["draft_updated_at"],
            "findings": notes_findings,
            "cz_before_original": chain_start["cz_before"] if chain_start else None,
            "styled_by_codex_latest": (latest["styled_by_codex"]
                                       if latest and latest["styled_by_codex"] else None),
            "history": _annotate_history(db_path, entries, own_history),
        }

    _EDITABLE_STATUSES = ("done", "flagged", "needs_human", "error")

    def _chapter_is_editable(row) -> bool:
        """`pending` je editovatelná JEN když MÁ existující `translated_text`
        - `state.commit_answer` (requeue po odpovědi na otázku) mění JEN
        `status`, text nemaže, takže "pending kvůli requeue" má co
        editovat, ale "pending, co nikdy nebyla přeložena" ne. Ruční
        oprava přímo v editoru je pak platná alternativa k čekání na
        `run` - uživatelův požadavek (2026-09-23): "problém přeložím
        jinak, žádná otázka nezbyde, kapitola nemusí čekat na retranslate"."""
        if row["status"] in _EDITABLE_STATUSES:
            return True
        return row["status"] == "pending" and row["translated_text"] is not None

    def _valid_finding_shape(f) -> bool:
        if not isinstance(f, dict):
            return False
        for key in ("id", "source", "type", "issue", "severity"):
            if key in f and f[key] is not None and not isinstance(f[key], str):
                return False
        if "id" in f and f["id"] == "":
            return False
        if "resolved" in f and not isinstance(f["resolved"], bool):
            return False
        return True

    def _no_duplicate_ids(findings_list: list) -> bool:
        ids = [f["id"] for f in findings_list if isinstance(f.get("id"), str) and f["id"]]
        return len(ids) == len(set(ids))

    def _merge_findings_by_id(current_findings: list, incoming: list, *,
                              known_ids: "set | None" = None) -> list:
        """Sloučí ULOŽENÉ nálezy (`current_findings`, včetně auditních
        markerů - GET je klientovi nikdy neposílá zpátky, takže jejich `id`
        se s `incoming` nikdy nepřekryje) s tím, co poslal klient
        (`incoming`, UŽ prošlé `findings.assign_ids`). Markery se ZACHOVÁVAJÍ
        VŽDY (nikdy se nemažou - append-only audit log). Server-side
        `resolved` je AUTORITATIVNÍ pro KAŽDÉ `id`, co server už zná.

        `known_ids` - klientova vlastní představa "který nález jsem znal
        PŘI NAČTENÍ" (`PERSISTED_IDS` z GET, Task 14). Non-marker nález z
        `current_findings`, co NENÍ v `incoming`, se NEPŘENESE JEN KDYŽ
        jeho `id` JE v `known_ids` (klient ho znal - buď ho superseduje
        čerstvou regenerací, nebo ho prostě zahodil). Nález, co klient
        NIKDY neznal (přidal ho JINÝ požadavek MEZI klientovým GET a
        týmhle save), se ZACHOVÁ i když ho `incoming` neobsahuje - karta-B-
        přidala-nález race zůstává chráněný. "Nikdy nic nemaže" (markery
        vždy, non-markery když nejsou v `known_ids`) PŘEDPOKLÁDÁ platná,
        unikátní `id` - `current_findings` bez `id` se do `current_by_id`
        vůbec nedostanou a `_merge_findings_by_id` je TICHE VYNECHÁ z
        výsledku."""
        if known_ids is None:
            known_ids = set()
        current_by_id = {f["id"]: f for f in current_findings if f.get("id")}
        incoming_ids = {f["id"] for f in incoming}
        merged_by_id = {fid: f for fid, f in current_by_id.items()
                        if findings.is_marker(f) or fid in incoming_ids
                        or fid not in known_ids}
        for f in incoming:
            fid = f["id"]
            if fid in current_by_id:
                f["resolved"] = current_by_id[fid].get("resolved", f.get("resolved"))
            merged_by_id[fid] = f
        return list(merged_by_id.values())

    @app.post("/api/chapter/{idx}/draft")
    def post_draft_chapter(idx: int, payload: dict):
        """Uloží ROZPRACOVANÝ koncept (2026-09-23) - beze změny status/
        translated_text, dostupné z JINÉHO počítače/prohlížeče (na rozdíl
        od localStorage). Bez CAS kontroly ("cz_before") záměrně - koncept
        je nízko-rizikový, poslední zápis vyhrává, na rozdíl od finálního
        "Uložit a dokončit" (post_save_chapter), co CAS potřebuje."""
        text = payload.get("text")
        if not isinstance(text, str):
            return JSONResponse({"error": "text musí být string"}, status_code=400)
        row = state.get_chapter(db_path, idx)
        if row is None:
            return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            state.save_chapter_draft(db_path, idx, text)
        return {"ok": True}

    @app.post("/api/chapter/{idx}/draft/discard")
    def post_discard_draft(idx: int):
        row = state.get_chapter(db_path, idx)
        if row is None:
            return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            state.clear_chapter_draft(db_path, idx)
        return {"ok": True}

    @app.post("/api/chapter/{idx}/save")
    def post_save_chapter(idx: int, payload: dict):
        cz_before = payload.get("cz_before")
        text = payload.get("text")
        raw_findings = payload.get("findings")
        styled_by_codex = payload.get("styled_by_codex", "")
        known_ids_raw = payload.get("known_ids")
        if known_ids_raw is None:
            known_ids_raw = []
        if (not isinstance(cz_before, str) or not isinstance(text, str)
                or not isinstance(raw_findings, list)
                or not all(_valid_finding_shape(f) for f in raw_findings)
                or not _no_duplicate_ids(raw_findings)
                or not isinstance(styled_by_codex, str)
                or not isinstance(known_ids_raw, list)
                or not all(isinstance(x, str) for x in known_ids_raw)):
            return JSONResponse(
                {"error": "cz_before/text/styled_by_codex musí být string, "
                          "findings musí být pole objektů se správnými typy "
                          "a unikátními id, known_ids (pokud přítomné) musí "
                          "být pole stringů"},
                status_code=400)

        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            row = state.get_chapter(db_path, idx)
            if (row is None or row["translated_text"] != cz_before
                    or not _chapter_is_editable(row)):
                return JSONResponse(
                    {"error": "kapitola se mezitím změnila mimo tenhle editor, "
                              "nebo nemá stav vhodný k uložení - načti stránku "
                              "znovu"}, status_code=409)
            import main
            if text == cz_before:
                current_findings = main._parse_findings(row["notes"])
                light_findings = _merge_findings_by_id(
                    current_findings, findings.assign_ids(list(raw_findings)),
                    known_ids=set(known_ids_raw))
                if (row["status"] == "done"
                        and json.dumps(light_findings, ensure_ascii=False)
                        == json.dumps(current_findings, ensure_ascii=False)):
                    return {"ok": True, "noop": True}
                try:
                    main._backup_db_once(db_path, app.state.backup_state)
                    with state.connect(db_path) as conn:
                        conn.execute(
                            "UPDATE chapters SET notes=?, status='done', "
                            "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                            (json.dumps(light_findings, ensure_ascii=False), idx))
                    # Finalizace (i beze změny textu) - starý koncept by
                    # jinak matl příští otevření editoru (2026-09-23).
                    state.clear_chapter_draft(db_path, idx)
                except Exception as e:
                    return JSONResponse(
                        {"error": f"Nálezy/stav se nepodařilo uložit "
                                  f"({type(e).__name__}: {e}) - zkus to znovu."},
                        status_code=500)
                return {"ok": True, "noop": False}

            en = row["raw_text"]
            glossary_rows = glossary.all_terms(db_path)
            resolved_findings = _merge_findings_by_id(
                main._parse_findings(row["notes"]), findings.assign_ids(list(raw_findings)),
                known_ids=set(known_ids_raw))
            try:
                main._commit_polish_result(
                    db_path, history_path, idx, en=en, cz_before=cz_before,
                    final_text=text, findings=resolved_findings,
                    glossary_rows=glossary_rows,
                    revision_rounds=row["revision_rounds"], source="polish-review",
                    model_label="ruční úprava (polish-review)",
                    styled_by_codex=styled_by_codex, backup_state=app.state.backup_state)
            except main.HistoryWriteFailedAfterCommit as e:
                return JSONResponse(
                    {"error": f"Text SE ULOŽIL do knihy úspěšně, ale zápis "
                              f"do historie selhal ({e}) - načti stránku "
                              "znovu, tenhle konkrétní zápis se NEOPAKUJ "
                              "(CAS by ho stejně odmítl)."}, status_code=500)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text NEBYL uložen ({type(e).__name__}: {e}) - "
                              "zkus to znovu."}, status_code=500)
            # Finalizace - starý koncept by jinak matl příští otevření
            # editoru (2026-09-23). `_commit_polish_result` už DB commit
            # dokončil úspěšně, tohle je nezávislý, ne-kritický úklid.
            state.clear_chapter_draft(db_path, idx)
        return {"ok": True}

    @app.post("/api/polish/regenerate")
    def post_regenerate(payload: dict):
        idx_raw = payload.get("idx")
        if type(idx_raw) is not int:
            return JSONResponse({"error": "idx musí být int"}, status_code=400)
        idx = idx_raw
        import main
        row = state.get_chapter(db_path, idx)
        if row is None:
            return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
        # `status not in _EDITABLE_STATUSES` NESTAČÍ (kolo 5 IMPORTANT) -
        # `run`/`_cmd_run` může nastavit `status="error"` PŘI PRVNÍM
        # neúspěšném pokusu o překlad, s `translated_text` pořád `NULL`
        # (main.py, `_cmd_run`/`pipeline.process_chapter`). `stylist.
        # polish(en, cz, ...)` s `cz=None` by spadlo na typové chybě
        # hluboko uvnitř `_polish_one_chapter`, ne na čitelné 400 tady.
        if not _chapter_is_editable(row) or row["translated_text"] is None:
            return JSONResponse(
                {"error": f"kapitola má status {row['status']!r} bez použitelného "
                          "textu, nelze polishovat"}, status_code=400)
        model, codex_cmd, preflight_err = main._polish_preflight()
        if preflight_err:
            return JSONResponse({"error": preflight_err}, status_code=503)
        # Kolo 2 IMPORTANT (plan-consensus) - stejný důvod jako `_cmd_
        # run`/`_cmd_polish` (main.py) - regenerate taky volá kritika
        # PO drahé Codex stylizaci.
        claude_cmd, claude_preflight_err = main._claude_cli_preflight()
        if claude_preflight_err:
            return JSONResponse({"error": claude_preflight_err}, status_code=503)
        # Kolo 3 BLOCKING (plan-consensus) - `stylist_check` (main.py's
        # `_polish_one_chapter`) zůstává MIMO rozsah (pořád `Anthropic
        # Client`/`ANTHROPIC_API_KEY`) - stejný důvod jako `_cmd_polish`
        # (main.py) výš.
        if not main.config.ANTHROPIC_API_KEY:
            return JSONResponse(
                {"error": "polish vyžaduje funkční Claude API pro "
                          "stylist_check: Chybí ANTHROPIC_API_KEY "
                          "v prostředí."}, status_code=503)
        # Kolo 13 IMPORTANT - `glossary.all_terms` (čtení, žádný zápis)
        # PŘESUNUTO PŘED kontrolu zámku, ne po ní - kontrola má být
        # POSLEDNÍ věc před PRVNÍM zápisem (`create_run` níž), ne mít
        # mezi sebou další volání (byť rychlé/lokální), co by teoreticky
        # mohlo o chvilku prodloužit okno.
        glossary_rows = glossary.all_terms(db_path)
        # Levná kontrola vlastnictví zámku (NE `write_lock` - `runs`/
        # `llm_calls` bookkeeping se nepřekrývá s kapitolovými zápisy
        # jiných requestů, serializace by jen zbytečně blokovala save/
        # export na JINÝCH kapitolách po dobu Codex volání).
        if not app.state.require_lock():
            return JSONResponse({"error": "zámek ztracen"}, status_code=503)

        rid = None
        status = "fatal"
        try:
            rid = state.create_run(db_path, "polish")
            # `interactive=False` - NIKDY True na serveru (cost-guard
            # `input()` by zablokoval HTTP request bez terminálu, viz
            # "Poznámka k zámku"). `require_lock=app.state.require_lock`
            # (kolo 11 BLOCKING) - `PipelineLLMClient` teď ověří zámek
            # PŘED KAŽDÝM `.complete()` (kritik/stylist_check volání
            # uvnitř `_polish_one_chapter`), ne jen jednou na začátku
            # handleru.
            cf = main._client_factory(rid, interactive=False,
                                      require_lock=app.state.require_lock,
                                      claude_cmd=claude_cmd)
            c = {"idx": row["idx"], "title": row["title"], "raw_text": row["raw_text"],
                "translated_text": row["translated_text"],
                "revision_rounds": row["revision_rounds"]}
            # STEJNÁ `rendered_terms` volba jako dávka/save (kolo 5
            # IMPORTANT konzistence, viz Task 3/5) - i PŘEDBĚŽNÝ náhled
            # z regenerace má ukázat nálezy odpovídající tomu, co by
            # SKUTEČNĚ zapsalo uložení téhle regenerace.
            history, err = _try_load_history(history_path)
            if err:
                return err
            rt = main._preferred_rendered_terms(
                db_path, idx, row["translated_text"], history["entries"])
            rec = main._polish_one_chapter(c, glossary_rows, cf, db_path, model, codex_cmd,
                                           rendered_terms=rt)
            # `status="ok"` i pro `rec["outcome"] == "failed"` (Codex CLI
            # selhal, ne infrastruktura) - stejná konvence jako dávkový
            # `_cmd_polish` (per-kapitolové selhání NEznamená `run_status
            # ="fatal"`, jen `FatalRunError`/výjimka odsud výš to udělá).
            status = "ok"
        except main.LockLostError as e:
            # Kolo 16 IMPORTANT - STEJNÁ podmínka jako startovní `require_
            # lock()` kontrola výš (ta vrací 503) - ztráta zámku uvnitř
            # `PipelineLLMClient.complete()` (kritik/stylist_check volání)
            # musí dostat STEJNÝ kód, ne obecnou 500 z větve níž. `except`
            # POŘADÍ je významné - specifičtější MUSÍ být PŘED obecným
            # `except Exception`, jinak by ho ten odchytil dřív.
            return JSONResponse({"error": f"Zámek ztracen: {e}"}, status_code=503)
        except Exception as e:
            return JSONResponse(
                {"error": f"Regenerace selhala ({type(e).__name__}: {e})"},
                status_code=500)
        finally:
            # `finish_run` selhání NESMÍ přebít odpověď výš (kolo 2
            # BLOCKING) - výjimka vyhozená z `finally` by nahradila i
            # `return` z `except` bloku nezachycenou 500 bez JSON těla.
            # Bookkeeping chyba tu je jen diagnostická ztráta, ne důvod
            # zahodit skutečný výsledek regenerace.
            #
            # Kolo 10 IMPORTANT - znovu ověř zámek TĚSNĚ PŘED zápisem -
            # `_polish_one_chapter` (řádek výš) může u pomalé Codex
            # odpovědi běžet dlouho - `require_lock()` na ZAČÁTKU handleru
            # (výš) ověřilo vlastnictví PŘED voláním, ale samo o sobě
            # nezaručuje, že ho pořád vlastníme O CHVÍLI POZDĚJI.
            try:
                if rid is not None and app.state.require_lock():
                    state.finish_run(db_path, rid, status)
            except Exception:
                pass
        if "outcome" in rec:
            return JSONResponse(
                {"error": f"Codex nenavrhl žádnou úpravu ({rec.get('outcome')})"
                          if rec.get("outcome") == "unchanged"
                          else f"Stylizace selhala ({rec.get('error')})"},
                status_code=422)
        return {"styled": rec["styled"], "findings": rec["findings"],
                "reason_types": rec["reason_types"]}

    @app.post("/api/findings/resolve")
    def post_resolve_finding(payload: dict):
        scope = payload.get("scope")
        idx_raw = payload.get("idx")
        finding_id = payload.get("finding_id")
        resolved = payload.get("resolved")
        # Kolo 17 IMPORTANT - `scope="history"` ODSTRANĚNA. Editovala
        # `polish.history.json` NEZÁVISLE na `chapters.notes`, co ale
        # UI/report (Task 8 GET, Task 12 report) čtou jako JEDINÝ zdroj
        # "aktuálního" stavu nálezů - "history" resolve by tiše vrátilo
        # 200, žádný checkbox/počet by se ale NEZMĚNIL, a stejný nález
        # (jiné `id`, protože `assign_ids` generuje NEZÁVISLE napříč
        # `notes`/historií) by mohl mít DIVERGENTNÍ `resolved` hodnotu na
        # dvou místech. Navíc ŽÁDNÝ prvek UI ji nikdy nevolal - `toggle
        # Resolved` (Task 14) posílá VŽDY `scope: 'notes'` natvrdo -
        # mrtvý, matoucí kód. `scope` pole v payloadu ZŮSTÁVÁ (ne
        # zjednodušeno pryč) kvůli vpřed kompatibilitě kontraktu.
        if (scope != "notes" or type(idx_raw) is not int
                or not isinstance(finding_id, str) or not isinstance(resolved, bool)):
            return JSONResponse(
                {"error": "scope musí být notes, idx int, finding_id "
                          "string, resolved bool"}, status_code=400)
        idx = idx_raw

        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            import main
            row = state.get_chapter(db_path, idx)
            if row is None:
                return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
            notes_findings = main._parse_findings(row["notes"])
            if not findings.set_resolved(notes_findings, finding_id, resolved):
                return JSONResponse({"error": "nález nenalezen"}, status_code=404)
            try:
                # Kolo 22 IMPORTANT - `_backup_db_once` CHYBĚLO - OBĚ
                # větve Tasku 9 ho volají (přímo nebo přes `_commit_
                # polish_result`), tenhle endpoint ne. Pokud je resolve
                # PRVNÍ mutující operace v týhle serverové session (user
                # otevře editor a rovnou něco zaškrtne, nikdy neuloží/
                # neregeneruje), `backup_state["done"]` zůstane `False` -
                # startovní snapshot (vytvořený PŘI STARTU serveru) se
                # při čistém vypnutí smaže (`finally` v `run_polish_
                # review_server`, "if not backup_state['done']: os.remove
                # (...)") a uživatel PŘIJDE o obnovitelnou zálohu stavu
                # PŘED touhle session, přestože reálný DB zápis proběhl.
                main._backup_db_once(db_path, app.state.backup_state)
                with state.connect(db_path) as conn:
                    # Kolo 18 NIT - `updated_at=CURRENT_TIMESTAMP` chybělo -
                    # seznam kapitol (Task 8/14) zobrazuje "Naposled
                    # upraveno" z tohohle sloupce, bez aktualizace by po
                    # zaškrtnutí nálezu ukazoval STARÝ čas, i když se
                    # kapitola právě změnila.
                    conn.execute("UPDATE chapters SET notes=?, "
                                "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                                (json.dumps(notes_findings, ensure_ascii=False), idx))
            except Exception as e:
                return JSONResponse(
                    {"error": f"Zápis nálezu selhal ({type(e).__name__}: {e})"},
                    status_code=500)
        return {"ok": True}

    @app.get("/findings")
    def get_findings_page():
        from fastapi.responses import HTMLResponse
        report = findings_report.build_findings_report(db_path)
        return HTMLResponse(findings_report.render_findings_html(report))

    @app.post("/api/export")
    def post_export(payload: dict = None):
        # `write_lock` - NENÍ tu zápis do DB, ale export musí vidět
        # KONZISTENTNÍ snímek knihy (Global Constraints). Souběžný
        # `POST /api/chapter/{idx}/save` (Task 9) běží uvnitř STEJNÉHO
        # `write_lock` - bez obalení tady by export mohl přečíst část
        # kapitol PŘED a část PO souběžném uložení, kniha+report by pak
        # neodpovídaly ŽÁDNÉMU skutečnému stavu DB. `require_lock()`
        # navíc odmítne export, když tenhle proces ztratil vlastnictví
        # zámku (jiný proces teď legitimně píše mimo tenhle server).
        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            import main
            book_path, skipped = main.export_book(db_path, only_done=False)
            report = findings_report.build_findings_report(db_path)
            findings_path = os.path.splitext(book_path)[0] + ".findings.txt"
            with open(findings_path, "w", encoding="utf-8") as f:
                f.write(findings_report.render_findings_txt(report))
        return {"book_path": book_path, "findings_path": findings_path,
               "skipped": skipped}

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
            revert_findings = findings.assign_ids(
                concordance.check_chapter(en, target, glossary_rows,
                                          latest["rendered_terms"])
                + [main._revert_marker(note)])

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
                    notes_json=_json.dumps(revert_findings, ensure_ascii=False), status="done",
                    new_candidates=[], mentions=mentions, questions=[])
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text NEBYL vrácen - záloha/DB commit selhal "
                              f"({type(e).__name__}: {e}) - zkus to znovu."},
                    status_code=500)

            # DB commit už proběhl, selhání zápisu historie NÍŽE je
            # odlišná třída chyby, co si zaslouží jasnou zprávu.
            # `_annotate_history` porovnává DB text s `cz_after`
            # NEJNOVĚJŠÍHO historie-záznamu a označí případný nesoulad
            # `stale: true, reason: "db_diverged_from_history"`.
            try:
                history["entries"].append({
                    "idx": idx, "applied_at": polish_store.utc_now_z(),
                    "cz_before": row["translated_text"], "cz_after": target,
                    "styled_by_codex": "", "title": latest["title"], "findings": revert_findings,
                    "rendered_terms": latest["rendered_terms"], "source": "revert",
                    "draft_id": uuid.uuid4().hex})   # povinné pole historie-schématu, unikátní
                polish_store.save_history(history_path, history)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text SE VRÁTIL v knize úspěšně, ale zápis do "
                              f"historie selhal ({type(e).__name__}: {e}) - "
                              "načti stránku znovu, `polish-review` detekuje "
                              "nesoulad."}, status_code=500)
        return {"ok": True}

    app.state.write_lock = write_lock
    app.state.lock_lost = lock_lost
    app.state.shutdown_heartbeat = shutdown
    app.state.heartbeat_thread = heartbeat_thread
    app.state.require_lock = _require_lock
    app.state.backup_state = backup_state
    app.state.db_path = db_path
    app.state.history_path = history_path
    return app


def run_polish_review_server(db_path: str, history_path: str,
                             lock_path: str, *, host: str = "127.0.0.1",
                             port: int = 8766) -> int:
    """Vrací VŽDY 0 - žádný CLI krok po `polish-review` nezávisí na tom,
    jestli něco bylo rozhodnuto (spec)."""
    import uvicorn
    app = build_app(db_path, history_path, lock_path)
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
