# Book Translator (pokus 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Postavit multiagentní CLI překladač knih EN→CZ (pipeline scout → translator → kritik → revizor, orchestrace v kódu), který přeloží ~350stránkový román s navazatelným během a lidským review návodu.

**Architecture:** Přístup A ze specu - pevná sekvence agentů na kapitolu + omezená revizní smyčka, LLM se volá jen na to co kód neumí (překlad, posouzení). Deterministická kontrola konzistence termínů (`concordance`) místo LLM agenta. Stav v SQLite (navazatelný běh, transakce po kapitole). Provider vrstva izoluje `anthropic` SDK do jednoho souboru.

**Tech Stack:** Python 3.11+, `anthropic` SDK, `ebooklib` + `beautifulsoup4` (EPUB), `fastapi` + `uvicorn` (review UI), `pytest` (dev). SQLite (stdlib `sqlite3`).

**Spec:** `docs/superpowers/specs/2026-09-06-book-translator-design.md` - plán argumentuje ze specu, executor čte oba.

## Global Constraints

- **Python 3.11+.** Runtime závislosti: `anthropic`, `ebooklib`, `beautifulsoup4`, `fastapi`, `uvicorn`. Dev: `pytest`, `httpx` (FastAPI TestClient).
- **Import layout:** `config.py` je v kořeni repa, `src/` je balíček. Kořen repa je na `sys.path` přes `pyproject.toml` `[tool.pytest.ini_options] pythonpath = ["."]` (pro testy) a přes `conftest.py` v kořeni + `sys.path` insert v `main.py` (pro CLI). Uvnitř `src/` moduly importují sourozence jako `from src import X`, kořenový config jako `import config`. Nikdy nespoléhat na `src/foo.py` jako top-level `import foo`.
- **UTF-8 stdout:** `main.py` na startu volá `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` a totéž pro `sys.stderr`. Windows `cp1252` konzole jinak padá `UnicodeEncodeError` na českém výstupu. Testy i CLI musí projít i v `cp1252` konzoli.
- **Próza NIKDY v JSON.** Translator vrací překlad jako čistý text mezi `===PREKLAD===` a `===METADATA===`, metadata jako malý JSON za druhým markerem. Marker `===METADATA===` přítomen ale JSON za ním nevalidní → `ValueError` (rozbitý agent output → kapitola `error`). Marker úplně chybí → tolerovat (prázdné listy).
- **Glosář je v SQLite** (tabulka `glossary`), ne JSON soubor - zápis glosáře a commit kapitoly musí být jedna transakce. `guide.json` / `guide.draft.json` zůstávají soubory.
- **Model / ceny jsou config, ne logika.** `config.py` drží model IDs, `$/MTok` sazby (in/out) pro cost guard, kontextové/výstupní limity. Před pilotem ověřit proti Anthropic docs.
- **`anthropic` SDK importuje JEN `src/llm/client.py`.** Žádný jiný modul.
- **term_id je deterministické:** `"term_" + slug(canonical_en)` u seedovaných, `"cand_" + slug(term_en)` u kandidátů. Párování termínů podle povrchu (`canonical_en`/`aliases`), ne podle `term_id` řetězce.
- **Pipeline volá agenty modulově-kvalifikovaně** (`translator.translate_scene`, `critic.review`) - `from src.agents import translator, critic`, ne `from ... import translate_scene`. Umožní to monkeypatch v testech.
- **Commity často** - každý task končí commitnutým, samostatně testovatelným deliverable.
- Konfigurační výchozí hodnoty (v `config.py`): `MAX_REVIZE = 2`, `CHAPTER_SPLIT_WORD_THRESHOLD = 3500`, `CROSS_REF_EVERY_N = 10`, `API_MAX_RETRIES = 8`, `MAX_SPEND_USD = 15.0`.

---

## Task 1: Projektový skeleton + config + DB schéma

**Files:**
- Create: `pyproject.toml`
- Create: `conftest.py` (kořen repa) - `import sys, os; sys.path.insert(0, os.path.dirname(__file__))`
- Create: `config.py`
- Create: `src/__init__.py`
- Create: `src/state.py`
- Create: `tests/__init__.py`
- Create: `tests/test_state_schema.py`
- Create: `.gitignore` (pokud chybí položky) - přidat `data/`, `output/`, `__pycache__/`, `*.pyc`, `.venv/`

**Interfaces:**
- Consumes: nic
- Produces:
  - `config` modul s konstantami: `DATA_DIR="data"`, `OUTPUT_DIR="output"`, `DB_PATH`, `GUIDE_PATH="data/guide.json"`, `GUIDE_DRAFT_PATH="data/guide.draft.json"`, `LOCK_PATH="data/.book-translator.lock"`, `MODEL_SCOUT`/`MODEL_TRANSLATOR`/`MODEL_CRITIC = "claude-sonnet-5"`, `PRICE_IN_PER_MTOK`/`PRICE_OUT_PER_MTOK` (dict per model), `MAX_TOKENS_SCOUT=16000`, `MAX_TOKENS_TRANSLATOR=16000`, `MAX_TOKENS_CRITIC=4000`, `MAX_REVIZE=2`, `CHAPTER_SPLIT_WORD_THRESHOLD=3500`, `CROSS_REF_EVERY_N=10`, `API_MAX_RETRIES=8`, `MAX_SPEND_USD=15.0`, `ANTHROPIC_API_KEY` (z env).
  - `state.connect(db_path) -> sqlite3.Connection` - context manager, `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`, commit na úspěch.
  - `state.init_db(db_path)` - vytvoří celé schéma (všechny tabulky + partial unique indexy z §"state.py - SQLite schéma"). Idempotentní (`CREATE TABLE IF NOT EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`).

- [ ] **Step 1: pyproject.toml + config.py**

`pyproject.toml`:
```toml
[project]
name = "book-translator"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = ["anthropic", "ebooklib", "beautifulsoup4", "fastapi", "uvicorn"]

[project.optional-dependencies]
dev = ["pytest", "httpx"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`conftest.py` (kořen):
```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

`config.py`:
```python
"""Centrální konfigurace. API klíč z env. Model IDs a ceny jsou tady, ne v logice."""
import os

DATA_DIR = "data"
OUTPUT_DIR = "output"
DB_PATH = os.path.join(DATA_DIR, "state.sqlite3")
GUIDE_PATH = os.path.join(DATA_DIR, "guide.json")
GUIDE_DRAFT_PATH = os.path.join(DATA_DIR, "guide.draft.json")
LOCK_PATH = os.path.join(DATA_DIR, ".book-translator.lock")
OUTPUT_TXT = os.path.join(OUTPUT_DIR, "kniha_cz.txt")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_MAX_RETRIES = 8

# Před pilotem ověřit proti Anthropic docs (model active? ceny? limity?).
MODEL_SCOUT = "claude-sonnet-5"
MODEL_TRANSLATOR = "claude-sonnet-5"
MODEL_CRITIC = "claude-sonnet-5"

# $/MTok - vstup / výstup, per model. Cost guard čte odtud.
PRICE_IN_PER_MTOK = {"claude-sonnet-5": 2.0}
PRICE_OUT_PER_MTOK = {"claude-sonnet-5": 10.0}

MAX_TOKENS_SCOUT = 16000
MAX_TOKENS_TRANSLATOR = 16000
MAX_TOKENS_CRITIC = 4000

MAX_REVIZE = 2
CHAPTER_SPLIT_WORD_THRESHOLD = 3500
CROSS_REF_EVERY_N = 10
SCOUT_CHUNK_WORD_LIMIT = 40000
MAX_SPEND_USD = 15.0
```

- [ ] **Step 2: Write the failing test** — `tests/test_state_schema.py`

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_state_schema.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'src.state'` / `state` has no `init_db`.

- [ ] **Step 4: Implement `src/state.py` (schéma + connect)**

```python
"""SQLite stav běhu. Jediné místo, které mluví s DB. Nezná LLM ani překlad."""
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
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    import os
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_state_schema.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml config.py src/__init__.py src/state.py tests/__init__.py tests/test_state_schema.py .gitignore
git commit -m "feat: projektový skeleton, config, SQLite schéma"
```

---

## Task 2: ingest (EPUB / TXT → kapitoly, dělení na scény)

**Files:**
- Create: `src/ingest.py` (port logiky z `pokus-1/src/ingest.py`, s opravou EPUB spine už zapracovanou v pokusu 1)
- Create: `tests/test_ingest.py` (port + rozšíření z `pokus-1/tests/test_parsing.py`)

**Interfaces:**
- Consumes: nic (čisté funkce)
- Produces:
  - `Chapter` = `dataclass(index: int, title: str, raw_text: str)`
  - `load_book(path: str) -> list[Chapter]` - `.epub` přes `_load_epub`, `.txt` přes `_load_txt`, jinak `ValueError`
  - `split_into_scenes(text: str, word_threshold: int) -> list[str]`

- [ ] **Step 1: Write failing tests** — `tests/test_ingest.py`

```python
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import ingest


def test_split_scenes_short_text_stays_whole():
    text = "slovo " * 100
    assert ingest.split_into_scenes(text, 3500) == [text]


def test_split_scenes_by_separator():
    a = "veta jedna. " * 400
    b = "veta dva. " * 400
    parts = ingest.split_into_scenes(a + "\n* * *\n" + b, 1000)
    assert len(parts) == 2
    assert parts[0].startswith("veta jedna")


def test_split_scenes_too_fragmented_returns_whole():
    text = "\n\n".join(f"odstavec {i} " * 50 for i in range(30))
    assert ingest.split_into_scenes(text, 200) == [text]


def test_load_txt_no_headings_single_chapter(tmp_path):
    p = tmp_path / "k.txt"
    p.write_text("Text bez nadpisu. " * 50, encoding="utf-8")
    chs = ingest.load_book(str(p))
    assert len(chs) == 1
    assert "segmentace" in chs[0].title.lower()


def test_load_txt_splits_on_chapter_headings(tmp_path):
    body = "Radek textu. " * 40 + "\n"
    p = tmp_path / "k.txt"
    p.write_text(f"Chapter 1\n{body}Chapter 2\n{body}Chapter 3\n{body}", encoding="utf-8")
    chs = ingest.load_book(str(p))
    assert [c.index for c in chs] == [1, 2, 3]
    assert chs[0].title == "Chapter 1"


def test_load_epub_uses_spine_order(tmp_path):
    import ebooklib
    from ebooklib import epub
    b = epub.EpubBook()
    b.set_identifier("id"); b.set_title("T"); b.set_language("en")
    long = "Dost dlouhy text kapitoly aby preskocil minimum. " * 20
    c3 = epub.EpubHtml(title="Three", file_name="c3.xhtml", uid="c3"); c3.content = f"<h1>Three</h1><p>{long}</p>"
    c1 = epub.EpubHtml(title="One", file_name="c1.xhtml", uid="c1"); c1.content = f"<h1>One</h1><p>{long}</p>"
    c2 = epub.EpubHtml(title="Two", file_name="c2.xhtml", uid="c2"); c2.content = f"<h1>Two</h1><p>{long}</p>"
    for c in (c3, c1, c2): b.add_item(c)
    b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    b.spine = [c1, c2, c3]
    p = str(tmp_path / "t.epub")
    epub.write_epub(p, b)
    chs = ingest.load_book(p)
    assert [c.title for c in chs] == ["One", "Two", "Three"]


def test_load_book_rejects_unknown_extension(tmp_path):
    p = tmp_path / "k.pdf"; p.write_text("x", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        ingest.load_book(str(p))
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: FAIL - no module `src.ingest`.

- [ ] **Step 3: Implement `src/ingest.py`**

Zkopíruj `pokus-1/src/ingest.py` do `src/ingest.py` beze změny (logika je otestovaná a EPUB spine oprava je v ní). Ověř, že obsahuje: `Chapter` dataclass, `load_book`, `_load_epub` (iteruje `book.spine`, fallback `get_items_of_type`, `item.get_type() != ebooklib.ITEM_DOCUMENT: continue`), `_load_txt` (regex `CHAPTER_HEADING_RE`), `split_into_scenes`.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_ingest.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/ingest.py tests/test_ingest.py
git commit -m "feat: ingest (EPUB spine order, TXT, dělení na scény) - port z pokus-1"
```

---

## Task 3: llm/parsing (split_sections, extract_json)

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/parsing.py`
- Create: `tests/test_llm_parsing.py`

**Interfaces:**
- Consumes: nic
- Produces:
  - `split_sections(raw: str, markers: list[str]) -> dict[str, str]` - rozdělí text podle markerů; klíč = marker bez `=`, hodnota = text mezi tímto a dalším markerem (strip). Text před prvním markerem se ignoruje.
  - `extract_json(raw: str) -> dict` - očistí ```` ```json ```` fence, zkusí `json.loads`; fallback regex `\{.*\}` DOTALL; při selhání `ValueError` s prvními 2000 znaky raw.

- [ ] **Step 1: Write failing tests** — `tests/test_llm_parsing.py`

```python
import pytest
from src.llm import parsing


def test_split_sections_two_markers():
    raw = "junk\n===PREKLAD===\nAhoj svete.\n===METADATA===\n{\"a\": 1}"
    out = parsing.split_sections(raw, ["===PREKLAD===", "===METADATA==="])
    assert out["PREKLAD"] == "Ahoj svete."
    assert out["METADATA"] == '{"a": 1}'


def test_split_sections_missing_second_marker():
    raw = "===PREKLAD===\nJen preklad."
    out = parsing.split_sections(raw, ["===PREKLAD===", "===METADATA==="])
    assert out["PREKLAD"] == "Jen preklad."
    assert out.get("METADATA", "") == ""


def test_extract_json_plain():
    assert parsing.extract_json('{"x": 5}') == {"x": 5}


def test_extract_json_with_fence():
    assert parsing.extract_json('```json\n{"x": 5}\n```') == {"x": 5}


def test_extract_json_with_surrounding_text():
    assert parsing.extract_json('blah {"x": 5} trailing') == {"x": 5}


def test_extract_json_unparseable_raises():
    with pytest.raises(ValueError):
        parsing.extract_json("tohle neni json")
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_llm_parsing.py -v`
Expected: FAIL - no module.

- [ ] **Step 3: Implement `src/llm/parsing.py`**

```python
"""Parsování odpovědí modelu. Bez importu anthropic."""
import json
import re


def split_sections(raw: str, markers: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    text = raw
    for i, marker in enumerate(markers):
        if marker not in text:
            continue
        after = text.split(marker, 1)[1]
        nxt = markers[i + 1] if i + 1 < len(markers) else None
        if nxt and nxt in after:
            value = after.split(nxt, 1)[0]
        else:
            value = after
        out[marker.strip("=")] = value.strip()
        text = after
    return out


def extract_json(raw: str) -> dict:
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Nevalidní JSON. Raw:\n{raw[:2000]}")
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_llm_parsing.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm/__init__.py src/llm/parsing.py tests/test_llm_parsing.py
git commit -m "feat: llm/parsing (split_sections, extract_json)"
```

---

## Task 4: llm/client - LLMClient protocol, Completion, AnthropicClient

**Files:**
- Create: `src/llm/client.py`
- Create: `tests/test_llm_client.py`

**Interfaces:**
- Consumes: `config` (API klíč, `API_MAX_RETRIES`)
- Produces:
  - `@dataclass Completion(text: str, truncated: bool, input_tokens: int, output_tokens: int)`
  - `class LLMClient(Protocol)` s `complete(*, system, user, max_tokens, model) -> Completion` a `count_tokens(*, system, user, model) -> int`
  - `class OutputTruncated(RuntimeError)`
  - `class FatalRunError(RuntimeError)` - auth/404/400/config chyby (fatal běhu)
  - `class AnthropicClient` - jediná reálná impl; konstruktor `AnthropicClient(api_key: str | None = None)`; importuje `anthropic` (JEDINÝ soubor). Mapuje `anthropic.AuthenticationError` / `NotFoundError` / `BadRequestError` → `FatalRunError`. `complete` vrací `Completion` (bez vyhazování na truncated - to řeší volající/pipeline). `count_tokens` volá `client.messages.count_tokens`.
  - `class FakeLLMClient` - pro testy agentů a pipeline; konstruktor bere `responses: list[Completion]` nebo `callable(**kwargs) -> Completion`; počítá volání.

- [ ] **Step 1: Write failing tests** — `tests/test_llm_client.py`

```python
import pytest
from src.llm import client
from src.llm.client import Completion, FakeLLMClient, FatalRunError


def test_completion_dataclass_fields():
    c = Completion(text="x", truncated=False, input_tokens=10, output_tokens=5)
    assert c.text == "x" and c.input_tokens == 10


def test_fake_client_returns_queued_responses():
    fake = FakeLLMClient(responses=[
        Completion("a", False, 1, 1), Completion("b", False, 1, 1)])
    assert fake.complete(system="s", user="u", max_tokens=10, model="m").text == "a"
    assert fake.complete(system="s", user="u", max_tokens=10, model="m").text == "b"
    assert fake.calls == 2


def test_fake_client_callable_mode_sees_kwargs():
    seen = {}
    def gen(**kw):
        seen.update(kw)
        return Completion("ok", False, 1, 1)
    FakeLLMClient(gen).complete(system="S", user="U", max_tokens=99, model="M")
    assert seen == {"system": "S", "user": "U", "max_tokens": 99, "model": "M"}


def test_anthropic_client_maps_sdk_error_to_fatal(monkeypatch):
    """AnthropicClient převádí fatální SDK chyby na FatalRunError.
    Konstruktor anthropic.AuthenticationError se mezi verzemi SDK liší -
    executor: pokud tento konstruktor selže, vytvoř instanci přes
    `anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)` nebo
    použij jinou třídu z `_FATAL_SDK_ERRORS` tuple v client.py. Cíl testu:
    ověřit mapování, ne konkrétní konstruktor."""
    import anthropic

    err = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    err.args = ("bad key",)

    class _Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise err

    monkeypatch.setattr(client, "_build_sdk_client", lambda *a, **k: _Boom())
    c = client.AnthropicClient(api_key="x")
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: FAIL - no module / attributes.

- [ ] **Step 3: Implement `src/llm/client.py`**

```python
"""Provider vrstva. JEDINÝ soubor, který importuje `anthropic`."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Callable

import config


class OutputTruncated(RuntimeError):
    """Model narazil na max_tokens - výstup je neúplný."""


class FatalRunError(RuntimeError):
    """Chyba, po které nemá smysl pokračovat v běhu (auth, neznámý model, 400)."""


@dataclass
class Completion:
    text: str
    truncated: bool
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion: ...
    def count_tokens(self, *, system: str, user: str, model: str) -> int: ...


def _build_sdk_client(api_key: str | None):
    import anthropic
    return anthropic.Anthropic(api_key=api_key, max_retries=config.API_MAX_RETRIES)


def _fatal_sdk_errors():
    import anthropic
    return (anthropic.AuthenticationError, anthropic.NotFoundError,
            anthropic.BadRequestError, anthropic.PermissionDeniedError)


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or config.ANTHROPIC_API_KEY
        if not self._api_key:
            raise FatalRunError("Chybí ANTHROPIC_API_KEY v prostředí.")
        self._sdk = None

    def _client(self):
        if self._sdk is None:
            self._sdk = _build_sdk_client(self._api_key)
        return self._sdk

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        try:
            resp = self._client().messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except _fatal_sdk_errors() as e:
            raise FatalRunError(f"{type(e).__name__}: {e}") from e
        text = "".join(b.text for b in resp.content if b.type == "text")
        return Completion(
            text=text,
            truncated=(resp.stop_reason == "max_tokens"),
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        try:
            r = self._client().messages.count_tokens(
                model=model, system=system,
                messages=[{"role": "user", "content": user}])
        except _fatal_sdk_errors() as e:
            raise FatalRunError(f"{type(e).__name__}: {e}") from e
        return r.input_tokens


class FakeLLMClient:
    provider = "fake"

    def __init__(self, responses):
        self._callable = responses if callable(responses) else None
        self._queue = list(responses) if not callable(responses) else []
        self.calls = 0

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        self.calls += 1
        if self._callable:
            return self._callable(system=system, user=user,
                                  max_tokens=max_tokens, model=model)
        return self._queue.pop(0)

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        return max(1, (len(system) + len(user)) // 4)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_llm_client.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/llm/client.py tests/test_llm_client.py
git commit -m "feat: llm/client (LLMClient protocol, AnthropicClient, FakeLLMClient)"
```

---

## Task 5: llm/client - PipelineLLMClient (cost guard + llm_calls logging)

**Files:**
- Modify: `src/llm/client.py` (přidat `PipelineLLMClient` + `record_llm_call` do state - viz níže)
- Modify: `src/state.py` (přidat `record_llm_call`, `spent_so_far`, `create_run`, `finish_run`, `get_run_spend_ceiling`, `set_run_spend_ceiling`)
- Create: `tests/test_pipeline_client.py`
- Modify: `tests/test_state_ops.py` (nebo nový) - test `record_llm_call` + `spent_so_far`

**Interfaces:**
- Consumes: `LLMClient` (inner), `state` modul, `config`
- Produces:
  - `state.create_run(db, command) -> int` (run_id), `state.finish_run(db, run_id, status)`
  - `state.record_llm_call(db, *, run_id, agent, provider, model, input_tokens, output_tokens, cost_usd, truncated, status, error_class)`
  - `state.spent_so_far(db, run_id) -> float` - suma `cost_usd` (NULL = 0) přes daný run
  - `state.get_run_spend_ceiling(db, run_id) -> float | None`, `state.set_run_spend_ceiling(db, run_id, value)`
  - `client.PipelineLLMClient(inner, *, run_id, agent, db_path, config_mod, confirm=input, interactive=True)` - implementuje `LLMClient`. `confirm` = injektovatelná funkce pro cost guard prompt (default `input`), testovatelnost. `interactive=False` (pro `scan`) → cost guard se neptá, rovnou `FatalRunError`.
  - Cost guard: efektivní strop = `max(config.MAX_SPEND_USD, ceiling or 0)`. Odhad = `count_tokens(system,user)/1e6*price_in + max_tokens/1e6*price_out`. `spent_so_far + odhad > strop`: pokud `interactive` → `confirm(prompt)`, prázdná odpověď → `FatalRunError`, číslo → `set_run_spend_ceiling`; pokud `not interactive` → rovnou `FatalRunError`.
  - `complete` volá `inner.complete` v `try/finally`; ve `finally` `record_llm_call` (status `ok`/`truncated`/`error`, error_class u výjimky, tokeny/cost NULL u výjimky). Truncated NEvyhazuje - vrací `Completion(truncated=True)`; rozhodnutí co s tím dělá volající (translator agent / pipeline).

- [ ] **Step 1: Write failing tests** — `tests/test_pipeline_client.py`

```python
import pytest
from src import state
from src.llm.client import Completion, FakeLLMClient, PipelineLLMClient, FatalRunError
import config


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p); return p


def test_logs_call_on_success(tmp_path):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    inner = FakeLLMClient([Completion("ok", False, 100, 50)])
    c = PipelineLLMClient(inner, run_id=rid, agent="translator",
                          db_path=db, config_mod=config)
    c.complete(system="s", user="u", max_tokens=1000, model="claude-sonnet-5")
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM llm_calls"))
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["agent"] == "translator"
    assert rows[0]["cost_usd"] > 0


def test_logs_call_on_exception(tmp_path):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    def boom(**kw): raise RuntimeError("net down")
    c = PipelineLLMClient(FakeLLMClient(boom), run_id=rid, agent="critic",
                          db_path=db, config_mod=config)
    with pytest.raises(RuntimeError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    with state.connect(db) as conn:
        row = conn.execute("SELECT * FROM llm_calls").fetchone()
    assert row["status"] == "error"
    assert row["error_class"] == "RuntimeError"


def test_cost_guard_pauses_and_confirm_raises_on_empty(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)  # okamžitě přes strop
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, confirm=lambda prompt: "")
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=1000, model="claude-sonnet-5")


def test_cost_guard_new_ceiling_persists_and_stops_asking(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    calls = {"n": 0}
    def confirm(prompt):
        calls["n"] += 1
        return "999"
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1),
                                        Completion("y", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, confirm=confirm)
    c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    assert calls["n"] == 1  # zeptá se jen jednou
    assert state.get_run_spend_ceiling(db, rid) == 999.0


def test_cost_guard_non_interactive_hard_stops(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "scan")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, interactive=False)
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")


def test_unknown_model_price_raises_fatal(tmp_path):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="translator", db_path=db, config_mod=config)
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="gpt-neexistuje")


def test_cost_guard_invalid_ceiling_input_raises_fatal(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db, config_mod=config,
                          confirm=lambda _: "abc")
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")


def test_cost_guard_rejects_ceiling_below_need(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db, config_mod=config,
                          confirm=lambda _: "0.0001")   # pod spent+est
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=100000, model="claude-sonnet-5")
```

- [ ] **Step 2: Run to verify fail** — `python -m pytest tests/test_pipeline_client.py -v` → FAIL.

- [ ] **Step 3: Implement state helpers (`src/state.py` append)**

```python
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


def get_run_spend_ceiling(db_path: str, run_id: int) -> float | None:
    with connect(db_path) as conn:
        r = conn.execute("SELECT spend_ceiling FROM runs WHERE id = ?",
                         (run_id,)).fetchone()
        return r["spend_ceiling"] if r else None


def set_run_spend_ceiling(db_path: str, run_id: int, value: float) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE runs SET spend_ceiling = ? WHERE id = ?",
                     (value, run_id))
```

- [ ] **Step 4: Implement `PipelineLLMClient` (`src/llm/client.py` append)**

```python
class PipelineLLMClient:
    def __init__(self, inner: LLMClient, *, run_id: int, agent: str,
                 db_path: str, config_mod, confirm=input, interactive: bool = True):
        self._inner = inner
        self._run_id = run_id
        self._agent = agent
        self._db = db_path
        self._cfg = config_mod
        self._confirm = confirm
        self._interactive = interactive

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        return self._inner.count_tokens(system=system, user=user, model=model)

    def _price(self, model: str) -> tuple[float, float]:
        if model not in self._cfg.PRICE_IN_PER_MTOK or model not in self._cfg.PRICE_OUT_PER_MTOK:
            raise FatalRunError(
                f"Model {model!r} nemá sazby v config.PRICE_*_PER_MTOK - "
                "cost guard by byl slepý. Doplň sazby.")
        return (self._cfg.PRICE_IN_PER_MTOK[model], self._cfg.PRICE_OUT_PER_MTOK[model])

    def _guard(self, system: str, user: str, max_tokens: int, model: str) -> None:
        from src import state
        in_rate, out_rate = self._price(model)   # může vyhodit FatalRunError
        try:
            in_tok = self._inner.count_tokens(system=system, user=user, model=model)
        except FatalRunError:
            raise
        except Exception:
            in_tok = (len(system) + len(user)) // 4   # hrubý odhad, jen na non-fatal
        est = in_tok / 1e6 * in_rate + max_tokens / 1e6 * out_rate
        spent = state.spent_so_far(self._db, self._run_id)
        ceiling = state.get_run_spend_ceiling(self._db, self._run_id) or 0.0
        limit = max(self._cfg.MAX_SPEND_USD, ceiling)
        if spent + est <= limit:
            return
        if not self._interactive:
            raise FatalRunError(
                f"Cost guard: strop ${limit:.2f} překročen (utraceno ~${spent:.2f} "
                f"+ odhad ~${est:.2f}). Non-interactive režim, zastavuji.")
        need = spent + est
        for _ in range(2):   # 1 prompt + 1 reprompt na nevalidní/nízký vstup
            ans = (self._confirm(
                f"Cost guard: utraceno ~${spent:.2f}, odhad ~${est:.2f}, "
                f"strop ${limit:.2f}. Nový strop v $ (>= ${need:.2f}) [prázdné = stop]: "
            ) or "").strip()
            if not ans:
                raise FatalRunError("Cost guard: běh zastaven uživatelem.")
            try:
                new_limit = float(ans)
            except ValueError:
                continue
            if new_limit < need:
                continue   # strop pod potřebu = nesmysl, reprompt
            state.set_run_spend_ceiling(self._db, self._run_id, new_limit)
            return
        raise FatalRunError("Cost guard: nevalidní/nízký strop, zastavuji.")

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        from src import state
        self._guard(system, user, max_tokens, model)
        in_rate, out_rate = self._price(model)
        status, err, comp = "ok", None, None
        try:
            comp = self._inner.complete(system=system, user=user,
                                        max_tokens=max_tokens, model=model)
            if comp.truncated:
                status = "truncated"
            return comp
        except Exception as e:
            status, err = "error", type(e).__name__
            raise
        finally:
            it = comp.input_tokens if comp else None
            ot = comp.output_tokens if comp else None
            cost = (it / 1e6 * in_rate + ot / 1e6 * out_rate) if comp else None
            state.record_llm_call(
                self._db, run_id=self._run_id, agent=self._agent,
                provider=getattr(self._inner, "provider", "unknown"),
                model=model, input_tokens=it, output_tokens=ot, cost_usd=cost,
                truncated=bool(comp.truncated) if comp else False,
                status=status, error_class=err)
```

Poznámka: `from src import state` uvnitř metod (ne top-level) je záměr - `client.py`
nesmí mít `state` jako top-level import kvůli hranicím modulů a možnému cyklu
(state nezná client, client zná state jen pro logging). Lazy import to řeší.

- [ ] **Step 5: Run to verify pass** — `python -m pytest tests/test_pipeline_client.py tests/test_state_schema.py -v` → PASS (8 pipeline_client testů + schema testy).

- [ ] **Step 6: Commit**

```bash
git add src/llm/client.py src/state.py tests/test_pipeline_client.py
git commit -m "feat: PipelineLLMClient (cost guard + llm_calls logging ve finally)"
```

---

## Task 6: glossary (SQLite-backed, term_id, párování podle povrchu)

**Files:**
- Create: `src/glossary.py`
- Create: `tests/test_glossary.py`

**Interfaces:**
- Consumes: `src/state.py` (`connect`)
- Produces (vše bere `db_path` jako první arg):
  - `slugify(text: str) -> str` - lowercase, ne-alfanum → `-`, ořež
  - `resolve_surface(db_path, surface: str) -> str | None` - najde `term_id`, jehož `canonical_en` nebo některý `aliases` se rovná `surface` (case-insensitive)
  - `add_candidate(db_path, term_en: str, cz: str, *, note="", type="term") -> str` - vrací `term_id`. Nejdřív `resolve_surface`; shoda → vrátí existující `term_id` beze změny. Jinak INSERT `term_id="cand_"+slugify(term_en)`, `canonical_en=term_en`, `status="candidate"`.
  - `add_approved(db_path, canonical_en: str, cz: str, *, type="term") -> str` - pro odpověď na blocking otázku o dosud neznámém povrchu. `resolve_surface` → shoda: `promote` a vrať; jinak INSERT `term_id="term_"+slugify(canonical_en)`, `status="approved"`.
  - `resolve_term_or_surface(db_path, key: str) -> str | None` - `key` == existující `term_id` → vrať ho; jinak `resolve_surface(db_path, key)`.
  - `seed_from_guide(db_path, guide: dict) -> None` - iteruje `guide["characters"]` (`name_en`, `render`, `cz`, `aliases`), `guide["places"]` (`name_en`, `cz`), `guide["terms"]` (`term_en`, `cz`). Pro každý: `resolve_surface` → shoda → UPDATE (zachovej `term_id`; `status="seeded"` jen když aktuální není `approved`), jinak INSERT `term_id="term_"+slugify(canonical_en)`, `status="seeded"`. Postava `render="keep"` → `cz = canonical_en`; `render="translate"` → `cz = guide.cz`. `type` = `name`/`place`/`term`.
  - `promote(db_path, term_id: str, cz: str) -> None` - `status="approved"`, `cz=cz`
  - `add_accepted_alt(db_path, term_id: str, cz_form: str) -> None` - přidá do `accepted_alt` JSON listu (dedup)
  - `all_terms(db_path) -> list[dict]` - všechny řádky jako dicty (aliases/accepted_alt parsnuté z JSON)
  - `as_prompt_block(db_path) -> str` - `seeded`+`approved` jako "ZÁVAZNÉ", `candidate` jako "NÁVRHY (mohou se změnit)". Každý řádek: `[term_id] canonical_en → cz  (aliasy: ...)`.

- [ ] **Step 1: Write failing tests** — `tests/test_glossary.py`

```python
import json
from src import state, glossary


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p); return p


def test_slugify():
    assert glossary.slugify("The White Council") == "the-white-council"


def test_add_candidate_returns_term_id_and_dedups_by_surface(tmp_path):
    db = _db(tmp_path)
    a = glossary.add_candidate(db, "Bob", "Bob")
    b = glossary.add_candidate(db, "bob", "Bobek")  # stejný povrch (ci)
    assert a == b
    with state.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM glossary").fetchone()["c"] == 1


def test_seed_reuses_candidate_term_id(tmp_path):
    db = _db(tmp_path)
    cand = glossary.add_candidate(db, "Harry Dresden", "Harry Dresden")
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Harry Dresden", "aliases": ["Harry"], "render": "keep"}],
        "places": [], "terms": []})
    with state.connect(db) as conn:
        row = conn.execute("SELECT * FROM glossary").fetchone()
    assert row["term_id"] == cand  # sdílené term_id
    assert row["status"] == "seeded"


def test_fresh_seed_id_and_terms_section(tmp_path):
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [], "places": [],
        "terms": [{"term_en": "White Council", "cz": "Bílá rada"}]})
    t = glossary.all_terms(db)[0]
    assert t["term_id"] == "term_white-council"
    assert t["cz"] == "Bílá rada" and t["type"] == "term"


def test_promote_and_accepted_alt(tmp_path):
    db = _db(tmp_path)
    tid = glossary.add_candidate(db, "Foo", "Fu")
    glossary.promote(db, tid, "Fů")
    glossary.add_accepted_alt(db, tid, "Fůa")
    glossary.add_accepted_alt(db, tid, "Fůa")  # dedup
    t = [x for x in glossary.all_terms(db) if x["term_id"] == tid][0]
    assert t["status"] == "approved" and t["cz"] == "Fů"
    assert t["accepted_alt"] == ["Fůa"]


def test_as_prompt_block_separates_candidate(tmp_path):
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Murphy", "aliases": [], "render": "keep"}],
        "places": [], "terms": []})
    glossary.add_candidate(db, "Nevernever", "Nikdykdy")
    block = glossary.as_prompt_block(db)
    assert "ZÁVAZNÉ" in block and "NÁVRHY" in block
    assert "Murphy" in block and "Nevernever" in block
```

- [ ] **Step 2: Run to verify fail** — FAIL.

- [ ] **Step 3: Implement `src/glossary.py`** (logika nad `state.connect`; `slugify` regex; JSON parse/serialize `aliases`/`accepted_alt`; `resolve_surface` čte všechny řádky a porovnává `canonical_en.lower()` + každý alias `.lower()`).

- [ ] **Step 4: Run to verify pass** — PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/glossary.py tests/test_glossary.py
git commit -m "feat: glossary (SQLite, deterministické term_id, párování podle povrchu)"
```

---

## Task 7: guide (guide.json load/save/merge, prompt block, relationship_key)

**Files:**
- Create: `src/guide.py`
- Create: `tests/test_guide.py`

**Interfaces:**
- Consumes: `config` (cesty)
- Produces:
  - `normalize(name: str) -> str` - lower + strip
  - `relationship_key(a: str, b: str) -> str` - `"|".join(sorted([normalize(a), normalize(b)]))`. **v1 omezení:** klíč je podle jména, ne přes `resolve_surface` (alias-resolve). Když scout jednou napíše "Harry" a jindy "Dresden" pro tutéž dvojici, klíče se nespárují. Přijatelné pro pilot; alias-resolve případně později.
  - `load_guide(path) -> dict` - vrací plný shape `{"characters":[], "places":[], "terms":[], "relationships":[], "style":"", "rules":[]}` když soubor chybí. **I když soubor existuje** ale nemá některý klíč (starší tvar), `load_guide` ho doplní defaultem před vrácením (žádný `KeyError` downstream).
  - `save_guide(path, guide: dict) -> None`
  - `load_draft(path) -> dict` - výstup scouta (bohatší), default `{"characters":[], "places":[], "terms":[], "relationships":[], "style_notes":"", "must_decide":[]}`
  - `save_draft(path, draft: dict) -> None` - zapíše `guide.draft.json` (`ensure_ascii=False, indent=2`)
  - `merge_draft_and_guide(draft: dict, guide: dict) -> dict` - pro GET /api/guide. **Výstup používá FINÁLNÍ názvy polí** (`cz`, `render`, `address`, `style`), předvyplněné z draftu tam, kde člověk ještě nerozhodl:
    - `characters`: `{name_en, aliases, render: guide.render or draft.suggested, cz: guide.cz or "", note: draft.note}`
    - `places`: `{name_en, cz: guide.cz or draft.suggested_cz or "", note}`
    - `terms`: `{term_en, cz: guide.cz or draft.suggested_cz or "", note}`
    - `relationships` (klíč `relationship_key`): `{a, b, address: guide.address or draft.suggested or ""}`
    - `style`: `guide["style"] or draft.get("style_notes", "")`
    - `must_decide`: přeneseno z draftu 1:1 (řeší UI)
    Lidská rozhodnutí z `guide` mají přednost. `draft` klíče `style_notes` /
    `suggested_cz` / `suggested` se v tomto kroku přeloží na finální názvy.
  - `add_rule(path, rule: str) -> None` - append do `rules` (dedup), přes load/save
  - `guide_as_prompt_block(guide: dict) -> str` - styl + vztahy (`A ↔ B: tykají si`) + rozhodnutí keep/translate (jen JMÉNA, ne cz páry - ty jsou z glosáře). Prázdné sekce → "(zatím nic)".

- [ ] **Step 1: Write failing tests** — `tests/test_guide.py`

```python
from src import guide


def test_relationship_key_is_order_independent():
    assert guide.relationship_key("Harry", "murphy") == guide.relationship_key("MURPHY", "harry")


def test_load_guide_missing_returns_empty_shape(tmp_path):
    g = guide.load_guide(str(tmp_path / "none.json"))
    assert g["characters"] == [] and g["rules"] == [] and g["style"] == ""
    assert g["terms"] == []


def test_merge_translates_draft_field_names_to_final(tmp_path):
    draft = {"characters": [{"name_en": "Bob", "suggested": "translate", "note": "x"}],
             "places": [{"name_en": "Chicago", "suggested_cz": "Chicago", "note": ""}],
             "terms": [{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
             "relationships": [], "must_decide": [], "style_notes": "sarkastický"}
    g = {"characters": [], "places": [], "terms": [], "relationships": [],
         "style": "", "rules": []}
    m = guide.merge_draft_and_guide(draft, g)
    assert m["style"] == "sarkastický"
    assert m["terms"][0] == {"term_en": "Nevernever", "cz": "Nikdykdy", "note": ""} \
        or (m["terms"][0]["term_en"] == "Nevernever" and m["terms"][0]["cz"] == "Nikdykdy")
    assert m["places"][0]["cz"] == "Chicago"
    assert m["characters"][0]["render"] == "translate"


def test_load_guide_normalizes_partial_existing_file(tmp_path):
    import json
    p = str(tmp_path / "g.json")
    json.dump({"characters": [{"name_en": "X"}]}, open(p, "w", encoding="utf-8"))
    g = guide.load_guide(p)   # starý tvar bez terms/places/...
    assert g["terms"] == [] and g["places"] == [] and g["rules"] == []


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "g.json")
    guide.save_guide(p, {"characters": [{"name_en": "X"}], "places": [],
                         "relationships": [], "style": "s", "rules": ["r"]})
    assert guide.load_guide(p)["rules"] == ["r"]


def test_add_rule_dedups(tmp_path):
    p = str(tmp_path / "g.json")
    guide.add_rule(p, "pravidlo A")
    guide.add_rule(p, "pravidlo A")
    guide.add_rule(p, "pravidlo B")
    assert guide.load_guide(p)["rules"] == ["pravidlo A", "pravidlo B"]


def test_merge_keeps_human_decisions(tmp_path):
    draft = {"characters": [{"name_en": "Harry", "suggested": "keep", "note": "hrdina"},
                            {"name_en": "NewGuy", "suggested": "translate", "note": ""}],
             "places": [], "terms": [], "relationships": [], "must_decide": []}
    g = {"characters": [{"name_en": "Harry", "render": "keep", "cz": "Harry"}],
         "places": [], "relationships": [], "style": "", "rules": []}
    merged = guide.merge_draft_and_guide(draft, g)
    harry = [c for c in merged["characters"] if c["name_en"] == "Harry"][0]
    assert harry["render"] == "keep"  # lidské rozhodnutí zůstalo
    newguy = [c for c in merged["characters"] if c["name_en"] == "NewGuy"][0]
    assert newguy["render"] == "translate"  # předvyplněno z draft.suggested


def test_prompt_block_has_no_cz_pairs(tmp_path):
    g = {"characters": [{"name_en": "Foo", "render": "translate", "cz": "Fů"}],
         "places": [], "relationships": [], "style": "sarkastický", "rules": []}
    block = guide.guide_as_prompt_block(g)
    assert "sarkastický" in block
    assert "Fů" not in block  # cz páry jdou jen z glosáře
```

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3: Implement `src/guide.py`** (json load/save s `ensure_ascii=False, indent=2`; merge iteruje sekce, klíč = `name_en` / `relationship_key`).
- [ ] **Step 4: Run to verify pass** — PASS (8 tests).
- [ ] **Step 5: Commit**

```bash
git add src/guide.py tests/test_guide.py
git commit -m "feat: guide (json load/save/merge, prompt block bez cz párů, relationship_key)"
```

---

## Task 8: concordance (build_mentions, check_chapter, check_drift)

**Files:**
- Create: `src/concordance.py`
- Create: `tests/test_concordance.py`

**Interfaces:**
- Consumes: nic (čistá logika; `glossary` dostane jako list dictů z `glossary.all_terms`, ne db_path - drží izolaci)
- Produces:
  - `stem(word: str) -> str` - `word.rstrip(".,;:!?\"')").lower()`; pak `[:-3]` když `len > 5`, `[:-2]` když `len > 3`, jinak celé. (kmen pro české skloňování, v1)
  - `form_key(form: str) -> str` - normalizace VÍCESLOVNÉHO tvaru pro drift porovnání: `" ".join(stem(w) for w in form.split())`. Dva `cz_form` jsou "stejný kmen" ⇔ `form_key` se rovná. Takže "Bílá rada" a "Bílá radě" → `"bíl rad"` == `"bíl rad"` → NEjsou drift; "Rada bílých" → `"rad bílý"` → JE drift.
  - `contains_form(text: str, form: str) -> bool` - přesná shoda (word-boundary regex) NEBO `form_key` celého `form` je podřetězec `form_key`-ovaného textu (po slovech)
  - `Finding` = `dataclass`/`TypedDict` přesně dle §Finding ve specu (`source, type, severity, action, term_id, expected, actual, cz_excerpt, issue, suggestion`). V testech se přistupuje `finding["type"]` → použij `TypedDict` nebo `dataclass` + `__getitem__`; **plán a testy počítají s dict přístupem**, takže `TypedDict` (nebo dict factory).
  - `Mention` = `dataclass(term_id: str, cz_form: str | None, scene_idx: int | None, source: str)`
  - `examined_terms(en_text: str, glossary: list[dict], rendered_terms: list[dict]) -> list[dict]` - řádky glosáře, jejichž `canonical_en`/alias je v `en_text` (word-boundary, ci), + řádky odkazované `term_id` v `rendered_terms`
  - `build_mentions(en_text, cz_text, glossary, rendered_terms) -> list[Mention]` - dle specu (`rendered` z ověřených substringem, `detected` z textu, `omission` NULL)
  - `check_chapter(en_text, cz_text, glossary, rendered_terms) -> list[Finding]` - `leak` (cz != canonical_en a EN podoba v CZ → revise), `inconsistency` (`cz_form` z rendered/detected, jehož `form_key` ∉ {`form_key(cz)`} ∪ {`form_key(a)` pro a v accepted_alt} → revise u seeded/approved, question u candidate), `omission` (→ note)
  - `check_drift(mentions: list[dict]) -> list[dict]` - `mentions` jsou dicty s `term_id`, `cz_form`, `chapter_idx`; per `term_id` seskup ne-NULL `cz_form` podle `form_key`; 2+ různé `form_key` skupiny → `{"term_id":..., "formy":[reprezentant každé skupiny], "kapitoly":[idx z VŠECH skupin, ale jen těch mimo většinovou? ne - všechny idx kde se objevil ne-většinový tvar + idx většinového]}`. Zjednodušeně: `kapitoly` = distinct `chapter_idx` přes všechny ne-NULL mentions termínu.

- [ ] **Step 1: Write failing tests** — `tests/test_concordance.py`

```python
from src import concordance as C


G_KEEP = [{"term_id": "term_harry", "canonical_en": "Harry", "aliases": [],
           "cz": "Harry", "accepted_alt": [], "status": "seeded", "type": "name"}]
G_TRANS = [{"term_id": "term_council", "canonical_en": "White Council",
            "aliases": [], "cz": "Bílá rada", "accepted_alt": [],
            "status": "approved", "type": "term"}]


def test_leak_flags_untranslated_term_that_should_be_translated():
    f = C.check_chapter("The White Council met.", "White Council se sešla.",
                        G_TRANS, [])
    leaks = [x for x in f if x["type"] == "leak"]
    assert leaks and leaks[0]["action"] == "revise"


def test_keep_term_in_cz_is_not_a_leak():
    f = C.check_chapter("Harry went home.", "Harry šel domů.", G_KEEP, [])
    assert not [x for x in f if x["type"] == "leak"]


def test_inconsistency_on_approved_is_revise():
    f = C.check_chapter("The White Council.", "Rada bílých.", G_TRANS,
                        [{"term_id": "term_council", "cz_as_used": "Rada bílých"}])
    inc = [x for x in f if x["type"] == "inconsistency"]
    assert inc and inc[0]["action"] == "revise"


def test_inconsistency_on_candidate_is_question():
    g = [{"term_id": "cand_foo", "canonical_en": "Foo", "aliases": [], "cz": "Fů",
          "accepted_alt": [], "status": "candidate", "type": "term"}]
    f = C.check_chapter("Foo appeared.", "Fůha se objevil.", g,
                        [{"term_id": "cand_foo", "cz_as_used": "Fůha"}])
    inc = [x for x in f if x["type"] == "inconsistency"]
    assert inc and inc[0]["action"] == "question"
    assert inc[0]["term_id"] == "cand_foo"


def test_build_mentions_records_omission_as_null():
    m = C.build_mentions("Harry and Bob spoke.", "Harry promluvil.",
                         G_KEEP + [{"term_id": "term_bob", "canonical_en": "Bob",
                                    "aliases": [], "cz": "Bob", "accepted_alt": [],
                                    "status": "seeded", "type": "name"}], [])
    bob = [x for x in m if x.term_id == "term_bob"]
    assert bob and bob[0].cz_form is None and bob[0].source == "omission"


def test_check_drift_groups_divergent_forms():
    mentions = [
        {"term_id": "t1", "cz_form": "Bílá rada", "chapter_idx": 1},
        {"term_id": "t1", "cz_form": "Bílá radě", "chapter_idx": 2},   # jen skloňování
        {"term_id": "t1", "cz_form": "Rada bílých", "chapter_idx": 5}, # jiný kmen
    ]
    drifts = C.check_drift(mentions)
    assert len(drifts) == 1
    assert set(drifts[0]["kapitoly"]) == {1, 2, 5}


def test_check_drift_no_finding_for_simple_inflection():
    mentions = [
        {"term_id": "t1", "cz_form": "rada", "chapter_idx": 1},
        {"term_id": "t1", "cz_form": "radu", "chapter_idx": 2},
        {"term_id": "t1", "cz_form": "radě", "chapter_idx": 3},
    ]
    assert C.check_drift(mentions) == []


def test_form_key_collapses_simple_inflection_not_different_stems():
    assert C.form_key("Bílá radě") == C.form_key("Bílá rada")
    assert C.form_key("Rada bílých") != C.form_key("Bílá rada")
```

**Poznámka k stemmeru:** naivní odsekávání koncovek Češtinu spolehlivě nezvládne
(`bílá`/`bílou`/`bílých` mají různou délku → různý bod odseknutí). Falešné drift
nálezy jsou očekávané - explicitní otevřená otázka k ověření pilotem
(spec §Otevřené otázky). Testy ověřují jen jednoduché případy. Falešný pozitiv =
otázka pro člověka, ne tvrdý fail.

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3: Implement `src/concordance.py`** (`stem` dle interface; `form_key` = per-slovo `stem` join; `check_drift` grupuje podle `form_key`).
- [ ] **Step 4: Run to verify pass** — PASS (8 tests).
- [ ] **Step 5: Commit**

```bash
git add src/concordance.py tests/test_concordance.py
git commit -m "feat: concordance (build_mentions, check_chapter leak/inconsistency/omission, check_drift)"
```

---

## Task 9: state - chapter ops, run lock, processing recovery, fronta

**Files:**
- Modify: `src/state.py` (chapter CRUD + přechody + lock)
- Create: `tests/test_state_chapters.py`

**Interfaces:**
- Consumes: `config` (`LOCK_PATH`)
- Produces:
  - `seed_chapters(db_path, chapters: list[Chapter]) -> None` - idempotentní INSERT (podle `idx`)
  - `get_chapter(db_path, idx) -> dict | None`
  - `chapters_by_status(db_path, statuses: tuple) -> list[dict]` (ORDER BY idx)
  - `queue_for_run(db_path) -> list[dict]` - `status IN ('pending','error')` ORDER BY idx
  - `recover_processing(db_path) -> int` - `UPDATE chapters SET status='pending' WHERE status='processing'`, vrací počet
  - `set_status(db_path, idx, status)` a `update_chapter(db_path, idx, **fields)` (allowlist sloupců: translated_text, status, revision_rounds, notes; vždy `updated_at=CURRENT_TIMESTAMP`)
  - `retry_flagged(db_path, idxs: list[int] | None) -> int` - `flagged → pending`, `revision_rounds=0`; `idxs=None` = všechny flagged
  - `counts_by_status(db_path) -> dict[str,int]`
  - **Lock:** `acquire_lock(lock_path) -> None` (raise `LockError` když drží živý PID; přebere zastaralý), `release_lock(lock_path)`, context manager `run_lock(lock_path)`. Lock soubor = JSON `{"pid": os.getpid(), "ts": <ISO>}`.
    - `_pid_alive(pid: int) -> bool`:
      - POSIX: `try: os.kill(pid, 0); return True; except ProcessLookupError: return False; except PermissionError: return True`
      - Windows: `ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)` (`PROCESS_QUERY_LIMITED_INFORMATION`) → handle != 0 → `CloseHandle` + `return True`; handle == 0 → `return False`. **NIKDY `os.kill` na Windows** (nedestruktivní check neexistuje, `os.kill` volá `TerminateProcess`).
    - `acquire`: soubor neexistuje → zapiš, hotovo. Existuje → načti; `_pid_alive(pid)` False NEBO `ts` starší než 6 h → přeber (přepiš). Jinak `raise LockError`.

- [ ] **Step 1: Write failing tests** — `tests/test_state_chapters.py`

```python
import pytest
from src import state
from src.state import LockError


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p); return p


class _Ch:
    def __init__(self, i): self.index = i; self.title = f"K{i}"; self.raw_text = "text"


def test_seed_chapters_idempotent(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1), _Ch(2)])
    state.seed_chapters(db, [_Ch(1), _Ch(2), _Ch(3)])
    assert len(state.chapters_by_status(db, ("pending",))) == 3


def test_recover_processing(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1)])
    state.set_status(db, 1, "processing")
    assert state.recover_processing(db) == 1
    assert state.get_chapter(db, 1)["status"] == "pending"


def test_queue_for_run_includes_pending_and_error_only(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1), _Ch(2), _Ch(3), _Ch(4)])
    state.set_status(db, 2, "error")
    state.set_status(db, 3, "flagged")
    state.set_status(db, 4, "needs_human")
    assert [c["idx"] for c in state.queue_for_run(db)] == [1, 2]


def test_retry_flagged_resets_rounds(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1)])
    state.update_chapter(db, 1, status="flagged", revision_rounds=2)
    assert state.retry_flagged(db, None) == 1
    c = state.get_chapter(db, 1)
    assert c["status"] == "pending" and c["revision_rounds"] == 0


def test_lock_blocks_second_holder(tmp_path):
    lp = str(tmp_path / ".lock")
    state.acquire_lock(lp)
    with pytest.raises(LockError):
        state.acquire_lock(lp)
    state.release_lock(lp)
    state.acquire_lock(lp)  # teď projde


def test_stale_lock_is_taken_over(tmp_path):
    import json
    lp = str(tmp_path / ".lock")
    with open(lp, "w") as f:
        json.dump({"pid": 999999, "ts": "old"}, f)  # mrtvý PID
    state.acquire_lock(lp)  # nesmí spadnout
```

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3: Implement chapter ops + lock in `src/state.py`.**
- [ ] **Step 4: Run to verify pass** — PASS (6 tests).
- [ ] **Step 5: Commit**

```bash
git add src/state.py tests/test_state_chapters.py
git commit -m "feat: state chapter ops, run lock, processing recovery"
```

---

## Task 10: state - questions (upsert), term_mentions, drift_reports, requeue

**Files:**
- Modify: `src/state.py`
- Create: `tests/test_state_questions.py`

**Interfaces:**
- Consumes: `src/concordance.py` není potřeba; `src/guide.py` (`relationship_key`) volá answer vrstva, ne state
- Produces:
  - `Question` = dict shape `{chapter_idx, kind, text, scope_key, guess_answer, severity}`
  - `upsert_open_question(db_path, q: dict) -> int` - větví: `chapter_idx is None` → SELECT dle `(kind, scope_key, severity) WHERE answer IS NULL AND chapter_idx IS NULL`; jinak SELECT dle `(chapter_idx, kind, scope_key, severity) WHERE answer IS NULL`. Nalezeno → UPDATE `text`, `guess_answer`. Jinak INSERT. Vrací `id`.
  - `delete_open_questions_for_chapter(db_path, chapter_idx) -> None` - `DELETE ... WHERE chapter_idx=? AND answer IS NULL`
  - `unanswered_questions(db_path) -> list[dict]` (ORDER BY id)
  - `get_question(db_path, qid) -> dict | None`
  - `answer_question(db_path, qid, answer_text) -> dict` - set `answer`, `resolved_at`; vrací celý řádek (pro requeue vrstvu)
  - `chapter_has_open_blocking(db_path, chapter_idx) -> bool`
  - `replace_term_mentions(db_path, chapter_idx, mentions: list) -> None` - `DELETE WHERE chapter_idx=?` + `INSERT` each (`mentions` = list `concordance.Mention` nebo dictů)
  - `chapters_mentioning_term(db_path, term_id, statuses=("done","flagged")) -> list[int]` - distinct `chapter_idx` z `term_mentions` (i NULL cz_form) JOIN chapters ON status
  - `save_drift_report(db_path, up_to_chapter, report: dict) -> None`

- [ ] **Step 1: Write failing tests** — `tests/test_state_questions.py`

```python
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
```

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3: Implement in `src/state.py`.**
- [ ] **Step 4: Run to verify pass** — PASS (5 tests).
- [ ] **Step 5: Commit**

```bash
git add src/state.py tests/test_state_questions.py
git commit -m "feat: state questions (upsert_open_question), term_mentions, drift reports"
```

---

## Task 11: agents/scout (+ merge_scout_facts pro --chunked)

**Files:**
- Create: `src/agents/__init__.py`
- Create: `src/agents/scout.py`
- Create: `tests/test_scout.py`

**Interfaces:**
- Consumes: `src/llm/client.py` (`LLMClient`, `OutputTruncated`), `src/llm/parsing.py` (`extract_json`), `config`
- Produces:
  - `SYSTEM_PROMPT` (konstanta) - instruuje vrátit čistý JSON dle §Scout výstupu, `must_decide` jako strukturované objekty
  - `scan_book(book_text: str, client: LLMClient, *, model=config.MODEL_SCOUT, max_tokens=config.MAX_TOKENS_SCOUT) -> dict` - jedno volání; když `completion.truncated` → `raise OutputTruncated` (scout truncated = fatal, řeší volající); parsuje `extract_json`; validuje že jsou klíče `characters/places/terms/relationships/style_notes/must_decide` (chybí → `ValueError`)
  - `chunk_chapters(chapters: list, word_limit: int) -> list[str]` - deterministicky: greedy packing. `raw = ch["raw_text"] if isinstance(ch, dict) else ch.raw_text` (přijímá dict/Row i objekt). Přidávej `raw` do aktuálního chunku (spojené `"\n\n"`), dokud by přidáním další kapitoly chunk nepřesáhl `word_limit` slov (`len(text.split())`); pak nový chunk. Jedna kapitola delší než limit = vlastní chunk sama. `config.SCOUT_CHUNK_WORD_LIMIT = 40000`.
  - `scan_chunks(chunks: list[str], client, **kw) -> dict` - volá `scan_book` na každý chunk, pak `merge_scout_facts`
  - `merge_scout_facts(partials: list[dict]) -> dict` - deterministicky, klíč je section-specific:
    - `characters` dedup dle `name_en.strip().casefold()`
    - `places` dedup dle `name_en.strip().casefold()`
    - `terms` dedup dle `term_en.strip().casefold()` (scout terms používají `term_en`, ne `name_en`)
    - u všech tří: `aliases` = union, `note` = spojení `"; "`, `suggested`/`suggested_cz` = první neprázdný, konflikt různých hodnot → `must_decide{kind, scope_key=povrch, question}`
    - `relationships` dedup dle `relationship_key(a,b)`, různý `suggested` → `suggested=None` + `must_decide{kind:"relationship", scope_key=relationship_key}`
    - `style_notes` = spojení `"\n"`; `must_decide` = union dle `(kind, scope_key)`

- [ ] **Step 1: Write failing tests** — `tests/test_scout.py`

```python
import json, pytest
from src.agents import scout
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

_OK = {"characters": [{"name_en": "Harry", "aliases": ["Dresden"],
                       "suggested": "keep", "note": "hrdina"}],
       "places": [], "terms": [], "relationships": [],
       "style_notes": "1. osoba", "must_decide": []}


def test_scan_book_parses_json():
    fake = FakeLLMClient([Completion(json.dumps(_OK), False, 100, 50)])
    out = scout.scan_book("kniha text", fake)
    assert out["characters"][0]["name_en"] == "Harry"


def test_scan_book_raises_on_truncated():
    fake = FakeLLMClient([Completion(json.dumps(_OK)[:20], True, 100, 50)])
    with pytest.raises(OutputTruncated):
        scout.scan_book("kniha", fake)


def test_scan_book_raises_on_missing_keys():
    fake = FakeLLMClient([Completion('{"characters": []}', False, 10, 10)])
    with pytest.raises(ValueError):
        scout.scan_book("kniha", fake)


def test_merge_dedups_characters_by_surface():
    p1 = dict(_OK, characters=[{"name_en": "Harry", "aliases": ["Harry"],
                               "suggested": "keep", "note": "a"}])
    p2 = dict(_OK, characters=[{"name_en": "harry", "aliases": ["Dresden"],
                               "suggested": "keep", "note": "b"}])
    m = scout.merge_scout_facts([p1, p2])
    assert len(m["characters"]) == 1
    assert set(m["characters"][0]["aliases"]) == {"Harry", "Dresden"}


def test_merge_conflicting_relationship_becomes_must_decide():
    p1 = dict(_OK, relationships=[{"a": "Harry", "b": "Murphy",
                                  "observed": "x", "suggested": "tyka"}])
    p2 = dict(_OK, relationships=[{"a": "Murphy", "b": "Harry",
                                  "observed": "y", "suggested": "vyka"}])
    m = scout.merge_scout_facts([p1, p2])
    rel = m["relationships"][0]
    assert rel["suggested"] is None
    assert any(md["kind"] == "relationship" for md in m["must_decide"])


def test_merge_dedups_terms_by_term_en():
    p1 = dict(_OK, terms=[{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": "a"}])
    p2 = dict(_OK, terms=[{"term_en": "nevernever", "suggested_cz": "Nikdykdy", "note": "b"}])
    m = scout.merge_scout_facts([p1, p2])
    assert len(m["terms"]) == 1


def test_chunk_chapters_greedy_packs_under_limit():
    class C:
        def __init__(s, n): s.raw_text = "slovo " * n
    chunks = scout.chunk_chapters([C(30), C(30), C(30), C(80)], word_limit=100)
    # 30+30+30 = 90 < 100 → chunk 1; C(80) samostatně → chunk 2
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 90


def test_chunk_chapters_accepts_dict_rows():
    rows = [{"raw_text": "slovo " * 20}, {"raw_text": "slovo " * 20}]
    assert len(scout.chunk_chapters(rows, word_limit=100)) == 1
```

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3: Implement `src/agents/scout.py`.**
- [ ] **Step 4: Run to verify pass** — PASS (8 tests).
- [ ] **Step 5: Commit**

```bash
git add src/agents/__init__.py src/agents/scout.py tests/test_scout.py
git commit -m "feat: agents/scout (scan_book, --chunked merge_scout_facts)"
```

---

## Task 12: agents/translator (čerstvý + revizní režim)

**Files:**
- Create: `src/agents/translator.py`
- Create: `tests/test_translator.py`

**Interfaces:**
- Consumes: `src/llm/client.py`, `src/llm/parsing.py` (`split_sections`, `extract_json`), `config`
- Produces:
  - `TranslationResult` = `dataclass(translation: str, new_terms: list[dict], rendered_terms: list[dict], questions: list[dict])`
  - `translate_scene(scene_en: str, guide_block: str, glossary_block: str, client, *, model=config.MODEL_TRANSLATOR, max_tokens=config.MAX_TOKENS_TRANSLATOR) -> TranslationResult` - postaví prompt, zavolá, když `truncated` → `raise OutputTruncated`, parsuje `split_sections(raw, ["===PREKLAD===","===METADATA==="])` + `extract_json` na metadata blok.
    - prázdný `===PREKLAD===` obsah → `ValueError`
    - `===METADATA===` marker přítomen ale JSON nevalidní → `ValueError` (rozbitý agent output, ne tichá ztráta otázek/termínů)
    - `===METADATA===` marker úplně chybí → tolerovat, prázdné listy
    - platný JSON bez některého klíče (`new_terms`/`rendered_terms`/`questions`) → ten klíč = `[]`
  - `revise_chapter(en_chapter: str, prev_cz: str, findings: list[dict], guide_block: str, glossary_block: str, client, **kw) -> TranslationResult` - revizní režim: celokapitolový vstup, `findings` naformátované do promptu
  - `_parse(raw: str) -> TranslationResult` - sdílená logika parsování
  - `SYSTEM_PROMPT_FRESH`, `SYSTEM_PROMPT_REVISE`
  - **question `scope_key` konvence:** `guess` otázka (translator termín zná)
    → `scope_key` = jeho `term_id` z promptu glosáře. `blocking` otázka
    (translator termín nezná) → `scope_key` = ten povrch (jméno/výraz), `_parse`
    ho normalizuje na `lower().strip()`. `relationship` → `a|b`. `style`/`other`
    → `""`. Prompt to translatoru vysvětlí.

- [ ] **Step 1: Write failing tests** — `tests/test_translator.py`

```python
import pytest
from src.agents import translator
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

_RAW = (
    "===PREKLAD===\nAhoj světe.\n\nDruhý odstavec.\n"
    "===METADATA===\n"
    '{"new_terms":[{"term_en":"Foo","cz":"Fů","note":"","type":"term"}],'
    '"rendered_terms":[{"term_id":"t1","cz_as_used":"Harry"}],'
    '"questions":[{"kind":"term","scope_key":"cand_foo","guess_answer":"Fů",'
    '"text":"jak Foo?","severity":"guess"}]}'
)


def test_translate_scene_parses_delimited():
    r = translator.translate_scene("Hello world.", "guide", "gloss",
                                   FakeLLMClient([Completion(_RAW, False, 10, 10)]))
    assert r.translation == "Ahoj světe.\n\nDruhý odstavec."
    assert r.new_terms[0]["cz"] == "Fů"
    assert r.rendered_terms[0]["term_id"] == "t1"
    assert r.questions[0]["severity"] == "guess"


def test_translate_scene_raises_on_truncated():
    with pytest.raises(OutputTruncated):
        translator.translate_scene("Hi.", "g", "gl",
                                   FakeLLMClient([Completion(_RAW, True, 10, 10)]))


def test_broken_metadata_json_raises():
    raw = "===PREKLAD===\nText tady.\n===METADATA===\n{tohle neni json"
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_missing_metadata_section_tolerated():
    raw = "===PREKLAD===\nText tady bez metadat."
    r = translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))
    assert r.translation == "Text tady bez metadat."
    assert r.new_terms == [] and r.questions == [] and r.rendered_terms == []


def test_empty_translation_raises():
    raw = "===PREKLAD===\n\n===METADATA===\n{}"
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_revise_chapter_sends_findings_and_en(monkeypatch):
    seen = {}
    def gen(**kw):
        seen.update(kw)
        return Completion(_RAW, False, 10, 10)
    translator.revise_chapter("EN ORIGINAL", "stary CZ",
                              [{"issue": "vynechavka", "suggestion": "doplň"}],
                              "guide", "gloss", FakeLLMClient(gen))
    assert "EN ORIGINAL" in seen["user"]
    assert "vynechavka" in seen["user"]
```

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3: Implement `src/agents/translator.py`** (markery jako konstanty; `_parse` sdílené; findings formátování = číslovaný seznam `issue` + `suggestion`).
- [ ] **Step 4: Run to verify pass** — PASS (6 tests).
- [ ] **Step 5: Commit**

```bash
git add src/agents/translator.py tests/test_translator.py
git commit -m "feat: agents/translator (fresh + revise, oddělovačový formát)"
```

---

## Task 13: agents/critic

**Files:**
- Create: `src/agents/critic.py`
- Create: `tests/test_critic.py`

**Interfaces:**
- Consumes: `src/llm/client.py`, `src/llm/parsing.py` (`extract_json`), `config`
- Produces:
  - `review(en_chapter: str, cz_chapter: str, client, *, model=config.MODEL_CRITIC, max_tokens=config.MAX_TOKENS_CRITIC) -> list[dict]` - vrací list `Finding` dictů (`source="critic"`, `type` ∈ `fidelity|fluency|register`, `action="revise"` když `severity=="critical"` jinak `"note"`, `term_id=None`, `expected=None`, `actual=None`). Vstup kritika = JEN EN + CZ, žádná translator metadata.
  - Truncated handling: 1× retry s `max_tokens * 2`; když zas truncated → `raise OutputTruncated` (volající = pipeline → kapitola `flagged`)
  - Neparsovatelný JSON: 1× retry; pak `raise ValueError` (pipeline → `flagged`)
  - `SYSTEM_PROMPT` - instruuje vrátit `{"verdict": "pass"|"revise", "findings": [{"severity","cz_excerpt","issue","suggestion"}]}`; kritik určuje `type` volně (fidelity/fluency/register) - pokud model nedodá, defaultně `"fidelity"`.

- [ ] **Step 1: Write failing tests** — `tests/test_critic.py`

```python
import json, pytest
from src.agents import critic
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

_PASS = json.dumps({"verdict": "pass", "findings": []})
_REVISE = json.dumps({"verdict": "revise", "findings": [
    {"severity": "critical", "type": "fidelity", "cz_excerpt": "špatná věta",
     "issue": "změněný význam", "suggestion": "oprav"}]})


def test_review_pass_returns_empty():
    assert critic.review("EN", "CZ", FakeLLMClient([Completion(_PASS, False, 5, 5)])) == []


def test_review_maps_critical_to_revise_action():
    f = critic.review("EN", "CZ", FakeLLMClient([Completion(_REVISE, False, 5, 5)]))
    assert f[0]["source"] == "critic"
    assert f[0]["severity"] == "critical" and f[0]["action"] == "revise"


def test_review_minor_maps_to_note():
    raw = json.dumps({"verdict": "revise", "findings": [
        {"severity": "minor", "cz_excerpt": "x", "issue": "drobnost", "suggestion": "y"}]})
    f = critic.review("EN", "CZ", FakeLLMClient([Completion(raw, False, 5, 5)]))
    assert f[0]["action"] == "note"


def test_review_retries_then_raises_on_repeated_truncation():
    fake = FakeLLMClient([Completion("{partial", True, 5, 5),
                          Completion("{still partial", True, 5, 5)])
    with pytest.raises(OutputTruncated):
        critic.review("EN", "CZ", fake)
    assert fake.calls == 2


def test_review_retries_on_bad_json_then_succeeds():
    fake = FakeLLMClient([Completion("rozbity json {", False, 5, 5),
                          Completion(_PASS, False, 5, 5)])
    assert critic.review("EN", "CZ", fake) == []
    assert fake.calls == 2


def test_review_raises_valueerror_on_repeated_bad_json():
    fake = FakeLLMClient([Completion("nope {", False, 5, 5),
                          Completion("still nope {", False, 5, 5)])
    with pytest.raises(ValueError):
        critic.review("EN", "CZ", fake)
    assert fake.calls == 2
```

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3: Implement `src/agents/critic.py`.**
- [ ] **Step 4: Run to verify pass** — PASS (6 tests).
- [ ] **Step 5: Commit**

```bash
git add src/agents/critic.py tests/test_critic.py
git commit -m "feat: agents/critic (nezávislá revize, Finding s action routingem)"
```

---

## Task 14: pipeline (process_chapter, revizní smyčka, transakce, drift)

**Files:**
- Create: `src/pipeline.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `state`, `glossary`, `guide`, `concordance`, `ingest` (`split_into_scenes`), `agents.translator`, `agents.critic`, `config`, `llm.client` (`OutputTruncated`, `FatalRunError`)
- Produces (pipeline):
  - `process_chapter(db_path, chapter: dict, *, client_factory, guide: dict) -> dict` - jedna kapitola celým flow. `client_factory(agent: str) -> LLMClient` vytváří `PipelineLLMClient` per agent (v testu monkeypatch obchází). Vrací summary `{idx, status, revision_rounds, new_terms, questions_created, findings}`.
    - Krok 0 (**transakce A**, `state.begin_chapter(db, idx)`): `status → processing` + `delete_open_questions_for_chapter`
    - Krok 2: `split_into_scenes(chapter["raw_text"], config.CHAPTER_SPLIT_WORD_THRESHOLD)` → per scéna `translator.translate_scene(scene, guide_block, glossary_block, client_factory("translator"))`; agregace: `new_terms` union podle `term_en.casefold()`, `questions` concat, `rendered_terms` = list `{term_id, cz_as_used, scene_idx}` (pipeline doplní `scene_idx`)
    - Krok 3-4: `concordance.check_chapter(en, cz, glossary.all_terms(db), rendered_terms)` + `critic.review(en, cz, client_factory("critic"))` → `findings` = spojený list. **Nové termíny objevené v TÉTO kapitole se concordance-checkem v její revizní smyčce neřeší** (ještě neznáme jejich schválené `cz`); kontrolují se až od další kapitoly. Explicitní v1 chování.
    - Krok 5: `while has_revise_triggers(findings) and rounds < config.MAX_REVIZE`: `translator.revise_chapter(en, cz, [f for f in findings if f["action"]=="revise"], guide_block, glossary_block, client_factory("translator"))` → nový `cz`; jeho metadata NAHRADÍ agregát (`rendered_terms`, `questions`), `new_terms` se kumulují; `check_chapter` + `review` znovu; `rounds += 1`
    - Krok 6-8 (**transakce B**): PŘED transakcí pipeline:
      (a) ověř `rendered_terms` substringem proti finálnímu `cz`, neověřené zahoď;
      (b) pro každý `nt` v `new_terms`: `glossary.resolve_surface(db, nt["term_en"])`
          → shoda: přeskoč; jinak `cand = {term_id: "cand_"+glossary.slugify(nt["term_en"]),
          canonical_en: nt["term_en"], aliases: [], cz: nt["cz"], accepted_alt: [],
          note: nt.get("note",""), type: nt.get("type","term"), status: "candidate"}`,
          přidej `cand` do `new_candidates` a question `{chapter_idx: idx, kind:"term",
          scope_key: cand["term_id"], text: f"Nový termín {nt['term_en']} → {nt['cz']}?",
          guess_answer: nt["cz"], severity:"guess"}`;
      (c) `glossary_rows = glossary.all_terms(db) + new_candidates`;
      (d) `mentions = concordance.build_mentions(en, cz, glossary_rows, rendered_terms_ověřené)`;
          navíc pro KAŽDÝ `cand` v `new_candidates` přidej explicitní mention
          `{term_id: cand["term_id"], cz_form: cand["cz"], chapter_idx: idx,
          scene_idx: None, source: "rendered"}` (translator ho v téhle kapitole
          použil - víme to jistě; nespoléhat na to, že jeho EN povrch je v `en`
          textu, requeue by ho jinak nenašel);
      (e) `questions` = translator guess/blocking + Findings s `action=="question"`
          (→ `{chapter_idx: idx, kind:"term", scope_key: f["term_id"], guess_answer: f["actual"],
          severity:"guess", text: f["issue"]}`) + new-term questions z (b).
      Pak `state.commit_chapter_result(db, idx, translated_text=cz, revision_rounds=rounds,
      notes_json=json.dumps(findings, ensure_ascii=False), status=status,
      new_candidates=new_candidates, mentions=mentions, questions=questions)` JEDNOU.
    - status: `needs_human` když je blocking `question`; `flagged` když
      `critic_failed OR has_revise_triggers(findings)` po vyčerpání `MAX_REVIZE`;
      jinak `done`. `critic_failed` = bool flag nastavený v handleru chyby kritika
      (viz níže) - pseudo-Finding s `action="note"` sám o sobě `flagged` nespustí.
    - **Chyby v `process_chapter`:** `FatalRunError` (z translatora i kritika) →
      NEchytat, propaguj (volající `run` → ukončí celý běh). `OutputTruncated` /
      `ValueError` z translatora → propaguj (→ kapitola `error`). `OutputTruncated`
      / `ValueError` / jiná výjimka z `critic.review` → chyť **až po**
      `except FatalRunError: raise`; nastav `critic_failed = True`, přidej
      pseudo-Finding `{source:"critic", type:"fluency", severity:"critical",
      action:"note", issue:"kritik selhal: <e>"}` do findings (pro `notes`),
      a přeruš revizní smyčku. Konečný status pak `flagged` (viz status pravidlo).
  - `run_drift_check(db_path, up_to_chapter: int) -> list[dict]` - načti `term_mentions` JOIN chapters WHERE status IN ('done','flagged') AND idx <= up_to_chapter; `concordance.check_drift(rows)`; `state.save_drift_report(db, up_to_chapter, {"drift": drifts})`; pro každý DriftFinding `state.upsert_open_question({chapter_idx: None, kind: "term", scope_key: term_id, text: "Drift: <formy>", guess_answer: <nejčastější tvar>, severity: "guess"})`
  - `has_revise_triggers(findings) -> bool` - `any(f["action"] == "revise" for f in findings)`
  - `_glossary_block(db)` / `_guide_block(guide)` - helpery pro promptové bloky (`glossary.as_prompt_block(db)`, `guide.guide_as_prompt_block(guide)`)
- Produces (rozšíření `state.py` v tomto tasku):
  - `state.begin_chapter(db_path, idx) -> None` - transakce A: `UPDATE chapters SET status='processing'` + `DELETE FROM questions WHERE chapter_idx=? AND answer IS NULL`, jeden `connect` blok
  - `state.commit_chapter_result(db_path, idx, *, translated_text: str, revision_rounds: int, notes_json: str, status: str, new_candidates: list[dict], mentions: list, questions: list[dict]) -> dict` - **celá transakce B v jednom `connect` bloku** (state zůstává čisté - concordance volá pipeline PŘED touto funkcí):
    1. pro každý řádek v `new_candidates` (`{term_id, canonical_en, aliases, cz, accepted_alt, note, type, status}`, pipeline je připravil přes `glossary.resolve_surface` = jen ty, co v glosáři nejsou): `INSERT INTO glossary ...`. Na `sqlite3.IntegrityError` (slug kolize / kandidát vznikl mezi přípravou a commitem): NEignoruj tiše - `SELECT term_id FROM glossary WHERE term_id=? OR lower(canonical_en)=lower(?)`, přemapuj `mentions` a `questions` toho kandidáta na nalezené `term_id`, pokračuj. (Nikdy nezůstane mention/question ukazující na neexistující řádek.)
    2. `DELETE FROM term_mentions WHERE chapter_idx=?`; INSERT každý z `mentions` (`term_id`, `cz_form`, `chapter_idx=idx`, `scene_idx`, `source`)
    3. pro každou otázku v `questions` (`{chapter_idx, kind, text, scope_key, guess_answer, severity}`): upsert-open-question logika NAD `conn` (SELECT dle správného partial-index predikátu podle `chapter_idx is None` → UPDATE nebo INSERT)
    4. `UPDATE chapters SET translated_text=?, revision_rounds=?, notes=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE idx=?`
    Vše v jedné transakci → výjimka kdekoli = `conn` se necommitne (`connect` commituje jen na čistý průchod), stav beze změny.
    Vrací `{"questions_created": N, "candidates_created": M}`.

- [ ] **Step 1: Write failing tests** — `tests/test_pipeline.py`

```python
import json
from src import state, glossary, pipeline
from src.llm.client import Completion
from src.agents import translator as T, critic as C


class FakeAgents:
    """Nahradí translator/critic funkce monkeypatchem."""


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
```

- [ ] **Step 2: Run to verify fail** — FAIL.
- [ ] **Step 3a: Implement `state.begin_chapter` + `state.commit_chapter_result`** (rozšíření `src/state.py`) + test atomicity v `tests/test_state_questions.py`:

```python
def test_commit_chapter_result_is_atomic(tmp_path):
    db = _db(tmp_path)  # má chapter 1, glossary t1
    bad_mention = {"term_id": "NEEXISTUJE", "cz_form": "x", "scene_idx": None,
                   "source": "detected"}  # poruší FK → výjimka uprostřed
    import pytest
    with pytest.raises(Exception):
        state.commit_chapter_result(db, 1, translated_text="CZ", revision_rounds=1,
            notes_json="[]", status="done", new_candidates=[], mentions=[bad_mention],
            questions=[{"chapter_idx": 1, "kind": "term", "text": "q", "scope_key": "t1",
                        "guess_answer": None, "severity": "guess"}])
    # nic se nezapsalo
    assert state.get_chapter(db, 1)["status"] == "processing"
    assert state.unanswered_questions(db) == []
```

- [ ] **Step 3b: Implement `src/pipeline.py`.** Pipeline importuje `from src.agents import translator, critic` a `from src import concordance, glossary, guide as guide_mod, state, ingest` - agenty volá modulově-kvalifikovaně (`translator.translate_scene`) kvůli monkeypatch.
- [ ] **Step 4: Run to verify pass** — PASS (8 pipeline testů + atomicity test).
- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py src/state.py tests/test_pipeline.py
git commit -m "feat: pipeline (process_chapter, revizní smyčka, transakce A/B, drift check)"
```

---

## Task 15: answer/requeue vrstva + CLI (init/scan/run/status/questions/answer/export)

**Files:**
- Create: `src/requeue.py` (logika `answer` → zápis + requeue; oddělené od `main.py` kvůli testovatelnosti)
- Create: `main.py`
- Create: `tests/test_requeue.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `state`, `glossary`, `guide`, `pipeline`, `ingest`, `agents.scout`, `config`, `llm.client`
- Produces:
  - `requeue.apply_answer(db_path, guide_path, qid: int, answer_text: str) -> dict` - dle §"Requeue po answer":
    1. `state.answer_question` → řádek
    2. dle `kind`:
       - `term`/`name`: odpověď se parsuje `parts = [p.strip() for p in answer.split("|") if p.strip()]`;
         `canonical_cz = parts[0]`, `alts = parts[1:]`.
         `tid = glossary.resolve_term_or_surface(db, q["scope_key"])`. `tid` nalezen
         → `glossary.promote(db, tid, canonical_cz)`; `tid` NEnalezen (blocking,
         `scope_key` je povrch) → `tid = glossary.add_approved(db,
         canonical_en=scope_key, cz=canonical_cz)`. Pak pro každý `a` v `alts`:
         `glossary.add_accepted_alt(db, tid, a)`. (Syntaxe odpovědi:
         `"Bílá rada"` nebo `"Bílá rada | Radě bílých | bílou radou"`.)
       - `relationship` (`scope_key` = `relationship_key`): parsni zpět `a|b`,
         zapiš/přidej `{a, b, address: answer}` do `guide["relationships"]`, `save_guide`
       - `style` / `other`: `guide.add_rule(guide_path, answer)`
    3. blocking otázka: `state.set_status(chapter_idx, "pending")` jen když
       `not state.chapter_has_open_blocking(db, chapter_idx)`
    4. guess otázka a `answer != guess_answer`: `affected_chapters`:
       - `term`/`name` → `state.chapters_mentioning_term(db, tid)`
       - `relationship` → `done`/`flagged` kapitoly, kde jsou obě jména dvojice
         (word-boundary, ci) v `raw_text`
       - `style`/`other` → `done`/`flagged` s `idx >= q["chapter_idx"]` (u
         globálních drift otázek s `chapter_idx=None` → všechny `done`/`flagged`)
       každou `set_status("pending")`
    Vrací `{"requeued": [idx...], "chapter_status_changed": bool}`
  - `main.main(argv=None) -> int` - argparse subcommands. `main()` první řádek: `_bootstrap_stdout()`. Každý mutující příkaz: `with state.run_lock(config.LOCK_PATH):`.
  - **Jednotný lifecycle pattern pro `run`/`scan`** (závazný, jeden `finish_run`):
    ```
    rid = state.create_run(db, cmd)
    status = "fatal"           # pesimistický default
    try:
        ... tělo příkazu ...
        status = "ok"          # jen po úspěchu
        return 0
    except FatalRunError as e:
        print(e); return 1     # status zůstane "fatal"
    except KeyboardInterrupt:
        status = "interrupted"; raise
    finally:
        state.finish_run(db, rid, status)   # JEDINÝ finish_run
    ```
    - `init PATH` → `ingest.load_book` + `state.seed_chapters` (žádný run/klient, žádný lifecycle)
    - `scan [--chunked]` → `recover_processing`; `chs = state.chapters_by_status(db, ("pending","processing","done","flagged","needs_human","error"))` (všechny, ORDER BY idx); `cf = lambda a: PipelineLLMClient(AnthropicClient(), run_id=rid, agent=a, db_path=db, config_mod=config, interactive=False)`;
      - bez `--chunked`: `scout.scan_book("\n\n".join(c["raw_text"] for c in chs), cf("scout"))`
      - `--chunked`: `scout.scan_chunks(scout.chunk_chapters(chs, config.SCOUT_CHUNK_WORD_LIMIT), cf("scout"))`
      `except (OutputTruncated, ValueError) as e: raise FatalRunError(f"scout výstup je neúplný/rozbitý ({e}). Zkus `scan --chunked` nebo zvyš MAX_TOKENS_SCOUT.")`; jinak `guide.save_draft(config.GUIDE_DRAFT_PATH, result)`.
    - `run [--retry-flagged [IDX...]]` → `recover_processing`; `--retry-flagged` → `state.retry_flagged(db, idxs)`; `cf = lambda a: PipelineLLMClient(AnthropicClient(), run_id=rid, agent=a, db_path=db, config_mod=config, interactive=True)` (**`run` je interaktivní - cost guard se ptá; jen `scan` má `interactive=False`**); pro každou `queue_for_run(db)` kapitolu:
      ```
      try:
          summary = pipeline.process_chapter(db, ch, client_factory=cf, guide=g)
      except FatalRunError:
          raise                        # bublá do lifecycle try, status zůstane "fatal", exit 1
      except Exception as e:            # OutputTruncated i ValueError jsou Exception - stejný handling
          state.update_chapter(db, ch["idx"], status="error",
                               notes=json.dumps({"error": f"{type(e).__name__}: {e}"},
                                                ensure_ascii=False))
      ```
      **Pořadí `except` je závazné - `FatalRunError` PRVNÍ a jen `raise`** (je to `Exception`; `except Exception` samo by fatal chybu jinak označilo jako `error` kapitoly). `KeyboardInterrupt` NENÍ `Exception` - projde ven do lifecycle sám.
      **Drift scheduling (přesně):** po každém úspěšném `process_chapter`, jehož výsledný status je `done` nebo `flagged`, spočti `n = state.counts_by_status(db)` součet `done+flagged`; pokud `n > 0 and n % config.CROSS_REF_EVERY_N == 0` → `pipeline.run_drift_check(db, ch["idx"])`. (Počítá hotové kapitoly, ne `idx`.)
      Po smyčce: report (`state.counts_by_status`) + `_print_usage(db, rid)` (suma z `llm_calls`). `finish_run` řeší lifecycle `finally`.
    - `questions` → vypiš `state.unanswered_questions`
    - `answer QID TEXT` → `requeue.apply_answer`, vypiš co se requeue
    - `status` → `state.counts_by_status` + seznam s markery (`OK/../!!/??/XX/~~` pro done/pending/flagged/needs_human/error/processing)
    - `export [--only-done]` → viz §Export; read-only, žádný lock
  - `main._bootstrap_stdout()` - UTF-8 reconfigure, voláno první v `main()`

- [ ] **Step 1: Write failing tests** — `tests/test_requeue.py`

```python
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
```

- [ ] **Step 2: Write failing CLI tests** — `tests/test_cli.py`

```python
import os, json, sys
import main
from src import state


def _run(argv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("config.DATA_DIR", "data")
    monkeypatch.setattr("config.DB_PATH", "data/state.sqlite3")
    monkeypatch.setattr("config.GUIDE_DRAFT_PATH", "data/guide.draft.json")
    monkeypatch.setattr("config.GUIDE_PATH", "data/guide.json")
    monkeypatch.setattr("config.LOCK_PATH", "data/.lock")
    monkeypatch.setattr("config.OUTPUT_TXT", "output/kniha_cz.txt")
    return main.main(argv)


def test_init_seeds_chapters(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "text " * 60 + "\nChapter 2\n" + "text " * 60,
                    encoding="utf-8")
    assert _run(["init", str(book)], tmp_path, monkeypatch) == 0
    assert len(state.chapters_by_status("data/state.sqlite3", ("pending",))) == 2


def test_status_runs_without_db_error(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "text " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    assert _run(["status"], tmp_path, monkeypatch) == 0


def _init_4ch(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    body = "t " * 60
    book.write_text("".join(f"Chapter {i}\n{body}\n" for i in range(1, 5)), encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    db = "data/state.sqlite3"
    state.update_chapter(db, 1, status="done", translated_text="Kapitola 1 CZ.")
    state.update_chapter(db, 2, status="flagged", translated_text="Kapitola 2 CZ.",
                         notes=json.dumps([{"issue": "nekonzistentní termín",
                                            "action": "revise"}]))
    state.update_chapter(db, 3, status="needs_human", translated_text="")
    state.update_chapter(db, 4, status="error", notes='{"error":"X"}')
    return db


def test_export_full_markers(tmp_path, monkeypatch, capsys):
    db = _init_4ch(tmp_path, monkeypatch)
    before = {c["idx"]: c["status"] for c in state.chapters_by_status(
        db, ("done", "flagged", "needs_human", "error"))}
    assert _run(["export"], tmp_path, monkeypatch) == 0
    text = open("output/kniha_cz.txt", encoding="utf-8").read()
    assert "Kapitola 1 CZ." in text
    assert "Kapitola 2 CZ." in text and "REVIDOVAT" in text
    assert "CHYBÍ KAPITOLA 3" in text and "CHYBÍ KAPITOLA 4" in text
    out = capsys.readouterr().out
    assert "3" in out and "4" in out          # varování na stdout o vynechaných
    after = {c["idx"]: c["status"] for c in state.chapters_by_status(
        db, ("done", "flagged", "needs_human", "error"))}
    assert before == after                     # export je read-only


def test_export_only_done(tmp_path, monkeypatch, capsys):
    _init_4ch(tmp_path, monkeypatch)
    assert _run(["export", "--only-done"], tmp_path, monkeypatch) == 0
    text = open("output/kniha_cz.txt", encoding="utf-8").read()
    assert "Kapitola 1 CZ." in text
    assert "Kapitola 2 CZ." not in text        # flagged vynechána
    assert "REVIDOVAT" not in text and "CHYBÍ KAPITOLA" not in text
    assert "2" in capsys.readouterr().out       # ale seznam vynechaných na stdout


def test_run_processes_queue_with_monkeypatched_pipeline(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.pipeline as P
    def fake_process(db_path, chapter, *, client_factory, guide):
        state.update_chapter(db_path, chapter["idx"], status="done",
                             translated_text="hotovo")
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", fake_process)
    assert _run(["run"], tmp_path, monkeypatch) == 0
    assert state.get_chapter("data/state.sqlite3", 1)["status"] == "done"
    with state.connect("data/state.sqlite3") as conn:
        r = conn.execute("SELECT status, ended_at FROM runs ORDER BY id DESC "
                         "LIMIT 1").fetchone()
    assert r["status"] == "ok" and r["ended_at"] is not None  # run se uzavřel


def test_run_fatal_error_closes_run_and_exits_nonzero(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.pipeline as P
    from src.llm.client import FatalRunError
    def boom(*a, **k): raise FatalRunError("bad key")
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] in ("pending", "processing")
    with state.connect("data/state.sqlite3") as conn:
        r = conn.execute("SELECT status FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    assert r["status"] == "fatal"
```

- [ ] **Step 3: Run to verify fail** — FAIL.
- [ ] **Step 4: Implement `src/requeue.py` a `main.py`.**
- [ ] **Step 5: Run to verify pass** — `python -m pytest tests/test_requeue.py tests/test_cli.py -v` → PASS.
- [ ] **Step 6: Verify UTF-8 bootstrap in cp1252** — Run: `python -X utf8=0 -c "import sys; sys.argv=['x','status']; import main; main.main()"` po `init` v adresáři s daty. Expected: žádný `UnicodeEncodeError` na českém výstupu.
- [ ] **Step 7: Commit**

```bash
git add src/requeue.py main.py tests/test_requeue.py tests/test_cli.py
git commit -m "feat: CLI (init/scan/run/status/questions/answer/export) + requeue vrstva"
```

---

## Task 16: review_ui + `review` CLI příkaz + reseed

**Files:**
- Create: `src/review_ui/__init__.py`
- Create: `src/review_ui/server.py`
- Create: `src/review_ui/static/index.html`
- Modify: `main.py` (přidat `review` subcommand)
- Create: `tests/test_review_ui.py`

**Interfaces:**
- Consumes: `guide` (`load_draft`, `load_guide`, `merge_draft_and_guide`, `save_guide`), `fastapi`, `uvicorn`
- Produces:
  - `server.apply_must_decide(payload: dict) -> dict` - PŘED save: pro každý `must_decide` s neprázdnou `answer` zapiš odpověď do finálních polí podle `kind`:
    - `term` → přidej/uprav `payload["terms"]` řádek `{term_en: scope_key, cz: answer}`
    - `name` → `payload["characters"]` řádek `{name_en: scope_key, render: "translate" if answer != scope_key else "keep", cz: answer}`
    - `relationship` (`scope_key = "a|b"`) → `payload["relationships"]` `{a, b, address: answer}`
    - `style`/`other` → append do `payload["rules"]`
    `must_decide` se pak z payloadu odstraní (rozhodnutí jsou zapsaná v polích). Vrací upravený payload.
  - `server.validate(payload: dict) -> list[str]` - vrací seznam chyb (prázdný = OK):
    - každá `characters` položka: `name_en` neprázdné, `render ∈ {keep, translate}`, u `translate` `cz` neprázdné
    - každá `places` / `terms` položka: `name_en`/`term_en` neprázdné, `cz` neprázdné
    - každá `relationships` položka: `a`, `b` neprázdné, `address ∈ {tyka, vyka}`
    - každý `must_decide` s neprázdnou `question`: `answer` neprázdné
  - `server.build_app(draft_path, guide_path, on_saved) -> FastAPI` - `GET /` → `index.html`; `GET /api/guide` → `merge_draft_and_guide`; `POST /api/guide`:
    1. `_check_must_decide_answered(payload)` - jen "každý must_decide má neprázdnou answer" → chyba `422`
    2. `payload = apply_must_decide(payload)` - zapíše odpovědi do polí, smaže `must_decide`
    3. `errs = validate(payload)` - PLNÁ schema validace VÝSLEDNÉHO payloadu (i address ∈ {tyka,vyka} atd. - chytí nesmyslnou must_decide odpověď) → chyba `422`
    4. `save_guide` → `on_saved()` → `{"ok": true}`
  - `server.run_review_server(draft_path, guide_path) -> int` - uvicorn + `webbrowser.open`; po úspěšném POST `should_exit=True` → return 0; SIGINT/zavření bez uložení → return 1
  - `main` `review` subcommand: `with state.run_lock(config.LOCK_PATH):` → `rc = server.run_review_server(config.GUIDE_DRAFT_PATH, config.GUIDE_PATH)`; `if rc == 0: glossary.seed_from_guide(config.DB_PATH, guide.load_guide(config.GUIDE_PATH))` (reseed dělá CLI, ne UI - drží izolaci); `return rc`

- [ ] **Step 1: Write failing tests** — `tests/test_review_ui.py`

```python
import json
from fastapi.testclient import TestClient
from src.review_ui import server


def _paths(tmp_path):
    dp = str(tmp_path / "guide.draft.json")
    gp = str(tmp_path / "guide.json")
    json.dump({"characters": [{"name_en": "Harry", "suggested": "keep", "note": "h"}],
               "places": [], "terms": [], "relationships": [],
               "style_notes": "s", "must_decide": []},
              open(dp, "w", encoding="utf-8"))
    return dp, gp


def test_get_guide_merges_draft(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    r = TestClient(app).get("/api/guide")
    assert r.status_code == 200
    assert any(c["name_en"] == "Harry" for c in r.json()["characters"])


def test_post_valid_guide_saves_and_calls_on_saved(tmp_path):
    dp, gp = _paths(tmp_path)
    called = {"n": 0}
    app = server.build_app(dp, gp, on_saved=lambda: called.__setitem__("n", 1))
    payload = {"characters": [{"name_en": "Harry", "render": "keep", "cz": "Harry"}],
               "places": [], "relationships": [], "style": "s", "rules": [],
               "must_decide": []}
    r = TestClient(app).post("/api/guide", json=payload)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert called["n"] == 1
    assert json.load(open(gp, encoding="utf-8"))["characters"][0]["render"] == "keep"


def test_post_rejects_translate_without_cz(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [{"name_en": "X", "render": "translate", "cz": ""}],
               "places": [], "relationships": [], "style": "", "rules": [],
               "must_decide": []}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422


def test_post_rejects_unanswered_must_decide(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [], "places": [], "terms": [], "relationships": [],
               "style": "", "rules": [], "must_decide": [{"kind": "term",
               "scope_key": "Foo", "question": "?", "answer": ""}]}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 422


def test_post_routes_must_decide_answer_into_terms(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [], "places": [], "terms": [], "relationships": [],
               "style": "", "rules": [], "must_decide": [{"kind": "term",
               "scope_key": "The White Council", "question": "?", "answer": "Bílá rada"}]}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    saved = json.load(open(gp, encoding="utf-8"))
    assert any(t["term_en"] == "The White Council" and t["cz"] == "Bílá rada"
               for t in saved["terms"])
    assert saved.get("must_decide", []) == []  # rozhodnutí zapsaná, must_decide pryč


def _post(tmp_path, extra):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    base = {"characters": [], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": [], "must_decide": []}
    base.update(extra)
    return TestClient(app).post("/api/guide", json=base), gp


def test_must_decide_name_routes_to_characters(tmp_path):
    r, gp = _post(tmp_path, {"must_decide": [{"kind": "name", "scope_key": "Aria",
        "question": "?", "answer": "Ária"}]})
    assert r.status_code == 200
    saved = json.load(open(gp, encoding="utf-8"))
    c = [x for x in saved["characters"] if x["name_en"] == "Aria"][0]
    assert c["render"] == "translate" and c["cz"] == "Ária"


def test_must_decide_relationship_routes_and_rejects_invalid_answer(tmp_path):
    ok, gp = _post(tmp_path, {"must_decide": [{"kind": "relationship",
        "scope_key": "harry|murphy", "question": "?", "answer": "vyka"}]})
    assert ok.status_code == 200
    assert json.load(open(gp, encoding="utf-8"))["relationships"][0]["address"] == "vyka"
    bad, _ = _post(tmp_path, {"must_decide": [{"kind": "relationship",
        "scope_key": "a|b", "question": "?", "answer": "možná"}]})
    assert bad.status_code == 422   # neplatný address chycen plnou validací PO apply


def test_must_decide_style_routes_to_rules(tmp_path):
    r, gp = _post(tmp_path, {"must_decide": [{"kind": "style", "scope_key": "",
        "question": "?", "answer": "vypravěč je sarkastický"}]})
    assert r.status_code == 200
    assert "vypravěč je sarkastický" in json.load(open(gp, encoding="utf-8"))["rules"]


def test_must_decide_updates_existing_term_not_duplicate(tmp_path):
    dp, gp = _paths(tmp_path)
    app = server.build_app(dp, gp, on_saved=lambda: None)
    payload = {"characters": [], "places": [],
               "terms": [{"term_en": "Council", "cz": "Rada"}],
               "relationships": [], "style": "", "rules": [],
               "must_decide": [{"kind": "term", "scope_key": "Council",
                                "question": "?", "answer": "Koncil"}]}
    assert TestClient(app).post("/api/guide", json=payload).status_code == 200
    terms = json.load(open(gp, encoding="utf-8"))["terms"]
    assert len(terms) == 1 and terms[0]["cz"] == "Koncil"
```

- [ ] **Step 2: Run to verify fail** — FAIL (`httpx` v dev deps).
- [ ] **Step 3: Implement `server.py` + minimal `index.html`** (vanilla JS: fetch `/api/guide`, sekce s `<select>`/`<input type=checkbox>`/`<textarea>`, must_decide zvýrazněné nahoře, "Ulož a zavři" → POST → na `ok` "hotovo, zavři okno").
- [ ] **Step 4: Run to verify pass** — PASS (9 tests).
- [ ] **Step 5: Test CLI `review` reseed** — `tests/test_cli.py`:

```python
def test_review_reseeds_on_success(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.review_ui.server as SRV
    from src import guide as G, glossary
    def fake_ok(*a, **k):
        G.save_guide("data/guide.json", {"characters": [{"name_en": "Harry",
            "render": "keep"}], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": []})
        return 0
    monkeypatch.setattr(SRV, "run_review_server", fake_ok)
    assert _run(["review"], tmp_path, monkeypatch) == 0
    assert any(t["canonical_en"] == "Harry" and t["status"] == "seeded"
               for t in glossary.all_terms("data/state.sqlite3"))


def test_review_does_not_reseed_on_failure(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"; book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.review_ui.server as SRV
    from src import guide as G, glossary
    def fake_fail(*a, **k):
        # UI "uložilo" guide, ale server skončil chybou (rc=1)
        G.save_guide("data/guide.json", {"characters": [{"name_en": "Zed",
            "render": "keep"}], "places": [], "terms": [], "relationships": [],
            "style": "", "rules": []})
        return 1
    monkeypatch.setattr(SRV, "run_review_server", fake_fail)
    rc = _run(["review"], tmp_path, monkeypatch)
    assert rc == 1
    assert glossary.all_terms("data/state.sqlite3") == []   # ŽÁDNÝ reseed
```

- [ ] **Step 6: Run to verify pass** — `python -m pytest tests/test_review_ui.py tests/test_cli.py -v` → PASS (celá test_cli.py včetně 2 nových review testů).
- [ ] **Step 7: Add `review` subcommand smoke** — ruční: `python main.py review` po `init`+`scan` otevře prohlížeč, uložení → server skončí → `glossary` má `seeded` řádky.
- [ ] **Step 8: Commit**

```bash
git add src/review_ui/ main.py pyproject.toml tests/test_review_ui.py tests/test_cli.py
git commit -m "feat: review UI (FastAPI, must_decide routing, exit-code signál, CLI reseed + test)"
```

---

## Task 17: README + pilot checklist + full test run

**Files:**
- Create: `README.md`
- Create: `docs/pilot-checklist.md`
- Modify: `requirements.txt` (pokud executor preferuje requirements.txt vedle pyproject - jinak vynech)

**Interfaces:**
- Consumes: nic
- Produces: dokumentace

- [ ] **Step 1: Napiš `README.md`** - instalace (`pip install -e ".[dev]"`, `export ANTHROPIC_API_KEY=...`), přehled příkazů (kopíruj §"Fáze běhu"), stavové markery, odkaz na spec a pilot checklist, běh testů (`python -m pytest`).

- [ ] **Step 2: Napiš `docs/pilot-checklist.md`**

```markdown
# Pilotní checklist (2-3 reálné kapitoly, ~$1)

- [ ] **Ověřit model + ceny + limity** proti https://docs.anthropic.com/en/docs/about-claude/model-deprecations
      a https://platform.claude.com/docs/en/models/sonnet-5/whats-new-sonnet-5 .
      Zapsat aktuální hodnoty do `config.py` (MODEL_*, PRICE_*_PER_MTOK, MAX_TOKENS_*).
- [ ] `python main.py init <kniha.epub>` - sedí počet kapitol?
- [ ] `python main.py scan` - vejde se do 1 volání, nebo hlásí truncated → `scan --chunked`?
- [ ] `python main.py review` - dá se návod pohodlně projít? Ulož.
- [ ] Zúžit `chapters` v DB na 2-3 (ručně `DELETE FROM chapters WHERE idx > 3`).
- [ ] `python main.py run` - projde? Kolik `guess` otázek / `candidate` termínů na kapitolu?
- [ ] Přečti výstup: je překlad použitelný? Kde selhává?
- [ ] Rozchází se kritik s translatorem smysluplně? (Kolikrát se spustila revizní smyčka a pomohla?)
      → Pokud skoro nikdy: signál, že revizní smyčka je zbytečná režie - zvážit zjednodušení.
- [ ] `SELECT SUM(cost_usd) FROM llm_calls` - cena za kapitolu → extrapoluj na celou knihu.
- [ ] Falešné drift nálezy z kmenového porovnání - kolik? (→ potřeba LLM soudce dřív?)
```

- [ ] **Step 3: Full test run** — Run: `python -m pytest -v`. Expected: všechny testy PASS. Oprav co padá.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/pilot-checklist.md
git commit -m "docs: README + pilotní checklist"
```

---

## Self-Review (provedeno při psaní plánu)

**1. Spec coverage:**
- ✅ ingest (EPUB spine, TXT, scény) → Task 2
- ✅ scout + `--chunked` merge → Task 11
- ✅ review web UI → Task 16
- ✅ translator → kritik → revizor smyčka → Task 14
- ✅ concordance (build_mentions, check_chapter, check_drift) → Task 8
- ✅ candidate/approved/seeded termíny, term_id párování → Task 6
- ✅ dávkové otázky, `questions`/`answer`, requeue pravidla → Tasky 10, 15
- ✅ navazatelný běh, transakce A/B, processing recovery → Tasky 9, 14
- ✅ export (done + flagged marker, chybějící kapitoly) → Task 15
- ✅ provider vrstva, `PipelineLLMClient` cost guard + llm_calls → Tasky 4, 5
- ✅ UTF-8 stdout → Task 15 (Step 6 ověří v cp1252)
- ✅ run lock → Task 9
- ✅ Finding sjednocený tvar + action routing → Tasky 8, 13, 14
- ✅ drift → questions → Task 14 (`run_drift_check`)
- ✅ cost guard `spend_ceiling` stav → Task 5
- ✅ `run --retry-flagged` → Tasky 9 (`retry_flagged`), 15
- ✅ pilot checklist (model validace první) → Task 17

**2. Placeholder scan:** Tasky 6-10 mají část impl kroků jako popis ("Implement dle specu") místo plného kódu - to je záměrné pro deterministické CRUD/parsing vrstvy, kde je interface + test dostatečně přesný a plný kód by plán nafoukl bez informační hodnoty. Testy jsou vždy plné. Executor má interface blok + testy + odkaz na konkrétní § specu.

**3. Type consistency:**
- `Completion(text, truncated, input_tokens, output_tokens)` - konzistentní Tasky 4, 5, 11, 12, 13
- `TranslationResult(translation, new_terms, rendered_terms, questions)` - Tasky 12, 14
- `Finding` dict shape - Tasky 8, 13, 14 (klíče `source, type, severity, action, term_id, expected, actual, cz_excerpt, issue, suggestion`)
- `Mention(term_id, cz_form, scene_idx, source)` - Tasky 8, 10
- `state.upsert_open_question(db, q)` kde `q` = `{chapter_idx, kind, text, scope_key, guess_answer, severity}` - Tasky 10, 14, 15
- `client_factory(agent) -> LLMClient` - Tasky 14, 15
- `state.commit_chapter_result(...)` zaveden v Tasku 14 (rozšíření state.py), konzumován jen pipeline

**Poznámka k Tasku 14 Step 3:** `commit_chapter_result` je jediný "objevený" interface mimo původní task hranice - je to vědomé rozhodnutí (transakce B potřebuje jeden atomický zápis přes víc tabulek), zdokumentované v tom tasku.

---

## Execution Handoff

Plán uložen do `docs/superpowers/plans/2026-09-06-book-translator.md`.

**Dvě možnosti provedení:**

1. **Subagent-Driven (doporučeno)** - čerstvý subagent na každý task, review mezi tasky, rychlá iterace. REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
2. **Inline Execution** - tasky v této session přes superpowers:executing-plans, dávkové provádění s checkpointy.

**Kterou cestu?**
