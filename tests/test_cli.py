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
