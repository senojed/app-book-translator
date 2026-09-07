import sqlite3
from src import state


def test_init_db_creates_all_tables(tmp_path):
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"chapters", "questions", "glossary", "term_mentions",
            "drift_reports", "runs", "llm_calls"} <= names


def test_init_db_is_idempotent(tmp_path):
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    state.init_db(db)  # nesmí spadnout


def test_partial_unique_index_on_open_questions(tmp_path):
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (1,'K1','x','pending')")
        conn.execute("INSERT INTO questions (chapter_idx,kind,text,scope_key,"
                     "severity) VALUES (1,'term','q','t1','guess')")
        # stejný klíč, obě otevřené → konflikt
        try:
            conn.execute("INSERT INTO questions (chapter_idx,kind,text,scope_key,"
                         "severity) VALUES (1,'term','q2','t1','guess')")
            raised = False
        except sqlite3.IntegrityError:
            raised = True
    assert raised


def test_answered_question_does_not_block_new_one(tmp_path):
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,status) "
                     "VALUES (1,'K1','x','pending')")
        conn.execute("INSERT INTO questions (chapter_idx,kind,text,scope_key,"
                     "severity,answer) VALUES (1,'term','q','t1','guess','ans')")
        conn.execute("INSERT INTO questions (chapter_idx,kind,text,scope_key,"
                     "severity) VALUES (1,'term','q2','t1','guess')")  # nesmí spadnout
