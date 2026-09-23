from src import state, glossary, guide, requeue


def _setup(tmp_path):
    db = str(tmp_path / "s.sqlite3"); state.init_db(db)
    gp = str(tmp_path / "guide.json")
    guide.save_guide(gp, {"characters": [], "places": [], "relationships": [],
                          "style": "", "rules": []})
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (1,'K1','Harry met Bob.','done')")
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (2,'K2','Bob left.','done')")
    tid = glossary.add_candidate(db, "Bob", "Bob")
    state.replace_term_mentions(db, 2, [
        {"term_id": tid, "cz_form": "Bobem", "scene_idx": None, "source": "detected"}])
    return db, gp, tid


def test_answer_promotes_term_and_requeues_when_changed(tmp_path):
    db, gp, tid = _setup(tmp_path)
    qid = state.upsert_open_question(db, {"chapter_idx": 2, "kind": "term",
        "text": "Bob?", "scope_key": tid, "guess_answer": "Bob", "severity": "guess"})
    out = requeue.apply_answer(db, gp, qid, "Robert")
    assert 2 in out["requeued"]
    assert state.get_chapter(db, 2)["status"] == "pending"
    assert [t for t in glossary.all_terms(db) if t["term_id"] == tid][0]["status"] == "approved"


def test_answer_equal_to_guess_does_not_requeue(tmp_path):
    db, gp, tid = _setup(tmp_path)
    qid = state.upsert_open_question(db, {"chapter_idx": 2, "kind": "term",
        "text": "Bob?", "scope_key": tid, "guess_answer": "Bob", "severity": "guess"})
    out = requeue.apply_answer(db, gp, qid, "Bob")
    assert out["requeued"] == []
    assert state.get_chapter(db, 2)["status"] == "done"


def test_blocking_answer_requeues_only_after_last_blocking(tmp_path):
    db, gp, tid = _setup(tmp_path)
    state.set_status(db, 1, "needs_human")
    q1 = state.upsert_open_question(db, {"chapter_idx": 1, "kind": "name",
        "text": "kdo je Aria?", "scope_key": "aria", "guess_answer": None,
        "severity": "blocking"})
    q2 = state.upsert_open_question(db, {"chapter_idx": 1, "kind": "name",
        "text": "kdo je Kell?", "scope_key": "kell", "guess_answer": None,
        "severity": "blocking"})
    requeue.apply_answer(db, gp, q1, "Aria")
    assert state.get_chapter(db, 1)["status"] == "needs_human"  # ještě q2
    requeue.apply_answer(db, gp, q2, "Kel")
    assert state.get_chapter(db, 1)["status"] == "pending"
    # odpověď na blocking otázku založila approved glosář řádek
    assert any(t["status"] == "approved" and t["canonical_en"] == "aria"
               for t in glossary.all_terms(db))


def test_blocking_answer_with_alternatives_creates_approved_with_alts(tmp_path):
    db, gp, tid = _setup(tmp_path)
    state.set_status(db, 1, "needs_human")
    q = state.upsert_open_question(db, {"chapter_idx": 1, "kind": "name",
        "text": "kdo je Grey Cloak?", "scope_key": "Grey Cloak",
        "guess_answer": None, "severity": "blocking"})
    requeue.apply_answer(db, gp, q, "Šedý plášť | Šedého pláště | šedým pláštěm")
    t = [x for x in glossary.all_terms(db) if x["canonical_en"] == "Grey Cloak"][0]
    assert t["status"] == "approved" and t["cz"] == "Šedý plášť"
    assert set(t["accepted_alt"]) == {"Šedého pláště", "šedým pláštěm"}
    assert state.get_chapter(db, 1)["status"] == "pending"


def test_process_chapter_then_answer_requeues_original_chapter(tmp_path, monkeypatch):
    """End-to-end: pipeline vytvoří kandidáta + mention, answer != guess → kapitola pending."""
    from src import pipeline, glossary
    from src.agents import translator as T, critic as C
    db = str(tmp_path / "s.sqlite3"); state.init_db(db)
    gp = str(tmp_path / "guide.json")
    guide.save_guide(gp, {"characters": [], "places": [], "terms": [],
                          "relationships": [], "style": "", "rules": []})
    state.seed_chapters(db, [type("Ch", (), {"index": 1, "title": "K1",
                                             "raw_text": "Foo appeared."})()])
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "Fů se objevil.", [{"term_en": "Foo", "cz": "Fů", "note": "", "type": "term"}],
        [], []))
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    def cf(_a):
        from src.llm.client import FakeLLMClient, Completion
        return FakeLLMClient([Completion("x", False, 1, 1)])
    pipeline.process_chapter(db, state.get_chapter(db, 1), client_factory=cf,
                             guide=guide.load_guide(gp))
    q = [x for x in state.unanswered_questions(db) if x["kind"] == "term"][0]
    assert q["guess_answer"] == "Fů"
    out = requeue.apply_answer(db, gp, q["id"], "Fúa")   # jiné než guess
    assert 1 in out["requeued"]
    assert state.get_chapter(db, 1)["status"] == "pending"


def test_preview_affected_chapters_for_known_term(tmp_path):
    """Otázka o existujícím termínu - náhled ukáže kapitoly, co ho zmiňují,
    BEZ zápisu odpovědi (na rozdíl od apply_answer)."""
    db, gp, tid = _setup(tmp_path)
    q = state.get_question(db, state.upsert_open_question(db, {
        "chapter_idx": 2, "kind": "term", "text": "Bob?", "scope_key": tid,
        "guess_answer": "Bob", "severity": "guess"}))
    affected = requeue.preview_affected_chapters(db, q)
    assert affected == [2]
    # otázka zůstává nezodpovězená - preview nic nezapisuje
    assert state.get_question(db, q["id"])["answer"] is None


def test_preview_affected_chapters_for_brand_new_term_is_empty(tmp_path):
    """Nový termín (dosud v glosáři není) nemá žádné existující zmínky -
    prázdný seznam, ne chyba."""
    db, gp, tid = _setup(tmp_path)
    q = state.get_question(db, state.upsert_open_question(db, {
        "chapter_idx": 1, "kind": "term", "text": "Nový termín?",
        "scope_key": "Nikdy neviděný povrch", "guess_answer": "X",
        "severity": "guess"}))
    assert requeue.preview_affected_chapters(db, q) == []
