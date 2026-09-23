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


def test_init_db_migrates_existing_db_missing_draft_columns(tmp_path):
    """`draft_text`/`draft_updated_at` (2026-09-23, uložení rozpracovaného
    konceptu) - PRVNÍ migrace v týhle DB, `CREATE TABLE IF NOT EXISTS`
    samo o sobě existující tabulku nedoplní o nový sloupec. Simuluje
    STAROU DB (bez těch dvou sloupců, jako je dnešní reálná projektová
    DB) - `init_db` na ní musí doplnit sloupce, NE spadnout, a existující
    data zachovat beze změny."""
    db = str(tmp_path / "s.sqlite3")
    old_schema = """
    CREATE TABLE chapters (
        idx INTEGER PRIMARY KEY, title TEXT NOT NULL, raw_text TEXT NOT NULL,
        translated_text TEXT, status TEXT NOT NULL DEFAULT 'pending',
        revision_rounds INTEGER NOT NULL DEFAULT 0, notes TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """
    with state.connect(db) as conn:
        conn.executescript(old_schema)
        conn.execute("INSERT INTO chapters (idx,title,raw_text,translated_text) "
                     "VALUES (1,'K1','en text','cz text')")
    state.init_db(db)   # migrace - nesmí spadnout, nesmí smazat data
    with state.connect(db) as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(chapters)")}
        assert "draft_text" in cols and "draft_updated_at" in cols
        row = conn.execute("SELECT * FROM chapters WHERE idx=1").fetchone()
        assert row["translated_text"] == "cz text"   # existující data zachována
        assert row["draft_text"] is None


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
