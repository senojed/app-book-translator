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


# --- běhy a účtování LLM volání -------------------------------------------

def create_run(db_path: str, command: str) -> int:
    with connect(db_path) as conn:
        cur = conn.execute("INSERT INTO runs (command) VALUES (?)", (command,))
        return cur.lastrowid


def finish_run(db_path: str, run_id: int, status: str) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE runs SET ended_at = CURRENT_TIMESTAMP, status = ? "
                     "WHERE id = ?", (status, run_id))


def record_llm_call(db_path: str, *, run_id, agent, provider, model,
                    input_tokens, output_tokens, cost_usd, truncated,
                    status, error_class) -> None:
    """Zápis po KAŽDÉM volání (i selhaném) - audit i cost guard čtou odtud."""
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO llm_calls (run_id,agent,provider,model,input_tokens,"
            "output_tokens,cost_usd,truncated,status,error_class) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (run_id, agent, provider, model, input_tokens, output_tokens,
             cost_usd, int(bool(truncated)), status, error_class))


def spent_so_far(db_path: str, run_id: int) -> float:
    with connect(db_path) as conn:
        r = conn.execute("SELECT COALESCE(SUM(cost_usd),0) AS s FROM llm_calls "
                         "WHERE run_id = ?", (run_id,)).fetchone()
        return float(r["s"])


def get_run_spend_ceiling(db_path: str, run_id: int):
    with connect(db_path) as conn:
        r = conn.execute("SELECT spend_ceiling FROM runs WHERE id = ?",
                         (run_id,)).fetchone()
        return r["spend_ceiling"] if r else None


def set_run_spend_ceiling(db_path: str, run_id: int, value: float) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE runs SET spend_ceiling = ? WHERE id = ?",
                     (value, run_id))


# --- kapitoly ---------------------------------------------------------------

_UPDATABLE = ("translated_text", "status", "revision_rounds", "notes")


def seed_chapters(db_path: str, chapters) -> None:
    """Nasype kapitoly z ingestu. Idempotentní - existující idx nechá být."""
    with connect(db_path) as conn:
        for ch in chapters:
            conn.execute(
                "INSERT OR IGNORE INTO chapters (idx,title,raw_text,status) "
                "VALUES (?,?,?,'pending')", (ch.index, ch.title, ch.raw_text))


def get_chapter(db_path: str, idx: int):
    with connect(db_path) as conn:
        r = conn.execute("SELECT * FROM chapters WHERE idx = ?", (idx,)).fetchone()
    return dict(r) if r else None


def chapters_by_status(db_path: str, statuses: tuple) -> list:
    marks = ",".join("?" * len(statuses))
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM chapters WHERE status IN ({marks}) ORDER BY idx",
            tuple(statuses)).fetchall()
    return [dict(r) for r in rows]


def queue_for_run(db_path: str) -> list:
    """Co bere `run`: pending a error (error = automatický retry).
    needs_human a flagged čekají na člověka."""
    return chapters_by_status(db_path, ("pending", "error"))


def recover_processing(db_path: str) -> int:
    """Kapitola uvízlá v `processing` = pád v půlce. Vrať ji do fronty."""
    with connect(db_path) as conn:
        cur = conn.execute("UPDATE chapters SET status='pending', "
                           "updated_at=CURRENT_TIMESTAMP WHERE status='processing'")
        return cur.rowcount


def set_status(db_path: str, idx: int, status: str) -> None:
    update_chapter(db_path, idx, status=status)


def update_chapter(db_path: str, idx: int, **fields) -> None:
    cols = [k for k in fields if k in _UPDATABLE]
    if not cols:
        return
    sets = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = CURRENT_TIMESTAMP"
    with connect(db_path) as conn:
        conn.execute(f"UPDATE chapters SET {sets} WHERE idx = ?",
                     tuple(fields[c] for c in cols) + (idx,))


def retry_flagged(db_path: str, idxs) -> int:
    """flagged → pending a vynuluj kola revize, ať smyčka může znovu doopravdy běžet."""
    with connect(db_path) as conn:
        if idxs:
            marks = ",".join("?" * len(idxs))
            cur = conn.execute(
                f"UPDATE chapters SET status='pending', revision_rounds=0, "
                f"updated_at=CURRENT_TIMESTAMP WHERE status='flagged' AND idx IN ({marks})",
                tuple(idxs))
        else:
            cur = conn.execute(
                "UPDATE chapters SET status='pending', revision_rounds=0, "
                "updated_at=CURRENT_TIMESTAMP WHERE status='flagged'")
        return cur.rowcount


def counts_by_status(db_path: str) -> dict:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT status, COUNT(*) c FROM chapters "
                            "GROUP BY status").fetchall()
    return {r["status"]: r["c"] for r in rows}


def is_db_empty(db_path: str) -> bool:
    with connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) c FROM chapters").fetchone()["c"] == 0


def reset_book(db_path: str) -> None:
    """Smaže veškerý stav knihy. Pro `init --reset`. Pořadí kvůli FK."""
    with connect(db_path) as conn:
        for table in ("term_mentions", "questions", "drift_reports", "llm_calls",
                      "runs", "glossary", "chapters"):
            conn.execute(f"DELETE FROM {table}")


# --- run lock ---------------------------------------------------------------

class LockError(RuntimeError):
    """Jiný mutující příkaz už běží."""


_LOCK_STALE_SECONDS = 6 * 3600


def _pid_alive(pid: int) -> bool:
    """Nedestruktivní zjištění, jestli proces žije.
    Na Windows NIKDY os.kill - ten volá TerminateProcess."""
    if pid is None or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _lock_is_live(lock_path: str) -> bool:
    """Zámek je živý jen když jde přečíst, má živý PID a není starší 6 h."""
    import datetime
    import json as _json
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        pid = int(data["pid"])
        ts = datetime.datetime.fromisoformat(data["ts"])
    except Exception:
        return False   # nečitelný / poškozený zámek bereme jako zastaralý
    if (datetime.datetime.now() - ts).total_seconds() > _LOCK_STALE_SECONDS:
        return False
    return _pid_alive(pid)


def acquire_lock(lock_path: str) -> None:
    import datetime
    import json as _json
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    for _ in range(3):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _lock_is_live(lock_path):
                raise LockError(
                    f"Běží jiný příkaz (zámek {lock_path}). Počkej na jeho konec.")
            try:
                os.unlink(lock_path)   # zastaralý zámek přebíráme
            except FileNotFoundError:
                pass
            continue
        payload = _json.dumps({"pid": os.getpid(),
                               "ts": datetime.datetime.now().isoformat()})
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        return
    raise LockError(f"Zámek {lock_path} se nepodařilo získat.")


def release_lock(lock_path: str) -> None:
    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass


@contextmanager
def run_lock(lock_path: str):
    acquire_lock(lock_path)
    try:
        yield
    finally:
        release_lock(lock_path)
