"""
Perzistentní stav běhu v SQLite. Kniha se překládá dlouho a běh může spadnout
(síť, rate limit, restart stroje) - stav musí přežít proces.

Stavy kapitoly:
  pending          - ještě nezpracována
  translated       - přeložena, čeká na kritika
  critic_flagged   - kritik našel problém, čeká na opravu
  done             - hotovo, prošlo kritikem
  needs_human      - agent narazil na otázku, kterou nedokáže sám rozhodnout
  error            - zpracování spadlo (výjimka), detail v critic_notes; 'run' to zkusí znovu
"""
import sqlite3
import json
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS chapters (
    idx INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    translated_text TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    critic_notes TEXT,           -- JSON list nálezů kritika
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS open_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_idx INTEGER NOT NULL,
    question TEXT NOT NULL,
    context TEXT,
    answer TEXT,                 -- NULL dokud uživatel neodpoví
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS cross_ref_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    up_to_chapter INTEGER NOT NULL,
    report TEXT NOT NULL,        -- JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def connect(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str):
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def seed_chapters(db_path: str, chapters):
    """Vloží kapitoly z ingestu, pokud v DB ještě nejsou (idempotentní)."""
    with connect(db_path) as conn:
        for ch in chapters:
            existing = conn.execute("SELECT idx FROM chapters WHERE idx = ?", (ch.index,)).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO chapters (idx, title, raw_text, status) VALUES (?, ?, ?, 'pending')",
                (ch.index, ch.title, ch.raw_text),
            )


def get_chapter(db_path: str, idx: int):
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM chapters WHERE idx = ?", (idx,)).fetchone()
        return dict(row) if row else None


def get_pending_chapters(db_path: str, statuses=("pending", "critic_flagged", "error")):
    with connect(db_path) as conn:
        placeholders = ",".join("?" * len(statuses))
        rows = conn.execute(
            f"SELECT * FROM chapters WHERE status IN ({placeholders}) ORDER BY idx", statuses
        ).fetchall()
        return [dict(r) for r in rows]


def update_chapter(db_path: str, idx: int, **fields):
    if not fields:
        return
    fields["updated_at"] = "CURRENT_TIMESTAMP_PLACEHOLDER"
    set_clause = ", ".join(
        f"{k} = CURRENT_TIMESTAMP" if v == "CURRENT_TIMESTAMP_PLACEHOLDER" else f"{k} = ?"
        for k, v in fields.items()
    )
    values = [v for v in fields.values() if v != "CURRENT_TIMESTAMP_PLACEHOLDER"]
    with connect(db_path) as conn:
        conn.execute(f"UPDATE chapters SET {set_clause} WHERE idx = ?", (*values, idx))


def add_open_question(db_path: str, chapter_idx: int, question: str, context: str = ""):
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO open_questions (chapter_idx, question, context) VALUES (?, ?, ?)",
            (chapter_idx, question, context),
        )


def get_unanswered_questions(db_path: str):
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM open_questions WHERE answer IS NULL ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def answer_question(db_path: str, question_id: int, answer: str):
    """Zapíše odpověď. Vrací index kapitoly, ke které otázka patří (nebo None) -
    volající podle toho může kapitolu vrátit k přepracování."""
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE open_questions SET answer = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (answer, question_id),
        )
        row = conn.execute(
            "SELECT chapter_idx FROM open_questions WHERE id = ?", (question_id,)
        ).fetchone()
        return row["chapter_idx"] if row else None


def chapter_has_unanswered_questions(db_path: str, chapter_idx: int) -> bool:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM open_questions WHERE chapter_idx = ? AND answer IS NULL LIMIT 1",
            (chapter_idx,),
        ).fetchone()
        return row is not None


def requeue_chapter(db_path: str, idx: int) -> bool:
    """Vrátí kapitolu do fronty k přepracování. Jen z stavů, kde to dává smysl
    (needs_human, critic_flagged, error) - hotovou kapitolu nepřepisuje.
    Vrací True, pokud se stav změnil."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE chapters SET status = 'pending', updated_at = CURRENT_TIMESTAMP "
            "WHERE idx = ? AND status IN ('needs_human', 'critic_flagged', 'error')",
            (idx,),
        )
        return cur.rowcount > 0


def save_cross_ref_report(db_path: str, up_to_chapter: int, report: dict):
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO cross_ref_reports (up_to_chapter, report) VALUES (?, ?)",
            (up_to_chapter, json.dumps(report, ensure_ascii=False)),
        )
