import argparse
import os, json, shutil, sys
import pytest
import config
import main
from src import state
from src import polish_store


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
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
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
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
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
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
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
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
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
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
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


def test_already_styled_true_for_polish_marker():
    notes = json.dumps([main._stylist_marker("cz", "m")])
    assert main._already_styled(notes) is True


def test_already_styled_false_for_revert_marker():
    notes = json.dumps([main._revert_marker("vráceno")])
    assert main._already_styled(notes) is False


def test_revert_marker_carries_note_as_issue():
    m = main._revert_marker("vráceno na verzi před poslední stylizací")
    assert m["source"] == "stylist" and m["type"] == "revert"
    assert m["issue"] == "vráceno na verzi před poslední stylizací"


def test_stylist_marker_wording_does_not_claim_original():
    m = main._stylist_marker("nejaky text", "model-x")
    assert "původní" not in m["issue"]


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


# --- Task 9: main._snapshot_db / _backup_db_once -----------------------------

def test_snapshot_db_produces_logically_equal_copy(tmp_path):
    src = str(tmp_path / "s.sqlite3")
    state.init_db(src)
    with state.connect(src) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t/a','A','Á')")
    snap = str(tmp_path / "snap.sqlite3")
    main._snapshot_db(src, snap)
    with state.connect(snap) as conn:
        rows = conn.execute("SELECT term_id FROM glossary").fetchall()
    assert [r["term_id"] for r in rows] == ["t/a"]


def test_snapshot_db_backup_called_with_pages_100(tmp_path, monkeypatch):
    src = str(tmp_path / "s.sqlite3"); state.init_db(src)
    seen = []
    real_connect = main.sqlite3.connect

    class _Proxy:
        def __init__(self, real): self._real = real
        def backup(self, dst, **kw):
            seen.append(kw.get("pages"))
            return self._real.backup(dst._real if isinstance(dst, _Proxy) else dst, **kw)
        def __getattr__(self, n): return getattr(self._real, n)
        def close(self): self._real.close()

    monkeypatch.setattr(main.sqlite3, "connect", lambda p: _Proxy(real_connect(p)))
    main._snapshot_db(src, str(tmp_path / "snap.sqlite3"))
    assert 100 in seen


def test_snapshot_db_deadline_interrupts(tmp_path, monkeypatch):
    src = str(tmp_path / "s.sqlite3"); state.init_db(src)
    real_connect = main.sqlite3.connect
    times = iter([0.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr(main.time, "monotonic", lambda: next(times))

    class _Proxy:
        def __init__(self, real): self._real = real
        def backup(self, dst, *, pages=None, progress=None):
            progress(0, 5, 10)   # deadline check uvnitř vyhodí
        def __getattr__(self, n): return getattr(self._real, n)
        def close(self): self._real.close()

    monkeypatch.setattr(main.sqlite3, "connect", lambda p: _Proxy(real_connect(p)))
    with pytest.raises(TimeoutError):
        main._snapshot_db(src, str(tmp_path / "snap.sqlite3"))


def test_snapshot_db_integrity_check_failure_raises_oserror(tmp_path, monkeypatch):
    src = str(tmp_path / "s.sqlite3"); state.init_db(src)
    real_connect = main.sqlite3.connect
    calls = {"n": 0}

    class _Proxy:
        def __init__(self, real): self._real = real
        def execute(self, sql, *a):
            if "integrity_check" in sql:
                class _C:
                    def fetchone(self): return ("not ok",)
                return _C()
            return self._real.execute(sql, *a)
        def backup(self, dst, **kw): return self._real.backup(dst._real, **kw)
        def __getattr__(self, n): return getattr(self._real, n)
        def close(self): self._real.close()

    monkeypatch.setattr(main.sqlite3, "connect", lambda p: _Proxy(real_connect(p)))
    with pytest.raises(OSError):
        main._snapshot_db(src, str(tmp_path / "snap.sqlite3"))


def test_backup_db_once_promotes_snapshot_atomically(tmp_path):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    snap = db + ".pre-polish-snapshot"
    main._snapshot_db(db, snap)
    bs = {"done": False, "snapshot_path": snap}
    main._backup_db_once(db, bs)
    assert bs["done"] is True
    assert os.path.exists(db + ".pre-polish-backup")
    assert not os.path.exists(snap)
    # druhé volání je no-op
    main._backup_db_once(db, bs)


def test_backup_db_once_promotion_survives_broken_print(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    snap = db + ".pre-polish-snapshot"
    main._snapshot_db(db, snap)
    monkeypatch.setattr("builtins.print", lambda *a, **k: (_ for _ in ()).throw(BrokenPipeError()))
    bs = {"done": False, "snapshot_path": snap}
    main._backup_db_once(db, bs)   # nesmí vyhodit
    assert bs["done"] is True and os.path.exists(db + ".pre-polish-backup")


# --- Task 10: main._write_polish_report --------------------------------------

def _read_only_report(dirpath):
    import glob
    files = glob.glob(os.path.join(dirpath, "polish-reports", "run-*.json"))
    assert len(files) == 1, files
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


def test_write_polish_report_shape(tmp_path):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    report = [{"idx": 1, "outcome": "applied", "reason_types": []},
              {"idx": 2, "outcome": "unchanged"},
              {"idx": 3, "outcome": "failed", "error": "boom"}]
    main._write_polish_report(db, 7, report, codex_model="gpt-5-codex",
                              planned_count=4, batch_completed=True, run_status="ok")
    r = _read_only_report(str(tmp_path))
    assert r["schema_version"] == 1 and r["run_id"] == 7
    assert r["codex_model"] == "gpt-5-codex"
    assert r["planned_count"] == 4 and r["attempted_count"] == 3
    assert r["batch_completed"] is True and r["run_status"] == "ok"
    assert r["run_error"] is None and r["finalization_error"] is None
    assert r["summary"] == {"applied": 1, "unchanged": 1,
                            "failed": 1, "fatal": 0, "interrupted": 0}
    assert r["generated_at"]


def test_write_polish_report_best_effort_on_json_typeerror(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    monkeypatch.setattr(main.json, "dump",
                        lambda *a, **k: (_ for _ in ()).throw(TypeError("x")))
    main._write_polish_report(db, 1, [], codex_model="m", planned_count=0,
                              batch_completed=True, run_status="ok")   # nesmí vyhodit
    import glob
    assert glob.glob(os.path.join(str(tmp_path), "polish-reports", "*.tmp")) == []
    assert glob.glob(os.path.join(str(tmp_path), "polish-reports", "*.json")) == []


def test_write_polish_report_best_effort_on_makedirs_oserror(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    monkeypatch.setattr(main.os, "makedirs",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    main._write_polish_report(db, 1, [], codex_model="m", planned_count=0,
                              batch_completed=True, run_status="ok")   # nesmí vyhodit


# --- Task 11: main._polish_one_chapter ---------------------------------------

from src.llm.client import FatalRunError
from src.agents import stylist as _stylist


def _polish_db(tmp_path):
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,translated_text,"
                     "status,revision_rounds) VALUES (1,'K1','EN','Původní věta.','done',0)")
    return db


def _c():
    return {"idx": 1, "title": "K1", "raw_text": "EN",
            "translated_text": "Původní věta.", "revision_rounds": 0, "notes": None}


def test_rendered_terms_for_chapter_reads_rendered_source_mentions(tmp_path):
    db = _polish_db(tmp_path)
    with state.connect(db) as conn:
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('term_x','X','Ix')")
        conn.execute(
            "INSERT INTO term_mentions (term_id,cz_form,chapter_idx,scene_idx,source) "
            "VALUES ('term_x','Ix',1,NULL,'rendered')")
        conn.execute(
            "INSERT INTO term_mentions (term_id,cz_form,chapter_idx,scene_idx,source) "
            "VALUES ('term_x','Ix',1,NULL,'detected')")
    out = main._rendered_terms_for_chapter(db, 1)
    assert out == [{"term_id": "term_x", "cz_as_used": "Ix", "scene_idx": None}]


def test_polish_one_chapter_uses_passed_rendered_terms_not_live_db(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    passed = [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0}]
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"],
                                   rendered_terms=passed)
    assert rec["rendered_terms"] == passed   # ne živě odvozené (fixture nemá term_mentions)


def test_polish_one_chapter_uses_passed_empty_list_not_live_db(tmp_path, monkeypatch):
    """`rendered_terms=[]` MUSÍ zůstat `[]` (explicitní "žádné termíny"),
    ne spadnout na živé odvození jen proto, že je to falsy hodnota."""
    db = _polish_db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t/a','A','Á')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Á", "scene_idx": 0, "source": "rendered"}])
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"], rendered_terms=[])
    assert rec["rendered_terms"] == []   # NE [{"term_id": "t/a", ...}] z živé DB


def test_preferred_rendered_terms_uses_history_when_in_sync(tmp_path):
    db = _polish_db(tmp_path)
    entries = [{"idx": 1, "cz_after": "Původní věta.",
               "rendered_terms": [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0}]}]
    out = main._preferred_rendered_terms(db, 1, "Původní věta.", entries)
    assert out == [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0}]


def test_preferred_rendered_terms_falls_back_to_live_when_history_stale(tmp_path):
    db = _polish_db(tmp_path)
    entries = [{"idx": 1, "cz_after": "Stará verze (před novým run).",
               "rendered_terms": [{"term_id": "t/stale", "cz_as_used": "X", "scene_idx": 0}]}]
    # `current_text` NESEDÍ s historií - text mezitím prošel novým `run`
    out = main._preferred_rendered_terms(db, 1, "Původní věta.", entries)
    assert out == []   # živá DB (žádné term_mentions ve fixture), NE stará historie


def test_commit_polish_result_writes_db_and_history(tmp_path):
    db = _polish_db(tmp_path)   # existující fixture main.py:666 - kapitola
                                 # idx=1, status='done', translated_text='Původní věta.'
    history_path = str(tmp_path / "polish.history.json")
    snapshot_path = str(tmp_path / "snap.db")
    main._snapshot_db(db, snapshot_path)   # backup_state vyžaduje HOTOVÝ snapshot
    backup_state = {"done": False, "snapshot_path": snapshot_path}
    main._commit_polish_result(
        db, history_path, 1, en="EN text.", cz_before="Původní věta.",
        final_text="Vylepšeno.", findings=[{"id": "f1", "resolved": False,
                                            "source": "concordance", "type": "omission"}],
        glossary_rows=[], revision_rounds=0,
        source="polish-batch", model_label="m", styled_by_codex="Vylepšeno.",
        backup_state=backup_state)

    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Vylepšeno."
    assert row["status"] == "done"
    saved_notes = json.loads(row["notes"])
    assert saved_notes[0]["id"] == "f1"
    assert any(f["source"] == "stylist" and f["type"] == "polish" for f in saved_notes)

    history = polish_store.load_history(history_path)
    assert len(history["entries"]) == 1
    entry = history["entries"][0]
    assert entry["idx"] == 1
    assert entry["cz_before"] == "Původní věta."
    assert entry["cz_after"] == "Vylepšeno."
    assert entry["styled_by_codex"] == "Vylepšeno."
    assert entry["source"] == "polish-batch"


def test_polish_preflight_rejects_fs_risk_not_accepted(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    model, codex_cmd, err = main._polish_preflight()
    assert model is None and codex_cmd is None
    assert "STYLIST_ACCEPT_FS_RISK" in err


def test_polish_preflight_rejects_empty_model(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "")
    model, codex_cmd, err = main._polish_preflight()
    assert model is None
    assert "CODEX_MODEL" in err


def test_polish_preflight_ok(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "gpt-5.6-terra")
    monkeypatch.setattr(main.stylist, "_resolve_codex_cmd", lambda base: ["codex"])
    model, codex_cmd, err = main._polish_preflight()
    assert model == "gpt-5.6-terra"
    assert codex_cmd == ["codex"]
    assert err is None


def _cf_stub(agent):
    return object()


def test_polish_one_chapter_unchanged(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Původní věta.")
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert rec == {"idx": 1, "outcome": "unchanged"}


def test_polish_one_chapter_stylist_error_is_failed(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    def _boom(*a, **k): raise _stylist.StylistError("nope")
    monkeypatch.setattr(main.stylist, "polish", _boom)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert rec["outcome"] == "failed" and "nope" in rec["error"]
    assert state.get_chapter(db, 1)["translated_text"] == "Původní věta."


def test_polish_one_chapter_returns_draft_dict_when_no_reasons(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "gpt-5-codex", ["codex"])
    assert "outcome" not in rec
    assert rec["idx"] == 1 and rec["title"] == "K1"
    assert rec["cz_before"] == "Původní věta." and rec["styled"] == "Vylepšená věta."
    assert rec["revision_rounds"] == 0 and rec["reason_types"] == []
    assert isinstance(rec["findings"], list) and isinstance(rec["rendered_terms"], list)
    # NIC se nezapsalo do DB - to teď dělá jen `polish-review` apply endpoint
    assert state.get_chapter(db, 1)["translated_text"] == "Původní věta."
    assert not os.path.exists(db + ".pre-polish-backup")


def test_polish_one_chapter_findings_have_ids(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jina uplne jina veta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert all("id" in f and "resolved" in f for f in rec["findings"])


def test_polish_one_chapter_returns_draft_dict_with_reason_types_when_rejected(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta SECRET.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: ([{"source": "critic", "action": "revise",
                                           "severity": "critical", "type": "fidelity",
                                           "issue": "SECRET"}], False))
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert "outcome" not in rec
    assert rec["reason_types"] == ["critic/fidelity"]
    assert any(f.get("issue") == "SECRET" for f in rec["findings"])
    assert state.get_chapter(db, 1)["translated_text"] == "Původní věta."


def test_polish_one_chapter_prints_critic_minor_findings_as_context(tmp_path, monkeypatch, capsys):
    # Kontextový výpis kritikových minor nálezů je pořád součástí "plného"
    # konzolového detailu (`full`), stejně jako dřív - jen vrácený `rec`
    # dict je VŽDY plný, konzole zůstává gatovaná.
    from src.llm.client import Completion, FakeLLMClient
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jina uplne jina veta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", True)
    resp = json.dumps({"verdict": "revise", "findings": [
        {"severity": "minor", "type": "fidelity", "cz_excerpt": "Harry Dresdene",
         "issue": "PRIDANE PRIJMENI CO NENI V ORIGINALE", "suggestion": "Harry"}]})
    def _cf(agent):
        return FakeLLMClient([Completion(resp, False, 5, 5)])
    rec = main._polish_one_chapter(_c(), [], _cf, db, "m", ["codex"])
    assert "outcome" not in rec
    out = capsys.readouterr().out
    assert "PRIDANE PRIJMENI CO NENI V ORIGINALE" in out
    assert any(f.get("issue") == "PRIDANE PRIJMENI CO NENI V ORIGINALE"
              for f in rec["findings"])


def test_polish_one_chapter_rejected_full_detail_when_opted_in(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved",
                        lambda *a, **k: [{"source": "stylist_check",
                                          "type": "meaning_drift", "issue": "x"}])
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", True)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert "outcome" not in rec and rec["styled"] == "Jiná věta."
    assert rec["reason_types"] == ["stylist_check/meaning_drift"]


@pytest.mark.parametrize("flag", [False, 1, "False", None])
def test_polish_one_chapter_rejected_detail_gated_console_only(tmp_path, monkeypatch, flag):
    """`STYLIST_REPORT_REJECTED_TEXT` teď gatuje jen KONZOLOVÝ výpis nálezů
    (vrácený `rec` dict je VŽDY plný). Jen literál `True` odemkne detail
    na konzoli."""
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta se SECRET123.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: ([{"source": "critic", "action": "revise",
                                           "severity": "critical", "type": "fidelity",
                                           "issue": "SECRET123"}], False))
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", flag)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert "outcome" not in rec
    assert any(f.get("issue") == "SECRET123" for f in rec["findings"])   # draft VŽDY plný


def test_polish_one_chapter_real_critic_failure_redacts_console_by_default(tmp_path, monkeypatch, capsys):
    from src.llm.client import Completion, FakeLLMClient
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jina veta uplne jinak.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", False)
    bad = json.dumps({"verdict": "SECRET123", "findings": []})
    def _cf(agent):
        return FakeLLMClient([Completion(bad, False, 5, 5), Completion(bad, False, 5, 5)])
    rec = main._polish_one_chapter(_c(), [], _cf, db, "m", ["codex"])
    assert "outcome" not in rec and "critic/critic_failed" in rec["reason_types"]
    assert "SECRET123" not in capsys.readouterr().out   # konzole redigovaná
    assert any("SECRET123" in (f.get("issue") or "") for f in rec["findings"])  # draft plný


def test_polish_one_chapter_critic_fatal_is_wrapped_redacted(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: (_ for _ in ()).throw(FatalRunError("SECRET123")))
    with pytest.raises(FatalRunError) as ei:
        main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert "SECRET123" not in str(ei.value)


def test_polish_one_chapter_critic_failed_skips_meaning_check(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], True))
    called = {"n": 0}
    def _mc(*a, **k):
        called["n"] += 1
        return []
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", _mc)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert "outcome" not in rec and rec["reason_types"] == ["critic/critic_failed"]
    assert called["n"] == 0


def test_polish_one_chapter_forwards_only_rendered_mentions_as_rendered_terms(tmp_path, monkeypatch):
    """Kolo 7 plán-ping-pongu BLOCKING - `_polish_one_chapter` NEVOLÁ
    `concordance.build_mentions` (to dělá teď až apply/revert endpoint,
    viz Task 9/10) - `rendered_terms` tu počítá PŘÍMO z `state.
    chapter_mentions`, filtrováno na `source == "rendered"`. Test dřív
    mylně čekal volání `build_mentions`, co v týhle funkci vůbec
    neexistuje, a nikdy by neprošel."""
    db = _polish_db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES "
                     "('t/a','A','Á')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Áčko", "scene_idx": 0, "source": "rendered"},
        {"term_id": "t/a", "cz_form": "Bčko", "scene_idx": 1, "source": "detected"},
    ])
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"])
    assert rec["rendered_terms"] == [{"term_id": "t/a", "cz_as_used": "Áčko", "scene_idx": 0}]


# --- main._cmd_polish + registrace příkazu ----------------------------------

class _Args:
    def __init__(self, only=None, force=False):
        self.only = only
        self.force = force


def _polish_env(tmp_path, monkeypatch, n_done=1):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "state.sqlite3"))
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "gpt-5-codex")
    monkeypatch.setattr(config, "GUIDE_PATH", str(tmp_path / "guide.json"))
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", str(tmp_path / "polish.draft.json"))
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", str(tmp_path / "polish.history.json"))
    monkeypatch.setattr(config, "LOCK_PATH", str(tmp_path / ".lock"))
    state.acquire_lock(config.LOCK_PATH)
    state.init_db(config.DB_PATH)
    with state.connect(config.DB_PATH) as conn:
        for i in range(1, n_done + 1):
            conn.execute("INSERT INTO chapters (idx,title,raw_text,translated_text,"
                         "status,revision_rounds) VALUES (?,?,?,?,'done',0)",
                         (i, f"K{i}", "EN", f"Věta {i}."))
    monkeypatch.setattr(main.stylist, "_resolve_codex_cmd", lambda c: ["codex", "resolved"])
    monkeypatch.setattr(main.guide_mod, "load_guide", lambda p: {})
    monkeypatch.setattr(main.guide_mod, "guide_as_prompt_block", lambda g: "")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    monkeypatch.setattr(main, "_claude_cli_preflight", lambda: (["claude"], None))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(main, "_client_factory",
                        lambda rid, *, interactive, require_lock=None,
                              translator_backend="claude", claude_cmd=None:
                            (lambda a: object()))
    return config.DB_PATH


def test_export_book_writes_done_chapters(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)   # main.py fixture - idx=1, status='done'
    monkeypatch.setattr(config, "OUTPUT_TXT", str(tmp_path / "out.txt"))
    path, skipped = main.export_book(db, only_done=False)
    assert path == str(tmp_path / "out.txt")
    assert skipped == []
    assert "K1" in open(path, encoding="utf-8").read()


def test_export_book_skips_non_done_without_only_done_flag_marks_missing(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    state.set_status(db, 1, "pending")
    monkeypatch.setattr(config, "OUTPUT_TXT", str(tmp_path / "out.txt"))
    path, skipped = main.export_book(db, only_done=False)
    assert skipped == [1]
    assert "CHYBÍ KAPITOLA 1" in open(path, encoding="utf-8").read()


@pytest.mark.parametrize("bad_notes", ["null", "42", "[null]", "not json"])
def test_finding_summary_does_not_crash_on_malformed_notes(bad_notes):
    assert main._finding_summary(bad_notes) == "neznámý nález"


def test_lock_still_owned_true_when_lock_held(tmp_path):
    lock_path = str(tmp_path / ".lock")
    state.acquire_lock(lock_path)
    assert main._lock_still_owned(lock_path) is True


def test_lock_still_owned_false_when_refresh_fails(tmp_path, monkeypatch):
    lock_path = str(tmp_path / ".lock")
    monkeypatch.setattr(state, "refresh_lock",
                        lambda *a, **k: (_ for _ in ()).throw(state.LockError("ukraden")))
    assert main._lock_still_owned(lock_path) is False


def test_cmd_polish_passes_require_lock_callback_to_client_factory(tmp_path, monkeypatch):
    """Kolo 13 IMPORTANT - drátování: `_cmd_polish` MUSÍ `_client_factory`
    zavolat s `require_lock=...`, jinak `PipelineLLMClient` uvnitř
    `_polish_one_chapter` nemá jak zámek ověřit PŘED KAŽDÝM LLM voláním
    (viz Task 10 stejný vzor pro server)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    seen = {}
    def _fake_client_factory(rid, *, interactive, require_lock=None,
                             translator_backend="claude", claude_cmd=None):
        seen["require_lock"] = require_lock
        return lambda a: object()
    monkeypatch.setattr(main, "_client_factory", _fake_client_factory)
    main._cmd_polish(_Args(only=None, force=False))
    assert callable(seen["require_lock"])


def _report(db):
    import glob
    files = glob.glob(os.path.join(os.path.dirname(db), "polish-reports", "run-*.json"))
    assert len(files) == 1, files
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


def test_cmd_polish_refuses_without_fs_risk_optin(tmp_path, monkeypatch, capsys):
    _polish_env(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", 1)   # truthy != True
    assert main._cmd_polish(_Args()) == 1
    assert "vypnutý" in capsys.readouterr().out


def test_cmd_polish_refuses_without_model(tmp_path, monkeypatch):
    _polish_env(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "CODEX_MODEL", "  ")
    assert main._cmd_polish(_Args()) == 1
    with state.connect(config.DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"] == 0


def test_cmd_polish_preflight_failure_returns_1(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch)
    def _boom(c): raise _stylist.StylistError("Codex nenalezen")
    monkeypatch.setattr(main.stylist, "_resolve_codex_cmd", _boom)
    assert main._cmd_polish(_Args()) == 1


def test_cmd_polish_writes_directly_to_db(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    main._cmd_polish(_Args(only=None, force=False))
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Jiná věta."   # skutečně přepsáno
    history = polish_store.load_history(config.POLISH_HISTORY_PATH)
    assert history["entries"][0]["source"] == "polish-batch"
    assert not os.path.exists(config.POLISH_DRAFT_PATH)   # draft soubor nevzniká


def test_cmd_polish_includes_flagged_chapters(tmp_path, monkeypatch):
    """`run` označí kapitolu `flagged`, když kritik něco namítne - to
    NESMÍ znamenat, že ji `polish` navždy přeskočí. Uživatel chce
    přeložit CELOU knihu, přes polish protáhnout VŠECHNO (i flagged),
    a kritický nálezy si vyřešit ručně v editoru NAD hotovým textem -
    ne aby dávka na flagged kapitole zůstala trčet navždy."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='flagged' WHERE idx=1")
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    assert main._cmd_polish(_Args(only=None, force=False)) == 0
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Jiná věta."
    assert row["status"] == "done"   # úspěšná stylizace kapitolu schválí


def test_cmd_polish_includes_needs_human_chapters(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='needs_human' WHERE idx=1")
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    assert main._cmd_polish(_Args(only=None, force=False)) == 0
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Jiná věta."
    assert row["status"] == "done"


def test_cmd_polish_still_skips_error_status_no_text(tmp_path, monkeypatch):
    """`error` kapitola může mít `translated_text=NULL` (první neúspěšný
    pokus o překlad, main.py `run`u `except Exception` větev) - na
    rozdíl od `flagged`/`needs_human` (vždy mají reálný text z `pipeline.
    process_chapter`) se NESMÍ zařadit do dávky, jinak spadne hluboko
    ve `stylist.polish` na `None` textu."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='error', translated_text=NULL WHERE idx=1")
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("nemá se volat")))
    assert main._cmd_polish(_Args(only=None, force=False)) == 0
    row = state.get_chapter(db, 1)
    assert row["status"] == "error"   # beze změny - nezařazeno do dávky


def test_cmd_polish_unchanged_chapter_marked_and_skipped_next_run(tmp_path, monkeypatch):
    """Kolo 9 IMPORTANT - beze zápisu markeru by druhý běh kapitolu,
    co Codex nechal beze změny, poslal Codexu ZNOVU (a znovu zaplatil).
    `--force` musí i tak umět kapitolu vrátit zpátky do zpracování."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    calls = {"n": 0}

    def fake_polish(en, cz, **k):
        calls["n"] += 1
        return cz   # Codex nenavrhuje žádnou úpravu

    monkeypatch.setattr(main.stylist, "polish", fake_polish)
    main._cmd_polish(_Args(only=None, force=False))
    assert calls["n"] == 1
    row = state.get_chapter(db, 1)
    notes = main._parse_findings(row["notes"])
    assert any(f["source"] == "stylist" and f["type"] == "unchanged" for f in notes)
    assert main._already_styled(row["notes"]) is True

    main._cmd_polish(_Args(only=None, force=False))
    assert calls["n"] == 1   # druhý běh bez --force kapitolu PŘESKOČIL

    main._cmd_polish(_Args(only=None, force=True))
    assert calls["n"] == 2   # --force ji i tak zpracuje znovu


def test_cmd_polish_survives_fatal_midbatch_first_chapter_already_committed(tmp_path, monkeypatch):
    """Stejný princip jako dřív u inkrementálního draftu, teď nad přímým
    DB zápisem - kapitola 1 se stihne zapsat dřív, než kapitola 2 shodí
    celý běh přes FatalRunError, a MUSÍ zůstat zapsaná i po pádu."""
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    from src.llm.client import FatalRunError as _FRE
    seen = {"n": 0}
    def _crit(*a, **k):
        seen["n"] += 1
        if seen["n"] == 2:
            raise _FRE("cost guard")
        return ([], False)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    monkeypatch.setattr(main.pipeline, "_run_critic", _crit)
    assert main._cmd_polish(_Args()) == 1
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1. uprav"
    assert state.get_chapter(db, 2)["translated_text"] == "Věta 2."   # nedotčeno, spadlo dřív


def test_cmd_polish_commit_failure_still_recorded_in_report(tmp_path, monkeypatch):
    """Stejný princip jako dřív u `save_draft` selhání - selhání ZÁPISU
    (teď přímo do DB přes `_commit_polish_result`) se musí zabalit do
    `FatalRunError`, A kapitola musí i tak skončit v reportu (jako
    `fatal`), ne beze stopy zmizet z attempted_count."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    monkeypatch.setattr(main.state, "commit_chapter_result",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk plný")))
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal"
    assert r["attempted_count"] == 1
    assert r["chapters"][0]["outcome"] == "fatal"


def test_cmd_polish_claude_cli_preflight_failure_blocks_batch_before_stylize(
        tmp_path, monkeypatch):
    """Kolo 2 IMPORTANT (plan-consensus) - `_cmd_polish` volá kritika
    (`claude` CLI) PO drahé Codex stylizaci (`_polish_one_chapter`), ne
    před ní - bez eager kontroly by chybějící/nepřihlášené `claude` CLI
    nechalo proběhnout CELOU (draze zaplacenou) dávkovou stylizaci, než
    by selhalo na PRVNÍM kritikově volání."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr("main._claude_cli_preflight",
                        lambda: (None, "claude CLI není přihlášené."))
    calls = {"n": 0}
    def boom(en, cz, **k):
        calls["n"] += 1
        return cz
    monkeypatch.setattr(main.stylist, "polish", boom)
    assert main._cmd_polish(_Args()) == 1
    assert calls["n"] == 0   # Codex stylizace se VŮBEC nespustila


def test_cmd_polish_missing_anthropic_key_blocks_batch_before_stylize(
        tmp_path, monkeypatch):
    """Kolo 3 BLOCKING (plan-consensus) - `stylist_check` (main.py:698)
    zůstává MIMO rozsah tohohle plánu, pořád `AnthropicClient`/
    `ANTHROPIC_API_KEY` - bez týhle kontroly by chybějící klíč nechal
    proběhnout DRAHOU Codex stylizaci CELÉ dávky, než by selhalo na
    PRVNÍM `stylist_check` volání."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
    calls = {"n": 0}
    def boom(en, cz, **k):
        calls["n"] += 1
        return cz
    monkeypatch.setattr(main.stylist, "polish", boom)
    assert main._cmd_polish(_Args()) == 1
    assert calls["n"] == 0   # Codex stylizace se VŮBEC nespustila (i když claude CLI uspěje)


def test_cmd_polish_happy_path_writes_db_and_reports(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    monkeypatch.setattr(main.stylist, "polish",
                        lambda en, cz, **k: cz.replace("Věta", "Lepší věta"))
    assert main._cmd_polish(_Args()) == 0
    assert state.get_chapter(db, 1)["translated_text"] == "Lepší věta 1."
    assert state.get_chapter(db, 2)["translated_text"] == "Lepší věta 2."
    history = polish_store.load_history(config.POLISH_HISTORY_PATH)
    assert {e["idx"] for e in history["entries"]} == {1, 2}
    r = _report(db)
    assert r["run_status"] == "ok" and r["batch_completed"] is True
    assert r["planned_count"] == 2 and r["attempted_count"] == 2
    assert r["summary"]["applied"] == 2
    with state.connect(db) as conn:
        assert conn.execute("SELECT status FROM runs").fetchone()["status"] == "ok"


def test_cmd_polish_all_failed_is_fatal_but_batch_completed(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(_stylist.StylistError("x")))
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is True
    assert r["attempted_count"] == 3 and r["summary"]["failed"] == 3


def test_cmd_polish_all_generic_exceptions_is_fatal(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.concordance, "check_chapter",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is True
    assert r["attempted_count"] == 3 and r["summary"]["failed"] == 3
    assert all(c["outcome"] == "failed" for c in r["chapters"])


def test_cmd_polish_skips_already_styled_without_force(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"source": "stylist", "type": "polish"}]),))
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("nemá se volat")))
    assert main._cmd_polish(_Args()) == 0


def test_cmd_polish_only_reports_skipped_non_done(tmp_path, monkeypatch, capsys):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " x")
    assert main._cmd_polish(_Args(only=[1, 99])) == 0
    assert "99" in capsys.readouterr().out


def test_cmd_polish_report_survives_broken_stdout(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " x")
    monkeypatch.setattr("builtins.print",
                        lambda *a, **k: (_ for _ in ()).throw(BrokenPipeError()))
    assert main._cmd_polish(_Args()) == 0
    r = _report(db)
    assert r["summary"]["applied"] == 1


def test_cmd_polish_keyboardinterrupt_during_chapter(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    def _ki(*a, **k): raise KeyboardInterrupt()
    monkeypatch.setattr(main.stylist, "polish", _ki)
    with pytest.raises(KeyboardInterrupt):
        main._cmd_polish(_Args())
    r = _report(db)
    assert r["run_status"] == "interrupted"
    assert r["chapters"][0]["outcome"] == "interrupted"


def test_cmd_polish_finish_run_failure_does_not_mask_result(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " x")
    monkeypatch.setattr(main.state, "finish_run",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("db locked")))
    assert main._cmd_polish(_Args()) == 0
    r = _report(db)
    assert r["finalization_error"] and r["run_status"] == "ok"


def test_cmd_polish_generic_exception_is_failed_batch_continues(tmp_path, monkeypatch, capsys):
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", False)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    def _boom_on_2(en, cz, gl, rendered):
        if "2" in cz:
            raise ValueError("SECRET-boom")
        return []
    monkeypatch.setattr(main.concordance, "check_chapter", _boom_on_2)
    assert main._cmd_polish(_Args()) == 0
    out = capsys.readouterr().out
    r = _report(db)
    assert r["run_status"] == "ok" and r["batch_completed"] is True
    outcomes = {c["idx"]: c["outcome"] for c in r["chapters"]}
    assert outcomes == {1: "applied", 2: "failed", 3: "applied"}
    assert "SECRET-boom" not in json.dumps(r) and "SECRET-boom" not in out


def test_cmd_polish_force_interrupt_before_new_commit_is_interrupted(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"source": "stylist", "type": "polish"}]),))
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        main._cmd_polish(_Args(force=True))
    r = _report(db)
    ch1 = [c for c in r["chapters"] if c["idx"] == 1]
    assert len(ch1) == 1 and ch1[0]["outcome"] == "interrupted"


def test_cmd_polish_client_factory_failure_after_create_run_still_reports(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    def _boom(rid, *, interactive, require_lock=None):
        raise RuntimeError("no client")
    monkeypatch.setattr(main, "_client_factory", _boom)
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["attempted_count"] == 0 and r["planned_count"] == 2
    assert r["run_error"] and r["run_status"] == "fatal"


def test_cmd_polish_critic_fatalrunerror_stops_whole_batch(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    from src.llm.client import FatalRunError
    calls = {"n": 0}
    def _crit(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise FatalRunError("cost guard")
        return ([], False)
    monkeypatch.setattr(main.pipeline, "_run_critic", _crit)
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is False
    assert r["attempted_count"] == 2
    assert [c["outcome"] for c in r["chapters"]] == ["applied", "fatal"]


def test_cmd_polish_report_records_every_iteration(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=4)

    def _draft(idx):
        return {"idx": idx, "title": f"K{idx}", "cz_before": "a", "styled": "b",
                "revision_rounds": 0, "reason_types": [], "findings": [],
                "rendered_terms": [], "draft_id": f"draft-{idx}"}

    seq = iter([_draft(1),
                {"idx": 2, "outcome": "unchanged"},
                _draft(3),
                {"idx": 4, "outcome": "failed", "error": "x"}])
    monkeypatch.setattr(main, "_polish_one_chapter", lambda *a, **k: next(seq))
    assert main._cmd_polish(_Args()) == 0
    r = _report(db)
    assert [c["idx"] for c in r["chapters"]] == [1, 2, 3, 4]
    assert r["attempted_count"] == 4
    assert r["summary"] == {"applied": 2, "unchanged": 1, "failed": 1,
                            "fatal": 0, "interrupted": 0}


def test_cmd_polish_ki_during_error_logging_records_exactly_once(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    monkeypatch.setattr(main, "_polish_one_chapter",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    real_say = main._say
    def _say_ki(msg):
        if "neočekávaná chyba" in msg:
            raise KeyboardInterrupt()
        return real_say(msg)
    monkeypatch.setattr(main, "_say", _say_ki)
    with pytest.raises(KeyboardInterrupt):
        main._cmd_polish(_Args())
    r = _report(db)
    ch1 = [c for c in r["chapters"] if c["idx"] == 1]
    assert len(ch1) == 1
    assert r["run_status"] == "interrupted"


def test_polish_command_registered_and_mutating():
    p = main._build_parser()
    ns = p.parse_args(["polish", "--only", "1", "2", "--force"])
    assert ns.func is main._cmd_polish
    assert ns.only == [1, 2] and ns.force is True


def test_polish_review_command_registered_and_mutating():
    assert "polish-review" in main._MUTATING
    args = main._build_parser().parse_args(["polish-review"])
    assert args.func is main._cmd_polish_review


def test_cmd_polish_review_calls_server_with_configured_paths(tmp_path, monkeypatch):
    seen = {}
    def _fake_run(db_path, history_path, lock_path, **kw):
        seen.update(db_path=db_path, history_path=history_path, lock_path=lock_path)
        return 0
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "s.sqlite3"))
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", str(tmp_path / "h.json"))
    monkeypatch.setattr(config, "LOCK_PATH", str(tmp_path / ".lock"))
    import src.review_ui.polish_server as ps_module
    monkeypatch.setattr(ps_module, "run_polish_review_server", _fake_run)
    rc = main._cmd_polish_review(argparse.Namespace())
    assert rc == 0
    assert seen["db_path"] == config.DB_PATH
    assert seen["history_path"] == config.POLISH_HISTORY_PATH
    assert seen["lock_path"] == config.LOCK_PATH


def test_cmd_polish_review_reports_startup_failure_instead_of_traceback(
        tmp_path, monkeypatch, capsys):
    """`build_app` (uvnitř `run_polish_review_server`) může vyhodit
    `PolishStoreError` (poškozená historie) nebo `OSError`/`TimeoutError`
    (`_snapshot_db` selhání) - `_cmd_polish_review` tohle musí chytit a
    vrátit čitelné `return 1`, ne nechat traceback propadnout až do
    `main()`."""
    def _fake_run(db_path, history_path, lock_path, **kw):
        raise polish_store.PolishStoreError("corrupt")
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "s.sqlite3"))
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", str(tmp_path / "h.json"))
    monkeypatch.setattr(config, "LOCK_PATH", str(tmp_path / ".lock"))
    import src.review_ui.polish_server as ps_module
    monkeypatch.setattr(ps_module, "run_polish_review_server", _fake_run)
    rc = main._cmd_polish_review(argparse.Namespace())
    assert rc == 1
    out = capsys.readouterr().out
    assert "corrupt" in out
    assert "polish-review" in out


def _init_args(path, reset=False):
    return argparse.Namespace(path=path, reset=reset)


def test_init_reset_archives_draft_and_history(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (1,'Old','en','done')")
    monkeypatch.setattr(config, "DB_PATH", db)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", draft_path)
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", history_path)
    open(draft_path, "w", encoding="utf-8").write('{"schema_version":1,'
        '"generated_at":"x","codex_model":"m","chapters":[]}')
    open(history_path, "w", encoding="utf-8").write('{"schema_version":1,"entries":[]}')
    book = tmp_path / "book.txt"
    book.write_text("Kapitola 1\ntext")
    monkeypatch.setattr(main.ingest, "load_book", lambda p: [])
    rc = main._cmd_init(_init_args(str(book), reset=True))
    assert rc == 0
    assert not os.path.exists(draft_path)
    assert not os.path.exists(history_path)
    archived = os.listdir(tmp_path)
    assert any(f.startswith("polish.draft.") and f != "polish.draft.json" for f in archived)
    assert any(f.startswith("polish.history.") and f != "polish.history.json" for f in archived)
    assert state.is_db_empty(db)   # reset proběhl


def test_init_reset_missing_polish_files_is_a_noop(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", str(tmp_path / "polish.draft.json"))
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", str(tmp_path / "polish.history.json"))
    book = tmp_path / "book.txt"
    book.write_text("x")
    monkeypatch.setattr(main.ingest, "load_book", lambda p: [])
    assert main._cmd_init(_init_args(str(book), reset=True)) == 0


def test_init_reset_rolls_back_history_rename_if_draft_rename_fails(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    monkeypatch.setattr(config, "DB_PATH", db)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", draft_path)
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", history_path)
    open(draft_path, "w", encoding="utf-8").write("draft-content")
    open(history_path, "w", encoding="utf-8").write("history-content")
    real_rename = os.rename
    def _boom_on_draft(src, dst):
        # `_archive_polish_file` volá `os.rename(path, archived)` PŘÍMO
        # (žádný tmp soubor) - selhat musí přesně na draft_path jako
        # zdroji, ať historie stihne úspěšně přejmenovat PRVNÍ (pořadí:
        # historie → draft, viz `_cmd_init`).
        if src == draft_path:
            raise OSError("simulated failure")
        real_rename(src, dst)
    monkeypatch.setattr(main.os, "rename", _boom_on_draft)
    book = tmp_path / "book.txt"
    book.write_text("x")
    monkeypatch.setattr(main.ingest, "load_book", lambda p: [])
    rc = main._cmd_init(_init_args(str(book), reset=True))
    assert rc == 1
    # rollback: OBA soubory zpátky na původních jménech
    assert open(draft_path, encoding="utf-8").read() == "draft-content"
    assert open(history_path, encoding="utf-8").read() == "history-content"
    # `state.reset_book` se NIKDY nevolalo (selhalo se dřív) - žádné přímé
    # tvrzení o DB obsahu tu netřeba, netriviální DB pokrývá další test.


def test_init_reset_rolls_back_both_renames_if_reset_book_fails(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (1,'Old','en','done')")
    monkeypatch.setattr(config, "DB_PATH", db)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", draft_path)
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", history_path)
    open(draft_path, "w", encoding="utf-8").write("draft-content")
    open(history_path, "w", encoding="utf-8").write("history-content")
    monkeypatch.setattr(main.state, "reset_book",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("boom")))
    book = tmp_path / "book.txt"
    book.write_text("x")
    monkeypatch.setattr(main.ingest, "load_book", lambda p: [])
    rc = main._cmd_init(_init_args(str(book), reset=True))
    assert rc == 1
    assert open(draft_path, encoding="utf-8").read() == "draft-content"
    assert open(history_path, encoding="utf-8").read() == "history-content"
    assert state.get_chapter(db, 1)["title"] == "Old"   # DB beze změny


def test_init_reset_rollback_failure_itself_is_reported_not_traceback(tmp_path, monkeypatch, capsys):
    """Kolo 2 plán-ping-pongu IMPORTANT - i SAMOTNÝ rollback (`os.rename`
    zpět) může selhat (disk skutečně rozbitý) - musí to vypsat přesný
    stav, ne spadnout jako nezachycený traceback."""
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    monkeypatch.setattr(config, "DB_PATH", db)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", draft_path)
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", history_path)
    open(draft_path, "w", encoding="utf-8").write("draft-content")
    open(history_path, "w", encoding="utf-8").write("history-content")
    real_rename = os.rename
    def _boom_on_rollback_to_draft(src, dst):
        # Blokuje JEN zápis NA `draft_path` - to je přesně rollback krok
        # (`os.rename(archived, draft_path)`), ne prvotní archivace
        # (jejíž cíl je timestampovaná cesta, ne `draft_path`).
        if dst == draft_path:
            raise OSError("rollback samo selhalo")
        real_rename(src, dst)
    monkeypatch.setattr(main.os, "rename", _boom_on_rollback_to_draft)
    monkeypatch.setattr(main.state, "reset_book",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("boom")))
    book = tmp_path / "book.txt"
    book.write_text("x")
    monkeypatch.setattr(main.ingest, "load_book", lambda p: [])
    rc = main._cmd_init(_init_args(str(book), reset=True))
    assert rc == 1   # nesmí spadnout jako traceback
    out = capsys.readouterr().out
    assert "rollback" in out.lower()


def test_init_reset_invalid_book_touches_nothing(tmp_path, monkeypatch):
    """Kolo 5 plán-ping-pongu BLOCKING - kniha se validuje JAKO PRVNÍ,
    PŘED archivací/resetem. Špatný vstupní soubor tak nesmí zanechat DB
    resetnutou ani draft/historii archivovanou."""
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (1,'Old','en','done')")
    monkeypatch.setattr(config, "DB_PATH", db)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", draft_path)
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", history_path)
    open(draft_path, "w", encoding="utf-8").write("draft-content")
    open(history_path, "w", encoding="utf-8").write("history-content")
    monkeypatch.setattr(main.ingest, "load_book",
                        lambda p: (_ for _ in ()).throw(ValueError("špatný formát")))
    book = tmp_path / "book.txt"
    book.write_text("x")
    rc = main._cmd_init(_init_args(str(book), reset=True))
    assert rc == 1
    # NIC se nezměnilo - žádná archivace, žádný reset.
    assert open(draft_path, encoding="utf-8").read() == "draft-content"
    assert open(history_path, encoding="utf-8").read() == "history-content"
    assert state.get_chapter(db, 1)["title"] == "Old"


def test_init_reset_seed_failure_after_reset_gives_clear_recovery_path(tmp_path, monkeypatch, capsys):
    """Kolo 5 plán-ping-pongu BLOCKING - `state.seed_chapters` může
    selhat i PO úspěšném resetu (infrastrukturní chyba - `reset_book`
    samo o sobě není vratné, žádný snapshot dat CHAPTERS tahle spec
    nedělá). Musí to jasně vysvětlit, že DB je teď PRÁZDNÁ a obyčejný
    `init` (bez --reset) je bezpečná cesta ven."""
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (1,'Old','en','done')")
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", str(tmp_path / "polish.draft.json"))
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", str(tmp_path / "polish.history.json"))
    monkeypatch.setattr(main.ingest, "load_book", lambda p: [])
    monkeypatch.setattr(main.state, "seed_chapters",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("disk full")))
    book = tmp_path / "book.txt"
    book.write_text("x")
    rc = main._cmd_init(_init_args(str(book), reset=True))
    assert rc == 1
    assert state.is_db_empty(db) is True   # reset PROBĚHLO, seed ne
    out = capsys.readouterr().out
    assert "init" in out.lower() and "reset" in out.lower()
    assert "polish" in main._MUTATING


def test_client_factory_translator_backend_codex_uses_codex_client(monkeypatch):
    from src.llm.client import CodexLLMClient
    # Kolo 28 NIT (plan-consensus) - `factory()` teď staví `CodexLLMClient`
    # z RAW `config.CODEX_MODEL`, NE z `_polish_preflight()`'s ořezaného
    # návratu (viz vysvětlení u `_client_factory` výš) - mock preflightu
    # tedy `model` element ignoruje ("ignored", nikdy nepoužit), test
    # ověřuje proti `config.CODEX_MODEL` mocku místo toho.
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("ignored", ["codex", "resolved"], None))
    monkeypatch.setattr(config, "CODEX_MODEL", "m")
    factory = main._client_factory(1, interactive=False, translator_backend="codex")
    client = factory("translator")
    assert isinstance(client._inner, CodexLLMClient)
    assert client._inner._codex_model == "m"
    assert client._inner._codex_cmd == ["codex", "resolved"]
    assert client._inner.billed_model == "m"


def test_client_factory_critic_always_uses_claude_cli_client(monkeypatch):
    from src.llm.client import ClaudeCliClient
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    factory = main._client_factory(1, interactive=False)
    client = factory("critic")
    assert isinstance(client._inner, ClaudeCliClient)
    assert client._inner.billed_model == f"{config.MODEL_CRITIC}-cli"


def test_client_factory_critic_uses_cli_reinforcement(monkeypatch):
    """`claude -p --safe-mode` nedodrží kritikův JSON formát spolehlivě
    bez reinforcementu (pozorováno manuálně, opraveno stejnou technikou
    jako translator - viz `critic.CLI_REINFORCEMENT`, spike 2026-09-22,
    6/6 úspěch)."""
    from src.agents import critic as critic_mod
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    factory = main._client_factory(1, interactive=False)
    client = factory("critic")
    assert client._inner._reinforcement == critic_mod.CLI_REINFORCEMENT


def test_client_factory_critic_uses_preflight_resolved_claude_cmd(monkeypatch):
    """Kolo 3 IMPORTANT (plan-consensus) - `_claude_cli_preflight()`
    (Task 3) resolvne `claude` na ABSOLUTNÍ cestu A ověří přihlášení
    PRO TENHLE KONKRÉTNÍ binární soubor. Bez threadování téhle hodnoty
    do `_client_factory`/`ClaudeCliClient` by se PATH lookup provedl
    ZNOVU, líně, uvnitř `_exec_claude()` - TOCTOU mezera (PATH se mezi
    preflightem a prvním skutečným voláním teoreticky může změnit) a
    zbytečná duplicitní práce."""
    from src.llm.client import ClaudeCliClient
    factory = main._client_factory(1, interactive=False,
                                   claude_cmd=["/resolved/path/claude"])
    client = factory("critic")
    assert client._inner._claude_cmd == ["/resolved/path/claude"]


def test_client_factory_critic_uses_claude_cli_even_with_codex_translator(monkeypatch):
    """Kritik zůstává na `claude` CLI NEZÁVISLE na `translator_backend` -
    žádný fallback, žádná podmínka na `--translator`."""
    from src.llm.client import ClaudeCliClient
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    factory = main._client_factory(1, interactive=False, translator_backend="codex")
    client = factory("critic")
    assert isinstance(client._inner, ClaudeCliClient)


def test_client_factory_translator_backend_claude_cli_uses_claude_cli_client(monkeypatch):
    """`--translator claude-cli` (spike 2026-09-22) - translator dostane
    `ClaudeCliClient` s translator-specifickým `reinforcement`/
    `fatal_error_cls`, kritik stejného runu zůstává na jeho vlastním
    `ClaudeCliFatalError` (žádná křížová kontaminace mezi rolemi)."""
    from src.llm.client import ClaudeCliClient, ClaudeCliFatalError, ClaudeCliTranslatorFatalError
    from src.agents import translator as translator_mod
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    factory = main._client_factory(1, interactive=False, translator_backend="claude-cli")
    t_client = factory("translator")
    assert isinstance(t_client._inner, ClaudeCliClient)
    assert t_client._inner._model == config.MODEL_TRANSLATOR
    assert t_client._inner._timeout == config.CLAUDE_CLI_TRANSLATOR_TIMEOUT_SECONDS
    assert t_client._inner._reinforcement == translator_mod.CLI_FORMAT_REINFORCEMENT
    assert t_client._inner._fatal_error_cls is ClaudeCliTranslatorFatalError
    c_client = factory("critic")
    assert c_client._inner._fatal_error_cls is ClaudeCliFatalError
    # Kritik má SVOJI reinforcement (critic.CLI_REINFORCEMENT, přidáno
    # 2026-09-22) - jinou než translator, ne None - ověřuje se u ní jen,
    # že translator/critic reinforcement NEJSOU stejný text (žádná
    # křížová kontaminace), přesný obsah kritikovy varianty testuje
    # test_client_factory_critic_uses_cli_reinforcement zvlášť.
    assert c_client._inner._reinforcement != t_client._inner._reinforcement


def test_client_factory_translator_default_claude_unaffected_by_critic_change(
        monkeypatch):
    """Translator (--translator claude, default) zůstává na AnthropicClient -
    tenhle plán mění JEN kritika."""
    from src.llm.client import AnthropicClient
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    factory = main._client_factory(1, interactive=False)
    client = factory("translator")
    assert isinstance(client._inner, AnthropicClient)


def test_client_factory_default_backend_claude_translator_unaffected(monkeypatch):
    """Beze změny chování pro VŠECHNA existující volání bez `translator_
    backend` argumentu - default `"claude"` musí `_polish_preflight`
    vůbec nezavolat (žádná FS-risk kontrola, když se Codex nepoužívá)."""
    from src.llm.client import AnthropicClient
    def boom():
        raise AssertionError("_polish_preflight se nemá volat pro claude backend")
    monkeypatch.setattr("main._polish_preflight", boom)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    factory = main._client_factory(1, interactive=False)
    client = factory("translator")
    assert isinstance(client._inner, AnthropicClient)


def test_client_factory_translator_backend_codex_preflight_failure_raises_fatal(monkeypatch):
    """Kolo 12 IMPORTANT (plan-consensus) - `CodexTranslatorFatalError`
    (ne holý `FatalRunError`) - tahle LÍNÁ preflight kontrola (uvnitř
    `factory()`) běží PO `state.begin_chapter()` (kapitola už
    `processing`) - bez správného typu by `_cmd_run` (Task 5) tenhle
    pád neoznačil `flagged`, kapitola by zůstala uvízlá stejně jako
    před kolem 10/11."""
    from src.llm.client import CodexTranslatorFatalError
    monkeypatch.setattr("main._polish_preflight",
                        lambda: (None, None, "Codex CLI není použitelné"))
    factory = main._client_factory(1, interactive=False, translator_backend="codex")
    with pytest.raises(CodexTranslatorFatalError, match="Codex CLI není použitelné"):
        factory("translator")


def test_run_translator_flag_passed_to_client_factory(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    # Kolo 4 BLOCKING (plan-consensus) - kolo 3 přidalo eager preflight
    # na začátek _cmd_run (main._polish_preflight()); bez mocku by test
    # narazil na SKUTEČNOU STYLIST_ACCEPT_FS_RISK/CODEX_MODEL/CLI
    # kontrolu (reálný filesystem/PATH lookup) a v CI bez codex binárky
    # by spadl na "== 0" dřív, než se spy factory vůbec zavolá.
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    # Kolo 22 (plan-consensus) - eager preflight teď navíc ověří
    # ANTHROPIC_API_KEY (kritik je vždy Claude) - test-prostředí ho
    # nemusí mít, bez mocku by test spadl na "== 0" dřív, než se spy
    # factory vůbec zavolá.
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    seen = {}
    def fake_process(db_path, chapter, *, client_factory, guide):
        seen["client_factory"] = client_factory
        state.update_chapter(db_path, chapter["idx"], status="done",
                             translated_text="hotovo")
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", fake_process)
    real_factory = main._client_factory
    captured = {}
    def spy_factory(rid, *, interactive, require_lock=None,
                    translator_backend="claude", claude_cmd=None):
        captured["translator_backend"] = translator_backend
        return real_factory(rid, interactive=interactive, require_lock=require_lock,
                            translator_backend=translator_backend, claude_cmd=claude_cmd)
    monkeypatch.setattr(main, "_client_factory", spy_factory)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 0
    assert captured["translator_backend"] == "codex"


def test_run_translator_flag_defaults_to_claude(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    monkeypatch.setattr(P, "process_chapter",
                        lambda db_path, chapter, *, client_factory, guide: {
                            "idx": chapter["idx"], "status": "done", "revision_rounds": 0})
    real_factory = main._client_factory
    captured = {}
    def spy_factory(rid, *, interactive, require_lock=None,
                    translator_backend="claude", claude_cmd=None):
        captured["translator_backend"] = translator_backend
        return real_factory(rid, interactive=interactive, require_lock=require_lock,
                            translator_backend=translator_backend, claude_cmd=claude_cmd)
    monkeypatch.setattr(main, "_client_factory", spy_factory)
    assert _run(["run"], tmp_path, monkeypatch) == 0   # BEZ --translator
    assert captured["translator_backend"] == "claude"


def test_run_translator_codex_without_fs_risk_optin_is_fatal(tmp_path, monkeypatch):
    """Stejná brána jako `polish` - `--translator codex` bez opt-inu
    nesmí tiše spadnout zpátky na Claude ani projít bez varování.
    Kolo 3 IMPORTANT (plan-consensus) - `_cmd_run` teď ověřuje eager,
    PŘED frontou (main.py, ne líné `_client_factory`), takže `pipeline.
    process_chapter` se v tomhle testu vůbec nezavolá."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] in ("pending", "processing")


def test_run_translator_codex_preflight_failure_still_recovers_processing(
        tmp_path, monkeypatch):
    """Kolo 8 IMPORTANT (plan-consensus) - kapitola uvízlá v `processing`
    z dřívějšího pádu MUSÍ být zotavená (vrácená do `pending`) i když
    `--translator codex` preflight selže - `state.recover_processing`
    je vždy úplně první krok KAŽDÉHO `run`, bez výjimky (jinak by
    zůstala navěky neviditelná pro `queue_for_run`, co vrací jen
    "pending"/"error", nikdy "processing")."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    state.set_status("data/state.sqlite3", 1, "processing")
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "pending"


def test_run_translator_codex_fs_risk_checked_even_with_empty_queue(tmp_path, monkeypatch):
    """Kolo 3 IMPORTANT (plan-consensus) - bez eager kontroly by prázdná
    fronta (kapitola už `done`) preflight úplně obešla - `client_factory
    ("translator")` by se nikdy nezavolalo, `--translator codex` by
    tiše "uspělo" (0 kapitol) bez jediného ověřeného Codex volání."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    state.update_chapter("data/state.sqlite3", 1, status="done", translated_text="x")
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1


def test_run_claude_cli_preflight_failure_blocks_queue_before_translation(
        tmp_path, monkeypatch):
    """Kolo 1 IMPORTANT (plan-consensus) - bez eager kontroly by
    chybějící/nepřihlášené `claude` CLI nechalo proběhnout celý
    (u --translator codex zaplacený) překlad, než by run selhal na
    kritikovi - stejné riziko jako `ANTHROPIC_API_KEY` (minulý plán,
    zrušeno) i jako Codexova FS-risk eager kontrola."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight",
                        lambda: (None, "claude CLI není přihlášené."))
    import src.pipeline as P
    calls = {"n": 0}
    def boom(db_path, chapter, *, client_factory, guide):
        calls["n"] += 1
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run"], tmp_path, monkeypatch) == 1
    assert calls["n"] == 0   # zadny preklad se vubec nespustil


def test_run_threads_preflight_resolved_claude_cmd_into_client_factory(
        tmp_path, monkeypatch):
    """Kolo 5 IMPORTANT (plan-consensus) - end-to-end ověření, že
    `_cmd_run` SKUTEČNĚ předá `_claude_cli_preflight()`'s resolvnutou
    hodnotu do `_client_factory(..., claude_cmd=...)`, ne jen že
    `_client_factory` sama umí parametr přijmout (to ověřují Task 2/3's
    unit testy zvlášť)."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight",
                        lambda: (["/resolved/claude"], None))
    import src.pipeline as P
    monkeypatch.setattr(P, "process_chapter",
                        lambda db_path, chapter, *, client_factory, guide: {
                            "idx": chapter["idx"], "status": "done", "revision_rounds": 0})
    real_factory = main._client_factory
    captured = {}
    def spy_factory(rid, *, interactive, require_lock=None,
                    translator_backend="claude", claude_cmd=None):
        captured["claude_cmd"] = claude_cmd
        return real_factory(rid, interactive=interactive, require_lock=require_lock,
                            translator_backend=translator_backend, claude_cmd=claude_cmd)
    monkeypatch.setattr(main, "_client_factory", spy_factory)
    assert _run(["run"], tmp_path, monkeypatch) == 0
    assert captured["claude_cmd"] == ["/resolved/claude"]


def test_run_translator_codex_error_notes_are_redacted(tmp_path, monkeypatch):
    """Kolo 3 IMPORTANT (plan-consensus) - `extract_json()`'s `ValueError`
    nese až 2000 raw znaků modelové odpovědi; `--translator codex` chyby
    musí projít stejnou redakcí jako `_cmd_polish` (`stylist.
    _redact_detail`), jinak by `chapters.notes` dostalo raw Codex výstup
    bez ohledu na `config.STYLIST_REPORT_REJECTED_TEXT`."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    def boom(db_path, chapter, *, client_factory, guide):
        raise ValueError("Nevalidní JSON. Raw:\ntajny-obsah-z-codexu")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 0
    notes = state.get_chapter("data/state.sqlite3", 1)["notes"]
    assert "tajny-obsah-z-codexu" not in notes
    assert "potlačeny" in notes


def test_run_translator_claude_error_notes_not_redacted(tmp_path, monkeypatch):
    """Beze změny chování pro default `claude` backend - žádná regrese v
    debugovatelnosti běžných Claude chyb (nemají s FS-risk nic společného)."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    def boom(db_path, chapter, *, client_factory, guide):
        raise ValueError("nejaka claude chyba")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run"], tmp_path, monkeypatch) == 0   # BEZ --translator
    notes = state.get_chapter("data/state.sqlite3", 1)["notes"]
    assert "nejaka claude chyba" in notes


def test_run_translator_codex_invalid_translation_output_is_fatal(tmp_path, monkeypatch):
    """Kolo 6 IMPORTANT (plan-consensus) - InvalidTranslationOutput ze
    scénové smyčky (translator._parse(), formát driftl) NESMÍ skončit
    jako per-kapitolový error - state.queue_for_run by ji jinak tiše
    zkoušel znovu při KAŽDÉM příštím run, na VŠECH takhle postižených
    kapitolách (stejné riziko jako kolo 2's StylistError fix, jiná
    příčina).

    Kolo 10 IMPORTANT (plan-consensus) - status je teď `flagged`, ne
    `pending`/`processing` - persistentní záznam, že tahle KONKRÉTNÍ
    kapitola spadla, vyžaduje explicitní `--retry-flagged`."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    from src.agents.translator import InvalidTranslationOutput
    def boom(db_path, chapter, *, client_factory, guide):
        raise InvalidTranslationOutput("chybí ===KONEC===")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "flagged"


def test_run_translator_codex_fatal_error_flags_chapter_not_silently_retried(
        tmp_path, monkeypatch):
    """Kolo 10 IMPORTANT (plan-consensus) - kapitola, na které vyletí
    CodexTranslatorFatalError (rozbitý CLI/auth), musí dostat
    persistentní `flagged` status, NE zůstat `processing`→`pending`
    limbo, co by DALŠÍ `run` (bez explicitního `--retry-flagged`) tiše
    znovu zkusil.

    Kolo 11 IMPORTANT (plan-consensus) - mock používá SPECIFICKY
    `CodexTranslatorFatalError` (ne holý `FatalRunError`) - `_cmd_run`
    teď rozlišuje podle TYPU, ne podle `args.translator`."""
    from src.llm.client import CodexTranslatorFatalError
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    calls = {"n": 0}
    def boom(db_path, chapter, *, client_factory, guide):
        calls["n"] += 1
        raise CodexTranslatorFatalError("codex auth expired")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "flagged"
    assert calls["n"] == 1


def test_run_translator_claude_cli_invalid_translation_output_is_fatal(tmp_path, monkeypatch):
    """`--translator claude-cli` (spike 2026-09-22) - stejné riziko jako
    Codex (kolo 6/10): reinforcement text SNIŽUJE formát-drift, ale
    NEGARANTUJE ho na nulu - InvalidTranslationOutput musí dostat stejnou
    flagged-status ochranu jako Codex, ne skončit jako tichý per-kapitolový
    error, co by `state.queue_for_run` navěky zkoušel znovu."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    from src.agents.translator import InvalidTranslationOutput
    def boom(db_path, chapter, *, client_factory, guide):
        raise InvalidTranslationOutput("chybí ===METADATA===")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "claude-cli"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "flagged"


def test_run_translator_claude_cli_fatal_error_flags_chapter_not_silently_retried(
        tmp_path, monkeypatch):
    """Mirror `test_run_translator_codex_fatal_error_flags_chapter_not_
    silently_retried` pro `claude-cli` backend - `ClaudeCliTranslatorFatalError`
    musí dostat stejnou flagged-status ochranu jako `CodexTranslatorFatalError`."""
    from src.llm.client import ClaudeCliTranslatorFatalError
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    calls = {"n": 0}
    def boom(db_path, chapter, *, client_factory, guide):
        calls["n"] += 1
        raise ClaudeCliTranslatorFatalError("claude cli auth expired")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "claude-cli"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "flagged"
    assert calls["n"] == 1


def test_run_translator_claude_cli_error_notes_are_redacted(tmp_path, monkeypatch):
    """Mirror `test_run_translator_codex_error_notes_are_redacted` pro
    `claude-cli` backend - raw modelová odpověď v `ValueError` nesmí
    skončit nezredigovaná v `chapters.notes`."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    def boom(db_path, chapter, *, client_factory, guide):
        raise ValueError("Nevalidní JSON. Raw:\ntajny-obsah-z-claude-cli")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "claude-cli"], tmp_path, monkeypatch) == 0
    notes = state.get_chapter("data/state.sqlite3", 1)["notes"]
    assert "tajny-obsah-z-claude-cli" not in notes
    assert "potlačeny" in notes


def test_run_translator_codex_fatal_error_console_output_is_redacted(
        tmp_path, monkeypatch, capsys):
    """Kolo 16 IMPORTANT (plan-consensus) - bare `raise` (beze změny
    zprávy) by re-raisovalo PŮVODNÍ, NEREDIGOVANOU výjimku - `_cmd_run`'s
    outer `except FatalRunError as e: print(f"Fatální chyba běhu: {e}")`
    (main.py) by ji vypsal RAW na konzoli, i když `chapters.notes`
    dostal správně redigovanou verzi. Musí se re-raisovat NOVÁ výjimka
    s redigovanou zprávou."""
    from src.llm.client import CodexTranslatorFatalError
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    def boom(db_path, chapter, *, client_factory, guide):
        raise CodexTranslatorFatalError("tajny-obsah-z-codexu")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    out = capsys.readouterr().out
    assert "tajny-obsah-z-codexu" not in out
    assert "potlačeny" in out


def test_run_translator_codex_generic_fatal_run_error_from_critic_not_flagged(
        tmp_path, monkeypatch):
    """Kolo 11 IMPORTANT (plan-consensus) - obecný FatalRunError (např.
    kritikův cost guard - kritik zůstává VŽDY Claude, i při --translator
    codex) NESMÍ dostat flagged/redakci určenou pro Codex-translator
    selhání - beze změny oproti chování PŘED tímhle plánem (kapitola
    zůstane processing, žádná falešná diagnostika o "chybě od Codexu")."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    def boom(db_path, chapter, *, client_factory, guide):
        raise FatalRunError("Cost guard: strop $5.00 překročen")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] in ("pending", "processing")


def test_run_translator_codex_lazy_preflight_failure_flags_chapter(tmp_path, monkeypatch):
    """Kolo 12 IMPORTANT (plan-consensus) - eager preflight (main.
    _cmd_run, kolo 8) může uspět, ale LÍNÁ kontrola uvnitř `_client_
    factory`'s `factory()` (Task 4) - volaná AŽ při prvním `factory
    ("translator")`, PO `state.begin_chapter()` (kapitola už `processing`) -
    může selhat SAMOSTATNĚ (jiné volání, jiný okamžik). I tenhle pád
    musí kapitolu označit `flagged`, ne ji nechat uvíznout - `factory()`
    teď vyhazuje `CodexTranslatorFatalError` (Task 4's kolo-12 fix),
    stejný typ jako `CodexLLMClient.complete()`, takže `_cmd_run`'s
    typová větev (kolo 11) ho zachytí stejně."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    calls = {"n": 0}
    def preflight():
        calls["n"] += 1
        if calls["n"] == 1:
            return ("m", ["codex"], None)   # eager (main._cmd_run) uspěje
        return (None, None, "Codex CLI mezitím přestalo fungovat")   # línÁ (factory) selže
    monkeypatch.setattr("main._polish_preflight", preflight)
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "flagged"


def test_run_translator_claude_invalid_translation_output_stays_per_chapter_error(
        tmp_path, monkeypatch):
    """Beze změny chování pro default `claude` backend - formát-drift
    riziko je specifické pro Codex (spike ho u Claude nepozoroval),
    takže Claude cesta zůstává na existujícím per-kapitolovém error."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    import src.pipeline as P
    from src.agents.translator import InvalidTranslationOutput
    def boom(db_path, chapter, *, client_factory, guide):
        raise InvalidTranslationOutput("rozbité JSON metadata")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run"], tmp_path, monkeypatch) == 0   # BEZ --translator
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "error"
