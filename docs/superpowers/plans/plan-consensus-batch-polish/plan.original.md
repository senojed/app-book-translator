# Dávkový polish + čtenářský review workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `polish` proběhne dávkově přes celou knihu a výsledek se rovnou zapíše
jako finální text (žádná čekající review fronta); nová web UI nabídne seznam
všech kapitol, editor libovolné kapitoly (i bez "draftu"), ruční
zaškrtávání vyřešených nálezů, tlačítko "znovu polish" a export knihy +
report nálezů.

**Architecture:** `_polish_one_chapter` (Codex + concordance + kritik +
strukturální kontrola) se nemění. Mění se jen to, co se s výsledkem dělá -
nový sdílený `_commit_polish_result` helper (main.py) zapisuje rovnou do DB
+ `polish.history.json`, ať volá z dávkového `_cmd_polish`, nebo z nového
"Uložit" endpointu editoru. `polish.draft.json` (čekající fronta) mizí
úplně. Nálezy dostávají stabilní `id` + `resolved` flag (`src/findings.py`)
místo automatického přepočtu po ruční úpravě.

**Tech Stack:** Python, FastAPI/uvicorn (`src/review_ui/polish_server.py`),
SQLite (`src/state.py`), vanilla JS/HTML (žádný frontend framework, stejně
jako dnes), pytest.

**Spec:** `docs/superpowers/specs/2026-09-14-batch-polish-reader-workflow-design.md`
(rozšiřuje `docs/superpowers/specs/2026-09-11-polish-review-design.md` -
zámkový/CAS/atomický-zápis aparát odtamtud zůstává beze změny a tenhle plán
ho znovu používá, nevysvětluje ho znovu).

## Global Constraints

- Windows cílová platforma (existující kód spoléhá na `os.rename`
  chování specifické pro Windows u zámků/archivace - viz `src/state.py`).
- Čeština v komunikaci s uživatelem (`_say`, chybové hlášky, UI texty) -
  zachovej stávající konvenci projektu.
- Žádný `innerHTML` s interpolovaným textem ve frontendu (nedůvěryhodný
  text - Codex výstup, text knihy) - vždy `createElement`/`textContent`,
  posluchače přes `addEventListener`, nikdy inline `onclick="..."`.
- Atomické zápisy JSON (tmp + `os.replace`, unikátní tmp jméno na každé
  volání) - `src/polish_store.py`'s `_atomic_write_json` už tohle dělá,
  žádný nový kód nesmí zapisovat `polish.history.json` jinak.
- CAS kontrola PŘED každým zápisem, co mění `chapters.translated_text` -
  porovnej aktuální DB stav s tím, z čeho editor/dávka vycházela, než
  cokoli zapíšeš (stejný princip jako dnešní `apply`/`revert`).
- `write_lock` (threading.Lock) + `app.state.require_lock()` (zámek
  napříč procesy) obaluje CELÉ tělo každého zápisového endpointu - žádný
  nový endpoint, co píše do DB/JSON, tenhle vzor neobchází.
- TDD: každý task napřed napíše test, ověří selhání, pak implementuje.

---

## Task 1: `config.py` - parametrizace kořenové složky projektu

**Files:**
- Modify: `config.py:39-47`
- Test: `tests/test_config.py` (nový soubor)

**Interfaces:**
- Produces: `config.PROJECT_DIR: str`, `config.DATA_DIR`/`config.OUTPUT_DIR`
  odvozené z `PROJECT_DIR` (stejné jméno proměnných jako dnes, jiný zdroj).

- [ ] **Step 1: Napiš test**

```python
# tests/test_config.py
import importlib
import os


def _reload_config(monkeypatch, project_dir=None):
    if project_dir is None:
        monkeypatch.delenv("BOOK_TRANSLATOR_PROJECT_DIR", raising=False)
    else:
        monkeypatch.setenv("BOOK_TRANSLATOR_PROJECT_DIR", project_dir)
    import config
    importlib.reload(config)
    return config


def test_project_dir_defaults_to_dot(monkeypatch):
    config = _reload_config(monkeypatch)
    assert config.PROJECT_DIR == "."
    assert config.DATA_DIR == os.path.join(".", "data")
    assert config.OUTPUT_DIR == os.path.join(".", "output")


def test_project_dir_reads_env_var(monkeypatch, tmp_path):
    config = _reload_config(monkeypatch, project_dir=str(tmp_path))
    assert config.PROJECT_DIR == str(tmp_path)
    assert config.DATA_DIR == os.path.join(str(tmp_path), "data")
    assert config.DB_PATH == os.path.join(str(tmp_path), "data", "state.sqlite3")
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_config.py -v`
Expected: FAIL - `config.PROJECT_DIR` neexistuje (`AttributeError`).

- [ ] **Step 3: Implementuj**

V `config.py` nahraď (řádky 39-47):

```python
DATA_DIR = "data"
OUTPUT_DIR = "output"
```

za:

```python
PROJECT_DIR = os.environ.get("BOOK_TRANSLATOR_PROJECT_DIR", ".")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
```

Zbytek souboru (`DB_PATH`, `GUIDE_PATH`, ... `OUTPUT_TXT`) se nemění - už
dnes jsou postavené jako `os.path.join(DATA_DIR, ...)`/`os.path.join(
OUTPUT_DIR, ...)`, takže je automaticky zdědí.

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: parametrizuj kořenovou složku projektu (příprava na další knihy)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: `src/findings.py` - stabilní id + resolved flag

**Files:**
- Create: `src/findings.py`
- Test: `tests/test_findings.py`

**Interfaces:**
- Produces:
  - `assign_ids(findings: list[dict]) -> list[dict]` - mutuje V MÍSTĚ a vrací
    stejný seznam (pohodlné řetězení), idempotentní.
  - `set_resolved(findings: list[dict], finding_id: str, resolved: bool) -> bool`
    - `True` když nález našel a upravil, `False` když `finding_id`
    neexistuje v seznamu.
  - `is_marker(finding: dict) -> bool` - `True` pro audit markery
    (`_stylist_marker`/`_kept_original_marker`/`_revert_marker` z
    `main.py`), `False` pro skutečné nálezy (concordance/kritik/
    strukturální).
  - `count_unresolved(findings: list[dict]) -> int` - počet NE-markerových
    nálezů s `resolved` != `True`.

- [ ] **Step 1: Napiš test**

```python
# tests/test_findings.py
from src import findings


def test_assign_ids_adds_id_and_resolved_false():
    fs = [{"source": "concordance", "type": "omission", "issue": "x"}]
    out = findings.assign_ids(fs)
    assert out is fs   # mutuje v místě, stejný objekt
    assert isinstance(fs[0]["id"], str) and fs[0]["id"]
    assert fs[0]["resolved"] is False


def test_assign_ids_is_idempotent():
    fs = [{"source": "concordance", "type": "omission", "id": "keep-me",
           "resolved": True}]
    findings.assign_ids(fs)
    assert fs[0]["id"] == "keep-me"
    assert fs[0]["resolved"] is True


def test_assign_ids_gives_unique_ids_to_each_finding():
    fs = [{"issue": "a"}, {"issue": "b"}]
    findings.assign_ids(fs)
    assert fs[0]["id"] != fs[1]["id"]


def test_set_resolved_updates_matching_finding():
    fs = [{"id": "f1", "resolved": False}, {"id": "f2", "resolved": False}]
    ok = findings.set_resolved(fs, "f2", True)
    assert ok is True
    assert fs[0]["resolved"] is False
    assert fs[1]["resolved"] is True


def test_set_resolved_returns_false_for_unknown_id():
    fs = [{"id": "f1", "resolved": False}]
    assert findings.set_resolved(fs, "nope", True) is False
    assert fs[0]["resolved"] is False


def test_is_marker_true_for_stylist_audit_types():
    assert findings.is_marker({"source": "stylist", "type": "polish"}) is True
    assert findings.is_marker({"source": "stylist", "type": "kept_original"}) is True
    assert findings.is_marker({"source": "stylist", "type": "revert"}) is True


def test_is_marker_false_for_real_findings():
    assert findings.is_marker({"source": "concordance", "type": "omission"}) is False
    assert findings.is_marker({"source": "critic", "type": "fidelity"}) is False
    assert findings.is_marker({"source": "stylist_check", "type": "register_drift"}) is False


def test_count_unresolved_excludes_markers_and_resolved():
    fs = [
        {"source": "stylist", "type": "polish", "resolved": False},   # marker - never counts
        {"source": "critic", "type": "fidelity", "resolved": False},  # counts
        {"source": "critic", "type": "fidelity", "resolved": True},   # resolved - excluded
    ]
    assert findings.count_unresolved(fs) == 1
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_findings.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'src.findings'`

- [ ] **Step 3: Implementuj**

```python
# src/findings.py
"""Stabilní identita nálezů (concordance/kritik/strukturální kontrola)
napříč `run`/`polish` běhy. Bez tohodle nejde uživateli dovolit ručně
"odškrtnout vyřešeno" - nálezy se dnes přegenerují od nuly při každém
běhu a nemají žádnou trvalou identitu."""
import uuid

_MARKER_TYPES = {("stylist", "polish"), ("stylist", "kept_original"),
                 ("stylist", "revert")}


def assign_ids(findings: list) -> list:
    """Doplní `id`/`resolved` KAŽDÉMU nálezu, co je ještě nemá - nikdy
    nepřepíše existující hodnotu (idempotentní, bezpečné volat opakovaně
    na stejný seznam). Mutuje v místě a vrací stejný seznam."""
    for f in findings:
        f.setdefault("id", uuid.uuid4().hex)
        f.setdefault("resolved", False)
    return findings


def set_resolved(findings: list, finding_id: str, resolved: bool) -> bool:
    """Najde nález podle `id` a přepíše `resolved`. Vrací, jestli se
    nález našel - volající (server endpoint) na `False` odpoví 404."""
    for f in findings:
        if f.get("id") == finding_id:
            f["resolved"] = resolved
            return True
    return False


def is_marker(finding: dict) -> bool:
    """Audit marker (`main._stylist_marker`/`_kept_original_marker`/
    `_revert_marker`) NENÍ nález k vyřešení - je to jen záznam "kdy/jak
    se text změnil", uživatel ho nemá zaškrtávat."""
    return (finding.get("source"), finding.get("type")) in _MARKER_TYPES


def count_unresolved(findings: list) -> int:
    return sum(1 for f in findings if not is_marker(f) and not f.get("resolved"))
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_findings.py -v`
Expected: PASS (8 testů)

- [ ] **Step 5: Zapoj do `run` fáze (`src/pipeline.py`)**

Přečti `src/pipeline.py:150-186` (`process_chapter`) před úpravou. Uprav
konec funkce - PŘED `result = state.commit_chapter_result(...)` (řádek
181) přidej:

```python
    from src import findings as findings_mod
    findings = findings_mod.assign_ids(findings)

    result = state.commit_chapter_result(
```

(zbytek volání `commit_chapter_result` se nemění, `notes_json=json.dumps(findings, ...)`
teď serializuje findings s `id`/`resolved`).

- [ ] **Step 6: Test integrace do `pipeline.process_chapter`**

Najdi existující test v `tests/test_pipeline*.py`, co ověřuje `notes` po
úspěšném `process_chapter` (zkontroluj přes `Grep "notes_json\|def test.*process_chapter" tests/`),
a přidej k němu (nebo napiš nový, pokud žádný podobný neexistuje):

```python
def test_process_chapter_notes_have_finding_ids(tmp_path):
    # postav minimální DB/chapter/client_factory podle existujícího vzoru
    # v tomtéž testovacím souboru, zavolej process_chapter, pak:
    row = state.get_chapter(db, 1)
    saved = json.loads(row["notes"])
    assert all("id" in f and "resolved" in f for f in saved)
```

Run: `pytest tests/test_pipeline*.py -k finding_ids -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/findings.py tests/test_findings.py src/pipeline.py tests/test_pipeline*.py
git commit -m "feat: stabilní id + resolved flag u nálezů (run fáze)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: Zapoj `assign_ids` do `polish` fáze + přejmenuj outcome

**Files:**
- Modify: `main.py:454` (`_REPORT_OUTCOMES`), `main.py:561-657`
  (`_polish_one_chapter`), `main.py:1222-1228` (`_cmd_polish` report_rec)
- Test: `tests/test_cli.py` (existující testy na `_polish_one_chapter`/
  `_cmd_polish` výstup)

**Interfaces:**
- Consumes: `findings.assign_ids` (Task 2).
- Produces: `_polish_one_chapter`'s vrácený dict má `findings` VŽDY s
  `id`/`resolved`. `_REPORT_OUTCOMES` obsahuje `"applied"` místo
  `"drafted"`.

- [ ] **Step 1: Přečti a najdi dotčené testy**

`Grep "drafted" main.py tests/test_cli.py` - najdi všechna místa, co
řetězec `"drafted"` používají (report tally hlášky, testy na
`_write_polish_report`/`_cmd_polish` výstup). Tenhle task je čistě
přejmenování + jedno přidané volání, žádná testovací logika se nemění,
jen `"drafted"` → `"applied"` napříč nalezenými testy.

- [ ] **Step 2: Uprav `_polish_one_chapter` (main.py:561-657)**

Přidej import na začátek souboru (vedle ostatních `from src import ...`):

```python
from src import findings as findings_mod
```

V `_polish_one_chapter`, těsně PŘED `return {"idx": idx, "title": c["title"], ...}`
(řádek 654) přidej:

```python
    findings = findings_mod.assign_ids(findings)
```

- [ ] **Step 3: Přejmenuj `_REPORT_OUTCOMES` (main.py:454)**

```python
_REPORT_OUTCOMES = ("applied", "unchanged", "failed", "fatal", "interrupted")
```

- [ ] **Step 4: Uprav `_cmd_polish`'s report_rec (main.py:1222-1228)**

```python
                    full = config.STYLIST_REPORT_REJECTED_TEXT is True
                    report_rec = {"idx": rec["idx"], "outcome": "applied",
                                 "reason_types": rec["reason_types"]}
```

(jen `"drafted"` → `"applied"`, zbytek beze změny - tahle větev se
přepisuje dál v Tasku 5, tady jen sjednocujeme jméno outcome PŘED tím,
než se za chvíli mění i to, kam se zapisuje).

- [ ] **Step 5: Přejmenuj v testech**

V `tests/test_cli.py` nahraď `replace_all` výskyty `"drafted"` za
`"applied"` (řetězcové literály v assertions na `outcome`/`summary`/
`tally` klíče). NEnahrazuj český text jako "návrh připraven" - ten se
mění až v Tasku 5.

- [ ] **Step 6: Přidej test na finding id v draftu**

Najdi existující test volající `_polish_one_chapter` přímo (`Grep "_polish_one_chapter(" tests/test_cli.py`)
a přidej vedle něj:

```python
def test_polish_one_chapter_findings_have_ids(...):   # stejná fixture jako soused
    rec = main._polish_one_chapter(chapter, glossary_rows, cf, db, model, codex_cmd)
    assert all("id" in f and "resolved" in f for f in rec["findings"])
```

(zkopíruj přesnou fixture/setup ze SOUSEDNÍHO testu ve stejném souboru -
`_polish_one_chapter` potřebuje fake Codex skript přes `codex_cmd`, viz
existující vzor v `tests/test_cli.py`/`tests/test_stylist.py`.)

- [ ] **Step 7: Ověř**

Run: `pytest tests/test_cli.py -k polish -v`
Expected: PASS, žádný `"drafted"` string nikde v assertions.

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "refactor: finding id v polish fázi, přejmenuj outcome drafted->applied

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: `main.py` - `_rendered_terms_for_chapter` sdílený helper

**Files:**
- Modify: `main.py:561-599` (`_polish_one_chapter` - extrahuj existující
  duplikovanou logiku)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `_rendered_terms_for_chapter(db: str, idx: int) -> list[dict]`
  - `[{"term_id": str, "cz_as_used": str, "scene_idx": int|None}, ...]`

**Proč:** `_polish_one_chapter` už tohle počítá (řádky 593-597). Task 9
(editor "Uložit" endpoint) potřebuje STEJNÝ výpočet pro kapitolu bez
živého draftu - extrakce teď, ne duplikace kódu později.

- [ ] **Step 1: Napiš test**

```python
def test_rendered_terms_for_chapter_reads_rendered_source_mentions(tmp_path):
    db = _make_db_with_one_chapter(tmp_path)   # použij existující tests/test_cli.py fixture
    with state.connect(db) as conn:
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('term_x','X','Ix')")
        conn.execute(
            "INSERT INTO term_mentions (term_id,cz_form,chapter_idx,scene_idx,source) "
            "VALUES ('term_x','Ix',1,NULL,'rendered')")
        conn.execute(
            "INSERT INTO term_mentions (term_id,cz_form,chapter_idx,scene_idx,source) "
            "VALUES ('term_x','Ix',1,NULL,'detected')")
    out = main._rendered_terms_for_chapter(db, 1)
    assert out == [{"term_id": "term_x", "cz_as_used": "Ix", "scene_idx": None}]
```

(pouze `source == "rendered"` zápisy se vrací - `detected` se filtruje,
stejně jako dnešní inline kód v `_polish_one_chapter`.)

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_cli.py -k rendered_terms_for_chapter -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_rendered_terms_for_chapter'`

- [ ] **Step 3: Implementuj - extrahuj z `_polish_one_chapter`**

Přidej novou funkci PŘED `_polish_one_chapter` v `main.py`:

```python
def _rendered_terms_for_chapter(db: str, idx: int) -> list:
    """Translatorem HLÁŠENÉ (ne jen detekované) formy termínů pro danou
    kapitolu - vstup pro `concordance.build_mentions`/`check_chapter`,
    sdíleno `_polish_one_chapter` (dávka) i editor "Uložit" endpointem
    (Task 9, kapitola bez živého draftu potřebuje stejnou hodnotu)."""
    prior = state.chapter_mentions(db, idx)
    return [{"term_id": m["term_id"], "cz_as_used": m["cz_form"],
            "scene_idx": m["scene_idx"]}
           for m in prior
           if m.get("cz_form") and m.get("source") == "rendered"]
```

V `_polish_one_chapter` nahraď (řádky 593-597):

```python
    prior = state.chapter_mentions(db, idx)
    rendered_terms = [{"term_id": m["term_id"], "cz_as_used": m["cz_form"],
                       "scene_idx": m["scene_idx"]}
                      for m in prior
                      if m.get("cz_form") and m.get("source") == "rendered"]
```

za:

```python
    rendered_terms = _rendered_terms_for_chapter(db, idx)
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py -k "rendered_terms_for_chapter or polish" -v`
Expected: PASS - starý `_polish_one_chapter` test chování beze změny
(refaktor, ne nová logika).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "refactor: extrahuj _rendered_terms_for_chapter ze _polish_one_chapter

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `main.py` - `_commit_polish_result` + dávkový auto-apply

**Files:**
- Modify: `main.py:1095-1270` (`_cmd_polish`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `findings_mod.assign_ids` (Task 2), `_rendered_terms_for_chapter`
  (Task 4), `state.commit_chapter_result`, `polish_store.load_history`/
  `save_history`/`utc_now_z`, `concordance.build_mentions`,
  `main._backup_db_once`.
- Produces:
  - `_commit_polish_result(db: str, history_path: str, idx: int, *, en: str,
    cz_before: str, final_text: str, findings: list, rendered_terms: list,
    glossary_rows: list, revision_rounds: int, source: str,
    styled_by_codex: str, backup_state: dict) -> None` - VOLÁ SE i z Tasku 9
    (editor save endpoint), signatura je tím pádem PEVNÁ pro obě volající
    strany.
  - `_polish_preflight() -> tuple` - `(model, codex_cmd, None)` nebo
    `(None, None, chybová_hláška)`.

**Proč `final_text`, ne `styled` jako název parametru:** funkce se volá i
z ručního uložení editoru, kde text nemusí pocházet z Codexu vůbec (ruční
úprava bez "Znovu polish") - neutrální jméno.

- [ ] **Step 1: Napiš test na `_commit_polish_result`**

```python
def test_commit_polish_result_writes_db_and_history(tmp_path):
    db = _db(tmp_path, chapters=1)   # existující fixture z tests/test_cli.py,
                                      # kapitola idx=1, status='done', translated_text='Original.'
    history_path = str(tmp_path / "polish.history.json")
    backup_state = {"done": False, "snapshot_path": str(tmp_path / "snap.db")}
    main._commit_polish_result(
        db, history_path, 1, en="EN text.", cz_before="Original.",
        final_text="Vylepšeno.", findings=[{"id": "f1", "resolved": False,
                                            "source": "concordance", "type": "omission"}],
        rendered_terms=[], glossary_rows=[], revision_rounds=0,
        source="polish-batch", styled_by_codex="Vylepšeno.",
        backup_state=backup_state)

    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Vylepšeno."
    assert row["status"] == "done"
    saved_notes = json.loads(row["notes"])
    assert saved_notes[0]["id"] == "f1"

    history = polish_store.load_history(history_path)
    assert len(history["entries"]) == 1
    entry = history["entries"][0]
    assert entry["idx"] == 1
    assert entry["cz_before"] == "Original."
    assert entry["cz_after"] == "Vylepšeno."
    assert entry["styled_by_codex"] == "Vylepšeno."
    assert entry["source"] == "polish-batch"
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_cli.py -k commit_polish_result -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_commit_polish_result'`

- [ ] **Step 3: Implementuj `_commit_polish_result`**

Přidej PŘED `_cmd_polish` v `main.py`:

```python
def _commit_polish_result(db: str, history_path: str, idx: int, *, en: str,
                          cz_before: str, final_text: str, findings: list,
                          rendered_terms: list, glossary_rows: list,
                          revision_rounds: int, source: str,
                          styled_by_codex: str, backup_state: dict) -> None:
    """Sdílený zápis "text se STÁVÁ finálním" - volá dávkový `_cmd_polish`
    (`source="polish-batch"`) i editor "Uložit" endpoint (`polish_server.py`
    Task 9, `source="polish-review"`). JEDNO místo pro DB commit +
    historii, ať obě cesty zůstanou navždy v souladu (stejný vzor jako
    dnešní `POST /api/polish/apply`, jen extrahovaný a sdílený)."""
    mentions = concordance.build_mentions(en, final_text, glossary_rows, rendered_terms)
    _backup_db_once(db, backup_state)
    row_before = state.get_chapter(db, idx)
    title = row_before["title"] if row_before else f"Chapter {idx}"
    state.commit_chapter_result(
        db, idx, translated_text=final_text, revision_rounds=revision_rounds,
        notes_json=json.dumps(findings, ensure_ascii=False), status="done",
        new_candidates=[], mentions=mentions, questions=[])
    history = polish_store.load_history(history_path)
    history["entries"].append({
        "idx": idx, "applied_at": polish_store.utc_now_z(),
        "cz_before": cz_before, "cz_after": final_text,
        "styled_by_codex": styled_by_codex, "title": title,
        "findings": findings, "rendered_terms": rendered_terms,
        "source": source, "draft_id": uuid.uuid4().hex})
    polish_store.save_history(history_path, history)
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py -k commit_polish_result -v`
Expected: PASS

- [ ] **Step 5: Napiš test na `_polish_preflight`**

```python
def test_polish_preflight_rejects_fs_risk_not_accepted(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    model, codex_cmd, err = main._polish_preflight()
    assert model is None and codex_cmd is None
    assert "STYLIST_ACCEPT_FS_RISK" in err


def test_polish_preflight_rejects_empty_model(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "")
    model, codex_cmd, err = main._polish_preflight()
    assert model is None
    assert "CODEX_MODEL" in err


def test_polish_preflight_ok(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "gpt-5.6-terra")
    monkeypatch.setattr(stylist, "_resolve_codex_cmd", lambda base: ["codex"])
    model, codex_cmd, err = main._polish_preflight()
    assert model == "gpt-5.6-terra"
    assert codex_cmd == ["codex"]
    assert err is None
```

- [ ] **Step 6: Ověř selhání**

Run: `pytest tests/test_cli.py -k polish_preflight -v`
Expected: FAIL

- [ ] **Step 7: Implementuj `_polish_preflight` + přepiš `_cmd_polish`**

Přidej PŘED `_commit_polish_result`:

```python
def _polish_preflight() -> tuple:
    """Bezpečnostní + config kontroly sdílené `_cmd_polish` (dávka) a
    `POST /api/polish/regenerate` (server, Task 10) - OBĚ cesty volají
    Codex, obě musí projít STEJNOU bránou. Vrací `(model, codex_cmd, None)`
    při úspěchu, `(None, None, chybová_hláška)` při selhání."""
    if config.STYLIST_ACCEPT_FS_RISK is not True:
        return None, None, (
            "polish je vypnutý: spouští agentní `codex exec`, který má "
            "ČTECÍ přístup k CELÉMU disku (ověřeno). Prompt injection z "
            "textu knihy tak MŮŽE exfiltrovat citlivý soubor jako součást "
            "stylizovaného textu, dřív než guardraily proběhnou.\n"
            "Chceš-li to i tak spustit, nastav v config.py "
            "`STYLIST_ACCEPT_FS_RISK = True`.")
    model = (config.CODEX_MODEL or "").strip()
    if not model:
        return None, None, ("Chybí config.CODEX_MODEL - nastav ho (audit "
                            "stylizace musí vědět, jaký model se skutečně použil).")
    try:
        codex_cmd = stylist._resolve_codex_cmd(["codex"])
    except stylist.StylistError as e:
        return None, None, f"Codex CLI není použitelné: {e}"
    return model, codex_cmd, None
```

V `_cmd_polish` nahraď preflight blok (řádky 1095-1133 - bezpečnostní
kontrola + `CODEX_MODEL` kontrola + draft preflight) za:

```python
def _cmd_polish(args) -> int:
    db = config.DB_PATH
    model, codex_cmd, preflight_err = _polish_preflight()
    if preflight_err:
        _say(preflight_err)
        return 1
```

(`polish.draft.json` preflight KONČÍ - žádná fronta, co by blokovala
další běh, viz spec sekce "Architektura".)

Teď uprav samotnou smyčku - nahraď draft-akumulační `finally` větev
(řádky 1194-1228, konkrétně blok `if "outcome" not in rec:`) za přímý
zápis:

```python
                if "outcome" not in rec:
                    # Codex navrhl jinou stylizaci - ROVNOU zapiš jako
                    # finální text (spec "Architektura" - žádná čekající
                    # fronta). `en`/`cz` musí přijít ze STEJNÉHO `c`
                    # objektu, ne z čerstvého DB čtení - `c["translated_text"]`
                    # je přesně to, z čeho `_polish_one_chapter` vycházela.
                    findings_final = rec["findings"]
                    try:
                        _commit_polish_result(
                            db, config.POLISH_HISTORY_PATH, c["idx"],
                            en=c["raw_text"], cz_before=c["translated_text"],
                            final_text=rec["styled"], findings=findings_final,
                            rendered_terms=rec["rendered_terms"],
                            glossary_rows=glossary_rows,
                            revision_rounds=rec["revision_rounds"],
                            source="polish-batch", styled_by_codex=rec["styled"],
                            backup_state=backup_state)
                    except Exception as e:
                        report.append({"idx": rec["idx"], "outcome": "fatal",
                                       "error": stylist._redact_detail(
                                           f"{type(e).__name__}: {e}")})
                        raise FatalRunError(
                            f"Zápis výsledku selhal ({stylist._redact_detail(f'{type(e).__name__}: {e}')}) "
                            "- infrastrukturní chyba, celý běh `polish` se "
                            "zastavuje.") from e
                    _say(f"Kapitola {c['idx']}: stylizováno a zapsáno "
                         f"({len(findings_final)} nálezů).")
                    full = config.STYLIST_REPORT_REJECTED_TEXT is True
                    report_rec = {"idx": rec["idx"], "outcome": "applied",
                                 "reason_types": rec["reason_types"]}
                    if full:
                        report_rec["findings"] = rec["findings"]
                        report_rec["styled"] = rec["styled"]
                    rec = report_rec
```

`backup_state` musí existovat PŘED smyčkou - přidej hned po
`rid = state.create_run(db, "polish")`:

```python
        backup_state = {"done": False,
                        "snapshot_path": db + ".pre-polish-snapshot"}
```

A na konci `_cmd_polish` (po `batch_completed = True`, PŘED `tally = ...`)
smaž nepromovaný snapshot stejným best-effort vzorem jako jinde v
projektu (`Grep "backup_state\[.done.\]" main.py src/review_ui/polish_server.py`
pro přesný existující vzor, zopakuj ho tady):

```python
        if not backup_state["done"]:
            try:
                os.remove(backup_state["snapshot_path"])
            except OSError:
                pass
```

Nakonec smaž `draft_chapters = []` proměnnou a VŠECHNY odkazy na
`polish_store.save_draft`/`config.POLISH_DRAFT_PATH` uvnitř `_cmd_polish`
(cely blok "Zápis je INKREMENTÁLNÍ" z předchozí verze) a nahraď
`_say(f"Navrženo k review: ...")` (řádek 1234) za:

```python
        _say(f"Stylizováno a zapsáno: {tally['applied']}, beze změny: "
             f"{tally['unchanged']}, selhalo: {tally['failed']}")
```

- [ ] **Step 8: Přepiš testy `_cmd_polish` end-to-end**

Existující testy v `tests/test_cli.py`, co ověřují `polish.draft.json`
obsah po `_cmd_polish` (`Grep "POLISH_DRAFT_PATH\|polish.draft" tests/test_cli.py`),
se PŘEPISUJÍ na ověření přímého DB zápisu:

```python
def test_cmd_polish_writes_directly_to_db(tmp_path, monkeypatch):
    # ... existující fixture setup (fake codex_cmd skript, co vrací jiný text) ...
    main._cmd_polish(_Args(only=None, force=False))
    row = state.get_chapter(db, 1)
    assert row["translated_text"] != "Original."   # skutečně přepsáno
    history = polish_store.load_history(config.POLISH_HISTORY_PATH)
    assert history["entries"][0]["source"] == "polish-batch"
    assert not os.path.exists(config.POLISH_DRAFT_PATH)   # draft soubor nevzniká
```

- [ ] **Step 9: Ověř**

Run: `pytest tests/test_cli.py -k polish -v`
Expected: PASS. Projdi VŠECHNY testy v `test_cli.py`, co zmiňují
`polish.draft.json`/`"drafted"`/`_polish_one_chapter` návratovou hodnotu
bez `outcome` klíče - musí buď projít beze změny (test `_polish_one_chapter`
samotné - ta funkce se nemění), nebo být přepsané podle Step 8 vzoru.

- [ ] **Step 10: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: polish auto-apply - žádná čekající fronta, rovnou zapiš

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: `main.py` - `export_book()` extrakce

**Files:**
- Modify: `main.py:1066-1093` (`_cmd_export`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `export_book(db_path: str, only_done: bool) -> tuple[str, list]`
  - vrací `(cesta_k_souboru, seznam_vynechaných_idx)`.

- [ ] **Step 1: Napiš test**

```python
def test_export_book_writes_done_chapters(tmp_path, monkeypatch):
    db = _db(tmp_path, chapters=1)   # status='done'
    monkeypatch.setattr(config, "OUTPUT_TXT", str(tmp_path / "out.txt"))
    path, skipped = main.export_book(db, only_done=False)
    assert path == str(tmp_path / "out.txt")
    assert skipped == []
    assert "K1" in open(path, encoding="utf-8").read()


def test_export_book_skips_non_done_without_only_done_flag_marks_missing(tmp_path, monkeypatch):
    db = _db(tmp_path, chapters=1)
    state.set_status(db, 1, "pending")
    monkeypatch.setattr(config, "OUTPUT_TXT", str(tmp_path / "out.txt"))
    path, skipped = main.export_book(db, only_done=False)
    assert skipped == [1]
    assert "CHYBÍ KAPITOLA 1" in open(path, encoding="utf-8").read()
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_cli.py -k export_book -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute 'export_book'`

- [ ] **Step 3: Implementuj - extrahuj z `_cmd_export`**

Přečti aktuální `_cmd_export` (main.py:1066-1093) před úpravou. Nahraď
CELOU funkci za:

```python
def export_book(db_path: str, only_done: bool) -> tuple:
    """Čistá funkce (žádný I/O na argparse `args`, žádný `print`) - sdíleno
    CLI `_cmd_export` a novým `POST /api/export` (Task 12, tlačítko v UI).
    Vrací `(cesta_k_výslednému_souboru, seznam_vynechaných_idx)`."""
    chapters = state.chapters_by_status(
        db_path, ("pending", "processing", "done", "flagged", "needs_human", "error"))
    out_lines, skipped = [], []
    for ch in chapters:
        idx, st = ch["idx"], ch["status"]
        if st == "done":
            out_lines.append(f"\n\n{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged" and not only_done:
            out_lines.append(
                f"\n\n[!! REVIDOVAT: {_finding_summary(ch['notes'])}]\n"
                f"{ch['title']}\n\n{ch['translated_text'] or ''}")
        elif st == "flagged":
            skipped.append(idx)
        else:
            skipped.append(idx)
            if not only_done:
                out_lines.append(f"\n\n[!! CHYBÍ KAPITOLA {idx} - stav {st}]")
    os.makedirs(os.path.dirname(config.OUTPUT_TXT) or ".", exist_ok=True)
    with open(config.OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines).strip() + "\n")
    return config.OUTPUT_TXT, skipped


def _cmd_export(args) -> int:
    path, skipped = export_book(config.DB_PATH, args.only_done)
    print(f"Export: {path}")
    if skipped:
        print("Vynechané kapitoly: " + ", ".join(str(i) for i in skipped))
    return 0
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py -k export -v`
Expected: PASS (existující `_cmd_export` testy i nové `export_book` testy)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "refactor: extrahuj export_book() z _cmd_export pro znovupoužití v UI

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: `src/findings_report.py` - agregovaný report nálezů

**Files:**
- Create: `src/findings_report.py`
- Test: `tests/test_findings_report.py`

**Interfaces:**
- Consumes: `state.chapters_by_status`, `state.get_chapter`,
  `polish_store.load_history`, `polish_store.find_latest`,
  `findings.is_marker`, `main._parse_findings`.
- Produces:
  - `build_findings_report(db_path: str, history_path: str) -> list[dict]`
    - `[{"idx": int, "title": str, "findings": list[dict]}, ...]` seřazeno
    podle `idx`, obsahuje jen NE-markerové nálezy (`findings.is_marker`
    filtr), kapitoly bez žádných nálezů se VYNECHÁVAJÍ ze seznamu.
  - `render_findings_html(report: list[dict]) -> str` - kompletní HTML
    stránka (žádné interaktivní prvky, jen text - k vytištění).
  - `render_findings_txt(report: list[dict]) -> str` - prostý text.

- [ ] **Step 1: Napiš test**

```python
# tests/test_findings_report.py
import json
from src import findings_report, polish_store, state


def _db_with_notes(tmp_path, notes):
    db = str(tmp_path / "s.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute(
            "INSERT INTO chapters (idx,title,raw_text,translated_text,status,"
            "revision_rounds,notes) VALUES (1,'K1','EN','CZ','done',0,?)",
            (json.dumps(notes, ensure_ascii=False),))
    return db


def test_build_findings_report_includes_notes_findings(tmp_path):
    db = _db_with_notes(tmp_path, [
        {"id": "f1", "resolved": False, "source": "concordance",
         "type": "omission", "issue": "chybí termín"}])
    history_path = str(tmp_path / "polish.history.json")
    report = findings_report.build_findings_report(db, history_path)
    assert report == [{"idx": 1, "title": "K1",
                       "findings": [{"id": "f1", "resolved": False,
                                    "source": "concordance", "type": "omission",
                                    "issue": "chybí termín"}]}]


def test_build_findings_report_excludes_markers(tmp_path):
    db = _db_with_notes(tmp_path, [
        {"id": "m1", "resolved": False, "source": "stylist", "type": "polish",
         "issue": "stylizováno..."}])
    history_path = str(tmp_path / "polish.history.json")
    report = findings_report.build_findings_report(db, history_path)
    assert report == []   # jediný nález byl marker, kapitola se vynechá


def test_build_findings_report_merges_history_findings(tmp_path):
    db = _db_with_notes(tmp_path, [])
    history_path = str(tmp_path / "polish.history.json")
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "a", "cz_after": "b", "styled_by_codex": "b",
            "title": "K1", "findings": [{"id": "h1", "resolved": False,
                                        "source": "critic", "type": "fidelity",
                                        "issue": "posun smyslu"}],
            "rendered_terms": [], "source": "polish-batch", "draft_id": "d1"}]})
    report = findings_report.build_findings_report(db, history_path)
    assert report[0]["findings"][0]["id"] == "h1"


def test_render_findings_html_contains_chapter_and_issue():
    report = [{"idx": 1, "title": "K1",
              "findings": [{"id": "f1", "resolved": False, "severity": "minor",
                           "issue": "chybí termín"}]}]
    html = findings_report.render_findings_html(report)
    assert "K1" in html and "chybí termín" in html


def test_render_findings_txt_contains_chapter_and_issue():
    report = [{"idx": 1, "title": "K1",
              "findings": [{"id": "f1", "resolved": True, "severity": "minor",
                           "issue": "vyřešeno"}]}]
    txt = findings_report.render_findings_txt(report)
    assert "K1" in txt and "vyřešeno" in txt
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_findings_report.py -v`
Expected: FAIL - `ModuleNotFoundError`

- [ ] **Step 3: Implementuj**

```python
# src/findings_report.py
"""Agregovaný report nálezů napříč VŠEMI kapitolami - spojuje `run` fáze
nálezy (`chapters.notes`) s posledním `polish` během (`polish.history.json`).
Dva výstupy ze STEJNÉHO `build_findings_report`: HTML k vytištění a prostý
txt vedle exportu knihy. Viz spec 2026-09-14, sekce "Report nálezů"."""
import html as _html

from src import findings, polish_store, state


def build_findings_report(db_path: str, history_path: str) -> list:
    from main import _parse_findings   # lazy - main importuje spoustu modulů, ne naopak
    chapters = state.chapters_by_status(
        db_path, ("pending", "processing", "done", "flagged", "needs_human", "error"))
    history = polish_store.load_history(history_path)
    out = []
    for ch in sorted(chapters, key=lambda c: c["idx"]):
        notes_findings = [f for f in _parse_findings(ch["notes"])
                          if not findings.is_marker(f)]
        latest = polish_store.find_latest(history["entries"], ch["idx"])
        history_findings = ([f for f in latest["findings"] if not findings.is_marker(f)]
                            if latest else [])
        combined = notes_findings + history_findings
        if combined:
            out.append({"idx": ch["idx"], "title": ch["title"], "findings": combined})
    return out


def render_findings_html(report: list) -> str:
    parts = ["<!DOCTYPE html><html lang=\"cs\"><head><meta charset=\"utf-8\">"
            "<title>Report nálezů</title><style>"
            "body{font-family:system-ui,sans-serif;margin:2rem;color:#1a1a1a}"
            "h2{border-bottom:1px solid #ccc;padding-bottom:.3rem}"
            "li{margin-bottom:.4rem}.resolved{color:#888;text-decoration:line-through}"
            "</style></head><body><h1>Report nálezů</h1>"]
    if not report:
        parts.append("<p>Žádné nálezy.</p>")
    for ch in report:
        parts.append(f"<h2>#{_html.escape(str(ch['idx']))} - "
                     f"{_html.escape(ch['title'])}</h2><ul>")
        for f in ch["findings"]:
            cls = " class=\"resolved\"" if f.get("resolved") else ""
            sev = _html.escape(f.get("severity") or "?")
            issue = _html.escape(f.get("issue") or "(bez popisu)")
            parts.append(f"<li{cls}>[{sev}] {issue}</li>")
        parts.append("</ul>")
    parts.append("</body></html>")
    return "".join(parts)


def render_findings_txt(report: list) -> str:
    lines = ["REPORT NÁLEZŮ", ""]
    if not report:
        lines.append("Žádné nálezy.")
    for ch in report:
        lines.append(f"# {ch['idx']} - {ch['title']}")
        for f in ch["findings"]:
            mark = "[VYŘEŠENO] " if f.get("resolved") else ""
            lines.append(f"  {mark}[{f.get('severity') or '?'}] "
                         f"{f.get('issue') or '(bez popisu)'}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_findings_report.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/findings_report.py tests/test_findings_report.py
git commit -m "feat: agregovaný report nálezů (HTML + txt)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: `polish_server.py` - `GET /api/chapters` + `GET /api/chapter/{idx}`

**Files:**
- Modify: `src/review_ui/polish_server.py`
- Test: `tests/test_polish_server.py`

**Interfaces:**
- Consumes: `findings.count_unresolved`/`is_marker`/`assign_ids`,
  `main._parse_findings`, `polish_store.find_latest`/`find_chain_start`,
  `_annotate_history` (existující funkce, beze změny).
- Produces:
  - `GET /api/chapters` → `{"chapters": [{"idx", "title", "status",
    "unresolved_findings", "updated_at"}, ...]}` seřazeno podle `idx`.
  - `GET /api/chapter/{idx}` → `{"idx", "title", "raw_text",
    "translated_text", "status", "findings" (notes + latest history,
    ne-markerové, s id/resolved), "cz_before_original" (str|null),
    "styled_by_codex_latest" (str|null), "history" (pole záznamů PRO
    TUHLE kapitolu, přes `_annotate_history`)}` nebo 404, když kapitola
    neexistuje.

Tenhle task JEN PŘIDÁVÁ endpointy - staré `GET /api/polish` zůstává
zatím nedotčené (odstraňuje se až Task 13, spolu s frontendem).

- [ ] **Step 1: Napiš test**

```python
def test_get_chapters_lists_all_with_unresolved_count(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=2)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    body = client.get("/api/chapters").json()
    by_idx = {c["idx"]: c for c in body["chapters"]}
    assert by_idx[1]["unresolved_findings"] == 1
    assert by_idx[2]["unresolved_findings"] == 0


def test_get_chapter_detail_returns_current_text_and_findings(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    body = client.get("/api/chapter/1").json()
    assert body["idx"] == 1
    assert body["translated_text"] == "Věta 1."
    assert body["cz_before_original"] is None    # žádná historie zatím
    assert body["styled_by_codex_latest"] is None


def test_get_chapter_detail_404_for_missing_chapter(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.get("/api/chapter/99")
    assert r.status_code == 404


def test_get_chapter_detail_includes_history_baselines(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "Věta 1.", "cz_after": "Lepší věta.",
            "styled_by_codex": "Lepší věta.", "title": "K1", "findings": [],
            "rendered_terms": [], "source": "polish-batch", "draft_id": "d1"}]})
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text=? WHERE idx=1",
                     ("Lepší věta.",))
    client = TestClient(app)
    body = client.get("/api/chapter/1").json()
    assert body["cz_before_original"] == "Věta 1."
    assert body["styled_by_codex_latest"] == "Lepší věta."
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_polish_server.py -k "get_chapters or get_chapter_detail" -v`
Expected: FAIL - 404 na neexistující route (`GET /api/chapters` vrátí 404
FastAPI defaultem).

- [ ] **Step 3: Implementuj**

V `build_app` (za `GET /api/polish`, PŘED `POST /api/polish/apply`),
přidej:

```python
    @app.get("/api/chapters")
    def get_chapters():
        import main
        rows = state.chapters_by_status(
            db_path, ("pending", "processing", "done", "flagged",
                     "needs_human", "error"))
        out = []
        for row in sorted(rows, key=lambda r: r["idx"]):
            notes_findings = main._parse_findings(row["notes"])
            out.append({"idx": row["idx"], "title": row["title"],
                       "status": row["status"],
                       "unresolved_findings": findings.count_unresolved(notes_findings),
                       "updated_at": row["updated_at"]})
        return {"chapters": out}

    @app.get("/api/chapter/{idx}")
    def get_chapter_detail(idx: int):
        import main
        row = state.get_chapter(db_path, idx)
        if row is None:
            return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
        history, err = _try_load_history(history_path)
        if err:
            return err
        entries = history["entries"]
        latest = polish_store.find_latest(entries, idx)
        chain_start = polish_store.find_chain_start(entries, idx)
        notes_findings = [f for f in main._parse_findings(row["notes"])
                          if not findings.is_marker(f)]
        history_findings = ([f for f in latest["findings"] if not findings.is_marker(f)]
                            if latest else [])
        own_history = [e for e in entries if e["idx"] == idx]
        return {
            "idx": row["idx"], "title": row["title"], "raw_text": row["raw_text"],
            "translated_text": row["translated_text"], "status": row["status"],
            "findings": notes_findings + history_findings,
            "cz_before_original": chain_start["cz_before"] if chain_start else None,
            "styled_by_codex_latest": (latest["styled_by_codex"]
                                       if latest and latest["styled_by_codex"] else None),
            "history": _annotate_history(db_path, entries, own_history),
        }
```

Přidej import nahoru: `from src import findings` (vedle existujícího
`from src import concordance, glossary, polish_store, state`).

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_polish_server.py -k "get_chapters or get_chapter_detail" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/polish_server.py tests/test_polish_server.py
git commit -m "feat: GET /api/chapters + GET /api/chapter/{idx} (nezávislé na draftu)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: `polish_server.py` - `POST /api/chapter/{idx}/save`

**Files:**
- Modify: `src/review_ui/polish_server.py`
- Test: `tests/test_polish_server.py`

**Interfaces:**
- Consumes: `main._commit_polish_result` (Task 5), `main._rendered_terms_for_chapter`
  (Task 4), `findings.assign_ids`, `glossary.all_terms`.
- Produces: `POST /api/chapter/{idx}/save` - payload
  `{"cz_before": str, "text": str, "findings": list[dict],
  "styled_by_codex": str (volitelné, default "")}` → `{"ok": true}` nebo
  `{"ok": true, "noop": true}` (text == cz_before, nic se nezapsalo), nebo
  409 (CAS neshoda), 400 (špatný tvar), 503 (zámek ztracen).

Tohle NAHRAZUJE `POST /api/polish/apply` (starý endpoint zůstává zatím
funkční, odstraňuje se až Task 13 - obě cesty mohou dočasně koexistovat).

- [ ] **Step 1: Napiš test**

```python
def test_save_chapter_commits_and_writes_history(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Lepší věta 1.",
        "findings": [{"id": "f1", "resolved": False, "source": "critic",
                     "type": "fidelity", "issue": "x"}]})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Lepší věta 1."
    history = polish_store.load_history(history_path)
    assert history["entries"][0]["source"] == "polish-review"
    assert history["entries"][0]["cz_before"] == "Věta 1."


def test_save_chapter_noop_when_text_unchanged(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.", "findings": []})
    assert r.json() == {"ok": True, "noop": True}
    history = polish_store.load_history(history_path)
    assert history["entries"] == []   # žádný zbytečný záznam


def test_save_chapter_409_on_cas_mismatch(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Něco jiného.", "text": "X", "findings": []})
    assert r.status_code == 409


def test_save_chapter_400_on_bad_shape(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={"cz_before": "Věta 1."})   # chybí text
    assert r.status_code == 400
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_polish_server.py -k save_chapter -v`
Expected: FAIL - 404 (route neexistuje)

- [ ] **Step 3: Implementuj**

Za nový `GET /api/chapter/{idx}` (Task 8), přidej:

```python
    @app.post("/api/chapter/{idx}/save")
    def post_save_chapter(idx: int, payload: dict):
        cz_before = payload.get("cz_before")
        text = payload.get("text")
        raw_findings = payload.get("findings")
        styled_by_codex = payload.get("styled_by_codex", "")
        if (not isinstance(cz_before, str) or not isinstance(text, str)
                or not isinstance(raw_findings, list)
                or not isinstance(styled_by_codex, str)):
            return JSONResponse(
                {"error": "cz_before/text/styled_by_codex musí být string, "
                          "findings musí být pole"}, status_code=400)

        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            row = state.get_chapter(db_path, idx)
            if row is None or row["translated_text"] != cz_before or row["status"] != "done":
                return JSONResponse(
                    {"error": "kapitola se mezitím změnila mimo tenhle editor - "
                              "načti stránku znovu"}, status_code=409)
            if text == cz_before:
                return {"ok": True, "noop": True}

            import main
            en = row["raw_text"]
            glossary_rows = glossary.all_terms(db_path)
            rendered_terms = main._rendered_terms_for_chapter(db_path, idx)
            resolved_findings = findings.assign_ids(list(raw_findings))
            try:
                main._commit_polish_result(
                    db_path, history_path, idx, en=en, cz_before=cz_before,
                    final_text=text, findings=resolved_findings,
                    rendered_terms=rendered_terms, glossary_rows=glossary_rows,
                    revision_rounds=row["revision_rounds"], source="polish-review",
                    styled_by_codex=styled_by_codex, backup_state=app.state.backup_state)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text NEBYL uložen ({type(e).__name__}: {e}) - "
                              "zkus to znovu."}, status_code=500)
        return {"ok": True}
```

(zálohu vytváří `_commit_polish_result` samo, přes svoje vlastní
`_backup_db_once` volání uvnitř - žádné druhé volání tady netřeba.)

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_polish_server.py -k save_chapter -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/polish_server.py tests/test_polish_server.py
git commit -m "feat: POST /api/chapter/{idx}/save - uložení bez živého draftu

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: `polish_server.py` - `POST /api/polish/regenerate`

**Files:**
- Modify: `src/review_ui/polish_server.py`
- Test: `tests/test_polish_server.py`

**Interfaces:**
- Consumes: `main._polish_one_chapter`, `main._polish_preflight` (Task 5),
  `main._rendered_terms_for_chapter` (Task 4), `state.create_run`/`finish_run`,
  `main._client_factory`.
- Produces: `POST /api/polish/regenerate` - payload `{"idx": int}` →
  `{"styled": str, "findings": list[dict], "reason_types": list[str]}` -
  NIC nezapisuje do DB/historie. 404 pro neexistující kapitolu, 400 pro
  `status != "done"`, 503 pro preflight selhání (chybějící Codex CLI apod.).

**Poznámka k zámku:** tenhle endpoint NEZAPISUJE nic (DB, JSON soubory) -
NEPOTŘEBUJE `write_lock`/`require_lock()`. Volá Codex (drahé, pomalé), ale
souběžné volání pro RŮZNÉ kapitoly nemá důvod čekat na sebe navzájem.

- [ ] **Step 1: Napiš test**

```python
def test_regenerate_returns_styled_text_without_writing(tmp_path, monkeypatch):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._polish_one_chapter",
                        lambda c, gr, cf, db_, model, codex_cmd: {
                            "idx": 1, "title": "K1", "cz_before": "Věta 1.",
                            "styled": "Vylepšená věta 1.", "revision_rounds": 0,
                            "reason_types": [], "findings": [], "rendered_terms": [],
                            "draft_id": "d1"})
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 200
    assert r.json()["styled"] == "Vylepšená věta 1."
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Věta 1."   # NEZMĚNĚNO


def test_regenerate_404_for_missing_chapter(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 99})
    assert r.status_code == 404


def test_regenerate_400_for_non_done_chapter(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='flagged' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 400


def test_regenerate_503_on_preflight_failure(tmp_path, monkeypatch):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("main._polish_preflight",
                        lambda: (None, None, "Codex CLI není použitelné"))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_polish_server.py -k regenerate -v`
Expected: FAIL - 404 (route neexistuje)

- [ ] **Step 3: Implementuj**

```python
    @app.post("/api/polish/regenerate")
    def post_regenerate(payload: dict):
        idx_raw = payload.get("idx")
        if type(idx_raw) is not int:
            return JSONResponse({"error": "idx musí být int"}, status_code=400)
        idx = idx_raw
        import main
        row = state.get_chapter(db_path, idx)
        if row is None:
            return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
        if row["status"] != "done":
            return JSONResponse(
                {"error": f"kapitola má status {row['status']!r}, ne 'done'"},
                status_code=400)
        model, codex_cmd, preflight_err = main._polish_preflight()
        if preflight_err:
            return JSONResponse({"error": preflight_err}, status_code=503)

        glossary_rows = glossary.all_terms(db_path)
        rid = state.create_run(db_path, "polish")
        cf = main._client_factory(rid, interactive=True)
        status = "fatal"
        try:
            c = {"idx": row["idx"], "title": row["title"], "raw_text": row["raw_text"],
                "translated_text": row["translated_text"],
                "revision_rounds": row["revision_rounds"]}
            rec = main._polish_one_chapter(c, glossary_rows, cf, db_path, model, codex_cmd)
            status = "ok"
        except Exception as e:
            return JSONResponse(
                {"error": f"Regenerace selhala ({type(e).__name__}: {e})"},
                status_code=500)
        finally:
            state.finish_run(db_path, rid, status)
        if "outcome" in rec:
            return JSONResponse(
                {"error": f"Codex nenavrhl žádnou úpravu ({rec.get('outcome')})"
                          if rec.get("outcome") == "unchanged"
                          else f"Stylizace selhala ({rec.get('error')})"},
                status_code=422)
        return {"styled": rec["styled"], "findings": rec["findings"],
                "reason_types": rec["reason_types"]}
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_polish_server.py -k regenerate -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/polish_server.py tests/test_polish_server.py
git commit -m "feat: POST /api/polish/regenerate - znovu-polish jedné kapitoly bez zápisu

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: `polish_server.py` - `POST /api/findings/resolve`

**Files:**
- Modify: `src/review_ui/polish_server.py`
- Test: `tests/test_polish_server.py`

**Interfaces:**
- Consumes: `findings.set_resolved` (Task 2), `main._parse_findings`,
  `polish_store.load_history`/`save_history`/`find_latest`.
- Produces: `POST /api/findings/resolve` - payload
  `{"scope": "notes"|"history", "idx": int, "finding_id": str,
  "resolved": bool}` → `{"ok": true}` nebo 404 (nenalezeno) / 400 (špatný
  tvar) / 503 (zámek ztracen).

- [ ] **Step 1: Napiš test**

```python
def test_resolve_finding_in_notes(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "notes", "idx": 1, "finding_id": "f1", "resolved": True})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    assert json.loads(row["notes"])[0]["resolved"] is True


def test_resolve_finding_in_history(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "a", "cz_after": "b", "styled_by_codex": "b",
            "title": "K1", "findings": [{"id": "h1", "resolved": False,
                                        "source": "critic", "type": "fidelity"}],
            "rendered_terms": [], "source": "polish-batch", "draft_id": "d1"}]})
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "history", "idx": 1, "finding_id": "h1", "resolved": True})
    assert r.status_code == 200
    history = polish_store.load_history(history_path)
    assert history["entries"][0]["findings"][0]["resolved"] is True


def test_resolve_finding_404_when_not_found(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "notes", "idx": 1, "finding_id": "nope", "resolved": True})
    assert r.status_code == 404


def test_resolve_finding_400_bad_scope(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "bogus", "idx": 1, "finding_id": "x", "resolved": True})
    assert r.status_code == 400
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_polish_server.py -k resolve_finding -v`
Expected: FAIL

- [ ] **Step 3: Implementuj**

```python
    @app.post("/api/findings/resolve")
    def post_resolve_finding(payload: dict):
        scope = payload.get("scope")
        idx_raw = payload.get("idx")
        finding_id = payload.get("finding_id")
        resolved = payload.get("resolved")
        if (scope not in ("notes", "history") or type(idx_raw) is not int
                or not isinstance(finding_id, str) or not isinstance(resolved, bool)):
            return JSONResponse(
                {"error": "scope musí být notes/history, idx int, finding_id "
                          "string, resolved bool"}, status_code=400)
        idx = idx_raw

        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            import main
            if scope == "notes":
                row = state.get_chapter(db_path, idx)
                if row is None:
                    return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
                notes_findings = main._parse_findings(row["notes"])
                if not findings.set_resolved(notes_findings, finding_id, resolved):
                    return JSONResponse({"error": "nález nenalezen"}, status_code=404)
                import json as _json
                with state.connect(db_path) as conn:
                    conn.execute("UPDATE chapters SET notes=? WHERE idx=?",
                                (_json.dumps(notes_findings, ensure_ascii=False), idx))
            else:
                history, err = _try_load_history(history_path)
                if err:
                    return err
                latest = polish_store.find_latest(history["entries"], idx)
                if latest is None or not findings.set_resolved(
                        latest["findings"], finding_id, resolved):
                    return JSONResponse({"error": "nález nenalezen"}, status_code=404)
                try:
                    polish_store.save_history(history_path, history)
                except Exception as e:
                    return JSONResponse(
                        {"error": f"Zápis historie selhal ({type(e).__name__}: {e})"},
                        status_code=500)
        return {"ok": True}
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_polish_server.py -k resolve_finding -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/polish_server.py tests/test_polish_server.py
git commit -m "feat: POST /api/findings/resolve - ruční zaškrtnutí vyřešeného nálezu

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 12: `polish_server.py` - `GET /findings` + `POST /api/export`

**Files:**
- Modify: `src/review_ui/polish_server.py`
- Test: `tests/test_polish_server.py`

**Interfaces:**
- Consumes: `findings_report.build_findings_report`/`render_findings_html`/
  `render_findings_txt` (Task 7), `main.export_book` (Task 6).
- Produces:
  - `GET /findings` → HTML stránka (Content-Type `text/html`).
  - `POST /api/export` → `{}` (žádný payload) → `{"book_path": str,
    "findings_path": str, "skipped": list[int]}`.

- [ ] **Step 1: Napiš test**

```python
def test_get_findings_page_renders_html(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity",
                                  "issue": "posun smyslu"}]),))
    client = TestClient(app)
    r = client.get("/findings")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "posun smyslu" in r.text


def test_post_export_writes_book_and_findings_files(tmp_path, monkeypatch):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("config.OUTPUT_TXT", str(tmp_path / "out.txt"))
    client = TestClient(app)
    r = client.post("/api/export", json={})
    assert r.status_code == 200
    body = r.json()
    assert os.path.exists(body["book_path"])
    assert os.path.exists(body["findings_path"])
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_polish_server.py -k "get_findings_page or post_export" -v`
Expected: FAIL - 404 (routy neexistují)

- [ ] **Step 3: Implementuj**

Přidej import nahoru: `from src import findings_report` (vedle
`from src import findings, concordance, glossary, polish_store, state`).

```python
    @app.get("/findings")
    def get_findings_page():
        from fastapi.responses import HTMLResponse
        report = findings_report.build_findings_report(db_path, history_path)
        return HTMLResponse(findings_report.render_findings_html(report))

    @app.post("/api/export")
    def post_export(payload: dict = None):
        import main
        book_path, skipped = main.export_book(db_path, only_done=False)
        report = findings_report.build_findings_report(db_path, history_path)
        findings_path = os.path.splitext(book_path)[0] + ".findings.txt"
        with open(findings_path, "w", encoding="utf-8") as f:
            f.write(findings_report.render_findings_txt(report))
        return {"book_path": book_path, "findings_path": findings_path,
               "skipped": skipped}
```

(`payload: dict = None` - FastAPI přijme prázdné tělo requestu; export
nic z requestu nečte, jen spouští export nad AKTUÁLNÍM stavem DB.)

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_polish_server.py -k "get_findings_page or post_export" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/polish_server.py tests/test_polish_server.py
git commit -m "feat: GET /findings stránka + POST /api/export (kniha + report)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 13: Odstraň draft-frontu (server) + zjednoduš revert + aktualizuj volající

**Files:**
- Modify: `src/review_ui/polish_server.py` (odstraň `GET /api/polish`,
  `POST /api/polish/apply`, `POST /api/polish/discard`, zjednoduš
  `POST /api/polish/revert`, uprav `build_app`/`run_polish_review_server`
  signaturu - odeber `draft_path`)
- Modify: `main.py:924-943` (`_cmd_polish_review` - nová signatura volání)
- Modify: `src/polish_store.py` (odstraň draft-specifické funkce/konstanty)
- Test: `tests/test_polish_server.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `build_app(db_path: str, history_path: str, lock_path: str) -> FastAPI`
  (BEZ `draft_path` parametru). `run_polish_review_server(db_path: str,
  history_path: str, lock_path: str, *, host=..., port=...) -> int`
  (stejně).

**Přečti PŘED úpravou:** `src/review_ui/polish_server.py` celý (jak je po
Taskách 8-12), `src/polish_store.py` celý (aktuální stav z Tasku 2 dál
beze změny), `main.py:924-943`.

- [ ] **Step 1: Uprav existující testy na novou signaturu `build_app`**

`tests/test_polish_server.py`'s `_app()` helper (řádek 39-49) volá
`polish_server.build_app(db, draft_path, history_path, lock_path)` a
VRACÍ `(app, db, draft_path, history_path, lock_path)` - přepiš na
`polish_server.build_app(db, history_path, lock_path)`, návratová
hodnota `(app, db, history_path, lock_path)` (BEZ `draft_path`). Odeber
`_draft`/`_chapter_draft` helpery a VŠECHNY testy, co používají
`draft_chapters=`/`_chapter_draft` (byly to testy draft-fronty - `GET
/api/polish` s draft obsahem, `POST /api/polish/apply`, `POST
/api/polish/discard`).

**DŮLEŽITÉ - testy z Tasků 8-12 se MUSÍ upravit taky**, ne jen zůstat
beze změny: v době, kdy vznikaly (Tasky 8-12), `_app()` ještě vracela
5-tici a JEJICH kód správně psal
`app, db, draft_path, history_path, lock_path = _app(...)`. Teď, když
`_app()` vrací 4-tici, by tenhle rozbalovací vzor spadl na
`ValueError: not enough values to unpack`. V CELÉM `tests/test_polish_server.py`
nahraď (`replace_all`, přes VŠECHNY testy, ne jen draft-specifické):

```
app, db, draft_path, history_path, lock_path = _app(
```

za:

```
app, db, history_path, lock_path = _app(
```

Po nahrazení zkontroluj `Grep "draft_path" tests/test_polish_server.py`
- jediné zbývající výskyty smí být uvnitř textu, co se právě MAŽE (Step
výš, draft-specifické testy) - pokud grep najde `draft_path` v testu z
Tasku 8-12, po smazání draft-specifických testů tam nesmí zůstat nic.

Konkrétní nová podoba `_app()` helperu (nahraď celou existující funkci):

```python
def _app(tmp_path, chapters=1):
    db = _db(tmp_path, chapters)
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    state.acquire_lock(lock_path)
    app = polish_server.build_app(db, history_path, lock_path)
    _LIVE_APPS.append(app)
    return app, db, history_path, lock_path
```

- [ ] **Step 2: Ověř, že smazané testy opravdu mizí, ne jen failují**

Run: `Grep "draft_path\|_chapter_draft\|POLISH_DRAFT" tests/test_polish_server.py`
Expected: žádný výskyt (kromě případně komentáře vysvětlujícího, proč
draft koncept skončil - to je v pořádku).

- [ ] **Step 3: Implementuj - `polish_server.py`**

Odstraň:
- `_stale_info` funkci (byla draft-specifická).
- `_try_load_draft` funkci.
- `GET /api/polish` endpoint.
- `POST /api/polish/apply` endpoint.
- `POST /api/polish/discard` endpoint.
- `polish_store.load_draft(draft_path)`/`save_draft` preflight volání v
  `build_app`.

V `POST /api/polish/revert`, odstraň draft-pending guard blok:

```python
            draft, err = _try_load_draft(draft_path)
            if err:
                return err
            if any(c["idx"] == idx for c in draft["chapters"]):
                return JSONResponse(
                    {"error": "kapitola má nevyřízený draft z novějšího `polish` "
                              "běhu - nejdřív ho vyřeš (ulož nebo zahoď), pak zkus "
                              "revert znovu"}, status_code=409)
```

(žádná náhrada - draft fronta neexistuje, revert nemá co blokovat.)

Uprav `build_app` signaturu:

```python
def build_app(db_path: str, history_path: str, lock_path: str) -> FastAPI:
```

a odstraň `polish_store.load_draft(draft_path)` z preflight bloku (ponech
`polish_store.load_history(history_path)`).

Uprav `run_polish_review_server` signaturu:

```python
def run_polish_review_server(db_path: str, history_path: str,
                             lock_path: str, *, host: str = "127.0.0.1",
                             port: int = 8766) -> int:
```

a jeho tělo (volání `build_app(db_path, draft_path, history_path, lock_path)`
→ `build_app(db_path, history_path, lock_path)`).

Uprav `@app.get("/")` handler - vrací teď NOVOU landing page (chapter
list), viz Task 14:

```python
    @app.get("/")
    def index():
        return FileResponse(os.path.join(_STATIC, "chapters.html"))

    @app.get("/editor")
    def editor_page():
        return FileResponse(os.path.join(_STATIC, "editor.html"))
```

- [ ] **Step 4: Implementuj - `main.py:924-943`**

```python
def _cmd_polish_review(args) -> int:
    from src.review_ui import polish_server
    try:
        return polish_server.run_polish_review_server(
            config.DB_PATH, config.POLISH_HISTORY_PATH, config.LOCK_PATH)
    except (polish_store.PolishStoreError, OSError, TimeoutError) as e:
        _say(f"polish-review se nepodařilo spustit ({type(e).__name__}: {e}) - "
             f"zkontroluj {config.POLISH_HISTORY_PATH} a DB ({config.DB_PATH}), "
             "případně poškozený soubor oprav nebo smaž.")
        return 1
```

- [ ] **Step 5: Implementuj - `src/polish_store.py` úklid**

Odstraň (mrtvý kód, draft fronta skončila): `DRAFT_SCHEMA_VERSION`,
`_DRAFT_CHAPTER_FIELDS`, `_validate_draft_payload`, `load_draft`,
`save_draft`, `is_draft_pending`. PONECH: `PolishStoreError`,
`HISTORY_SCHEMA_VERSION`, `_HISTORY_ENTRY_FIELDS`, `utc_now_z`, `_is_utc_z`,
`parse_z`, `_atomic_write_json`, `_validate_record`, `_validate_str_list`,
`_validate_dict_list`, `_is_exact_schema_version`, `_validate_history_payload`,
`load_history`, `save_history`, `find_latest`, `find_chain_start`,
`resolve_revert_target` (VŠECHNO history-related zůstává, revert i
editor baseline logika na tom stojí).

`Grep "load_draft\|save_draft\|is_draft_pending\|_DRAFT_CHAPTER_FIELDS\|DRAFT_SCHEMA_VERSION\|_validate_draft_payload" src/ main.py tests/`
PŘED smazáním - potvrď, že po Krocích 1-4 tohohle Tasku už žádné volající
místo nezůstalo. Pokud grep něco najde mimo `tests/test_polish_store.py`
(viz Step 6), dořeš to tady.

- [ ] **Step 6: Uprav `tests/test_polish_store.py`**

`Grep "load_draft\|save_draft\|is_draft_pending\|DRAFT_SCHEMA" tests/test_polish_store.py`
- smaž VŠECHNY testy, co testují jen odstraněné draft funkce. Testy na
`load_history`/`save_history`/`find_latest`/`find_chain_start`/
`resolve_revert_target`/`_atomic_write_json` zůstávají beze změny.

- [ ] **Step 7: `Grep "POLISH_DRAFT_PATH"` napříč projektem**

`Grep "POLISH_DRAFT_PATH" main.py config.py src/ tests/` - `config.
POLISH_DRAFT_PATH` konstanta samotná může v `config.py` zůstat (mrtvá,
neškodná, dokumentuje historii - NEBO ji smaž, pokud nikde jinde není
odkazovaná po tomhle Tasku; zkontroluj a rozhodni podle výsledku gripu).
Žádné volající místo (`main.py`/`polish_server.py`) už `POLISH_DRAFT_PATH`
nesmí používat.

- [ ] **Step 8: Ověř celou sadu**

Run: `pytest tests/test_polish_server.py tests/test_polish_store.py tests/test_cli.py -v`
Expected: PASS, 0 chyb, žádný test neodkazuje na draft frontu.

- [ ] **Step 9: Commit**

```bash
git add src/review_ui/polish_server.py src/polish_store.py main.py \
       tests/test_polish_server.py tests/test_polish_store.py tests/test_cli.py
git commit -m "refactor: odstraň draft-frontu ze serveru - editor pracuje přímo nad DB

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 14: Frontend - `chapters.html` (seznam kapitol) + `editor.html`

**Files:**
- Create: `src/review_ui/static/chapters.html`
- Create: `src/review_ui/static/editor.html`
- Modify: `src/review_ui/static/polish.html` → SMAZAT (nahrazeno oběma
  výš)
- Test: manuální (Playwright/browser testy nejsou v projektu zavedené -
  ověř přes `python main.py polish-review` + prohlížeč, viz Step 4)

**Interfaces:**
- Consumes: `GET /api/chapters`, `GET /api/chapter/{idx}`,
  `POST /api/chapter/{idx}/save`, `POST /api/polish/regenerate`,
  `POST /api/findings/resolve`, `POST /api/polish/revert` (beze změny
  kontraktu), `POST /api/export`.

**Bezpečnostní disciplína (Global Constraints):** žádný `innerHTML` s
interpolovaným textem - `createElement`+`textContent`/`addEventListener`,
stejně jako dnešní `polish.html`. Zkopíruj `el()` helper a `diffWords`/
`renderDiff` funkce z dnešního `polish.html` beze změny (Task 13 mazal
`polish.html` až po jeho obsah odsud přenesli - přečti ho PŘED smazáním,
pokud jsi to v Tasku 8-13 ještě neudělal).

- [ ] **Step 1: `chapters.html`**

```html
<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<title>Polish review - kapitoly</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 1.5rem;
        background: #f7f7f5; color: #1a1a1a; }
  h1 { font-size: 1.3rem; }
  table { width: 100%; border-collapse: collapse; font-size: .9rem; }
  td, th { padding: .4rem .6rem; border-bottom: 1px solid #eee; text-align: left; }
  .status { font-weight: 600; }
  .status-done { color: #1a6b3c; }
  .status-flagged { color: #b35c00; }
  .status-error, .status-needs_human { color: #b3261e; }
  .status-pending, .status-processing { color: #888; }
  .unresolved { font-weight: 600; }
  .unresolved.zero { color: #888; font-weight: 400; }
  button { cursor: pointer; border: 1px solid #ccc; background: #fff;
          border-radius: 4px; padding: .35rem .7rem; font-size: .85rem; }
  button.primary { background: #1a6b3c; color: #fff; border-color: #1a6b3c; }
  .toolbar { display: flex; gap: .6rem; align-items: center; margin-bottom: 1rem; }
  .msg { font-size: .85rem; margin-left: .5rem; }
  .msg.error { color: #b3261e; }
  .msg.ok { color: #1a6b3c; }
</style>
</head>
<body>
<h1>Polish review - kapitoly</h1>
<div class="toolbar">
  <button id="export-btn" class="primary">Export knihy</button>
  <a href="/findings" target="_blank">Report nálezů</a>
  <span id="toolbar-msg" class="msg"></span>
</div>
<table id="chapters-table">
  <thead><tr><th>#</th><th>Název</th><th>Status</th>
    <th>Nevyřešené nálezy</th><th>Naposled upraveno</th><th></th></tr></thead>
  <tbody id="chapters-body"></tbody>
</table>

<script>
function el(tag, opts, children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(opts || {})) {
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else e.setAttribute(k, v);
  }
  for (const c of children || []) e.appendChild(c);
  return e;
}

async function load() {
  const r = await fetch('/api/chapters');
  const body = await r.json().catch(() => ({}));
  const tbody = document.getElementById('chapters-body');
  tbody.textContent = '';
  if (!r.ok) {
    tbody.appendChild(el('tr', {}, [el('td', { colspan: '6', text: body.error || `HTTP ${r.status}` })]));
    return;
  }
  for (const ch of body.chapters) {
    const editBtn = el('button', { text: 'Editovat' });
    editBtn.addEventListener('click', () => {
      window.location.href = '/editor?idx=' + encodeURIComponent(ch.idx);
    });
    const unresolvedCls = 'unresolved' + (ch.unresolved_findings === 0 ? ' zero' : '');
    tbody.appendChild(el('tr', {}, [
      el('td', { text: String(ch.idx) }),
      el('td', { text: ch.title }),
      el('td', { class: 'status status-' + ch.status, text: ch.status }),
      el('td', { class: unresolvedCls, text: String(ch.unresolved_findings) }),
      el('td', { text: ch.updated_at || '' }),
      el('td', {}, [editBtn]),
    ]));
  }
}

document.getElementById('export-btn').addEventListener('click', async () => {
  const msg = document.getElementById('toolbar-msg');
  msg.textContent = 'Exportuji...';
  msg.className = 'msg';
  const r = await fetch('/api/export', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  const body = await r.json().catch(() => ({}));
  if (r.ok) {
    msg.textContent = `Hotovo: ${body.book_path} (+ ${body.findings_path})`;
    msg.className = 'msg ok';
  } else {
    msg.textContent = body.error || `HTTP ${r.status}`;
    msg.className = 'msg error';
  }
});

load();
</script>
</body>
</html>
```

- [ ] **Step 2: `editor.html`**

Zkopíruj `el`/`tokenizeWords`/`diffWords`/`renderDiff`/`DIFF_TOKEN_CAP`
funkce Z DNEŠNÍHO `src/review_ui/static/polish.html` (řádky 112-181)
BEZE ZMĚNY - stejná bezpečnostní/výkonová logika platí i tady.

```html
<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<title>Polish review - editor</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 1.5rem;
        background: #f7f7f5; color: #1a1a1a; }
  h1 { font-size: 1.3rem; }
  a.back { font-size: .85rem; }
  .findings { font-size: .85rem; color: #333; margin: .8rem 0; }
  .findings li { margin-bottom: .3rem; display: flex; align-items: center; gap: .4rem; }
  .findings li.resolved { color: #888; text-decoration: line-through; }
  .panes { display: flex; gap: 1rem; align-items: stretch; margin-top: 1rem; }
  .pane { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .pane h4 { margin: 0 0 .3rem; font-size: .8rem; text-transform: uppercase; color: #888; }
  .pane-content { height: 400px; box-sizing: border-box; font-family: inherit;
        font-size: .95rem; white-space: pre-wrap; padding: .5rem;
        border: 1px solid #ccc; border-radius: 4px; overflow-y: auto; }
  .pane pre.pane-content, .pane div.pane-content { background: #fafafa; margin: 0; }
  .pane textarea.pane-content { background: #fff; width: 100%; resize: horizontal; }
  .diff-box .diff-del { text-decoration: line-through; color: #b3261e; background: #fbe4e2; }
  .diff-box .diff-add { color: #1a6b3c; background: #e3f3e9; }
  .diff-too-big { color: #888; font-style: italic; margin: 0; }
  .buttons { margin-top: .8rem; display: flex; gap: .5rem; flex-wrap: wrap; }
  button { cursor: pointer; border: 1px solid #ccc; background: #fff;
          border-radius: 4px; padding: .4rem .8rem; font-size: .85rem; }
  button.primary { background: #1a6b3c; color: #fff; border-color: #1a6b3c; }
  button:disabled { opacity: .5; cursor: default; }
  .error { color: #b3261e; font-size: .85rem; margin-top: .3rem; }
  #history table { width: 100%; border-collapse: collapse; font-size: .85rem; margin-top: .5rem; }
  #history td, #history th { padding: .3rem .5rem; border-bottom: 1px solid #eee; text-align: left; }
</style>
</head>
<body>
<a class="back" href="/">&larr; Seznam kapitol</a>
<h1 id="chapter-title">Kapitola</h1>
<ul id="findings" class="findings"></ul>
<div class="panes">
  <div class="pane"><h4>Originál EN</h4><pre id="en-pane" class="pane-content"></pre></div>
  <div class="pane"><h4>Aktuální CZ</h4><pre id="cz-pane" class="pane-content"></pre></div>
  <div class="pane"><h4>Návrh (editovatelné)</h4><textarea id="text-area" class="pane-content"></textarea></div>
  <div class="pane"><h4>Rozdíl</h4><div id="diff-box" class="pane-content diff-box"></div></div>
</div>
<div class="buttons">
  <button id="btn-orig">Vrať na originál</button>
  <button id="btn-codex">Vrať na Codex</button>
  <button id="btn-regen">Znovu polish</button>
  <button id="btn-save" class="primary">Uložit</button>
</div>
<div id="err-box" class="error"></div>

<h2>Historie téhle kapitoly</h2>
<div id="history"></div>

<script>
function el(tag, opts, children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(opts || {})) {
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else e.setAttribute(k, v);
  }
  for (const c of children || []) e.appendChild(c);
  return e;
}

const DIFF_TOKEN_CAP = 6000;
function tokenizeWords(s) { return (s || '').split(/(\s+)/).filter(t => t.length > 0); }
function diffWords(before, after) {
  const a = tokenizeWords(before), b = tokenizeWords(after);
  if (a.length > DIFF_TOKEN_CAP || b.length > DIFF_TOKEN_CAP) return null;
  const n = a.length, m = b.length, w = m + 1;
  const dp = new Uint16Array((n + 1) * w);
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
    dp[i * w + j] = (a[i - 1] === b[j - 1]) ? dp[(i - 1) * w + (j - 1)] + 1
      : Math.max(dp[(i - 1) * w + j], dp[i * w + (j - 1)]);
  }
  const ops = []; let i = n, j = m;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) { ops.push({ type: 'equal', text: a[i - 1] }); i--; j--; }
    else if (dp[(i - 1) * w + j] >= dp[i * w + (j - 1)]) { ops.push({ type: 'del', text: a[i - 1] }); i--; }
    else { ops.push({ type: 'add', text: b[j - 1] }); j--; }
  }
  while (i > 0) ops.push({ type: 'del', text: a[--i] });
  while (j > 0) ops.push({ type: 'add', text: b[--j] });
  ops.reverse();
  return ops;
}
function renderDiff(container, before, after) {
  container.textContent = '';
  const ops = diffWords(before, after);
  if (ops === null) {
    container.appendChild(el('p', { class: 'diff-too-big',
      text: 'Náhled rozdílu je pro tak dlouhý text vypnutý.' }));
    return;
  }
  for (const op of ops) {
    if (op.type === 'equal') container.appendChild(document.createTextNode(op.text));
    else container.appendChild(el('span', { class: op.type === 'del' ? 'diff-del' : 'diff-add', text: op.text }));
  }
}

const IDX = Number(new URLSearchParams(window.location.search).get('idx'));
let CH = null;             // poslední GET /api/chapter/{idx} odpověď
let CURRENT_FINDINGS = [];  // findings zobrazené TEĎ (může pocházet z regenerate)
let CURRENT_STYLED_BY_CODEX = '';   // co poslat jako styled_by_codex při Uložit

function renderFindings() {
  const root = document.getElementById('findings');
  root.textContent = '';
  for (const f of CURRENT_FINDINGS) {
    const cb = el('input', { type: 'checkbox' });
    cb.checked = !!f.resolved;
    cb.addEventListener('change', () => toggleResolved(f, cb.checked));
    const li = el('li', { class: f.resolved ? 'resolved' : '' }, [cb,
      document.createTextNode(`[${f.severity || '?'}] ${f.issue || '(bez popisu)'}`)]);
    root.appendChild(li);
  }
}

async function toggleResolved(finding, resolved) {
  finding.resolved = resolved;
  renderFindings();
  // Nález může pocházet z `notes` (run fáze) NEBO z posledního `polish`
  // historie záznamu - server neví, odkud UI nález vzalo, tak to zkusí
  // OBĚ scope (druhý pokus je no-op, když první uspěl - server najde
  // nález podle `id`, ne podle scope samotného jako zdroje pravdy).
  for (const scope of ['notes', 'history']) {
    const r = await fetch('/api/findings/resolve', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope, idx: IDX, finding_id: finding.id, resolved }),
    });
    if (r.ok) return;
  }
}

async function loadChapter() {
  const r = await fetch('/api/chapter/' + encodeURIComponent(IDX));
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    document.getElementById('err-box').textContent = body.error || `HTTP ${r.status}`;
    return;
  }
  CH = body;
  CURRENT_FINDINGS = body.findings;
  CURRENT_STYLED_BY_CODEX = body.styled_by_codex_latest || '';
  document.getElementById('chapter-title').textContent = `#${body.idx} - ${body.title}`;
  document.getElementById('en-pane').textContent = body.raw_text != null ? body.raw_text : '(originál nedostupný)';
  document.getElementById('cz-pane').textContent = body.translated_text;
  document.getElementById('text-area').value = body.translated_text;
  document.getElementById('btn-orig').disabled = body.cz_before_original === null;
  document.getElementById('btn-codex').disabled = body.styled_by_codex_latest === null;
  renderFindings();
  refreshDiff();
  renderHistory(body.history);
}

function refreshDiff() {
  renderDiff(document.getElementById('diff-box'), CH.translated_text,
             document.getElementById('text-area').value);
}
let diffTimer = null;
document.getElementById('text-area').addEventListener('input', () => {
  clearTimeout(diffTimer);
  diffTimer = setTimeout(refreshDiff, 180);
});

document.getElementById('btn-orig').addEventListener('click', () => {
  document.getElementById('text-area').value = CH.cz_before_original;
  refreshDiff();
});
document.getElementById('btn-codex').addEventListener('click', () => {
  document.getElementById('text-area').value = CH.styled_by_codex_latest;
  refreshDiff();
});

document.getElementById('btn-regen').addEventListener('click', async () => {
  const btn = document.getElementById('btn-regen');
  const errBox = document.getElementById('err-box');
  btn.disabled = true;
  errBox.textContent = '';
  const r = await fetch('/api/polish/regenerate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idx: IDX }),
  });
  btn.disabled = false;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) { errBox.textContent = body.error || `HTTP ${r.status}`; return; }
  document.getElementById('text-area').value = body.styled;
  CURRENT_FINDINGS = body.findings;
  CURRENT_STYLED_BY_CODEX = body.styled;
  renderFindings();
  refreshDiff();
});

document.getElementById('btn-save').addEventListener('click', async () => {
  const errBox = document.getElementById('err-box');
  const r = await fetch('/api/chapter/' + encodeURIComponent(IDX) + '/save', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      cz_before: CH.translated_text,
      text: document.getElementById('text-area').value,
      findings: CURRENT_FINDINGS,
      styled_by_codex: CURRENT_STYLED_BY_CODEX,
    }),
  });
  if (r.ok) { loadChapter(); return; }
  const body = await r.json().catch(() => ({}));
  errBox.textContent = body.error || `HTTP ${r.status}`;
});

async function revertChapter(idx, to) {
  const r = await fetch('/api/polish/revert', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idx, to }),
  });
  if (r.ok) { loadChapter(); return; }
  const body = await r.json().catch(() => ({}));
  alert(body.error || `HTTP ${r.status}`);
}

function renderHistory(entries) {
  const root = document.getElementById('history');
  root.textContent = '';
  if (!entries.length) {
    root.appendChild(el('p', { text: 'Zatím žádná historie.' }));
    return;
  }
  const table = el('table');
  table.appendChild(el('tr', {}, [el('th', { text: 'Kdy' }), el('th', { text: 'Zdroj' }), el('th', {})]));
  for (const e of entries) {
    const btnCell = el('td');
    if (e.can_revert_previous) {
      const b = el('button', { text: 'Vrať zpět' });
      b.addEventListener('click', () => revertChapter(e.idx, 'previous'));
      btnCell.appendChild(b);
    }
    if (e.can_revert_original) {
      const b = el('button', { text: 'Vrať na původní' });
      b.addEventListener('click', () => revertChapter(e.idx, 'original'));
      btnCell.appendChild(b);
    }
    table.appendChild(el('tr', {}, [el('td', { text: e.applied_at }), el('td', { text: e.source }), btnCell]));
  }
  root.appendChild(table);
}

loadChapter();
</script>
</body>
</html>
```

- [ ] **Step 3: Smaž starý `polish.html`**

```bash
git rm src/review_ui/static/polish.html
```

- [ ] **Step 4: Manuální ověření v prohlížeči**

Spusť `python main.py polish-review`, otevři `http://127.0.0.1:8766/`:
1. Seznam kapitol se zobrazí (idx, title, status, nevyřešené nálezy).
2. Klikni "Editovat" na kapitole s historií (po Tasku 5 dávka `polish`
   nad testovací DB) - editor ukáže 4 panely, diff funguje při psaní.
3. "Vrať na originál"/"Vrať na Codex" přepíší textarea, diff se
   přepočítá.
4. "Znovu polish" (vyžaduje `STYLIST_ACCEPT_FS_RISK=True` a funkční
   Codex CLI) vrátí nový návrh do pole, nálezy se aktualizují.
5. Zaškrtnutí nálezu se projeví (přeškrtnutý text), přežije reload
   stránky.
6. "Uložit" zapíše, přesměruje/refreshne na nový stav, historie dole
   ukáže nový řádek.
7. Zpět na seznam kapitol - "Export knihy" vytvoří oba soubory, cesty se
   zobrazí.
8. `/findings` stránka (v novém tabu z odkazu) ukáže agregovaný seznam.

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/static/chapters.html src/review_ui/static/editor.html
git rm src/review_ui/static/polish.html
git commit -m "feat: nový frontend - seznam kapitol + editor bez draftu

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 15: Úklid - zbývající odkazy na starý workflow

**Files:**
- Modify: `tests/test_cli.py`, `tests/test_polish_server.py` (dosled)
- Modify: `docs/superpowers/specs/2026-09-11-polish-review-design.md`
  (poznámka na začátek, že je NAHRAZEN novým dokumentem - ne smazat,
  historická hodnota)

**Interfaces:** žádné nové - čistě úklidový task.

- [ ] **Step 1: Vyhledej zbývající odkazy na draft koncept**

```bash
grep -rn "polish\.draft\|POLISH_DRAFT\|_kept_original_marker\|kept_original" \
  main.py src/ tests/ --include="*.py"
```

Projdi výsledky:
- `_kept_original_marker` (main.py) - byla PŮVODNĚ jen pro apply
  no-op idempotenci vázanou na `draft_id`. V novém modelu "beze změny"
  case řeší `POST /api/chapter/{idx}/save`'s `if text == cz_before:
  return {"ok": True, "noop": True}` (Task 9) BEZ zápisu markeru vůbec -
  žádný zápis znamená žádná potřeba idempotenčního markeru. Pokud grep
  najde `_kept_original_marker` jen jako definici bez volajícího místa,
  smaž funkci i její testy (`Grep "_kept_original_marker" main.py
  tests/test_cli.py` pro přesná místa).
- Zbylé `"polish.draft"` zmínky mimo `docs/superpowers/specs/2026-09-11-*.md`
  (ten dokument NEmaž, je historický záznam) - oprav/smaž podle kontextu.

- [ ] **Step 2: Přidej poznámku na začátek starého spec dokumentu**

Na začátek `docs/superpowers/specs/2026-09-11-polish-review-design.md`
(hned pod nadpis, před "## Kontext a cíl") přidej:

```markdown
> **Nahrazeno** `docs/superpowers/specs/2026-09-14-batch-polish-reader-workflow-design.md`
> (2026-09-14) - draft fronta popsaná tímhle dokumentem byla odstraněna,
> `polish` teď zapisuje rovnou. Zámkový/CAS/atomický-zápis aparát popsaný
> níž ZŮSTÁVÁ v platnosti beze změny, jen se přestal používat pro
> draft-specifické endpointy (`apply`/`discard`/draft preflight).
```

- [ ] **Step 3: Spusť celou testovací sadu**

Run: `pytest -v`
Expected: PASS, 0 failures, 0 errors. Zkontroluj počet testů proti stavu
před Task 1 (méně testů je OK - smazali jsme draft-specifické - ale
žádný by neměl SPADNOUT, jen zmizet nebo projít).

- [ ] **Step 4: Manuální smoke test celého toku**

```bash
python main.py polish --only 1 2 3 --force
python main.py polish-review
```

Otevři prohlížeč, projdi kroky ze Step 4 Tasku 14 ještě jednou nad
reálnými daty (víc než jedna kapitola najednou v seznamu).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: úklid zbytků draft-fronty, poznámka do starého spec dokumentu

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
