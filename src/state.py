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
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            # `OpenProcess` samo o sobě NESTAČÍ - handle jde otevřít i na
            # PID, co už skončil (objekt procesu ve Windows chvíli přežívá
            # po ukončení, obzvlášť dokud na něj někdo jiný drží handle).
            # Ověřeno reálně: zabitý `polish-review` server (killnutý
            # `taskkill /F`) měl `OpenProcess` úspěšný ještě chvíli po
            # smrti, `_lock_is_live` ho tak brala jako živý a `polish`
            # se odmítal spustit "Běží jiný příkaz", i když zámek byl
            # dávno mrtvý. Bez `GetExitCodeProcess` kontroly je tenhle
            # check nespolehlivý.
            exit_code = ctypes.c_ulong(0)
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
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


def _write_lock_tmp(lock_path: str, payload: dict) -> str:
    """Zapíše payload do UNIKÁTNÍHO tmp souboru (spec kolo 16 - sdílená
    pevná tmp cesta by dva souběžní volající - heartbeat vlákno +
    synchronní refresh requestu - mohli navzájem poškodit interleaved
    zápisy) a vrátí jeho cestu, NEpublikuje ještě nic na `lock_path`.
    Selže-li samotný ZÁPIS, tmp soubor se úklidí (kolo 2 plán-ping-pongu
    IMPORTANT, stejný princip jako `_atomic_write_json`). `flush()`+
    `os.fsync()` před uzavřením (kolo 6 plán-ping-pongu NIT, stejný
    princip jako `_atomic_write_json`)."""
    import json as _json
    import threading
    import uuid
    directory = os.path.dirname(lock_path) or "."
    tmp = os.path.join(
        directory, f".{os.path.basename(lock_path)}."
                  f"{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(_json.dumps(payload))
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return tmp


def _publish_lock_exclusive(lock_path: str, payload: dict) -> None:
    """PRVOTNÍ publikace zámku - `os.rename` na Windows selže
    (`FileExistsError`), pokud `lock_path` UŽ existuje, což je tu
    ŽÁDOUCÍ (exkluzivita, ne jen atomicita zápisu - spec kolo 14). Tmp
    soubor se úklidí při JAKÉMKOLI selhání publikace, ne jen očekávaném
    `FileExistsError` (kolo 2 plán-ping-pongu IMPORTANT)."""
    tmp = _write_lock_tmp(lock_path, payload)
    try:
        os.rename(tmp, lock_path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _publish_lock_overwrite(lock_path: str, payload: dict) -> None:
    """REFRESH zámku, co UŽ vlastníme (kolo 1 BLOCKING plán-ping-pongu -
    `os.rename` by tu VŽDY selhalo, protože `lock_path` cílevědomě
    existuje a patří NÁM; `os.replace` je tu správně, protože
    vlastnictví se ověřuje SAMOSTATNĚ, PŘED voláním týhle funkce). Tmp
    soubor se úklidí i při selhání `os.replace` (kolo 2 plán-ping-pongu
    IMPORTANT)."""
    tmp = _write_lock_tmp(lock_path, payload)
    try:
        os.replace(tmp, lock_path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def acquire_lock(lock_path: str) -> None:
    """Existence souboru jako mutex - `os.rename` na existující cíl na
    Windows selže (`FileExistsError`), takže publikace je i exkluzivní
    (ne jen atomická). Zbytkové riziko: dva procesy mohou NEZÁVISLE
    vyhodnotit stejný STARÝ zámek jako mrtvý a oba se ho pokusit
    převzít - to tenhle fix NEŘEŠÍ (spec kolo 15, mimo rozsah - vyžaduje
    skutečný OS-level zámek nebo DB transakci)."""
    import datetime
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    for _ in range(3):
        if os.path.exists(lock_path):
            if _lock_is_live(lock_path):
                raise LockError(
                    f"Běží jiný příkaz (zámek {lock_path}). Počkej na jeho konec.")
            try:
                os.unlink(lock_path)   # zastaralý zámek přebíráme
            except FileNotFoundError:
                pass
        try:
            _publish_lock_exclusive(
                lock_path, {"pid": os.getpid(), "ts": datetime.datetime.now().isoformat()})
            return
        except FileExistsError:
            continue   # někdo jiný publikoval mezitím - zkus znovu
    raise LockError(f"Zámek {lock_path} se nepodařilo získat.")


def refresh_lock(lock_path: str) -> None:
    """Přepíše `ts` v zámku, co UŽ vlastníme - pro dlouho běžící server
    (`polish-review`), co potřebuje přežít `_LOCK_STALE_SECONDS` (spec
    kolo 2/3/7). Ověří vlastnictví (PID v souboru == náš PID) PŘED
    zápisem - jinak by refresh mohl přepsat zámek, co mezitím legitimně
    převzal jiný proces (spec kolo 3). TOCTOU mezi čtením a zápisem
    zůstává zdokumentované zbytkové riziko (spec kolo 4/15), ne řešeno
    tady. Selhání zápisu (`_publish_lock_overwrite`) je ZAHRNUTÉ ve
    STEJNÉM `try` jako čtení (kolo 11 plán-ping-pongu IMPORTANT - dřív
    zápis běžel MIMO `try`, takže obyčejný `OSError` z `os.replace`
    - plný disk, práva - propadl jako SUROVÝ `OSError`, ne `LockError`,
    a heartbeat/`_require_lock`'s `except state.LockError` by ho vůbec
    nezachytily; ztráta zámku musí být VŽDY `LockError`, ať volající
    kód má JEDNO místo, kde ji chytit)."""
    import datetime
    import json as _json
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        owner_pid = int(data["pid"])
        if owner_pid != os.getpid():
            raise LockError(f"Zámek {lock_path} teď vlastní jiný proces "
                            f"(pid={owner_pid}) - ztratili jsme vlastnictví.")
        _publish_lock_overwrite(
            lock_path, {"pid": os.getpid(), "ts": datetime.datetime.now().isoformat()})
    except (OSError, ValueError, KeyError) as e:
        raise LockError(f"Zámek {lock_path} zmizel, je nečitelný, nebo se "
                        f"nepodařilo obnovit ({type(e).__name__}: {e}) - "
                        "ztratili jsme vlastnictví.") from e


def release_lock(lock_path: str) -> None:
    """Neshoda vlastnictví (PID v souboru != náš) → NEmazat - je to teď
    cizí, legitimní zámek (spec kolo 3). Nečitelný/poškozený OBSAH
    existujícího souboru taky NEmazat (kolo 2 plán-ping-pongu BLOCKING -
    dřív `except: pass` pokračovalo na `os.unlink` bez ohledu na to, co
    se stalo výš - přesně to, co má tenhle vlastnický check zabránit,
    obcházené vlastní chybovou větví). JEN "soubor vůbec neexistuje" je
    legitimní no-op (nic k mazání, žádná neshoda vlastnictví se neřeší)."""
    import json as _json
    try:
        with open(lock_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        owner_pid = int(data["pid"])
    except FileNotFoundError:
        return   # nic tu není, nic k mazání
    except (OSError, ValueError, KeyError):
        return   # existuje, ale je nečitelný/poškozený - NEmazat, nemůžeme ověřit vlastnictví
    if owner_pid != os.getpid():
        return   # cizí, legitimní zámek
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


# --- otázky -----------------------------------------------------------------

def _open_question_row(conn, q: dict):
    """Najde otevřenou otázku se stejným klíčem. Globální (chapter_idx NULL) a
    kapitolové otázky mají různý predikát - proto explicitní větvení místo
    obecného ON CONFLICT."""
    if q.get("chapter_idx") is None:
        return conn.execute(
            "SELECT * FROM questions WHERE chapter_idx IS NULL AND kind=? "
            "AND scope_key=? AND severity=? AND answer IS NULL",
            (q["kind"], q["scope_key"], q["severity"])).fetchone()
    return conn.execute(
        "SELECT * FROM questions WHERE chapter_idx=? AND kind=? AND scope_key=? "
        "AND severity=? AND answer IS NULL",
        (q["chapter_idx"], q["kind"], q["scope_key"], q["severity"])).fetchone()


def _upsert_question_conn(conn, q: dict) -> int:
    """Upsert nad otevřeným spojením - používá i transakce B (commit_chapter_result)."""
    existing = _open_question_row(conn, q)
    if existing:
        conn.execute("UPDATE questions SET text=?, guess_answer=? WHERE id=?",
                     (q.get("text", ""), q.get("guess_answer"), existing["id"]))
        return existing["id"]
    cur = conn.execute(
        "INSERT INTO questions (chapter_idx,kind,text,scope_key,guess_answer,"
        "severity) VALUES (?,?,?,?,?,?)",
        (q.get("chapter_idx"), q["kind"], q.get("text", ""), q["scope_key"],
         q.get("guess_answer"), q["severity"]))
    return cur.lastrowid


def upsert_open_question(db_path: str, q: dict) -> int:
    """Zapíše otázku. Zodpovězená otázka stejného klíče novou NEblokuje."""
    with connect(db_path) as conn:
        return _upsert_question_conn(conn, q)


def delete_open_questions_for_chapter(db_path: str, chapter_idx: int) -> None:
    """Rerun kapitoly začíná načisto - staré nezodpovězené otázky zahodíme."""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM questions WHERE chapter_idx=? AND answer IS NULL",
                     (chapter_idx,))


def unanswered_questions(db_path: str) -> list:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM questions WHERE answer IS NULL "
                            "ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_question(db_path: str, qid: int):
    with connect(db_path) as conn:
        r = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    return dict(r) if r else None


def answer_question(db_path: str, qid: int, answer_text: str):
    with connect(db_path) as conn:
        conn.execute("UPDATE questions SET answer=?, resolved_at=CURRENT_TIMESTAMP "
                     "WHERE id=?", (answer_text, qid))
        r = conn.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    return dict(r) if r else None


def chapter_has_open_blocking(db_path: str, chapter_idx: int) -> bool:
    with connect(db_path) as conn:
        r = conn.execute(
            "SELECT COUNT(*) c FROM questions WHERE chapter_idx=? "
            "AND severity='blocking' AND answer IS NULL", (chapter_idx,)).fetchone()
    return r["c"] > 0


# --- pozorované výskyty termínů + drift -------------------------------------

def replace_term_mentions(db_path: str, chapter_idx: int, mentions) -> None:
    """Kapitola se může přeložit znovu - staré výskyty musí zmizet, jinak by
    drift počítal s tvary z výsledku, který už neexistuje."""
    with connect(db_path) as conn:
        conn.execute("DELETE FROM term_mentions WHERE chapter_idx=?", (chapter_idx,))
        for m in mentions or []:
            d = m if isinstance(m, dict) else {
                "term_id": m.term_id, "cz_form": m.cz_form,
                "scene_idx": m.scene_idx, "source": m.source}
            conn.execute(
                "INSERT INTO term_mentions (term_id,cz_form,chapter_idx,scene_idx,"
                "source) VALUES (?,?,?,?,?)",
                (d["term_id"], d.get("cz_form"), chapter_idx, d.get("scene_idx"),
                 d.get("source", "detected")))


def chapters_mentioning_term(db_path: str, term_id: str,
                             statuses=("done", "flagged")) -> list:
    marks = ",".join("?" * len(statuses))
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT DISTINCT tm.chapter_idx AS idx FROM term_mentions tm "
            f"JOIN chapters c ON c.idx = tm.chapter_idx "
            f"WHERE tm.term_id = ? AND c.status IN ({marks}) ORDER BY tm.chapter_idx",
            (term_id,) + tuple(statuses)).fetchall()
    return [r["idx"] for r in rows]


def chapter_mentions(db_path: str, chapter_idx: int) -> list:
    """Mentions JEDNÉ kapitoly - na rozdíl od `all_term_mentions`
    (agregátní, přes víc kapitol) tohle `polish` potřebuje jako VSTUP pro
    `concordance.check_chapter`/`build_mentions` (rendered_terms), aby
    nepřišel o termíny zachycené jen translatorovým vlastním hlášením."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT term_id, cz_form, scene_idx, source FROM term_mentions "
            "WHERE chapter_idx=? ORDER BY id", (chapter_idx,)).fetchall()
    return [dict(r) for r in rows]


def all_term_mentions(db_path: str, statuses=("done", "flagged")) -> list:
    """Podklad pro drift check - jen kapitoly, jejichž překlad platí."""
    marks = ",".join("?" * len(statuses))
    with connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT tm.* FROM term_mentions tm JOIN chapters c ON c.idx = tm.chapter_idx "
            f"WHERE c.status IN ({marks}) ORDER BY tm.id", tuple(statuses)).fetchall()
    return [dict(r) for r in rows]


def save_drift_report(db_path: str, up_to_chapter: int, report) -> None:
    import json as _json
    with connect(db_path) as conn:
        conn.execute("INSERT INTO drift_reports (up_to_chapter, report) VALUES (?,?)",
                     (up_to_chapter, _json.dumps(report, ensure_ascii=False)))


# --- transakce kolem zpracování kapitoly ------------------------------------

def begin_chapter(db_path: str, idx: int) -> None:
    """Transakce A: kapitola jde do `processing` a její staré nezodpovězené
    otázky zmizí (rerun je založí znovu podle aktuálního překladu)."""
    with connect(db_path) as conn:
        conn.execute("UPDATE chapters SET status='processing', "
                     "updated_at=CURRENT_TIMESTAMP WHERE idx=?", (idx,))
        conn.execute("DELETE FROM questions WHERE chapter_idx=? AND answer IS NULL",
                     (idx,))


def _insert_candidate(conn, cand: dict) -> str:
    """Vloží kandidáta a vrátí term_id, pod kterým skutečně žije.

    Kolize term_id má dvě příčiny: (a) tentýž povrch už v glosáři je - pak jen
    vrátíme existující id; (b) dva RŮZNÉ povrchy se slugifikovaly stejně - pak
    hledáme volné id se suffixem. Nikdy nesmí vzniknout mention na cizí entitě.
    """
    import json as _json
    base = cand["term_id"]
    tid = base
    n = 2
    while True:
        try:
            conn.execute(
                "INSERT INTO glossary (term_id,canonical_en,aliases,cz,accepted_alt,"
                "note,type,status) VALUES (?,?,?,?,?,?,?,?)",
                (tid, cand.get("canonical_en", ""),
                 _json.dumps(cand.get("aliases") or [], ensure_ascii=False),
                 cand.get("cz", ""),
                 _json.dumps(cand.get("accepted_alt") or [], ensure_ascii=False),
                 cand.get("note", ""), cand.get("type", "term"),
                 cand.get("status", "candidate")))
            return tid
        except sqlite3.IntegrityError:
            row = conn.execute("SELECT canonical_en, aliases FROM glossary "
                               "WHERE term_id=?", (tid,)).fetchone()
            if row is not None:
                surfaces = [(row["canonical_en"] or "").strip().lower()]
                surfaces += [(a or "").strip().lower()
                             for a in _json.loads(row["aliases"] or "[]")]
                if (cand.get("canonical_en", "") or "").strip().lower() in surfaces:
                    return tid          # táž entita, jen už tam je
            tid = f"{base}_{n}"
            n += 1


def commit_chapter_result(db_path: str, idx: int, *, translated_text: str,
                          revision_rounds: int, notes_json: str, status: str,
                          new_candidates: list, mentions: list,
                          questions: list) -> dict:
    """Transakce B: glosář + term_mentions + otázky + kapitola najednou.
    Výjimka kdekoli uvnitř = nic se necommitne (connect commituje jen na
    čistý průchod), stav zůstane `processing` a další `run` kapitolu zopakuje."""
    with connect(db_path) as conn:
        remap: dict = {}
        for cand in new_candidates or []:
            final = _insert_candidate(conn, cand)
            if final != cand["term_id"]:
                remap[cand["term_id"]] = final

        conn.execute("DELETE FROM term_mentions WHERE chapter_idx=?", (idx,))
        for m in mentions or []:
            d = m if isinstance(m, dict) else {
                "term_id": m.term_id, "cz_form": m.cz_form,
                "scene_idx": m.scene_idx, "source": m.source}
            tid = remap.get(d["term_id"], d["term_id"])
            conn.execute(
                "INSERT INTO term_mentions (term_id,cz_form,chapter_idx,scene_idx,"
                "source) VALUES (?,?,?,?,?)",
                (tid, d.get("cz_form"), idx, d.get("scene_idx"),
                 d.get("source", "detected")))

        created = 0
        for q in questions or []:
            q = dict(q)
            q["scope_key"] = remap.get(q.get("scope_key"), q.get("scope_key"))
            _upsert_question_conn(conn, q)
            created += 1

        conn.execute(
            "UPDATE chapters SET translated_text=?, revision_rounds=?, notes=?, "
            "status=?, updated_at=CURRENT_TIMESTAMP WHERE idx=?",
            (translated_text, revision_rounds, notes_json, status, idx))

    return {"questions_created": created,
            "candidates_created": len(new_candidates or [])}


# --- odpověď na otázku (jedna transakce) ------------------------------------

def _apply_glossary_op(conn, op: str, key: str, value: str, type_: str = "term") -> None:
    """SQL varianty glossary operací - musí běžet nad JEDNÍM spojením, aby byly
    ve stejné transakci jako zápis odpovědi a requeue kapitol."""
    import json as _json
    from src import glossary          # lazy: glossary importuje state, ne naopak
    if op == "promote":
        conn.execute("UPDATE glossary SET status='approved', cz=?, "
                     "updated_at=CURRENT_TIMESTAMP WHERE term_id=?", (value, key))
    elif op == "add_approved":
        tid = "term_" + glossary.slugify(key)
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,aliases,cz,accepted_alt,"
            "note,type,status) VALUES (?,?,'[]',?,'[]','',?,'approved')",
            (tid, key, value, type_))
    elif op == "add_accepted_alt":
        r = conn.execute("SELECT accepted_alt FROM glossary WHERE term_id=?",
                         (key,)).fetchone()
        if r is None:
            return
        alts = _json.loads(r["accepted_alt"] or "[]")
        if value not in alts:
            alts.append(value)
        conn.execute("UPDATE glossary SET accepted_alt=?, updated_at=CURRENT_TIMESTAMP "
                     "WHERE term_id=?", (_json.dumps(alts, ensure_ascii=False), key))
    else:
        raise ValueError(f"neznámá glossary operace: {op}")


def commit_answer(db_path: str, *, qid: int, answer_text: str, glossary_ops: list,
                  requeue_idxs: list, blocking_chapter_idx=None) -> dict:
    """Zápis odpovědi + glosář + přepočet kapitol v jedné transakci.
    Pád uprostřed = otázka zůstane nezodpovězená a `answer` se dá pustit znovu."""
    changed = False
    with connect(db_path) as conn:
        for op in glossary_ops or []:
            _apply_glossary_op(conn, *op)
        conn.execute("UPDATE questions SET answer=?, resolved_at=CURRENT_TIMESTAMP "
                     "WHERE id=?", (answer_text, qid))
        if blocking_chapter_idx is not None:
            left = conn.execute(
                "SELECT COUNT(*) c FROM questions WHERE chapter_idx=? "
                "AND severity='blocking' AND answer IS NULL",
                (blocking_chapter_idx,)).fetchone()["c"]
            if left == 0:
                conn.execute("UPDATE chapters SET status='pending', "
                             "updated_at=CURRENT_TIMESTAMP WHERE idx=? "
                             "AND status='needs_human'", (blocking_chapter_idx,))
                changed = True
        for idx in requeue_idxs or []:
            conn.execute("UPDATE chapters SET status='pending', "
                         "updated_at=CURRENT_TIMESTAMP WHERE idx=?", (idx,))
    return {"requeued": list(requeue_idxs or []), "chapter_status_changed": changed}
