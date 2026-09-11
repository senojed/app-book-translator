import os, json, sys
import main
from src import state


def _run(argv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("config.DATA_DIR", "data")
    monkeypatch.setattr("config.DB_PATH", "data/state.sqlite3")
    monkeypatch.setattr("config.GUIDE_DRAFT_PATH", "data/guide.draft.json")
    monkeypatch.setattr("config.GUIDE_PATH", "data/guide.json")
    monkeypatch.setattr("config.LOCK_PATH", "data/.lock")
    monkeypatch.setattr("config.OUTPUT_TXT", "output/kniha_cz.txt")
    return main.main(argv)


def test_init_seeds_chapters(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "text " * 60 + "\nChapter 2\n" + "text " * 60,
                    encoding="utf-8")
    assert _run(["init", str(book)], tmp_path, monkeypatch) == 0
    assert len(state.chapters_by_status("data/state.sqlite3", ("pending",))) == 2


def test_status_runs_without_db_error(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "text " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    assert _run(["status"], tmp_path, monkeypatch) == 0


def test_reinit_refuses_without_reset_and_reset_replaces(tmp_path, monkeypatch):
    b1 = tmp_path / "b1.txt"
    b1.write_text("".join(f"Chapter {i}\n" + "t " * 60 + "\n" for i in range(1, 6)),
                  encoding="utf-8")
    _run(["init", str(b1)], tmp_path, monkeypatch)
    assert len(state.chapters_by_status("data/state.sqlite3", ("pending",))) == 5
    b2 = tmp_path / "b2.txt"
    b2.write_text("Chapter 1\n" + "t " * 60 + "\nChapter 2\n" + "t " * 60, encoding="utf-8")
    assert _run(["init", str(b2)], tmp_path, monkeypatch) == 1   # odmítne bez --reset
    assert len(state.chapters_by_status("data/state.sqlite3", ("pending",))) == 5
    assert _run(["init", str(b2), "--reset"], tmp_path, monkeypatch) == 0
    chs = state.chapters_by_status("data/state.sqlite3", ("pending",))
    assert len(chs) == 2   # nahrazeno, žádné stale kapitoly 3-5


def test_answer_empty_text_is_controlled_error(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    state.upsert_open_question("data/state.sqlite3", {"chapter_idx": 1, "kind": "term",
        "text": "?", "scope_key": "t1", "guess_answer": None, "severity": "guess"})
    assert _run(["answer", "1", "   "], tmp_path, monkeypatch) == 1   # ne stacktrace


def _init_4ch(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    body = "t " * 60
    book.write_text("".join(f"Chapter {i}\n{body}\n" for i in range(1, 5)), encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    db = "data/state.sqlite3"
    state.update_chapter(db, 1, status="done", translated_text="Kapitola 1 CZ.")
    state.update_chapter(db, 2, status="flagged", translated_text="Kapitola 2 CZ.",
                         notes=json.dumps([{"issue": "nekonzistentní termín",
                                            "action": "revise"}]))
    state.update_chapter(db, 3, status="needs_human", translated_text="")
    state.update_chapter(db, 4, status="error", notes='{"error":"X"}')
    return db


def test_export_full_markers(tmp_path, monkeypatch, capsys):
    db = _init_4ch(tmp_path, monkeypatch)
    before = {c["idx"]: c["status"] for c in state.chapters_by_status(
        db, ("done", "flagged", "needs_human", "error"))}
    assert _run(["export"], tmp_path, monkeypatch) == 0
    text = open("output/kniha_cz.txt", encoding="utf-8").read()
    assert "Kapitola 1 CZ." in text
    assert "Kapitola 2 CZ." in text and "REVIDOVAT" in text
    assert "CHYBÍ KAPITOLA 3" in text and "CHYBÍ KAPITOLA 4" in text
    out = capsys.readouterr().out
    assert "3" in out and "4" in out          # varování na stdout o vynechaných
    after = {c["idx"]: c["status"] for c in state.chapters_by_status(
        db, ("done", "flagged", "needs_human", "error"))}
    assert before == after                     # export je read-only


def test_export_only_done(tmp_path, monkeypatch, capsys):
    _init_4ch(tmp_path, monkeypatch)
    assert _run(["export", "--only-done"], tmp_path, monkeypatch) == 0
    text = open("output/kniha_cz.txt", encoding="utf-8").read()
    assert "Kapitola 1 CZ." in text
    assert "Kapitola 2 CZ." not in text        # flagged vynechána
    assert "REVIDOVAT" not in text and "CHYBÍ KAPITOLA" not in text
    assert "2" in capsys.readouterr().out       # ale seznam vynechaných na stdout


def test_run_processes_queue_with_monkeypatched_pipeline(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.pipeline as P
    def fake_process(db_path, chapter, *, client_factory, guide):
        state.update_chapter(db_path, chapter["idx"], status="done",
                             translated_text="hotovo")
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", fake_process)
    assert _run(["run"], tmp_path, monkeypatch) == 0
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "done"
    with state.connect("data/state.sqlite3") as conn:
        r = conn.execute("SELECT status, ended_at FROM runs ORDER BY id DESC "
                         "LIMIT 1").fetchone()
    assert r["status"] == "ok" and r["ended_at"] is not None  # run se uzavřel


def test_run_fatal_error_closes_run_and_exits_nonzero(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.pipeline as P
    from src.llm.client import FatalRunError
    def boom(*a, **k): raise FatalRunError("bad key")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] in ("pending", "processing")
    with state.connect("data/state.sqlite3") as conn:
        r = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    assert r["status"] == "fatal"


def test_run_without_guide_json_still_works(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.pipeline as P
    def fake(db_path, chapter, *, client_factory, guide):
        assert isinstance(guide, dict) and "characters" in guide  # prázdný shape OK
        state.update_chapter(db_path, chapter["idx"], status="done", translated_text="x")
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", fake)
    assert _run(["run"], tmp_path, monkeypatch) == 0   # guide.json neexistuje, přesto OK


def test_scan_scout_truncated_is_fatal_no_draft(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.agents.scout as SC
    from src.llm.client import OutputTruncated
    monkeypatch.setattr(SC, "scan_book", lambda *a, **k: (_ for _ in ()).throw(
        OutputTruncated("useknuto")))
    assert _run(["scan"], tmp_path, monkeypatch) == 1
    assert not os.path.exists("data/guide.draft.json")
    with state.connect("data/state.sqlite3") as conn:
        assert conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1"
                            ).fetchone()["status"] == "fatal"


def test_scan_scout_bad_json_is_fatal(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.agents.scout as SC
    monkeypatch.setattr(SC, "scan_book", lambda *a, **k: (_ for _ in ()).throw(
        ValueError("rozbitý JSON")))
    assert _run(["scan"], tmp_path, monkeypatch) == 1


def test_review_reseeds_on_success(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.review_ui.server as SRV
    from src import guide as G, glossary
    def fake_ok(*a, **k):
        G.save_guide("data/guide.json", {"characters": [{"name_en": "Harry",
            "render": "keep"}], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": []})
        return 0
    monkeypatch.setattr(SRV, "run_review_server", fake_ok)
    assert _run(["review"], tmp_path, monkeypatch) == 0
    assert any(t["canonical_en"] == "Harry" and t["status"] == "seeded"
               for t in glossary.all_terms("data/state.sqlite3"))


def test_review_does_not_reseed_on_failure(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.review_ui.server as SRV
    from src import guide as G, glossary
    def fake_fail(*a, **k):
        # UI "uložilo" guide, ale server skončil chybou (rc=1)
        G.save_guide("data/guide.json", {"characters": [{"name_en": "Zed",
            "render": "keep"}], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": []})
        return 1
    monkeypatch.setattr(SRV, "run_review_server", fake_fail)
    rc = _run(["review"], tmp_path, monkeypatch)
    assert rc == 1
    assert glossary.all_terms("data/state.sqlite3") == []   # ŽÁDNÝ reseed


def _init_4ch_pending(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    body = "t " * 60
    book.write_text("".join(f"Chapter {i}\n{body}\n" for i in range(1, 5)), encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    return "data/state.sqlite3"


def test_run_only_processes_selected_chapters(tmp_path, monkeypatch):
    db = _init_4ch_pending(tmp_path, monkeypatch)
    import src.pipeline as P
    seen = []
    def fake(db_path, chapter, *, client_factory, guide):
        seen.append(chapter["idx"])
        state.update_chapter(db_path, chapter["idx"], status="done", translated_text="x")
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", fake)
    assert _run(["run", "--only", "1", "3"], tmp_path, monkeypatch) == 0
    assert seen == [1, 3]
    assert state.get_chapter(db, 2)["status"] == "pending"   # nedotčené
    assert state.get_chapter(db, 4)["status"] == "pending"


def test_run_without_only_still_takes_whole_queue(tmp_path, monkeypatch):
    db = _init_4ch_pending(tmp_path, monkeypatch)
    import src.pipeline as P
    seen = []
    def fake(db_path, chapter, *, client_factory, guide):
        seen.append(chapter["idx"])
        state.update_chapter(db_path, chapter["idx"], status="done", translated_text="x")
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", fake)
    assert _run(["run"], tmp_path, monkeypatch) == 0
    assert seen == [1, 2, 3, 4]


def test_reference_requires_scan_first(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    # guide.draft.json neexistuje
    assert _run(["reference", "--dir", str(tmp_path / "ref")], tmp_path, monkeypatch) == 1


def test_reference_missing_dir_is_fatal(tmp_path, monkeypatch):
    import json as _json
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    _json.dump({"characters": [], "places": [], "terms": [], "relationships": [],
                "style_notes": "", "must_decide": []},
               open("data/guide.draft.json", "w", encoding="utf-8"))
    assert _run(["reference", "--dir", str(tmp_path / "neexistuje")],
                tmp_path, monkeypatch) == 1
    assert not os.path.exists("data/reference.json")


def test_reference_writes_findings_and_closes_run(tmp_path, monkeypatch):
    import json as _json
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    _json.dump({"characters": [], "places": [],
                "terms": [{"term_en": "Nevernever", "suggested_cz": "N", "note": ""}],
                "relationships": [], "style_notes": "", "must_decide": []},
               open("data/guide.draft.json", "w", encoding="utf-8"))
    import src.reference as R
    import src.reference_mine as M
    monkeypatch.setattr(R, "load_corpus", lambda root: R.Corpus(
        cz={1: "Nevernever tady je uprostřed věty.", 2: "a Nevernever zase.",
            3: "Nevernever potřetí uprostřed."},
        en={1: "Nevernever", 2: "Nevernever", 3: "Nevernever"},
        manifest={}, source_root=root))
    monkeypatch.setattr(R, "load_cache", lambda p, r: None)
    monkeypatch.setattr(R, "save_cache", lambda c, p: None)
    ref_dir = tmp_path / "ref"; ref_dir.mkdir()
    assert _run(["reference", "--dir", str(ref_dir)], tmp_path, monkeypatch) == 0
    data = M.load_reference("data/reference.json")
    assert data["findings"][0]["classification"] in ("confirmed", "weak")
    with state.connect("data/state.sqlite3") as conn:
        r = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    assert r["status"] == "ok"


def test_reference_failure_leaves_previous_file_untouched(tmp_path, monkeypatch):
    import json as _json
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    _json.dump({"characters": [], "places": [],
                "terms": [{"term_en": "Foo", "suggested_cz": "", "note": ""}],
                "relationships": [], "style_notes": "", "must_decide": []},
               open("data/guide.draft.json", "w", encoding="utf-8"))
    os.makedirs("data", exist_ok=True)
    with open("data/reference.json", "w", encoding="utf-8") as f:
        f.write('{"schema_version": 1, "run_id": 0, "source_root": "/old", '
                '"fingerprint": {}, "findings": []}')
    before = open("data/reference.json", encoding="utf-8").read()
    import src.reference as R
    monkeypatch.setattr(R, "load_corpus", lambda root: (_ for _ in ()).throw(
        ValueError("korpus je rozbitý")))
    monkeypatch.setattr(R, "load_cache", lambda p, r: None)
    ref_dir = tmp_path / "ref"; ref_dir.mkdir()
    assert _run(["reference", "--dir", str(ref_dir)], tmp_path, monkeypatch) == 1
    assert open("data/reference.json", encoding="utf-8").read() == before


# --- Task 7: main.py pomocné funkce pro polish -------------------------------

def test_say_swallows_broken_pipe(monkeypatch):
    def _boom(*a, **kw):
        raise BrokenPipeError()
    monkeypatch.setattr("builtins.print", _boom)
    main._say("cokoli")   # nesmí vyhodit


def test_parse_findings_tolerates_non_list_and_broken_json():
    assert main._parse_findings("{}") == []
    assert main._parse_findings("nonsense") == []
    assert main._parse_findings(None) == []
    assert main._parse_findings('[{"source":"x"},1,"y"]') == [{"source": "x"}]


def test_already_styled_detects_marker():
    assert main._already_styled('[{"source":"stylist","type":"polish"}]') is True
    assert main._already_styled('[{"source":"concordance"}]') is False
    assert main._already_styled(None) is False


def test_stylist_marker_shape_and_hash():
    m = main._stylist_marker("Ahoj světe", "gpt-5-codex")
    assert m["source"] == "stylist" and m["action"] == "note" and m["severity"] == "info"
    import hashlib
    assert hashlib.sha256("Ahoj světe".encode("utf-8")).hexdigest() in m["issue"]
    assert "model=gpt-5-codex" in m["issue"]


def test_finding_key_includes_actual():
    f = {"type": "inconsistency", "term_id": "t/a", "actual": "špatně"}
    assert main._finding_key(f) == ("inconsistency", "t/a", "špatně")


# --- Task 8: main._rejection_reasons / _polish_rejected ---------------------

def _term(tid="t/wc", canonical="White Council", cz="Bílá rada", aliases=None):
    return {"term_id": tid, "canonical_en": canonical, "cz": cz,
            "aliases": aliases or []}


def test_rejection_meaning_drift_always_rejects():
    after = [{"source": "stylist_check", "type": "meaning_drift", "issue": "x"}]
    r = main._rejection_reasons([], after, "A", "B", [])
    assert len(r) == 1 and r[0]["type"] == "meaning_drift"
    assert main._polish_rejected([], after, "A", "B", []) is True


def test_rejection_register_drift_standalone_rejects():
    after = [{"source": "stylist_check", "type": "register_drift", "issue": "ty->vy"}]
    assert main._polish_rejected([], after, "A", "B", []) is True


def test_rejection_clean_input_is_not_rejected():
    assert main._rejection_reasons([], [], "A", "A", []) == []
    assert main._polish_rejected([], [], "A", "A", []) is False


def test_rejection_preexisting_concordance_key_not_rejected():
    base = [{"source": "concordance", "type": "omission", "term_id": "t/x",
             "actual": None}]
    after = [dict(base[0])]
    assert main._polish_rejected(base, after, "A", "A", []) is False


def test_rejection_new_concordance_key_rejected():
    base = [{"source": "concordance", "type": "omission", "term_id": "t/x",
             "actual": None}]
    after = base + [{"source": "concordance", "type": "inconsistency",
                     "term_id": "t/y", "actual": "špatný tvar"}]
    assert main._polish_rejected(base, after, "A", "A", []) is True


def test_rejection_critic_minor_note_accepted_revise_rejected():
    minor = [{"source": "critic", "action": "note", "severity": "minor",
              "type": "fluency"}]
    assert main._polish_rejected([], minor, "A", "A", []) is False
    revise = [{"source": "critic", "action": "revise", "severity": "critical",
               "type": "fluency"}]
    assert main._polish_rejected([], revise, "A", "A", []) is True


def test_rejection_leak_occurrence_increase_in_text_rejected():
    # stejný klíč v baseline i after, ale povrch přibyl v cz_after
    key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
           "actual": "White Council"}
    base, after = [dict(key)], [dict(key)]
    before = "Byla to White Council."
    a = "Byla to White Council a pak zas White Council."
    assert main._polish_rejected(base, after, before, a, [_term()]) is True
    # opačný směr - výskytů míň - není odmítnuto
    assert main._polish_rejected(base, after, a, before, [_term()]) is False


def test_rejection_new_alias_leak_rejected():
    key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
           "actual": "White Council"}
    base, after = [dict(key)], [dict(key)]
    before = "Byla to White Council."
    a = "Byla to White Council, totiž the Council."
    assert main._polish_rejected(base, after, before, a,
                                 [_term(aliases=["the Council"])]) is True


def test_rejection_keep_untranslated_term_no_leak_finding_not_rejected():
    """keep-untranslated termín (cz == canonical_en): `concordance.check_chapter`
    pro něj `leak` nález neemituje (ověř `src/concordance.py` - `leak` větev je
    pod `if cz != canonical`), takže `after_findings` žádný leak pro "Mouse"
    neobsahuje - přidaný výskyt "Mouse" není důvod k zamítnutí. Scénář spec
    2631-2633; `_rejection_reasons` kód by leak ZAMÍTL, kdyby dorazil - test to
    odráží tím, že leak v `after_findings` NENÍ."""
    t = _term(tid="t/mouse", canonical="Mouse", cz="Mouse")
    assert main._polish_rejected([], [], "Mouse tu byl.",
                                 "Mouse tu byl, Mouse zas.", [t]) is False


def test_rejection_added_occurrence_in_different_case_or_declension_rejected():
    """find_form_occurrences stemuje + lowercasuje - přidaný výskyt s jinou
    velikostí písmen se počítá (str.count by ho minul). Spec 2617-2622.
    (Konkrétně jiná VELIKOST PÍSMEN, ne skloňování - naivní stemmer (chop
    posledních 2-3 znaků, viz src/concordance.py:24-31) na "Council"→"councilu"
    dá jiný kmen kvůli hranici délky slova; ověřeno přímo, viz plán Task 8
    Step 4. Test proto zůstává u case-change, co spolehlivě demonstruje
    stejnou mechaniku - find_form_occurrences, ne str.count.)"""
    key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
           "actual": "White Council"}
    base, after = [dict(key)], [dict(key)]
    before = "Byla to White Council."
    a = "Byla to White Council a pak jeste white council pravila."
    assert main._polish_rejected(base, after, before, a, [_term()]) is True


def test_rejection_dedup_new_bad_surface_B_and_grown_surface_A_both_kept(monkeypatch):
    """Spec 2821-2826: termín má NOVÝ chybný povrch B (nový klíč) A SOUČASNĚ
    narostl výskyt UŽ EXISTUJÍCÍHO povrchu A. V `reasons` musí být OBA (dedup je
    na _finding_key, ne na celý termín)."""
    # A: pre-existující leak povrch "White Council" (baseline klíč), naroste 1->2
    # B: nový leak povrch aliasu "the Council" (nový klíč)
    a_key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
             "actual": "White Council"}
    b_key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
             "actual": "the Council"}
    base = [dict(a_key)]
    after = [dict(a_key), dict(b_key)]
    before = "White Council byla tam."
    a = "White Council a White Council, totiz the Council."
    r = main._rejection_reasons(base, after, before, a,
                                [_term(aliases=["the Council"])])
    actuals = sorted(x.get("actual") for x in r if x.get("type") == "leak")
    assert actuals == ["White Council", "the Council"]


def test_rejection_integration_real_check_chapter_occurrence_increase(tmp_path):
    """Spec 2638-2642: sama množina findings NESTAČÍ. Reálný `check_chapter`
    vrátí JEDEN `leak` nález i pro termín leaklý 2×; `_polish_rejected` musí
    přes find_form_occurrences rozdíl v počtu zachytit."""
    from src import concordance, glossary
    db = str(tmp_path / "g.sqlite3"); state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,aliases,cz,"
                     "accepted_alt,type,status) VALUES "
                     "('t/wc','White Council','[]','Bílá rada','[]','term','approved')")
    grows = glossary.all_terms(db)
    en = "The White Council met again."
    cz_before = "Sešla se White Council."
    cz_after = "Sešla se White Council a znovu se sešla White Council."
    base = concordance.check_chapter(en, cz_before, grows, [])
    after = concordance.check_chapter(en, cz_after, grows, [])
    # předpoklad testu: check_chapter DEDUPUJE - baseline i after mají PRÁVĚ
    # JEDEN leak se SHODNÝM _finding_key. `_polish_rejected` True tak může
    # přijít JEN z počtu výskytů, ne z nového klíče (spec 2638-2642).
    base_leaks = [f for f in base if f.get("type") == "leak"]
    after_leaks = [f for f in after if f.get("type") == "leak"]
    assert len(base_leaks) == 1 and len(after_leaks) == 1
    assert {main._finding_key(f) for f in base_leaks} == {main._finding_key(f) for f in after_leaks}
    assert main._polish_rejected(base, after, cz_before, cz_after, grows) is True
    # bez nárůstu (stejný text před i po) -> nezamítnuto
    assert main._polish_rejected(base, base, cz_before, cz_before, grows) is False
