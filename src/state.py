"""SQLite stav běhu. Jediné místo, které mluví s DB. Nezná LLM ani překlad."""
import os
import sqlite3
from contextlib import contextmanager

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chapters (
    idx INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    translated_text TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    revision_rounds INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS glossary (
    term_id TEXT PRIMARY KEY,
    canonical_en TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    cz TEXT NOT NULL,
    accepted_alt TEXT NOT NULL DEFAULT '[]',
    note TEXT,
    type TEXT NOT NULL DEFAULT 'term',
    status TEXT NOT NULL DEFAULT 'candidate',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_idx INTEGER,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    guess_answer TEXT,
    severity TEXT NOT NULL,
    answer TEXT,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS term_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term_id TEXT NOT NULL REFERENCES glossary(term_id),
    cz_form TEXT,
    chapter_idx INTEGER NOT NULL,
    scene_idx INTEGER,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drift_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    up_to_chapter INTEGER NOT NULL,
    report TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    status TEXT,
    spend_ceiling REAL
);
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER REFERENCES runs(id),
    agent TEXT,
    provider TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    truncated INTEGER,
    status TEXT NOT NULL,
    error_class TEXT,
    ts TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_questions_open_chapter
    ON questions(chapter_idx, kind, scope_key, severity) WHERE answer IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_questions_open_global
    ON questions(kind, scope_key, severity)
    WHERE answer IS NULL AND chapter_idx IS NULL;
"""


@contextmanager
def connect(db_path: str):
    """Otevře DB, zapne cizí klíče, na úspěšný konec bloku commitne."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    """Vytvoří celé schéma. Idempotentní - lze volat při každém startu."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
