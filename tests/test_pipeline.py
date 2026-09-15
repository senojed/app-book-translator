import json
from src import state, glossary, pipeline
from src.llm.client import Completion
from src.agents import translator as T, critic as C


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p)
    state.seed_chapters(p, [type("Ch", (), {"index": 1, "title": "K1",
                                            "raw_text": "Harry met Bob."})()])
    return p


def _factory(_agent):  # fake klient nikdy nevolá reálné API v těchto testech
    from src.llm.client import FakeLLMClient
    return FakeLLMClient([Completion("unused", False, 1, 1)])


def test_clean_chapter_reaches_done(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        translation="Harry potkal Boba.", new_terms=[], rendered_terms=[], questions=[]))
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "done"
    assert state.get_chapter(db, 1)["translated_text"] == "Harry potkal Boba."


def test_process_chapter_notes_have_finding_ids(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "špatný překlad", [], [], []))
    monkeypatch.setattr(T, "revise_chapter", lambda *a, **k: T.TranslationResult(
        "pořád špatný", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    ch = state.get_chapter(db, 1)
    pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    row = state.get_chapter(db, 1)
    saved = json.loads(row["notes"])
    assert saved   # nálezy skutečně vznikly
    assert all("id" in f and "resolved" in f for f in saved)


def test_critical_finding_triggers_revision_then_flags_after_max(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "špatný překlad", [], [], []))
    monkeypatch.setattr(T, "revise_chapter", lambda *a, **k: T.TranslationResult(
        "pořád špatný", [], [], []))
    always_bad = [{"source": "critic", "type": "fidelity", "severity": "critical",
                   "action": "revise", "term_id": None, "expected": None,
                   "actual": None, "cz_excerpt": "x", "issue": "chyba", "suggestion": "y"}]
    monkeypatch.setattr(C, "review", lambda *a, **k: always_bad)
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "flagged"
    assert state.get_chapter(db, 1)["revision_rounds"] == 2  # MAX_REVIZE


def test_blocking_question_sets_needs_human(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "překlad", [], [], [{"kind": "name", "scope_key": "cand_x",
                             "guess_answer": None, "text": "kdo je X?",
                             "severity": "blocking"}]))
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    ch = state.get_chapter(db, 1)
    out = pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "needs_human"
    assert state.chapter_has_open_blocking(db, 1)


def test_new_term_creates_candidate_and_question(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "Nevernever je divný.", [{"term_en": "Nevernever", "cz": "Nikdykdy",
                                  "note": "", "type": "place"}], [], []))
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    ch = state.get_chapter(db, 1)
    pipeline.process_chapter(db, ch, client_factory=_factory, guide={
        "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    terms = glossary.all_terms(db)
    cand = [t for t in terms if t["canonical_en"] == "Nevernever"]
    assert cand and cand[0]["status"] == "candidate"
    assert any(q["kind"] == "term" for q in state.unanswered_questions(db))
    # nový kandidát MUSÍ mít term_mentions řádek (jinak ho requeue nenajde),
    # i když jeho EN povrch není v EN textu kapitoly
    assert state.chapters_mentioning_term(db, cand[0]["term_id"]) == [1]


def test_processing_recovered_before_next_run(tmp_path, monkeypatch):
    db = _db(tmp_path)
    state.set_status(db, 1, "processing")
    assert state.recover_processing(db) == 1


def test_critic_fatal_error_propagates_not_flagged(tmp_path, monkeypatch):
    db = _db(tmp_path)
    from src.llm.client import FatalRunError
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "překlad", [], [], []))
    def boom(*a, **k): raise FatalRunError("bad key")
    monkeypatch.setattr(C, "review", boom)
    ch = state.get_chapter(db, 1)
    with __import__("pytest").raises(FatalRunError):
        pipeline.process_chapter(db, ch, client_factory=_factory, guide={
            "characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert state.get_chapter(db, 1)["status"] != "flagged"


def test_hallucinated_rendered_term_does_not_trigger_revision(tmp_path, monkeypatch):
    db = _db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("UPDATE glossary SET canonical_en='Grey Cloak', cz='Šedý plášť', "
                     "status='approved' WHERE term_id='t1'")
    # translator hlásí rendered_term, který ve výsledném CZ NENÍ
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "Šedý plášť promluvil.",   # CZ obsahuje kanonický tvar
        [], [{"term_id": "t1", "cz_as_used": "Popelář"}], []))   # ale hlásí "Popelář"
    monkeypatch.setattr(C, "review", lambda *a, **k: [])
    out = pipeline.process_chapter(db, state.get_chapter(db, 1), client_factory=_factory,
        guide={"characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "done"          # žádná falešná inconsistency/revize
    assert out["revision_rounds"] == 0


def test_critic_recoverable_failure_flags_chapter(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(T, "translate_scene", lambda *a, **k: T.TranslationResult(
        "překlad", [], [], []))
    def boom(*a, **k): raise ValueError("rozbitý JSON od kritika")
    monkeypatch.setattr(C, "review", boom)
    out = pipeline.process_chapter(db, state.get_chapter(db, 1), client_factory=_factory,
        guide={"characters": [], "places": [], "relationships": [], "style": "", "rules": []})
    assert out["status"] == "flagged"
    assert "kritik selhal" in state.get_chapter(db, 1)["notes"]


def test_run_drift_check_creates_global_question(tmp_path):
    db = _db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='done' WHERE idx=1")
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (2,'K2','x','done')")
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) "
                     "VALUES ('tc','Council','Rada')")
    state.replace_term_mentions(db, 1, [{"term_id": "tc", "cz_form": "Rada",
                                         "scene_idx": None, "source": "detected"}])
    state.replace_term_mentions(db, 2, [{"term_id": "tc", "cz_form": "Koncil",
                                         "scene_idx": None, "source": "detected"}])
    drifts = pipeline.run_drift_check(db, 2)
    assert drifts and drifts[0]["term_id"] == "tc"
    gq = [q for q in state.unanswered_questions(db) if q["chapter_idx"] is None]
    assert gq and gq[0]["scope_key"] == "tc"
