from src import state


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p)
    with state.connect(p) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) VALUES (1,'K1','x','processing')")
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t1','Foo','Fu')")
    return p


def test_upsert_open_question_dedups_and_updates(tmp_path):
    db = _db(tmp_path)
    q = {"chapter_idx": 1, "kind": "term", "text": "q1", "scope_key": "t1",
         "guess_answer": "Fu", "severity": "guess"}
    i1 = state.upsert_open_question(db, q)
    q2 = dict(q, text="q1-updated", guess_answer="Fů")
    i2 = state.upsert_open_question(db, q2)
    assert i1 == i2
    row = state.get_question(db, i1)
    assert row["text"] == "q1-updated" and row["guess_answer"] == "Fů"


def test_upsert_global_question_separate_from_chapter(tmp_path):
    db = _db(tmp_path)
    state.upsert_open_question(db, {"chapter_idx": 1, "kind": "term", "text": "a",
                                   "scope_key": "t1", "guess_answer": None,
                                   "severity": "guess"})
    gid = state.upsert_open_question(db, {"chapter_idx": None, "kind": "term",
                                         "text": "drift", "scope_key": "t1",
                                         "guess_answer": None, "severity": "guess"})
    assert state.get_question(db, gid)["chapter_idx"] is None
    assert len(state.unanswered_questions(db)) == 2


def test_delete_open_questions_keeps_answered(tmp_path):
    db = _db(tmp_path)
    state.upsert_open_question(db, {"chapter_idx": 1, "kind": "term", "text": "open",
                                   "scope_key": "t1", "guess_answer": None,
                                   "severity": "guess"})
    with state.connect(db) as conn:
        conn.execute("INSERT INTO questions (chapter_idx,kind,text,scope_key,"
                     "severity,answer) VALUES (1,'style','x','h','guess','done')")
    state.delete_open_questions_for_chapter(db, 1)
    assert len(state.unanswered_questions(db)) == 0
    with state.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM questions").fetchone()["c"] == 1


def test_chapter_has_open_blocking(tmp_path):
    db = _db(tmp_path)
    state.upsert_open_question(db, {"chapter_idx": 1, "kind": "name", "text": "?",
                                   "scope_key": "t1", "guess_answer": None,
                                   "severity": "blocking"})
    assert state.chapter_has_open_blocking(db, 1) is True
    q = state.unanswered_questions(db)[0]
    state.answer_question(db, q["id"], "odpoved")
    assert state.chapter_has_open_blocking(db, 1) is False


def test_replace_term_mentions_and_lookup(tmp_path):
    db = _db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='done' WHERE idx=1")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t1", "cz_form": None, "scene_idx": None, "source": "omission"}])
    assert state.chapters_mentioning_term(db, "t1") == [1]
    state.replace_term_mentions(db, 1, [])  # smaže
    assert state.chapters_mentioning_term(db, "t1") == []


def test_commit_chapter_result_is_atomic(tmp_path):
    db = _db(tmp_path)  # má chapter 1 (status processing), glossary t1
    good_cand = {"term_id": "cand_new", "canonical_en": "New", "aliases": [],
                 "cz": "Nový", "accepted_alt": [], "note": "", "type": "term",
                 "status": "candidate"}
    bad_mention = {"term_id": "NEEXISTUJE", "cz_form": "x", "scene_idx": None,
                   "source": "detected"}  # poruší FK → výjimka uprostřed transakce B
    import pytest
    with pytest.raises(Exception):
        state.commit_chapter_result(db, 1, translated_text="CZ", revision_rounds=1,
            notes_json="[]", status="done", new_candidates=[good_cand],
            mentions=[bad_mention],
            questions=[{"chapter_idx": 1, "kind": "term", "text": "q", "scope_key": "t1",
                        "guess_answer": None, "severity": "guess"}])
    # VŠECHNO se rollbacklo - kandidát, otázka, stav kapitoly
    assert state.get_chapter(db, 1)["status"] == "processing"
    assert state.get_chapter(db, 1)["translated_text"] is None
    assert state.unanswered_questions(db) == []
    with state.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM glossary WHERE term_id='cand_new'"
                            ).fetchone()["c"] == 0
