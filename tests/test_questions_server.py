import pytest
from fastapi.testclient import TestClient
from src import state
from src.review_ui import questions_server


def _db(tmp_path, questions=()):
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        for q in questions:
            conn.execute(
                "INSERT INTO questions (chapter_idx, kind, text, scope_key, "
                "guess_answer, severity) VALUES (?,?,?,?,?,?)",
                (q.get("chapter_idx"), q["kind"], q["text"], q["scope_key"],
                 q.get("guess_answer"), q.get("severity", "guess")))
    return db


def _app(tmp_path, questions=()):
    db = _db(tmp_path, questions)
    guide_path = str(tmp_path / "guide.json")
    app = questions_server.build_app(db, guide_path)
    return app, db


def test_get_questions_returns_unanswered_list(tmp_path):
    app, db = _app(tmp_path, questions=[
        {"kind": "term", "text": "Sedí to?", "scope_key": "Chicago",
         "guess_answer": "Chicago", "chapter_idx": 2},
    ])
    client = TestClient(app)
    r = client.get("/api/questions")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["text"] == "Sedí to?"
    assert rows[0]["guess_answer"] == "Chicago"
    assert rows[0]["chapter_idx"] == 2


def test_post_answer_writes_and_returns_requeue_info(tmp_path):
    app, db = _app(tmp_path, questions=[
        {"kind": "term", "text": "Sedí to?", "scope_key": "Chicago",
         "guess_answer": "Chicago", "chapter_idx": 2, "severity": "guess"},
    ])
    with state.connect(db) as conn:
        qid = conn.execute("SELECT id FROM questions").fetchone()["id"]
    client = TestClient(app)
    r = client.post("/api/answer", json={"qid": qid, "text": "Chicago"})
    assert r.status_code == 200
    body = r.json()
    assert "requeued" in body and "chapter_status_changed" in body
    q = state.get_question(db, qid)
    assert q["answer"] == "Chicago"


def test_post_answer_already_answered_returns_400(tmp_path):
    app, db = _app(tmp_path, questions=[
        {"kind": "term", "text": "Sedí to?", "scope_key": "Chicago",
         "guess_answer": "Chicago", "chapter_idx": 2},
    ])
    with state.connect(db) as conn:
        qid = conn.execute("SELECT id FROM questions").fetchone()["id"]
    client = TestClient(app)
    r1 = client.post("/api/answer", json={"qid": qid, "text": "Chicago"})
    assert r1.status_code == 200
    r2 = client.post("/api/answer", json={"qid": qid, "text": "Chicago"})
    assert r2.status_code == 400


def test_post_answer_empty_text_returns_400(tmp_path):
    app, db = _app(tmp_path, questions=[
        {"kind": "term", "text": "Sedí to?", "scope_key": "Chicago",
         "guess_answer": "Chicago", "chapter_idx": 2},
    ])
    with state.connect(db) as conn:
        qid = conn.execute("SELECT id FROM questions").fetchone()["id"]
    client = TestClient(app)
    r = client.post("/api/answer", json={"qid": qid, "text": "   "})
    assert r.status_code == 400


def test_post_answer_unknown_qid_returns_400(tmp_path):
    app, db = _app(tmp_path, questions=[])
    client = TestClient(app)
    r = client.post("/api/answer", json={"qid": 999, "text": "x"})
    assert r.status_code == 400


def test_index_serves_html(tmp_path):
    app, db = _app(tmp_path, questions=[])
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_post_dismiss_marks_resolved_without_glossary_write(tmp_path):
    app, db = _app(tmp_path, questions=[
        {"kind": "term", "text": "Termín se překládá různě: pružná, prdele "
         "(kapitoly 5). Který tvar je správný?", "scope_key": "pružná"},
    ])
    with state.connect(db) as conn:
        qid = conn.execute("SELECT id FROM questions").fetchone()["id"]
    client = TestClient(app)
    r = client.post("/api/dismiss", json={"qid": qid, "note": "stemmer sum"})
    assert r.status_code == 200
    q = state.get_question(db, qid)
    assert q["answer"] is not None
    assert "zamítnuto" in q["answer"]
    assert "stemmer sum" in q["answer"]
    # NEobjeví se v nezodpovězených
    assert q["id"] not in [r["id"] for r in state.unanswered_questions(db)]


def test_post_dismiss_already_answered_returns_400(tmp_path):
    app, db = _app(tmp_path, questions=[
        {"kind": "term", "text": "Sedí to?", "scope_key": "x", "guess_answer": "x"},
    ])
    with state.connect(db) as conn:
        qid = conn.execute("SELECT id FROM questions").fetchone()["id"]
    client = TestClient(app)
    r1 = client.post("/api/dismiss", json={"qid": qid})
    assert r1.status_code == 200
    r2 = client.post("/api/dismiss", json={"qid": qid})
    assert r2.status_code == 400


def test_post_dismiss_unknown_qid_returns_400(tmp_path):
    app, db = _app(tmp_path, questions=[])
    client = TestClient(app)
    r = client.post("/api/dismiss", json={"qid": 999})
    assert r.status_code == 400
