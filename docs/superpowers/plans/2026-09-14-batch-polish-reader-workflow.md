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
  nový endpoint, co píše do `chapters`/historie, tenhle vzor neobchází.
  **Výjimka (kolo 10 IMPORTANT, zúženo přesně):** endpoint, co píše
  VÝHRADNĚ auditní bookkeeping (`runs`/`llm_calls` přes `state.create_run`/
  `finish_run`) a NIKDY `chapters`/historii, `write_lock` nepotřebuje
  (žádné dvě takové zápisy na RŮZNÝCH kapitolách si nepřekáží) - MUSÍ ale
  pořád ověřit `app.state.require_lock()` bezprostředně PŘED KAŽDÝM
  takovým zápisem (ne jen jednou na začátku) - viz `POST /api/polish/
  regenerate` (Task 10) jako jediný dnešní příklad týhle výjimky.
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

import config as config_module


def test_project_dir_defaults_to_dot(monkeypatch):
    """`importlib.reload` mutuje `config` V MÍSTĚ - je to sdílený
    singleton, co importují i JINÉ testovací soubory. `monkeypatch.undo()`
    + druhý `reload` v `finally` VRACÍ modul do stavu před testem, jinak
    by tenhle test natrvalo poškodil `config.PROJECT_DIR`/`DATA_DIR`/...
    pro zbytek testovací session (samotný `monkeypatch` vrátí jen env
    proměnnou, ne důsledek reloadu, co už na ní stihl postavit)."""
    monkeypatch.delenv("BOOK_TRANSLATOR_PROJECT_DIR", raising=False)
    importlib.reload(config_module)
    try:
        assert config_module.PROJECT_DIR == "."
        assert config_module.DATA_DIR == os.path.join(".", "data")
        assert config_module.OUTPUT_DIR == os.path.join(".", "output")
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)


def test_project_dir_reads_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("BOOK_TRANSLATOR_PROJECT_DIR", str(tmp_path))
    importlib.reload(config_module)
    try:
        assert config_module.PROJECT_DIR == str(tmp_path)
        assert config_module.DATA_DIR == os.path.join(str(tmp_path), "data")
        assert config_module.DB_PATH == os.path.join(str(tmp_path), "data", "state.sqlite3")
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)
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
    (`_stylist_marker`/`_kept_original_marker`/`_revert_marker`/
    `_unchanged_marker` z `main.py`), `False` pro skutečné nálezy
    (concordance/kritik/strukturální).
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


def test_assign_ids_coerces_non_str_issue_to_str():
    """Kolo 5 IMPORTANT - `critic._to_finding` čte `issue` přímo z LLM
    JSON bez typové kontroly; bez tyhle normalizace by uživatel po GET+
    save cyklu NEMOHL uložit vůbec nic na kapitole s takovým nálezem
    (`_valid_finding_shape` by 400 odmítlo `issue: 123`)."""
    fs = [{"source": "critic", "type": "fidelity", "issue": 123, "severity": None}]
    findings.assign_ids(fs)
    assert fs[0]["issue"] == "123" and isinstance(fs[0]["issue"], str)
    assert fs[0]["severity"] is None   # None zůstává None, nekonvertuje se na "None"


def test_assign_ids_replaces_explicit_null_id():
    """Kolo 3 IMPORTANT - klient (Task 9 save) může poslat `id: null`
    (validace to propouští) - `setdefault` by to nechalo být, protože
    klíč UŽ existuje. Musí se to poznat stejně jako chybějící klíč."""
    fs = [{"source": "concordance", "type": "omission", "id": None,
           "resolved": None}]
    findings.assign_ids(fs)
    assert isinstance(fs[0]["id"], str) and fs[0]["id"]
    assert fs[0]["resolved"] is False


def test_assign_ids_gives_unique_ids_to_each_finding():
    fs = [{"issue": "a"}, {"issue": "b"}]
    findings.assign_ids(fs)
    assert fs[0]["id"] != fs[1]["id"]


def test_assign_ids_replaces_non_string_id():
    """Kolo 23 IMPORTANT - `id: 123` (číslo, TRUTHY, ale ne `str`) by
    starým `if not f.get("id")` prošlo beze změny - GET by ho vrátilo
    klientovi, ale resolve/save by ho NAVŽDY odmítly (vyžadují `str`).
    Zdroj takových dat: pre-Task-2 `chapters.notes`, migrace (Task 13
    Step 8) je jen filtruje na ne-dict, ne na shape `id` uvnitř dict."""
    fs = [{"id": 123, "issue": "a"}]
    findings.assign_ids(fs)
    assert isinstance(fs[0]["id"], str)
    assert fs[0]["id"] != 123


def test_assign_ids_replaces_duplicate_ids_within_same_batch():
    """Kolo 23 IMPORTANT - dvě položky se STEJNÝM `id` v JEDNÉ dávce
    (možné z pre-Task-2 dat) - `set_resolved`/`_merge_findings_by_id`
    předpokládají unikátnost. Druhý výskyt dostane NOVÉ `id`, první
    zůstává beze změny (první-vyhrává, ne oba přepsané)."""
    fs = [{"id": "dup", "issue": "a"}, {"id": "dup", "issue": "b"}]
    findings.assign_ids(fs)
    assert fs[0]["id"] == "dup"
    assert fs[1]["id"] != "dup"
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
    assert findings.is_marker({"source": "stylist", "type": "unchanged"}) is True   # kolo 9 IMPORTANT


def test_is_marker_false_for_real_findings():
    assert findings.is_marker({"source": "concordance", "type": "omission"}) is False
    assert findings.is_marker({"source": "critic", "type": "fidelity"}) is False
    assert findings.is_marker({"source": "stylist_check", "type": "register_drift"}) is False


def test_is_marker_false_not_crash_for_unhashable_source():
    """Kolo 4 IMPORTANT - producent nálezu (kritik/concordance) NENÍ
    validován jako klientský save vstup; `source: []` by bez isinstance
    kontroly spadlo na TypeError v `(source, type) in _MARKER_TYPES`."""
    assert findings.is_marker({"source": [], "type": "x"}) is False


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
                 ("stylist", "revert"), ("stylist", "unchanged")}   # "unchanged"
                 # kolo 9 IMPORTANT - main._unchanged_marker (Task 5), viz tamní
                 # docstring proč musí být marker, ne obyčejný nález


_STR_FIELDS = ("source", "type", "issue", "severity", "cz_excerpt", "suggestion")


def assign_ids(findings: list) -> list:
    """Doplní `id`/`resolved` KAŽDÉMU nálezu, co je ještě nemá - nikdy
    nepřepíše existující PLATNOU (str, neprázdnou, v týhle dávce
    UNIKÁTNÍ) hodnotu (idempotentní, bezpečné volat opakovaně na stejný
    seznam). Mutuje v místě a vrací stejný seznam.

    `f.get("id")` (ne `"id" in f`/`setdefault`) - kolo 3 IMPORTANT oprava:
    klient (Task 9 save endpoint) MŮŽE poslat `{"id": null, ...}`
    (validace v `_valid_finding_shape` `None` u `id` propouští, viz
    tamní docstring). `setdefault` by tenhle PŘÍTOMNÝ, ale prázdný klíč
    nepřepsalo - nález by zůstal s `id: None` navždy, nešel by nikdy
    znovu najít podle `id` (`set_resolved` by ho nikdy nenašlo, víc
    takových nálezů by si navzájem "kolidovalo" na stejné `None`).

    Kolo 23 IMPORTANT - `id` musí být PLATNÝ, ne jen PŘÍTOMNÝ. Dřívější
    `if not f.get("id"):` nechávalo TRUTHY, ale NE-STRING `id` (např.
    `id: 123`, celé číslo) beze změny - zdroj: `_valid_entries` (Task 13
    Step 8 migrace) filtruje jen NE-DICT položky, ne SHAPE `id` uvnitř
    dict. Takový nález by GET vrátil klientovi s `id: 123`, ale `POST
    /api/findings/resolve`/`save`'s vlastní validace (`isinstance(...,
    str)`) by ho pak NAVŽDY odmítla - trvalý, neopravitelný "mrtvý"
    nález v UI. Duplicitní `id` (dvě položky se STEJNÝM, jinak platným
    `id` v JEDNÉ dávce - taky možné z pre-Task-2 dat) měly STEJNÝ
    problém jiným směrem - `set_resolved`/`_merge_findings_by_id`
    předpokládají unikátnost, ale nic ji dřív nevynucovalo. Fix -
    `seen_ids` (lokální jen pro TUHLE dávku, NE globální napříč
    voláními - uniknost se vynucuje jen v rámci JEDNOHO seznamu nálezů,
    stejný rozsah jako `_no_duplicate_ids`) sleduje, co UŽ bylo v týhle
    dávce přiděleno - `id` je platné a ZACHOVÁ SE jen když je `str`,
    neprázdné, A ještě NEVIDĚNÉ v týhle dávce; jinak dostane nové `uuid4
    ().hex`.

    NORMALIZUJE i `source`/`type`/`issue`/`severity`/`cz_excerpt`/
    `suggestion` na `str` (kolo 5 IMPORTANT - `assign_ids` je JEDINÝ
    společný choke-point, přes který projdou VŠECHNY nálezy, ať z `run`u
    (kritik/concordance), `polish`u, nebo klientského save requestu.
    `critic._to_finding` (`src/agents/critic.py:45`) čte `issue` PŘÍMO
    z LLM JSON odpovědi (`raw.get("issue") or ""`) bez kontroly typu -
    model teoreticky MŮŽE vrátit `"issue": 123` (číslo). Bez normalizace
    TADY by takový nález prošel `assign_ids`/GET/reportem v pořádku
    (display-time `str()` coerce v `render_findings_html` by ho
    ustála), ale `POST /api/chapter/{idx}/save`'s `_valid_finding_shape`
    by ho odmítlo 400 - JAKMILE by editor GET kapitolu s tímhle nálezem
    a poslal ho zpátky (i beze změny), uživatel by NEMOHL uložit VŮBEC
    NIC na tý kapitole, dokud by se nálezu nezbavil. Normalizace TADY,
    hned při vzniku, zaručuje, že klient NIKDY nedostane nález v tvaru,
    co by sám neuměl zpátky uložit."""
    seen_ids = set()
    for f in findings:
        fid = f.get("id")
        if not isinstance(fid, str) or not fid or fid in seen_ids:
            fid = uuid.uuid4().hex
            f["id"] = fid
        seen_ids.add(fid)
        if "resolved" not in f or f["resolved"] is None:
            f["resolved"] = False
        for key in _STR_FIELDS:
            if key in f and f[key] is not None and not isinstance(f[key], str):
                f[key] = str(f[key])
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
    `_revert_marker`/`_unchanged_marker`) NENÍ nález k vyřešení - je to jen záznam "kdy/jak
    se text změnil", uživatel ho nemá zaškrtávat.

    Obranné `isinstance` (kolo 4 IMPORTANT) - `source`/`type` u nálezů z
    `_run_critic`/`concordance` nejsou nikde vynuceně `str` (jen `Task 9`
    save endpoint tohle validuje pro KLIENTSKÝ vstup, ne producenty jako
    kritik). Netypovaná hodnota (např. `source: []`) by jako prvek
    tuplu byla NEHASHOVATELNÁ - `in` na množině tuplů by spadlo na
    `TypeError` místo vrácení `False`."""
    source, type_ = finding.get("source"), finding.get("type")
    if not isinstance(source, str) or not isinstance(type_, str):
        return False
    return (source, type_) in _MARKER_TYPES


def count_unresolved(findings: list) -> int:
    return sum(1 for f in findings if not is_marker(f) and not f.get("resolved"))
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_findings.py -v`
Expected: PASS (13 testů - kolo 23 přidalo 2 nové)

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

**NIT (kolo 3) - konzolové hlášky uvnitř funkce lžou o novém chování.**
`_polish_one_chapter` (main.py:628-645) pořád vypisuje "- půjde k
ručnímu review" u OBOU větví (`reasons`/beze `reasons`), i když dávka
(Task 5) teď výsledek rovnou zapisuje - žádná fronta k ručnímu review
už neexistuje. Konzole by tak vedle sebe ukázala "půjde k ručnímu
review" a hned pod tím "stylizováno a zapsáno" (Task 5's vlastní
hláška) - matoucí protimluv. Uprav OBĚ `_say` volání (main.py:628-630 a
645):

```python
    if reasons:
        _say(f"Kapitola {idx}: kontrola má výhrady ({', '.join(reason_types)}).")
```

a:

```python
    else:
        _say(f"Kapitola {idx}: návrh připraven, žádné výhrady.")
```

(jen odstraň " - půjde k ručnímu review"/"- půjde k ručnímu review" ze
konce obou řetězců, zbytek logiky pod `if full:` beze změny.)

**Kolo 5 IMPORTANT (revize kola 4 - Codex dal konkrétní reprodukci, co
moje dřívější zamítnutí vyvrací, viz plán-consensus log), kolo 6
BLOCKING oprava pořadí:** `_polish_one_chapter`'s concordance kontrola
(uvnitř funkce) a `_commit_polish_result`'s zápis (Task 5/9) NESMÍ
používat NEZÁVISLE odvozené `rendered_terms` - `_commit_polish_result`
je předává i do `concordance.build_mentions`, co PŘEPISUJE
`term_mentions` (živou DB) - když kontrola uvnitř `_polish_one_chapter`
viděla JINOU množinu, než jakou zápis PROSADÍ do DB, může se stát, že
konkordanční kontrola nahlásí jen slabý `omission/minor` tam, kde by se
STEJNÝM vstupem jako zápis správně viděla `inconsistency/critical`
(schválený tvar termínu "zapomenutý" jen v živé DB, ale STÁLE platný
podle historie - konkrétní scénář viz `_preferred_rendered_terms`
docstring). Fix: `_polish_one_chapter` dostane NOVÝ volitelný parametr,
volající (dávka Task 5, regenerace Task 10) MU HO PŘEDÁ stejnou
hodnotou, jakou pak použije i zápis - žádné dvojí, vzájemně
nekonzistentní odvozování.

**Kolo 6 BLOCKING - tahle konkrétní úprava se PROVÁDÍ AŽ v Tasku 4 Step
3, NE tady** - `_rendered_terms_for_chapter` (funkce, co tenhle fallback
volá) ještě NEEXISTUJE, dokud Task 4 neproběhne (teprve Task 4 EXTRAHUJE
dnešní inline kód do týhle funkce). Kdyby se signatura/tělo měnily už
tady v Tasku 3, implementátor by odkazoval na funkci, co v tomhle bodě
plánu ještě nikde není definovaná. Task 4 Step 3 (níž v plánu) obsahuje
KOMPLETNÍ, ve správném pořadí zařazenou verzi téhle úpravy - žádná akce
tady v Tasku 3 Step 2 není potřeba.

(beze změny volajících v Tasku 3 Step 6/Task 4 testech - `rendered_
terms=None`/vynechaný parametr = STEJNÉ chování jako dřív, žádný
existující test se nerozbije. Volající, co CHTĚJÍ konzistenci se
zápisem (Task 5, Task 10), parametr EXPLICITNĚ předají - viz tamní
úpravy.)

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

**NIT, ale BLOKUJE Krok 9 níž (ověření testů):** `_cmd_polish`'s finální
`_say(f"Navrženo k review: {tally['drafted']}, ...")` (main.py:1234)
dělá dict lookup `tally['drafted']` - `tally` se počítá jako `{k: ... for
k in _REPORT_OUTCOMES}` (main.py:1232-1233), a `_REPORT_OUTCOMES` už po
Kroku 3 klíč `'drafted'` NEMÁ. Bez opravy TADY by `tally['drafted']`
vyhodilo `KeyError` při KAŽDÉM běhu `_cmd_polish`, co dorazí až k tyhle
hlášce - Krok 9 by na existujícím end-to-end testu `_cmd_polish` spadl
dřív, než se k němu vůbec dostane Task 5. Over `_say` řádek PROTO uprav
UŽ TADY (Task 5 ho pak stejně dál přepíše na finální znění, ale
mezikrok nesmí být rozbitý):

```python
        _say(f"Navrženo k review: {tally['applied']}, beze změny: "
             f"{tally['unchanged']}, selhalo: {tally['failed']}")
```

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
    db = _polish_db(tmp_path)   # main.py:666 fixture - idx=1, status='done'
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

za (kolo 5/6 - fallback JEN když volající nic nepředal, viz `_polish_
one_chapter`'s nová hlavička níž):

```python
    if rendered_terms is None:
        rendered_terms = _rendered_terms_for_chapter(db, idx)
```

**A ZÁROVEŇ** (stejný Step, jedna souvislá úprava `_polish_one_chapter`
- kolo 6 BLOCKING oprava pořadí, tahle část byla dřív mylně umístěná v
Tasku 3, kde `_rendered_terms_for_chapter` ještě neexistovala) uprav
hlavičku funkce (main.py:561-562):

```python
def _polish_one_chapter(c, glossary_rows, cf, db, model: str,
                        codex_cmd: list, rendered_terms: "list | None" = None) -> dict:
```

Přidej test na zachování EXPLICITNĚ předané hodnoty (i prázdného
seznamu `[]` - `is None` kontrola, ne truthiness, musí `[]` odlišit od
"nic nepředáno"):

```python
def test_polish_one_chapter_uses_passed_rendered_terms_not_live_db(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    passed = [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0}]
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"],
                                   rendered_terms=passed)
    assert rec["rendered_terms"] == passed   # ne živě odvozené (fixture nemá term_mentions)


def test_polish_one_chapter_uses_passed_empty_list_not_live_db(tmp_path, monkeypatch):
    """`rendered_terms=[]` MUSÍ zůstat `[]` (explicitní "žádné termíny"),
    ne spadnout na živé odvození jen proto, že je to falsy hodnota."""
    db = _polish_db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t/a','A','Á')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Á", "scene_idx": 0, "source": "rendered"}])
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", ["codex"], rendered_terms=[])
    assert rec["rendered_terms"] == []   # NE [{"term_id": "t/a", ...}] z živé DB
```

Run: `pytest tests/test_cli.py -k "polish_one_chapter_uses_passed" -v`
Expected: PASS

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py -k "rendered_terms_for_chapter or polish" -v`
Expected: PASS - starý `_polish_one_chapter` test chování beze změny
(refaktor, ne nová logika).

- [ ] **Step 5: `_preferred_rendered_terms` - historie JEN když je "v souladu"**

IMPORTANT nález kola 2: prosté "vždy přednostně historie" (jak to dřív
dělal jen Task 9) je nekonzistentní SE SAMOTNOU dávkou (Task 5 pořád
odvozovala živě) A navíc nebezpečné, když text mezitím prošel NOVÝM
`run`/`answer` (přepsal `translated_text` MIMO polish/editor workflow) -
poslední historie záznam by pak popisoval JINOU verzi textu, než jaká je
teď v DB, a jeho `rendered_terms` by k AKTUÁLNÍMU textu nemusely sedět.
Pravidlo: historie je důvěryhodná JEN když jejím `cz_after` PŘESNĚ sedí s
textem, ze kterého operace vychází (`cz_before` volajícího) - jinak žívá
DB.

```python
def _preferred_rendered_terms(db: str, idx: int, current_text: str,
                              history_entries: list) -> list:
    """Historie MÁ přednost před živou `term_mentions` (ta se PŘEPISUJE
    při každém `commit_chapter_result` na základě `concordance.build_
    mentions`, co může být UŽŠÍ množina, než co translator PŮVODNĚ
    nahlásil při `run`u - opakované úpravy by jinak postupně "zapomínaly"
    původně nahlášené tvary) - ALE JEN pokud poslední historie záznam
    popisuje PRÁVĚ `current_text` (`cz_after == current_text`). Jinak
    (žádná historie, nebo text mezitím prošel `run`/`answer` mimo
    polish/editor) je živá DB jediný platný zdroj - stará historie by
    patřila jiné verzi textu. `polish_store` už je importovaný na úrovni
    modulu (main.py's existující `from src import ..., polish_store,
    ...`), žádný nový import netřeba."""
    latest = polish_store.find_latest(history_entries, idx)
    if latest is not None and latest["cz_after"] == current_text:
        return latest["rendered_terms"]
    return _rendered_terms_for_chapter(db, idx)
```

Test:

```python
def test_preferred_rendered_terms_uses_history_when_in_sync(tmp_path):
    db = _polish_db(tmp_path)
    entries = [{"idx": 1, "cz_after": "Původní věta.",
               "rendered_terms": [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0}]}]
    out = main._preferred_rendered_terms(db, 1, "Původní věta.", entries)
    assert out == [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0}]


def test_preferred_rendered_terms_falls_back_to_live_when_history_stale(tmp_path):
    db = _polish_db(tmp_path)
    entries = [{"idx": 1, "cz_after": "Stará verze (před novým run).",
               "rendered_terms": [{"term_id": "t/stale", "cz_as_used": "X", "scene_idx": 0}]}]
    # `current_text` NESEDÍ s historií - text mezitím prošel novým `run`
    out = main._preferred_rendered_terms(db, 1, "Původní věta.", entries)
    assert out == []   # živá DB (žádné term_mentions ve fixture), NE stará historie
```

Run: `pytest tests/test_cli.py -k preferred_rendered_terms -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "refactor: extrahuj _rendered_terms_for_chapter, přidej _preferred_rendered_terms

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `main.py` - `_commit_polish_result` + dávkový auto-apply

**Files:**
- Modify: `main.py:1095-1270` (`_cmd_polish`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `findings_mod.assign_ids` (Task 2), `_preferred_rendered_terms`
  (Task 4), `state.commit_chapter_result`, `state.refresh_lock`,
  `polish_store.load_history`/`save_history`/`utc_now_z`,
  `concordance.build_mentions`, `main._backup_db_once`, `main._snapshot_db`,
  `main._stylist_marker`.
- Produces:
  - `_commit_polish_result(db: str, history_path: str, idx: int, *, en: str,
    cz_before: str, final_text: str, findings: list, glossary_rows: list,
    revision_rounds: int, source: str, model_label: str, styled_by_codex: str,
    backup_state: dict, rendered_terms: "list | None" = None) -> None` -
    VOLÁ SE i z Tasku 9 (editor save endpoint), signatura je tím pádem
    PEVNÁ pro obě volající strany. Sama připojuje `_stylist_marker` do
    ukládaných nálezů (viz "Proč marker" níž), defenzivně volá `findings_
    mod.assign_ids` na výsledný seznam PŘED zápisem. `rendered_terms` je
    VOLITELNÝ (kolo 7 NIT - tenhle popis dřív zastarale tvrdil "NENÍ
    parametr", než kolo 5 potřebu parametru znovu zavedlo kvůli
    konzistenci analýza/zápis) - `None` (Task 9 save, žádná předchozí
    `_polish_one_chapter` analýza) spustí interní výpočet přes
    `_preferred_rendered_terms`; PŘEDANÁ hodnota (dávka Task 5,
    spočítaná JEDNOU a použitá i pro `_polish_one_chapter` volání, viz
    Task 4/5) se použije BEZE ZMĚNY.
  - `_polish_preflight() -> tuple` - `(model, codex_cmd, None)` nebo
    `(None, None, chybová_hláška)`.
  - `_lock_still_owned(lock_path: str) -> bool` (kolo 13 IMPORTANT) -
    aktivně obnoví zámek (`state.refresh_lock`) a vrátí, jestli se to
    povedlo. Použito jako `require_lock` callback do `_client_factory`
    (Task 5 Step 8, CLI) i vzorem pro Task 10's server-side `_client_
    factory` volání (server má VLASTNÍ `app.state.require_lock`, tenhle
    modul jen sdílí STEJNÉ JMÉNO parametru na `_client_factory`).

**Proč `final_text`, ne `styled` jako název parametru:** funkce se volá i
z ručního uložení editoru, kde text nemusí pocházet z Codexu vůbec (ruční
úprava bez "Znovu polish") - neutrální jméno.

**Proč marker uvnitř `_commit_polish_result`, ne u volajícího (jak to
dělal dnešní `apply` endpoint):** `_already_styled` (main.py:100, řídí
`--force` chování dávky) hledá `source=="stylist"`/`type=="polish"` marker
v `chapters.notes`. Obě volající cesty (dávka i ruční uložení v editoru)
musí marker zapsat STEJNĚ, jinak `--force` sémantika přestane fungovat
pro jednu z nich (ruční úprava beze markeru = příští dávkový `polish`
by kapitolu tiše přepsal, i když ji uživatel právě ručně opravil). JEDNO
místo, co marker vždy připojí, tohle jistí napříč oběma cestami.
`model_label` je volný popisný text pro marker - dávka předá skutečný
Codex model (`model` z `_polish_preflight`), editor "Uložit" (Task 9)
předá pevný popis ruční úpravy (viz tamní volání).

**Kolo 9 IMPORTANT - `outcome == "unchanged"` marker (Step 8 níž,
NEPROCHÁZÍ `_commit_polish_result`):** Codex u kapitoly nenavrhl žádnou
úpravu (`_polish_one_chapter` vrátí `{"idx", "outcome": "unchanged"}`,
main.py:589-591, beze změny). Beze zápisu markeru zůstane `_already_
styled` `False` - PŘÍŠTÍ `polish` běh (i BEZ `--force`, i další den, i
po přidání dalších kapitol) tuhle konkrétní kapitolu znovu zahrne a
ZNOVU ZAPLATÍ Codexu za kontrolu, co už jednou dala stejnou odpověď,
dokud se text kapitoly věcně nezmění. Marker MUSÍ mít JINÝ `type` než
`_stylist_marker` (`"polish"`) - kapitola nebyla přestylizovaná, jen
zkontrolovaná, report/UI to má umět rozlišit - ale `_already_styled`
musí OBĚ hodnoty uznat jako "už řešeno, přeskoč bez `--force`". Přidej
DO main.py vedle `_stylist_marker`/`_kept_original_marker`/`_revert_
marker` (main.py:109-150):

```python
def _unchanged_marker(model: str) -> dict:
    """Kolo 9 IMPORTANT: `_polish_one_chapter` vrátí `outcome=="unchanged"`,
    když Codex nenavrhl žádnou úpravu - beze zápisu markeru by
    `_already_styled` zůstalo `False` a příští `polish` (i bez `--force`)
    by kapitolu znovu poslal (a zaplatil) Codexu, donekonečna. Vlastní
    `type` (ne `"polish"` jako `_stylist_marker`) - kapitola NENÍ
    přepsaná, jen zkontrolovaná, report/UI to musí umět rozlišit, ale
    `_already_styled` (main.py:100) obě hodnoty uznává stejně."""
    return {"source": "stylist", "type": "unchanged", "severity": "info",
            "action": "note", "term_id": None, "expected": None,
            "actual": None, "cz_excerpt": None,
            "issue": f"Codex zkontroloval (model={model}), žádná úprava "
                    "nenavržena.",
            "suggestion": None}
```

A rozšiř existující `_already_styled` (main.py:100-106) - `type == "polish"`
se stává `type in ("polish", "unchanged")`:

```python
def _already_styled(notes_json: str | None) -> bool:
    """`type` je `"polish"` (skutečně přestylizováno) NEBO `"unchanged"`
    (kolo 9 - Codex zkontroloval, nic neměnil, ale marker pořád znamená
    "už řešeno, nezkoušej znovu bez --force"). Revert marker a
    "kept_original" marker mají STEJNÝ source, ale JINÝ type, aby po
    revertu / potvrzení originálu bylo možné `polish` znovu nabídnout
    bez `--force`."""
    return any(f.get("source") == "stylist" and f.get("type") in ("polish", "unchanged")
              for f in _parse_findings(notes_json))
```

- [ ] **Step 1: Napiš test na `_commit_polish_result`**

```python
def test_commit_polish_result_writes_db_and_history(tmp_path):
    db = _polish_db(tmp_path)   # existující fixture main.py:666 - kapitola
                                 # idx=1, status='done', translated_text='Původní věta.'
    history_path = str(tmp_path / "polish.history.json")
    snapshot_path = str(tmp_path / "snap.db")
    main._snapshot_db(db, snapshot_path)   # backup_state vyžaduje HOTOVÝ snapshot
    backup_state = {"done": False, "snapshot_path": snapshot_path}
    main._commit_polish_result(
        db, history_path, 1, en="EN text.", cz_before="Původní věta.",
        final_text="Vylepšeno.", findings=[{"id": "f1", "resolved": False,
                                            "source": "concordance", "type": "omission"}],
        glossary_rows=[], revision_rounds=0,
        source="polish-batch", model_label="m", styled_by_codex="Vylepšeno.",
        backup_state=backup_state)

    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Vylepšeno."
    assert row["status"] == "done"
    saved_notes = json.loads(row["notes"])
    assert saved_notes[0]["id"] == "f1"
    assert any(f["source"] == "stylist" and f["type"] == "polish" for f in saved_notes)

    history = polish_store.load_history(history_path)
    assert len(history["entries"]) == 1
    entry = history["entries"][0]
    assert entry["idx"] == 1
    assert entry["cz_before"] == "Původní věta."
    assert entry["cz_after"] == "Vylepšeno."
    assert entry["styled_by_codex"] == "Vylepšeno."
    assert entry["source"] == "polish-batch"
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_cli.py -k commit_polish_result -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_commit_polish_result'`

- [ ] **Step 3: Rozšiř `polish_store._VALID_HISTORY_SOURCES`**

`_commit_polish_result` zapisuje historii se `source="polish-batch"`
(dávka) i `source="polish-review"` (editor) - `src/polish_store.py`'s
`_validate_history_payload` dnes přijímá JEN `("polish-review", "revert")`
(`src/polish_store.py:20`). Bez rozšíření `save_history` selže
`PolishStoreError` PO ÚSPĚŠNÉM DB commitu (DB se změní, historie ne -
nekonzistentní stav). V `src/polish_store.py` uprav:

```python
_VALID_HISTORY_SOURCES = ("polish-review", "polish-batch", "revert")
```

Přidej test do `tests/test_polish_store.py`:

```python
def test_save_history_accepts_polish_batch_source(tmp_path):
    path = str(tmp_path / "h.json")
    polish_store.save_history(path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "a", "cz_after": "b", "styled_by_codex": "b",
            "title": "K1", "findings": [], "rendered_terms": [],
            "source": "polish-batch", "draft_id": "d1"}]})
    loaded = polish_store.load_history(path)
    assert loaded["entries"][0]["source"] == "polish-batch"
```

Run: `pytest tests/test_polish_store.py -k polish_batch_source -v`
Expected: PASS

- [ ] **Step 4: Implementuj `_commit_polish_result`**

Přidej PŘED `_cmd_polish` v `main.py`:

```python
class HistoryWriteFailedAfterCommit(Exception):
    """DB commit UŽ proběhl (nevratně), tohle selhání je z JINÉ třídy
    než selhání PŘED commitem - volající to MUSÍ hlásit jinak (stejný
    princip jako `2026-09-11` spec's `apply`/`revert` "text SE uložil,
    ale historie ne" rozlišení). BLOCKING oprava kola 2 - `_commit_
    polish_result` dřív načítala/validovala historii AŽ PO DB commitu,
    takže poškozený `polish.history.json` by nechal DB už změněnou, ale
    volající by to nesprávně hlásil jako "text NEBYL uložen"."""


def _commit_polish_result(db: str, history_path: str, idx: int, *, en: str,
                          cz_before: str, final_text: str, findings: list,
                          glossary_rows: list, revision_rounds: int, source: str,
                          model_label: str, styled_by_codex: str,
                          backup_state: dict, rendered_terms: "list | None" = None) -> None:
    """Sdílený zápis "text se STÁVÁ finálním" - volá dávkový `_cmd_polish`
    (`source="polish-batch"`) i editor "Uložit" endpoint (`polish_server.py`
    Task 9, `source="polish-review"`). JEDNO místo pro DB commit +
    historii, ať obě cesty zůstanou navždy v souladu (stejný vzor jako
    dnešní `POST /api/polish/apply`, jen extrahovaný a sdílený). PŘEPISUJE
    `chapters.notes` (nenačítá/nemergeuje předchozí obsah) - stejné chování
    jako dnešní `apply` endpoint už dělá; report nálezů (Task 7/8) proto
    čte JEN `chapters.notes` jako aktuální stav, ne merge s historií (viz
    tamní poznámka o duplicitě).

    Historie se NAČTE/OVĚŘÍ JAKO PRVNÍ krok, PŘED jakýmkoli zápisem do DB
    (kolo 2 BLOCKING oprava) - poškozený `polish.history.json` tak zastaví
    CELOU operaci dřív, než se text vůbec změní. Selhání SAMOTNÉHO zápisu
    historie (`save_history` na konci, PO úspěšném DB commitu) je jiná
    třída chyby - `HistoryWriteFailedAfterCommit` výš, volající ji MUSÍ
    zachytit zvlášť.

    `rendered_terms` je VOLITELNÝ (kolo 5 IMPORTANT, revize kola 2) -
    když volající NEPŘEDÁ nic (`None`, Task 9 save endpoint - žádná
    předchozí `_polish_one_chapter` analýza, se kterou by se muselo
    shodovat), spočítá se TADY přes `_preferred_rendered_terms(db, idx,
    cz_before, history["entries"])` (Task 4). Když volající HODNOTU
    předá (dávka Task 5, `_polish_one_chapter` ji dostala STEJNOU - viz
    Task 3), použije se BEZE ZMĚNY - analýza (concordance kontrola
    uvnitř `_polish_one_chapter`) a zápis (`concordance.build_mentions`
    tady) musí vidět STEJNOU množinu, jinak může kontrola podhodnotit
    závažnost nálezu (`omission/minor` místo `inconsistency/critical`),
    protože zápis mezitím do `term_mentions` prosadí JINOU sadu, než
    jakou kontrola viděla (konkrétní reprodukce v plán-consensus logu,
    kolo 5)."""
    findings_to_store = findings_mod.assign_ids(
        list(findings) + [_stylist_marker(final_text, model_label)])
    history = polish_store.load_history(history_path)   # PŘED DB zápisem
    if rendered_terms is None:
        rendered_terms = _preferred_rendered_terms(db, idx, cz_before, history["entries"])
    mentions = concordance.build_mentions(en, final_text, glossary_rows, rendered_terms)
    _backup_db_once(db, backup_state)
    row_before = state.get_chapter(db, idx)
    title = row_before["title"] if row_before else f"Chapter {idx}"
    state.commit_chapter_result(
        db, idx, translated_text=final_text, revision_rounds=revision_rounds,
        notes_json=json.dumps(findings_to_store, ensure_ascii=False), status="done",
        new_candidates=[], mentions=mentions, questions=[])
    # DB commit VÝŠ už proběhl a je NEODVOLATELNÝ - selhání NÍŽE je JINÁ
    # třída chyby (kolo 2 BLOCKING), zabalená do `HistoryWriteFailedAfterCommit`.
    history["entries"].append({
        "idx": idx, "applied_at": polish_store.utc_now_z(),
        "cz_before": cz_before, "cz_after": final_text,
        "styled_by_codex": styled_by_codex, "title": title,
        "findings": findings_to_store, "rendered_terms": rendered_terms,
        "source": source, "draft_id": uuid.uuid4().hex})
    try:
        polish_store.save_history(history_path, history)
    except Exception as e:
        raise HistoryWriteFailedAfterCommit(str(e)) from e
```

- [ ] **Step 5: Ověř úspěch**

Run: `pytest tests/test_cli.py -k commit_polish_result -v`
Expected: PASS

- [ ] **Step 6: Napiš test na `_polish_preflight`**

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
    monkeypatch.setattr(main.stylist, "_resolve_codex_cmd", lambda base: ["codex"])
    model, codex_cmd, err = main._polish_preflight()
    assert model == "gpt-5.6-terra"
    assert codex_cmd == ["codex"]
    assert err is None
```

- [ ] **Step 7: Ověř selhání**

Run: `pytest tests/test_cli.py -k polish_preflight -v`
Expected: FAIL

- [ ] **Step 8: Implementuj `_polish_preflight` + přepiš `_cmd_polish`**

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

**Kolo 13 IMPORTANT - `cf = _client_factory(rid, interactive=True)`
(main.py:1172, beze změny až doteď) musí i pro CLI `_cmd_polish` dostat
`require_lock` callback, STEJNĚ jako server (Task 10, kolo 11/12).**
Kolo-11 zdůvodnění "CLI drží OS zámek po celou dobu běhu, `refresh_lock`
před KAŽDÝM commitem to řeší" bylo NEDOSTATEČNÉ - ten `refresh_lock`
(Step 8 kód níž) se volá TĚSNĚ PŘED zápisem `chapters`/historie, ale
`cf("critic")`/`cf("stylist_check")` (uvnitř `_polish_one_chapter`,
volané PŘED tímhle refreshem, o řádky výš) zapisují `llm_calls`
NEZÁVISLE na něm - kdyby zámek zestárl/byl převzat BĚHEM zpracování
JEDNÉ kapitoly (dlouhé LLM volání), tenhle audit zápis by proběhl BEZ
ověření, přesně scénář, co Task 10 řeší pro server. Rozdíl oproti
serveru: CLI nemá `app.state.require_lock`/heartbeat vlákno - potřebuje
EKVIVALENTNÍ callback, co navíc AKTIVNĚ OBNOVUJE zámek (ne jen kontroluje
- CLI na rozdíl od serveru žádné jiné vlákno obnovu nedělá), analogicky
k `_require_lock` v `polish_server.py:182-199`. Na rozdíl od serveru
(kde `_require_lock` je closure uvnitř `build_app`) tady MUSÍ jít o
MODULOVOU funkci, ne lokální closure uvnitř `_cmd_polish` - jinak by ji
nešlo samostatně testovat (Step 8b níž) bez toho, aby test musel spustit
celý `_cmd_polish`. Přidej DO main.py, hned za `_client_factory`
(main.py:52-58):

```python
def _lock_still_owned(lock_path: str) -> bool:
    """`require_lock`-styl helper pro CLI (`_cmd_polish`) - server má
    vlastní `_require_lock` v `polish_server.py` (plus heartbeat vlákno
    na pozadí), CLI žádné takové vlákno nemá - AKTIVNĚ obnovuje zámek
    při KAŽDÉM volání (`state.refresh_lock`, ne jen pasivní kontrola),
    ať se staleness okno vůbec neotvírá mezi dvěma po sobě jdoucími
    LLM voláními uvnitř JEDNÉ kapitoly."""
    try:
        state.refresh_lock(lock_path)
        return True
    except state.LockError:
        return False
```

Nahraď (main.py:1172):

```python
        cf = _client_factory(rid, interactive=True)
```

za:

```python
        cf = _client_factory(rid, interactive=True,
                             require_lock=lambda: _lock_still_owned(config.LOCK_PATH))
```

(`interactive=True` beze změny - CLI batch pořád smí čekat na vstup u
cost guardu, `require_lock` je NEZÁVISLÁ, nová podmínka navíc. Ztráta
zámku uprostřed LLM volání teď vyhodí `FatalRunError` ze samotného
`PipelineLLMClient.complete()` PŘED voláním - stejně jako u serveru,
propaguje skrz `_polish_one_chapter` až do `_cmd_polish`'s vlastního
`except FatalRunError as fe: raise` v hlavní smyčce, což zastaví CELOU
dávku - správné chování, ztráta zámku uprostřed běhu není bezpečné tiše
přeskočit jen tuhle kapitolu.)

- [ ] **Step 8b: Testy na `_lock_still_owned` + drátování (kolo 13 IMPORTANT)**

**Pozor na past:** `_polish_env` (Step 9 níž) `_client_factory` ÚPLNĚ
mockuje (`cf(agent)` vrací holý `object()`, žádný skutečný `PipelineLLMClient`
nevzniká) - přes tenhle mock NEJDE otestovat, že ztráta zámku BĚHEM
`PipelineLLMClient.complete()` vede k `FatalRunError` (mock žádné LLM
volání vůbec nedělá). Proto DVA samostatné testy - jeden na `_lock_still_
owned` PŘÍMO (bez `_cmd_polish`), jeden na DRÁTOVÁNÍ (že `_cmd_polish`
callback vůbec PŘEDÁ) - skutečné end-to-end chování `PipelineLLMClient`
při ztrátě zámku už pokrývají testy v `tests/test_pipeline_client.py`
(Task 10, kolo 12), tady se netestuje znovu.

```python
def test_lock_still_owned_true_when_lock_held(tmp_path):
    lock_path = str(tmp_path / ".lock")
    state.acquire_lock(lock_path)
    assert main._lock_still_owned(lock_path) is True


def test_lock_still_owned_false_when_refresh_fails(tmp_path, monkeypatch):
    lock_path = str(tmp_path / ".lock")
    monkeypatch.setattr(state, "refresh_lock",
                        lambda *a, **k: (_ for _ in ()).throw(state.LockError("ukraden")))
    assert main._lock_still_owned(lock_path) is False


def test_cmd_polish_passes_require_lock_callback_to_client_factory(tmp_path, monkeypatch):
    """Kolo 13 IMPORTANT - drátování: `_cmd_polish` MUSÍ `_client_factory`
    zavolat s `require_lock=...`, jinak `PipelineLLMClient` uvnitř
    `_polish_one_chapter` nemá jak zámek ověřit PŘED KAŽDÝM LLM voláním
    (viz Task 10 stejný vzor pro server)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    seen = {}
    def _fake_client_factory(rid, *, interactive, require_lock=None):
        seen["require_lock"] = require_lock
        return lambda a: object()
    monkeypatch.setattr(main, "_client_factory", _fake_client_factory)
    main._cmd_polish(_Args(only=None, force=False))
    assert callable(seen["require_lock"])
```

Run: `pytest tests/test_cli.py -k "lock_still_owned or passes_require_lock" -v`
Expected: PASS

**Kolo 5 IMPORTANT - `_polish_one_chapter` volání (main.py:1176, uvnitř
`try:` bloku, PŘED tím, co tenhle Task dál upravuje) musí dostat STEJNÝ
`rendered_terms`, jaký pak použije zápis** (viz Task 3's `_polish_one_
chapter` docstring a `_commit_polish_result` docstring výš - jinak
kontrola uvnitř `_polish_one_chapter` může podhodnotit závažnost nálezu
proti tomu, co zápis do `term_mentions` skutečně prosadí). Nahraď:

```python
                rec = _polish_one_chapter(c, glossary_rows, cf, db, model, codex_cmd)
```

za:

```python
                history_for_rt = polish_store.load_history(config.POLISH_HISTORY_PATH)
                rt = _preferred_rendered_terms(
                    db, c["idx"], c["translated_text"], history_for_rt["entries"])
                rec = _polish_one_chapter(c, glossary_rows, cf, db, model, codex_cmd,
                                          rendered_terms=rt)
```

(`history_for_rt` se načítá ZNOVU při KAŽDÉ iteraci - historie roste s
každým commitem předchozí kapitoly v týž běhu, zastaralá kopie by
`_preferred_rendered_terms`'s "je historie v souladu s aktuálním
textem" kontrolu mohla vyhodnotit špatně pro kapitoly zpracované PO
první. Cena čtení malého JSON souboru na kapitolu je zanedbatelná proti
Codex volání, co beztak následuje.)

Teď uprav samotnou smyčku - nahraď draft-akumulační `finally` větev
(řádky 1194-1228, konkrétně blok `if "outcome" not in rec:`) za přímý
zápis s obnovou zámku a CAS kontrolou PŘED každým commitem (Global
Constraints - dávka nad ~50 kapitolami může běžet dlouho, `_cmd_polish`
na rozdíl od `polish-review` serveru nemá heartbeat vlákno; bez
`refresh_lock` tady by zámek po `_LOCK_STALE_SECONDS` (6 h) zestárl,
i když tenhle proces ho pořád legitimně drží, a jiný proces by ho mohl
převzít a psát do STEJNÉ DB souběžně):

```python
                if "outcome" not in rec:
                    # Codex navrhl jinou stylizaci - ROVNOU zapiš jako
                    # finální text (spec "Architektura" - žádná čekající
                    # fronta). Obnov zámek PŘED KAŽDÝM zápisem - dlouhá
                    # dávka (desítky kapitol, minuty Codex volání na
                    # kapitolu) jinak riskuje překročení stálosti zámku
                    # uprostřed běhu.
                    try:
                        state.refresh_lock(config.LOCK_PATH)
                    except state.LockError as e:
                        report.append({"idx": rec["idx"], "outcome": "fatal",
                                       "error": f"Zámek ztracen: {e}"})
                        raise FatalRunError(
                            f"Zámek ztracen uprostřed dávky ({e}) - jiný "
                            "proces teď píše do DB, běh se zastavuje.") from e
                    # CAS - `en`/`cz_before` musí přijít ze STEJNÉHO `c`
                    # objektu, ale DB se od zahájení smyčky mohla změnit
                    # (i v rámci JEDNOHO zámku - obranná kontrola, ne jen
                    # cross-proces). Neshoda → přeskoč TUHLE kapitolu,
                    # nezastavuj celou dávku.
                    row_now = state.get_chapter(db, c["idx"])
                    if (row_now is None
                            or row_now["translated_text"] != c["translated_text"]
                            or row_now["status"] != "done"):
                        rec = {"idx": c["idx"], "outcome": "failed",
                               "error": "kapitola se mezitím změnila mimo "
                                       "tenhle běh, přeskočeno"}
                    else:
                        findings_final = rec["findings"]
                        try:
                            _commit_polish_result(
                                db, config.POLISH_HISTORY_PATH, c["idx"],
                                en=c["raw_text"], cz_before=c["translated_text"],
                                final_text=rec["styled"], findings=findings_final,
                                glossary_rows=glossary_rows,
                                revision_rounds=rec["revision_rounds"],
                                source="polish-batch", model_label=model,
                                styled_by_codex=rec["styled"],
                                backup_state=backup_state,
                                rendered_terms=rt)   # STEJNÁ hodnota jako
                                # analýza výš (`_polish_one_chapter`
                                # volání) - kolo 5 IMPORTANT konzistence.
                        except HistoryWriteFailedAfterCommit as e:
                            # Text UŽ JE v DB (kolo 2 BLOCKING rozlišení) -
                            # jiná hláška než "nezapsáno", i když se běh
                            # pořád zastavuje (historie je z tohohle místa
                            # dál nekonzistentní, bezpečnější nepokračovat).
                            report.append({"idx": rec["idx"], "outcome": "fatal",
                                           "error": stylist._redact_detail(
                                               f"HistoryWriteFailedAfterCommit: {e}")})
                            raise FatalRunError(
                                f"Kapitola {c['idx']}: text SE zapsal do knihy, ale "
                                f"zápis do historie selhal ({stylist._redact_detail(str(e))}) "
                                "- celý běh `polish` se zastavuje, zkontroluj "
                                f"{config.POLISH_HISTORY_PATH} ručně.") from e
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
                elif rec.get("outcome") == "unchanged":
                    # Kolo 9 IMPORTANT - marker zapiš i BEZE ZMĚNY textu
                    # (viz "Proč marker uvnitř _commit_polish_result" výš) -
                    # jinak `_already_styled` zůstane `False` a příští
                    # `polish` bez `--force` kapitolu znovu (a zbytečně)
                    # pošle Codexu. `_commit_polish_result` se tu NEPOUŽÍVÁ
                    # (žádná VĚCNÁ změna textu, historie by dostala
                    # zavádějící `cz_before == cz_after` záznam) - stejný
                    # lehký zápis jako Task 9's notes-only větev.
                    try:
                        state.refresh_lock(config.LOCK_PATH)
                    except state.LockError as e:
                        report.append({"idx": rec["idx"], "outcome": "fatal",
                                       "error": f"Zámek ztracen: {e}"})
                        raise FatalRunError(
                            f"Zámek ztracen uprostřed dávky ({e}) - jiný "
                            "proces teď píše do DB, běh se zastavuje.") from e
                    row_now = state.get_chapter(db, c["idx"])
                    if (row_now is None
                            or row_now["translated_text"] != c["translated_text"]
                            or row_now["status"] != "done"):
                        # Kapitola se mezitím změnila mimo tenhle běh -
                        # na rozdíl od "applied" větve NENÍ text co
                        # zahodit (nic se nezměnilo), marker jen zůstane
                        # nezapsaný - příští `polish` to zkusí znovu na
                        # AKTUÁLNÍM stavu kapitoly.
                        pass
                    else:
                        marker = findings_mod.assign_ids([_unchanged_marker(model)])[0]
                        current_notes = _parse_findings(row_now["notes"])
                        try:
                            _backup_db_once(db, backup_state)
                            with state.connect(db) as conn:
                                conn.execute(
                                    "UPDATE chapters SET notes=?, "
                                    "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                                    (json.dumps(current_notes + [marker], ensure_ascii=False),
                                     c["idx"]))
                        except Exception as e:
                            report.append({"idx": rec["idx"], "outcome": "fatal",
                                           "error": stylist._redact_detail(
                                               f"{type(e).__name__}: {e}")})
                            raise FatalRunError(
                                f"Zápis markeru selhal ({stylist._redact_detail(f'{type(e).__name__}: {e}')}) "
                                "- infrastrukturní chyba, celý běh `polish` se "
                                "zastavuje.") from e
```

`backup_state` musí existovat PŘED smyčkou, a na rozdíl od jednoduchého
"jen nastav cestu" musí SKUTEČNĚ vytvořit snapshot přes `_snapshot_db` -
`_backup_db_once` (viz jeho docstring, main.py:373) jen PROMUJE už
existující soubor na `backup_state["snapshot_path"]` (`os.replace`), samo
nic nekopíruje. Bez tohohle kroku první zápis dávky skončí
`FileNotFoundError`.

**Pořadí + úklid (kolo 2 NIT, zpřesnění):** `_backup_db_once`'s celá
premisa je "záloha popisuje stav PŘED tímhle během" (main.py:373-392
docstring) - snapshot proto musí vzniknout PŘED `state.create_run`
(create_run samo nemění `chapters`/`translated_text`, ale je to první
zápisová operace běhu, snapshot má logicky předcházet VŠEMU). Úklid
nepromovaného snapshotu navíc musí proběhnout i při přerušení (`Ctrl-C`,
`FatalRunError` z první kapitoly), ne jen na šťastné cestě "smyčka
doběhla celá" - proto do EXISTUJÍCÍHO `finally:` bloku (main.py, ten co
už dnes volá `state.finish_run`/`_write_polish_report`), ne jako
samostatný krok za smyčkou.

`backup_state = None` inicializuj HNED na začátku funkce (vedle `rid =
None`, PŘED vnějším `try:`), skutečnou hodnotu přiřaď a snapshot vytvoř
TĚSNĚ PŘED `try:` blokem (main.py, dnešní `rid = None; status = "fatal"
...` sekce PŘED `try:`):

```python
    rid = None
    status = "fatal"
    report = []
    planned_count = 0
    batch_completed = False
    run_error = None
    backup_state = {"done": False, "snapshot_path": db + ".pre-polish-snapshot"}
    # `_snapshot_db` selhání (`OSError`/`TimeoutError`) MUSÍ dostat
    # ŘÍZENÉ ošetření (kolo 4 BLOCKING - oprava vlastního dřívějšího
    # chybného tvrzení, viz níž) - VLASTNÍ `try/except`, ne propad do
    # hlavního `try:` bloku (ten se ještě nezačal).
    try:
        _snapshot_db(db, backup_state["snapshot_path"])
    except (OSError, TimeoutError) as e:
        _say(f"Záloha DB před polishem selhala ({type(e).__name__}: {e}) - "
             "běh se nespouští, dokud se nedá udělat bezpečná záloha.")
        return 1
    try:
```

**Oprava vlastního dřívějšího tvrzení (kolo 4 BLOCKING):** "main() to
zachytí jako obecnou chybu" bylo NEPRAVDIVÉ - `main()` (main.py:1341-1346)
zachytává VÝHRADNĚ `state.LockError`, žádnou jinou výjimku. Bez
`try/except` výš by `OSError`/`TimeoutError` z `_snapshot_db` propadly
jako NEZACHYCENÝ traceback celou cestou k uživateli, místo čitelné
`_say` hlášky jako u KAŽDÉHO jiného preflight selhání v týhle funkci.
Zbytek dřívějšího odstavce (srovnání s `polish_server.py`'s `build_app`,
kde `_snapshot_db` volání JE taky mimo try/finally) zůstává platný -
tamní chování je SAMOSTATNÁ otázka (server start, ne `_cmd_polish`),
mimo rozsah tohohle Tasku, jen se to nesmí používat jako důvod NEošetřit
to tady, kde to snadno jde.

Uvnitř smyčky (Step 8 kód výš) `backup_state` používej BEZE ZMĚNY -
proměnná teď jen vzniká dřív, ne uvnitř `try`.

Do EXISTUJÍCÍHO `finally:` bloku (main.py, tam kde dnes `if rid is not
None: ... state.finish_run(...) ... _write_polish_report(...)`) přidej
úklid snapshotu jako SAMOSTATNÝ krok, NEZÁVISLE na `if rid is not None:`
(snapshot může existovat, i když `create_run` samo selhalo):

```python
    finally:
        if not backup_state["done"]:
            try:
                os.remove(backup_state["snapshot_path"])
            except OSError:
                pass
        if rid is not None:
            finalization_error = None
            try:
                state.finish_run(db, rid, status)
            except Exception as e:
                finalization_error = f"{type(e).__name__}: {e}"
                _say(f"POZOR: zápis konečného stavu běhu selhal "
                     f"({finalization_error}) - run zůstává nedokončený "
                     "v DB, ale výsledek/chyba výš je platná.")
            _write_polish_report(db, rid, report, codex_model=model,
                                 planned_count=planned_count,
                                 batch_completed=batch_completed, run_status=status,
                                 run_error=run_error,
                                 finalization_error=finalization_error)
```

Nakonec smaž `draft_chapters = []` proměnnou a VŠECHNY odkazy na
`polish_store.save_draft`/`config.POLISH_DRAFT_PATH` uvnitř `_cmd_polish`
(cely blok "Zápis je INKREMENTÁLNÍ" z předchozí verze) a nahraď
`_say(f"Navrženo k review: ...")` (řádek 1234) za:

```python
        _say(f"Stylizováno a zapsáno: {tally['applied']}, beze změny: "
             f"{tally['unchanged']}, selhalo: {tally['failed']}")
```

- [ ] **Step 9: Oprav `_polish_env` fixture (main.py:861 v `tests/test_cli.py`)**

`_polish_env` monkeypatchuje `config.POLISH_DRAFT_PATH` na `tmp_path`, ale
NEpřesměrovává `config.POLISH_HISTORY_PATH` - `_cmd_polish` po tomhle
Tasku zapisuje historii přes `config.POLISH_HISTORY_PATH`, takže BEZ
přesměrování by nové testy zapisovaly do SKUTEČNÉHO `data/polish.history.json`
projektu.

**BLOCKING (kolo 2) - `_polish_env` navíc NEZÍSKÁVÁ zámek.** Testy volají
`_cmd_polish(args)` PŘÍMO, ne přes `main()` (ten by normálně zámek získal
sám PŘED voláním `_MUTATING` příkazu). Nová dávková smyčka (Step 8 výš)
volá `state.refresh_lock(config.LOCK_PATH)` PŘED každým commitem - bez
existujícího, VLASTNĚNÉHO zámku by `refresh_lock` vždy selhalo (zámek
buď neexistuje, nebo by ho vlastnil JINÝ PID), a KAŽDÝ test, co dojde až
ke commitu, by spadl na `FatalRunError` hned na první kapitole. V
`_polish_env` (main.py:861-881 v `tests/test_cli.py`) přidej hned vedle
existujícího `POLISH_DRAFT_PATH` řádku:

```python
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", str(tmp_path / "polish.history.json"))
    monkeypatch.setattr(config, "LOCK_PATH", str(tmp_path / ".lock"))
    state.acquire_lock(config.LOCK_PATH)
```

(`POLISH_DRAFT_PATH` řádek můžeš ponechat - neškodí, i když ho po tomhle
Tasku už nic nečte. Zámek se v `tmp_path` sám "uklidí" s adresářem -
žádný explicitní `release_lock` v testech netřeba, každý test dostává
ČERSTVÝ `tmp_path`.)

**Kolo 13 IMPORTANT - `_polish_env`'s VLASTNÍ `_client_factory` mock
(main.py:880 v `tests/test_cli.py`) musí přijmout nový `require_lock`
kwarg, jinak KAŽDÝ test používající `_polish_env` po přidání `require_
lock` do reálného volání (`cf = _client_factory(rid, interactive=True,
require_lock=...)`, viz výš) spadne na `TypeError: got an unexpected
keyword argument 'require_lock'`.** Uprav existující řádek:

```python
    monkeypatch.setattr(main, "_client_factory", lambda rid, *, interactive: (lambda a: object()))
```

na:

```python
    monkeypatch.setattr(main, "_client_factory",
                        lambda rid, *, interactive, require_lock=None: (lambda a: object()))
```

(`require_lock=None` PŘIJME a ZAHODÍ nový kwarg - `_polish_env` už i
tak `cf(agent)` úplně mockuje na `object()`, žádný REÁLNÝ `PipelineLLMClient`
tady nevzniká, takže `require_lock` callback by se tímhle mockem stejně
nikdy nezavolal. Testy na SAMOTNÉ chování `require_lock`/`_lock_still_
owned` proto NEJDOU postavit přes `_polish_env` - viz Step 10b níž, co
mock NEPOUŽÍVÁ, testuje přímo.)

- [ ] **Step 10: Přepiš testy `_cmd_polish` end-to-end**

Existující testy v `tests/test_cli.py`, co ověřují `polish.draft.json`
obsah po `_cmd_polish` (`Grep "POLISH_DRAFT_PATH\|polish.draft" tests/test_cli.py`),
se PŘEPISUJÍ na ověření přímého DB zápisu - POUŽIJ existující `_polish_env`
fixturu (main.py:861), NE neexistující `_db`/`_make_db_with_one_chapter`:

```python
def test_cmd_polish_writes_directly_to_db(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    main._cmd_polish(_Args(only=None, force=False))
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Jiná věta."   # skutečně přepsáno
    history = polish_store.load_history(config.POLISH_HISTORY_PATH)
    assert history["entries"][0]["source"] == "polish-batch"
    assert not os.path.exists(config.POLISH_DRAFT_PATH)   # draft soubor nevzniká


def test_cmd_polish_unchanged_chapter_marked_and_skipped_next_run(tmp_path, monkeypatch):
    """Kolo 9 IMPORTANT - beze zápisu markeru by druhý běh kapitolu,
    co Codex nechal beze změny, poslal Codexu ZNOVU (a znovu zaplatil).
    `--force` musí i tak umět kapitolu vrátit zpátky do zpracování."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    calls = {"n": 0}

    def fake_polish(en, cz, **k):
        calls["n"] += 1
        return cz   # Codex nenavrhuje žádnou úpravu

    monkeypatch.setattr(main.stylist, "polish", fake_polish)
    main._cmd_polish(_Args(only=None, force=False))
    assert calls["n"] == 1
    row = state.get_chapter(db, 1)
    notes = main._parse_findings(row["notes"])
    assert any(f["source"] == "stylist" and f["type"] == "unchanged" for f in notes)
    assert main._already_styled(row["notes"]) is True

    main._cmd_polish(_Args(only=None, force=False))
    assert calls["n"] == 1   # druhý běh bez --force kapitolu PŘESKOČIL

    main._cmd_polish(_Args(only=None, force=True))
    assert calls["n"] == 2   # --force ji i tak zpracuje znovu
```

- [ ] **Step 11: Ověř**

Run: `pytest tests/test_cli.py -k polish -v`
Expected: PASS. Projdi VŠECHNY testy v `test_cli.py`, co zmiňují
`polish.draft.json`/`"drafted"`/`_polish_one_chapter` návratovou hodnotu
bez `outcome` klíče - musí buď projít beze změny (test `_polish_one_chapter`
samotné - ta funkce se nemění), nebo být přepsané podle Step 10 vzoru.

- [ ] **Step 12: Commit**

```bash
git add main.py src/polish_store.py tests/test_cli.py tests/test_polish_store.py
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
    db = _polish_db(tmp_path)   # main.py:666 fixture - idx=1, status='done'
    monkeypatch.setattr(config, "OUTPUT_TXT", str(tmp_path / "out.txt"))
    path, skipped = main.export_book(db, only_done=False)
    assert path == str(tmp_path / "out.txt")
    assert skipped == []
    assert "K1" in open(path, encoding="utf-8").read()


def test_export_book_skips_non_done_without_only_done_flag_marks_missing(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
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

- [ ] **Step 5: Oprav `_finding_summary` (main.py:53, existující funkce)**

Kolo 5 IMPORTANT - `export_book` volá `_finding_summary(ch['notes'])`
pro KAŽDOU `flagged` kapitolu. Přečti si aktuální implementaci
(main.py, `_finding_summary`) - dělá si VLASTNÍ ruční parsování místo
sdíleného `_parse_findings`:

```python
def _finding_summary(notes: str) -> str:
    try:
        data = json.loads(notes or "[]")
    except (ValueError, TypeError):
        return "neznámý nález"
    if isinstance(data, dict):
        return str(data.get("error") or "neznámý nález")
    for f in data:
        if f.get("issue"):
            return f["issue"]
    return "neznámý nález"
```

`notes = "null"` → `data = None` → `for f in None:` → `TypeError`
(NEchycené - `except` výš pokrývá jen `json.loads`, ne tenhle cyklus).
`notes = "42"` → `data = 42` → `for f in 42:` → stejný pád. `notes =
"[null]"` → `data = [None]` → `f.get("issue")` na `None` → `AttributeError`.
Jedna takováhle kapitola shodí CELÝ export knihy (žádná kapitola
zvlášť - `export_book` na tom spadne uprostřed smyčky). Nahraď za:

```python
def _finding_summary(notes: str) -> str:
    try:
        data = json.loads(notes or "[]")
    except (ValueError, TypeError):
        return "neznámý nález"
    if isinstance(data, dict):
        return str(data.get("error") or "neznámý nález")
    for f in _parse_findings(notes):   # bezpečné, jen dict prvky - main.py:84
        if f.get("issue"):
            return str(f["issue"])
    return "neznámý nález"
```

(`_parse_findings` dělá VLASTNÍ `json.loads` znovu - drobné zdvojení
práce, ne problém pro funkci volanou jednou na kapitolu; hlavní bod je
bezpečnost, ne výkon.)

Přidej test do `tests/test_cli.py`:

```python
@pytest.mark.parametrize("bad_notes", ["null", "42", "[null]", "not json"])
def test_finding_summary_does_not_crash_on_malformed_notes(bad_notes):
    assert main._finding_summary(bad_notes) == "neznámý nález"
```

Run: `pytest tests/test_cli.py -k finding_summary -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "refactor: extrahuj export_book(), oprav _finding_summary pádu na malformed notes

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: `src/findings_report.py` - agregovaný report nálezů

**Files:**
- Create: `src/findings_report.py`
- Test: `tests/test_findings_report.py`

**Interfaces:**
- Consumes: `state.chapters_by_status`, `findings.is_marker`,
  `main._parse_findings`.
- Produces:
  - `build_findings_report(db_path: str) -> list[dict]`
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
    report = findings_report.build_findings_report(db)
    assert report == [{"idx": 1, "title": "K1",
                       "findings": [{"id": "f1", "resolved": False,
                                    "source": "concordance", "type": "omission",
                                    "issue": "chybí termín"}]}]


def test_build_findings_report_excludes_markers(tmp_path):
    db = _db_with_notes(tmp_path, [
        {"id": "m1", "resolved": False, "source": "stylist", "type": "polish",
         "issue": "stylizováno..."}])
    report = findings_report.build_findings_report(db)
    assert report == []   # jediný nález byl marker, kapitola se vynechá


def test_build_findings_report_does_not_duplicate_via_history(tmp_path):
    """`_commit_polish_result` (Task 5) zapisuje STEJNÝ seznam nálezů do
    `notes` i do historie zároveň - report NESMÍ sáhnout do historie
    taky, jinak by se každý nález zobrazil dvakrát (stejné `id`)."""
    db = _db_with_notes(tmp_path, [
        {"id": "f1", "resolved": False, "source": "critic",
         "type": "fidelity", "issue": "posun smyslu"}])
    history_path = str(tmp_path / "polish.history.json")
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "a", "cz_after": "b", "styled_by_codex": "b",
            "title": "K1", "findings": [{"id": "f1", "resolved": False,
                                        "source": "critic", "type": "fidelity",
                                        "issue": "posun smyslu"}],
            "rendered_terms": [], "source": "polish-batch", "draft_id": "d1"}]})
    report = findings_report.build_findings_report(db)
    assert len(report[0]["findings"]) == 1


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
"""Agregovaný report nálezů napříč VŠEMI kapitolami, čtený z `chapters.
notes` (JEDINÝ zdroj - viz `build_findings_report` docstring, proč se
NEslučuje s `polish.history.json`). Dva výstupy ze STEJNÉHO
`build_findings_report`: HTML k vytištění a prostý txt vedle exportu
knihy. Viz spec 2026-09-14, sekce "Report nálezů"."""
import html as _html

from src import findings, state


def build_findings_report(db_path: str) -> list:
    """`chapters.notes` je JEDINÝ zdroj - `_commit_polish_result`
    (main.py Task 5) zapisuje do `notes` PŘESNĚ to, co zároveň připojí
    do `polish.history.json`.

    DÁVKA (`_cmd_polish`/Task 5) `notes` PŘEPISUJE - `_commit_polish_
    result` samo NEMERGUJE, jen uloží, co dostane (`rec["findings"]` z
    čerstvé `_polish_one_chapter` analýzy + marker); volající v Tasku 5
    žádný merge nedělá. Běžný běh (dávka jede JAKO PRVNÍ krok, hned po
    `run`u, PŘED jakoukoli ruční úpravou) tak `run`-fáze nálezy nahradí
    ČERSTVĚJŠÍMI (koncordance/kritik spočítané znovu proti NOVĚ
    stylizovanému textu, relevantnější než nálezy o textu, co už
    neexistuje) - to je ZÁMĚRNÉ, ne ztráta dat (kolo 6 NIT, oprava - dřív
    tenhle docstring mylně tvrdil, že AKUMULACE platí i pro dávku).

    EDITOR (`POST /api/chapter/{idx}/save`, Task 9) naopak `notes`
    AKUMULUJE, ne přepisuje - VOLAJÍCÍ (endpoint, ne `_commit_polish_
    result` samo) sloučí nové nálezy s `_merge_findings_by_id` PŘED
    voláním `_commit_polish_result`, ať žádná ruční úprava neztratí
    nález, co tam mezitím přidala jiná karta/regenerace. Report proto
    typicky ukazuje ROSTOUCÍ seznam PO PRVNÍ ruční úpravě kapitoly, ne
    hned po dávce - zaškrtávátko `resolved` je způsob, jak nález
    "uklidit" z pohledu, ne mazání ze storage.

    Slučování s posledním historie záznamem by KAŽDÝ nález zdvojilo
    (stejná data, stejná `id`, ze STEJNÉHO zápisu) - viz Task 5
    `_commit_polish_result` docstring."""
    from main import _parse_findings   # lazy - main importuje spoustu modulů, ne naopak
    chapters = state.chapters_by_status(
        db_path, ("pending", "processing", "done", "flagged", "needs_human", "error"))
    out = []
    for ch in sorted(chapters, key=lambda c: c["idx"]):
        notes_findings = [f for f in _parse_findings(ch["notes"])
                          if not findings.is_marker(f)]
        if notes_findings:
            out.append({"idx": ch["idx"], "title": ch["title"], "findings": notes_findings})
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
            # `str(...)` PŘED `_html.escape` (kolo 4 IMPORTANT) - producenti
            # nálezů (kritik/concordance) nejsou validovaní jako klientský
            # save vstup, `issue`/`severity` NEMUSÍ být `str` (`html.escape`
            # na non-str spadne na `TypeError`).
            sev = _html.escape(str(f.get("severity") or "?"))
            issue = _html.escape(str(f.get("issue") or "(bez popisu)"))
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
    "translated_text", "status", "findings" (JEN `chapters.notes`,
    ne-markerové, s id/resolved - NE sloučené s historií, viz Task 7
    poznámka o duplicitě), "cz_before_original" (str|null),
    "styled_by_codex_latest" (str|null), "history" (pole záznamů PRO
    TUHLE kapitolu, přes `_annotate_history`)}` nebo 404, když kapitola
    neexistuje. `cz_before_original` = `find_chain_start`'s `cz_before` -
    NIT: "originál" tu znamená "před současným NEPŘERUŠENÝM řetězcem
    úprav", ne nutně úplně PRVNÍ historický záznam vůbec (viz `find_
    chain_start` docstring v `src/polish_store.py` - historie může mít
    mezery od `answer`/`run` epizod mimo `polish`/editor workflow).
    Stejná, záměrně převzatá sémantika jako dnešní revert "vrať na
    původní" tlačítko (`2026-09-11` spec) - NEmění se tady, jen se
    zdůrazňuje přesný význam.

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
        # `notes` je JEDINÝ zdroj "aktuálních" nálezů (viz `build_findings_
        # report` docstring, Task 7) - `_commit_polish_result` zapisuje
        # STEJNÝ seznam do notes i do historie zároveň, sloučení by
        # zdvojilo každý nález.
        notes_findings = [f for f in main._parse_findings(row["notes"])
                          if not findings.is_marker(f)]
        own_history = [e for e in entries if e["idx"] == idx]
        return {
            "idx": row["idx"], "title": row["title"], "raw_text": row["raw_text"],
            "translated_text": row["translated_text"], "status": row["status"],
            "findings": notes_findings,
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
  (Task 4), `findings.assign_ids`, `glossary.all_terms`, `polish_store.find_latest`,
  `_try_load_history` (existující helper).
- Produces: `POST /api/chapter/{idx}/save` - payload
  `{"cz_before": str, "text": str, "findings": list[dict],
  "styled_by_codex": str (volitelné, default "")}` → `{"ok": true}` (text
  se změnil - normální zápis PŘES `_commit_polish_result`, nová historie
  položka) nebo `{"ok": true, "noop": bool}` (text == `cz_before` -
  "lehká" větev, MERGuje nálezy/status podle `id` BEZ nové historie
  položky, `noop: true` jen když se ani merge výsledek neliší od
  aktuálního stavu) nebo 409 (CAS neshoda NEBO status mimo
  `_EDITABLE_STATUSES`), 400 (špatný tvar, včetně jednotlivých položek
  `findings`), 503 (zámek ztracen).

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


def test_save_chapter_persists_findings_and_approves_flagged_without_text_change(tmp_path):
    """Kolo 2 IMPORTANT - text beze změny NEZNAMENÁ nulová operace,
    pokud kapitola byla `flagged` (uživatel ji Uložit tlačítkem ručně
    schválil) NEBO nese nové (dosud neuložené) nálezy z regenerace."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='flagged' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.",
        "findings": [{"id": "new1", "resolved": False,
                     "source": "critic", "type": "fidelity"}]})
    assert r.json() == {"ok": True, "noop": False}
    row = state.get_chapter(db, 1)
    assert row["status"] == "done"
    assert json.loads(row["notes"])[0]["id"] == "new1"
    history = polish_store.load_history(history_path)
    assert history["entries"] == []   # žádná NOVÁ historie položka - text se nezměnil


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


# Následující 4 testy PORTUJÍ ochranné scénáře ze starého draft-based
# `POST /api/polish/apply` (`tests/test_polish_server.py`, testy kolem
# `test_apply_503_when_lock_lost_no_db_or_json_write`/`test_apply_corrupt_
# history_returns_500_without_db_write`/`test_apply_pre_commit_failure_
# returns_500_db_and_draft_unchanged`/`test_apply_post_commit_save_
# failure_db_already_updated`) - Task 13 Step 1 tyhle staré testy MAŽE
# (draft fronta končí), ale SAMOTNÁ OCHRANA, co testovaly, dál platí pro
# nový endpoint a MUSÍ zůstat pokrytá - proto tady, ne zapomenutá.

def test_save_chapter_503_when_lock_lost_no_db_write(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 503
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_corrupt_history_returns_500_without_db_write(tmp_path):
    """Historie se validuje PŘED commitem (`_commit_polish_result`, kolo 2
    BLOCKING) - poškozený `polish.history.json` nesmí nechat DB změněnou."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    open(history_path, "w", encoding="utf-8").write("{not valid json")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 500
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_pre_commit_failure_returns_500_db_unchanged(tmp_path, monkeypatch):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(polish_server.state, "commit_chapter_result",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 500
    assert "nebyl" in r.json()["error"].lower()
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_post_commit_history_failure_db_already_updated(tmp_path, monkeypatch):
    """Selhání ZÁPISU historie AŽ PO úspěšném DB commitu je jiná třída
    chyby (`main.HistoryWriteFailedAfterCommit`) - DB SE ZMĚNILA a
    zpráva to musí říct, ne tvrdit "nebyl uložen"."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(polish_server.polish_store, "save_history",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 500
    assert "uloži" in r.json()["error"].lower() or "ulož" in r.json()["error"].lower()
    assert state.get_chapter(db, 1)["translated_text"] == "Nová."   # DB SE PŘESTO ZMĚNILA


def test_save_chapter_keeps_resolved_true_even_with_stale_client_payload(tmp_path):
    """Karta B mezitím vyřešila nález přes /api/findings/resolve; karta A
    ukládá se STARÝM (resolved=False) stavem téhož nálezu - uložení
    nesmí vyřešení ztratit."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": True,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.",
        "findings": [{"id": "f1", "resolved": False,
                     "source": "critic", "type": "fidelity"}]})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    saved = json.loads(row["notes"])
    assert next(f for f in saved if f["id"] == "f1")["resolved"] is True


def test_save_chapter_server_resolved_false_wins_over_stale_client_true(tmp_path):
    """Opačný směr téhož race (kolo 2 BLOCKING - kolo 1 chránilo jen
    false→true): karta B nález ZNOVU OTEVŘELA (server má false), karta A
    má ve své paměti STARÉ true a s ním uloží - server musí zůstat u
    false, ne se nechat přepsat zastaralým true."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.",
        "findings": [{"id": "f1", "resolved": True,
                     "source": "critic", "type": "fidelity"}]})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    saved = json.loads(row["notes"])
    assert next(f for f in saved if f["id"] == "f1")["resolved"] is False


def test_save_chapter_text_change_does_not_wipe_finding_added_via_light_write(tmp_path):
    """Kolo 4 BLOCKING - karta B (lehká větev, text beze změny) přidá
    nový nález; karta A pak uloží SKUTEČNOU změnu textu se STARÝM
    (bez B's nálezu) seznamem findings - textový CAS na tohle nekouká,
    ale merge-podle-id ho i tak musí zachovat."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    # Karta B: lehká větev přidá nález "b1" (text beze změny).
    r1 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.",
        "findings": [{"id": "b1", "resolved": False, "source": "critic", "type": "fidelity"}]})
    assert r1.status_code == 200
    # Karta A: STARÝ payload (bez b1), ale SKUTEČNÁ změna textu.
    r2 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nový text A.", "findings": []})
    assert r2.status_code == 200
    row = state.get_chapter(db, 1)
    saved_ids = {f["id"] for f in json.loads(row["notes"])}
    assert "b1" in saved_ids   # PŘEŽILO, i když ho karta A vůbec neznala


def test_save_chapter_400_on_invalid_finding_shape(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [None]})
    assert r.status_code == 400


def test_save_chapter_400_on_invalid_known_ids_shape(tmp_path):
    """Kolo 20 BLOCKING - `known_ids` (nové, volitelné pole) musí být
    pole stringů, pokud je PŘÍTOMNÉ - stejná disciplína jako `findings`."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [],
        "known_ids": [1, 2]})
    assert r.status_code == 400


def test_save_chapter_400_on_falsy_but_present_known_ids(tmp_path):
    """Kolo 21 NIT - `known_ids: false`/`0`/`""`/`{}` jsou PŘÍTOMNÉ, ale
    ne-list hodnoty - musí dostat 400, ne se tiše proměnit na `[]`
    (`payload.get("known_ids") or []` by tohle mylně propustilo)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [],
        "known_ids": False})
    assert r.status_code == 400


def test_save_chapter_missing_known_ids_defaults_to_empty(tmp_path):
    """Kolo 20 BLOCKING - CHYBĚJÍCÍ `known_ids` (starší klient/API
    volání) NESMÍ selhat ani nic ztratit - bezpečný fallback na `[]`
    (= "nic neznámo", nic se nemaže, viz `_merge_findings_by_id`)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": []})
    assert r.status_code == 200


def test_save_chapter_allows_flagged_status(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='flagged' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Opraveno.", "findings": []})
    assert r.status_code == 200
    assert state.get_chapter(db, 1)["status"] == "done"


def test_save_chapter_preserves_rendered_terms_from_history_not_narrowed_live_mentions(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "Původní.", "cz_after": "Věta 1.", "styled_by_codex": "Věta 1.",
            "title": "K1", "findings": [],
            "rendered_terms": [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0},
                               {"term_id": "t/b", "cz_as_used": "Bé", "scene_idx": 1}],
            "source": "polish-batch", "draft_id": "d1"}]})
    # živá `term_mentions` je ÚŽŠÍ (jen jeden termín) - simuluje předchozí
    # commit, co glosářově zúžil hlášené tvary.
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t/a','A','Á')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Á", "scene_idx": 0, "source": "rendered"}])
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Ještě lepší.", "findings": []})
    assert r.status_code == 200
    history = polish_store.load_history(history_path)
    new_entry = history["entries"][-1]
    assert len(new_entry["rendered_terms"]) == 2   # zachováno z historie, NE zúženo na 1
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_polish_server.py -k save_chapter -v`
Expected: FAIL - 404 (route neexistuje)

- [ ] **Step 3: Implementuj**

Za nový `GET /api/chapter/{idx}` (Task 8), přidej:

Nálezy z requestu se NESMÍ zapsat bez validace jednotlivých položek -
`[null]`/nesprávné typy by prošly `isinstance(raw_findings, list)` a
spadly by až uvnitř `findings.assign_ids` (`f.setdefault` na `None`).
Kolo 2 IMPORTANT zpřísnění - i typově "správný", ale nevhodný obsah umí
shodit NĚCO JINÉHO později: `{"source": [], "type": "x"}` projde
`isinstance` kontrolou, ale `findings.is_marker` dělá `(source, type) in
_MARKER_TYPES` - list je NEHASHOVATELNÝ, `in` na množině tuplů s ním
spadne na `TypeError`. `{"issue": 123}` projde, ale `_html.escape(f.get
("issue"))` (Task 7 report) vyžaduje `str`. Prázdné/duplicitní `id` by
navíc `findings.set_resolved` matchlo nejednoznačně (upraví JEN PRVNÍ
shodu). Validace proto pokrývá VŠECHNA pole, co se dál používají:

```python
def _valid_finding_shape(f) -> bool:
    if not isinstance(f, dict):
        return False
    for key in ("id", "source", "type", "issue", "severity"):
        if key in f and f[key] is not None and not isinstance(f[key], str):
            return False
    if "id" in f and f["id"] == "":
        return False
    if "resolved" in f and not isinstance(f["resolved"], bool):
        return False
    return True


def _no_duplicate_ids(findings_list: list) -> bool:
    ids = [f["id"] for f in findings_list if isinstance(f.get("id"), str) and f["id"]]
    return len(ids) == len(set(ids))


def _merge_findings_by_id(current_findings: list, incoming: list, *,
                          known_ids: "set | None" = None) -> list:
    """Sloučí ULOŽENÉ nálezy (`current_findings`, včetně auditních
    markerů - GET je klientovi nikdy neposílá zpátky, takže jejich `id`
    se s `incoming` nikdy nepřekryje) s tím, co poslal klient
    (`incoming`, UŽ prošlé `findings.assign_ids`). Markery se ZACHOVÁVAJÍ
    VŽDY (nikdy se nemažou - append-only audit log). Server-side
    `resolved` je AUTORITATIVNÍ pro KAŽDÉ `id`, co server už zná
    (kolo 4 BLOCKING - obě volající větve v Tasku 9 měly dřív VLASTNÍ,
    vzájemně nekonzistentní pravidlo - jedna merge, druhá plné přepsání,
    což ve druhé nechávalo karta-B-přidala-nález race otevřený). Použij
    STEJNOU funkci na OBOU cestách Tasku 9 (lehká větev i normální
    zápis).

    `known_ids` (kolo 19 BLOCKING, PŘEPRACOVÁNO kolo 20 BLOCKING - viz
    "Proč ne prosté drop_stale_non_markers=True" níž) - `findings_mod.
    assign_ids` dává KAŽDÉMU nálezu bez `id` NOVÉ náhodné `uuid4().hex`
    (Task 2) - `_polish_one_chapter` (Task 3 Step 2) volá `assign_ids`
    na SVÉ VLASTNÍ, čerstvě analyzované nálezy PŘI KAŽDÉM běhu (dávka i
    "Znovu polish" regenerace), takže STEJNÝ sémantický nález dostane
    při KAŽDÉM běhu JINÉ `id` (critic je navíc LLM, ne deterministický -
    "srovnej podle obsahu" není spolehlivá alternativa). Bez řešení by
    "Znovu polish" → "Uložit" NIKDY nenašlo shodu mezi starými (server)
    a novými (klient, čerstvě regenerované) `id` - nálezy by se
    HROMADILY (stejný problém dvakrát, jednou vyřešený navždy osiřelý,
    podruhé nevyřešený) při KAŽDÉM regenerate+save cyklu.

    Non-marker nález z `current_findings`, co NENÍ v `incoming` (podle
    `id`), se NEPŘENESE JEN KDYŽ jeho `id` JE v `known_ids` (klient ho
    znal - buď ho superseduje čerstvou regenerací, nebo ho prostě
    zahodil). Nález, co `id` v `known_ids` NEMÁ (klient o něm NIKDY
    nevěděl - přidal ho JINÝ požadavek/tab MEZI klientovým GET a týmhle
    save), se ZACHOVÁ VŽDY, bez ohledu na `incoming`.

    **Proč ne prosté `drop_stale_non_markers=True` bez `known_ids`
    (kolo 19 verze, kolo 20 BLOCKING oprava):** existující test `test_
    save_chapter_text_change_does_not_wipe_finding_added_via_light_
    write` (kolo 4) dokazuje reálný scénář, kde tohle rozlišení je
    NUTNÉ - karta B (lehká větev) přidá nález "b1", karta A (STARŠÍ,
    "b1" nikdy neviděla) pak uloží SKUTEČNOU změnu textu se svým STARÝM
    `findings: []` payloadem. CAS na `translated_text` tohle NEBLOKUJE
    (karta B měnila jen `notes`, ne text, takže karta A's `cz_before`
    pořád sedí) - kolo-19 verze (`drop_stale_non_markers=True` bez
    rozlišení "znal/neznal") by "b1" ZAHODILA, protože není v kartě A's
    `incoming`, PŘESTOŽE karta A ho nikdy neměla šanci znát. `known_ids`
    (odvozené z KLIENTOVA vlastního `PERSISTED_IDS` PŘI NAČTENÍ editoru,
    Task 14) rozlišuje přesně tenhle případ - "b1" NENÍ v kartě A's
    `known_ids` (načetla stránku PŘED tím, než ho karta B přidala), takže
    přežije. Naopak kolo-19 scénář (regenerace odsiřotí STARÝ nález) - ten
    starý nález BYL v klientově `known_ids` (klient ho viděl při GET),
    takže se správně zahodí, jakmile ho čerstvá regenerace nahradí.

    Volající - OBĚ větve Tasku 9 (kolo 21 BLOCKING - lehká větev
    PŮVODNĚ `known_ids` nepředávala vůbec, což mělo STEJNOU duplicitní
    chybu jako kolo 19 na textově měnící větvi, jen pro scénář "Znovu
    polish" → kandidát NEPŘIJAT → text zůstal stejný → uložit i tak" -
    OBĚ teď předávají `known_ids=set(payload.get("known_ids") or [])`.
    PRÁZDNÁ množina (klient `known_ids` nepošle, nebo pošle prázdné
    pole) znamená "nic neznámo", což BEZPEČNĚ DEGRADUJE na "nic se
    nemaže" (identické chování jako `None` výchozí) - žádná ztráta dat
    na chybějícím/starém poli, jen slabší úklid osiřelých nálezů. To
    dělá volání s `known_ids` BEZPEČNÉ i pro běžný toggle-only save bez
    jakékoli regenerace (typický `incoming` case obsahuje VŠECHNA
    `known_ids`, takže se nic nezahodí) I pro "karta B přidala nález"
    race (ten nález v `known_ids` NENÍ, protože karta A ho nikdy
    neviděla, takže přežije).

    "Nikdy nic nemaže" (markery vždy, non-markery když nejsou v
    `known_ids`) PŘEDPOKLÁDÁ platná, unikátní `id` (kolo 5 NIT) -
    `current_findings` bez `id` (nálezy z DB PŘED migrací, Task 13
    Step 8, dokud migrace neproběhla) se do `current_by_id` vůbec
    nedostanou (`if f.get("id")` filtr) a `_merge_findings_by_id` je
    TICHE VYNECHÁ z výsledku (efektivně "smaže", i když to funkce jako
    celek nedělá záměrně). Spusť migraci PŘED prvním použitím týhle
    cesty - `_valid_finding_shape`/`_no_duplicate_ids` na vstupní straně
    (Task 9 save) navíc garantují, že KLIENTSKÁ `incoming` strana má
    vždy platná unikátní `id`."""
    if known_ids is None:
        known_ids = set()
    current_by_id = {f["id"]: f for f in current_findings if f.get("id")}
    incoming_ids = {f["id"] for f in incoming}
    merged_by_id = {fid: f for fid, f in current_by_id.items()
                    if findings.is_marker(f) or fid in incoming_ids
                    or fid not in known_ids}
    for f in incoming:
        fid = f["id"]
        if fid in current_by_id:
            f["resolved"] = current_by_id[fid].get("resolved", f.get("resolved"))
        merged_by_id[fid] = f
    return list(merged_by_id.values())
```

**Vědomě NEpodporováno (kolo 4 BLOCKING, zbylá polovina): "smaž VŠECHNY
nálezy" přes prázdný `findings: []`.** Merge z principu nic nemaže - je
to bezpečnější výchozí chování (nikdy neztratíš cizí zápis), ale
znamená to, že explicitní úmysl "vyprázdnit nálezy" žádnou cestou nejde
vyjádřit. UI (Task 14) na tohle dneska ani nemá tlačítko ("smaž
všechny nálezy" není součást navrženého workflow - nálezy se ODŠKRTÁVAJÍ
jednotlivě, ne hromadně mažou) - mezera je proto přijatá, ne dořešená;
pokud se v budoucnu přidá "vyčistit nálezy" akce, bude potřebovat
VLASTNÍ explicitní signál (ne prázdné pole, to je nerozlišitelné od
"klient nálezy vůbec nezmínil").

**Podporované statusy k editaci:** editor (Task 8 GET) dovolí otevřít
libovolnou kapitolu, ale `pending`/`processing` nemají smysluplný
`translated_text` k úpravě (ještě neprošly `run`em). Ukládat jde jen
kapitolu, co už reálný text MÁ - `done`, `flagged`, `needs_human`,
`error` (typicky přesně scénář "kritik/otevřená otázka - oprav ručně,
viz kapitola 3 z předchozí session"). Po uložení se status VŽDY nastaví
na `done` (člověk ho právě ručně schválil/opravil).

```python
    _EDITABLE_STATUSES = ("done", "flagged", "needs_human", "error")

    @app.post("/api/chapter/{idx}/save")
    def post_save_chapter(idx: int, payload: dict):
        cz_before = payload.get("cz_before")
        text = payload.get("text")
        raw_findings = payload.get("findings")
        styled_by_codex = payload.get("styled_by_codex", "")
        # `known_ids` (kolo 20 BLOCKING) - VOLITELNÉ (chybějící/`None` =
        # `[]`, bezpečný fallback na "nic neznámo", viz `_merge_findings_
        # by_id` docstring) - když PŘÍTOMNÉ, musí to být pole stringů,
        # stejná disciplína jako `findings`. `payload.get("known_ids") or
        # []` (kolo 21 NIT) by BYLO ŠPATNĚ - `or` by falešné-ale-PŘÍTOMNÉ
        # hodnoty (`false`, `0`, `""`, `{}`) tiše proměnilo na `[]` a
        # nechalo projít validací, přestože kontrakt říká "pokud
        # přítomné, musí být pole stringů" - takový vstup MÁ dostat 400,
        # ne být tiše přijat jako "nic". Rozliš jen chybějící/`None`.
        known_ids_raw = payload.get("known_ids")
        if known_ids_raw is None:
            known_ids_raw = []
        if (not isinstance(cz_before, str) or not isinstance(text, str)
                or not isinstance(raw_findings, list)
                or not all(_valid_finding_shape(f) for f in raw_findings)
                or not _no_duplicate_ids(raw_findings)
                or not isinstance(styled_by_codex, str)
                or not isinstance(known_ids_raw, list)
                or not all(isinstance(x, str) for x in known_ids_raw)):
            return JSONResponse(
                {"error": "cz_before/text/styled_by_codex musí být string, "
                          "findings musí být pole objektů se správnými typy "
                          "a unikátními id, known_ids (pokud přítomné) musí "
                          "být pole stringů"},
                status_code=400)

        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            row = state.get_chapter(db_path, idx)
            if (row is None or row["translated_text"] != cz_before
                    or row["status"] not in _EDITABLE_STATUSES):
                return JSONResponse(
                    {"error": "kapitola se mezitím změnila mimo tenhle editor, "
                              "nebo nemá stav vhodný k uložení - načti stránku "
                              "znovu"}, status_code=409)
            import main
            # Rovnost TEXTU NEZNAMENÁ nulovou změnu (kolo 2 IMPORTANT) -
            # kapitola mohla být `flagged`/`needs_human`/`error` (uživatel
            # text nechal beze změny, ale ručně SCHVÁLIL přes Uložit), NEBO
            # klient posílá nálezy z "Znovu polish", co se ještě nikde
            # nepersistovaly (viz Task 14 `toggleResolved` - nové nálezy
            # existují JEN v prohlížeči, dokud se neuloží). V OBOU
            # případech je co zapsat, i když text zůstává stejný - ale BEZ
            # nové historie položky (žádná VĚCNÁ změna textu se neodehrála,
            # `_commit_polish_result` by jinak vytvořilo zavádějící
            # `cz_before == cz_after` záznam).
            #
            # MERGE podle `id`, NIKDY prosté přepsání (kolo 3 BLOCKING+
            # IMPORTANT, dvě opravy najednou):
            # 1) `raw_findings` z GET nikdy neobsahuje markery (Task 8
            #    GET je filtruje) - prosté přepsání by `_stylist_marker`
            #    ztratilo, `_already_styled` by pak vrátilo `False` a
            #    příští dávka by kapitolu přepsala BEZ `--force`. Merge
            #    markery automaticky zachová (jejich `id` se nikdy
            #    nepřekrývá s ničím v `raw_findings`).
            # 2) Karta B mohla mezitím přidat/uložit NOVÉ nálezy (třeba
            #    přes regeneraci) - prosté přepsání starším payloadem
            #    karty A by je smazalo. Merge jen DOPLŇUJE/aktualizuje
            #    podle `id` - a `known_ids` (kolo 21 BLOCKING, viz níž)
            #    umí NAVÍC bezpečně zahodit vlastní osiřelé nálezy klienta.
            #
            # Kolo 21 BLOCKING - `known_ids` MUSÍ jít i do LEHKÉ větve, ne
            # jen do textově měnící (kolo 19/20). Scénář: uživatel klikne
            # "Znovu polish" (fresh id nálezy), NEPŘIJME kandidát (textarea
            # necha PŮVODNÍ - `text == cz_before`), ale STEJNĚ uloží (např.
            # jen zaškrtnout nález). Bez `known_ids` tady by se čerstvé,
            # OSAMOCENÉ nálezy z odmítnutého kandidáta hromadily vedle
            # starých PŘI KAŽDÉM takovém cyklu - stejná duplicitní chyba
            # jako kolo 19, jen na lehké větvi. `known_ids=set()` (klient
            # `known_ids` nepošle/pošle prázdné, běžný toggle-only save
            # BEZ regenerace) je BEZPEČNÝ no-op - prázdná množina dělá
            # `fid not in known_ids` VŽDY `True`, takže se chová identicky
            # jako `known_ids=None` (nic se nemaže) - žádná regrese pro
            # normální lehké zápisy ANI pro "karta B přidala nález" race
            # (ten nález NENÍ v `known_ids`, protože ho karta A nikdy
            # neviděla, takže přežije stejně jako dřív).
            if text == cz_before:
                import json as _json
                current_findings = main._parse_findings(row["notes"])
                light_findings = _merge_findings_by_id(
                    current_findings, findings.assign_ids(list(raw_findings)),
                    known_ids=set(known_ids_raw))
                if (row["status"] == "done"
                        and _json.dumps(light_findings, ensure_ascii=False)
                        == _json.dumps(current_findings, ensure_ascii=False)):
                    return {"ok": True, "noop": True}
                try:
                    main._backup_db_once(db_path, app.state.backup_state)
                    with state.connect(db_path) as conn:
                        conn.execute(
                            "UPDATE chapters SET notes=?, status='done', "
                            "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                            (_json.dumps(light_findings, ensure_ascii=False), idx))
                except Exception as e:
                    return JSONResponse(
                        {"error": f"Nálezy/stav se nepodařilo uložit "
                                  f"({type(e).__name__}: {e}) - zkus to znovu."},
                        status_code=500)
                return {"ok": True, "noop": False}

            en = row["raw_text"]
            glossary_rows = glossary.all_terms(db_path)
            # `rendered_terms` se NEPOČÍTÁ tady - `_commit_polish_result`
            # (Task 5) ho odvodí samo přes `_preferred_rendered_terms`,
            # stejné pravidlo jako dávka (historie jen když je "v souladu"
            # s aktuálním textem, jinak živá DB).
            # STEJNÁ merge funkce jako lehká větev výš (kolo 4 BLOCKING -
            # dřív měla tahle větev VLASTNÍ pravidlo, co jen přebíralo
            # `resolved` pro známá `id`, ale JINAK celý seznam PŘEPSALO -
            # nález, co karta B přidala/uložila zatímco text stál (přes
            # lehkou větev), by tak zmizel, jakmile karta A se STARŠÍM
            # payloadem uloží skutečnou změnu textu (textový CAS na
            # tohle vůbec nekouká) - PROTO `known_ids`, ne prosté "drop
            # všechno chybějící" (kolo 20 BLOCKING oprava kola-19 verze,
            # viz `_merge_findings_by_id` docstring "Proč ne prosté
            # drop_stale_non_markers=True"). `known_ids` = KLIENTOVA
            # vlastní představa "který nález jsem znal PŘI NAČTENÍ" -
            # `PERSISTED_IDS` z GET (Task 8/14), poslaná v payloadu.
            # Nález, co klient NIKDY neznal (přidal ho JINÝ požadavek
            # MEZI klientovým GET a týmhle save), se ZACHOVÁ i když ho
            # `incoming` neobsahuje - karta-B-přidala-nález race (kolo
            # 3/4) zůstává chráněný. Nález, co klient ZNAL, ale teď ho
            # neposílá (superseduje ho čerstvou regenerací), se ZAHODÍ -
            # kolo-19 duplicitní-hromadění problém zůstává vyřešený.
            # Markery se zachovávají VŽDY, bez ohledu na `known_ids`.
            resolved_findings = _merge_findings_by_id(
                main._parse_findings(row["notes"]), findings.assign_ids(list(raw_findings)),
                known_ids=set(known_ids_raw))
            try:
                main._commit_polish_result(
                    db_path, history_path, idx, en=en, cz_before=cz_before,
                    final_text=text, findings=resolved_findings,
                    glossary_rows=glossary_rows,
                    revision_rounds=row["revision_rounds"], source="polish-review",
                    model_label="ruční úprava (polish-review)",
                    styled_by_codex=styled_by_codex, backup_state=app.state.backup_state)
            except main.HistoryWriteFailedAfterCommit as e:
                # Text UŽ JE v knize (kolo 2 BLOCKING rozlišení) - JINÁ
                # hláška, ne "nebyl uložen" (to by bylo nepravdivé a
                # ZTRÁCELO by ruční Codex/uživatelovu práci, kdyby to
                # uživatel zkusil uložit ZNOVU po tomhle chybovém
                # hlášení - druhý pokus by selhal na CAS, protože DB se
                # od prvního pokusu UŽ změnila).
                return JSONResponse(
                    {"error": f"Text SE ULOŽIL do knihy úspěšně, ale zápis "
                              f"do historie selhal ({e}) - načti stránku "
                              "znovu, tenhle konkrétní zápis se NEOPAKUJ "
                              "(CAS by ho stejně odmítl)."}, status_code=500)
            except Exception as e:
                return JSONResponse(
                    {"error": f"Text NEBYL uložen ({type(e).__name__}: {e}) - "
                              "zkus to znovu."}, status_code=500)
        return {"ok": True}
```

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
- Modify: `src/review_ui/polish_server.py`, `main.py` (`_client_factory`,
  kolo 11 BLOCKING), `src/llm/client.py` (`PipelineLLMClient`, kolo 11
  BLOCKING)
- Test: `tests/test_polish_server.py`, `tests/test_pipeline_client.py`
  (existující soubor, `PipelineLLMClient` unit testy - kolo 11 BLOCKING)

**Interfaces:**
- Consumes: `main._polish_one_chapter`, `main._polish_preflight` (Task 5),
  `state.create_run`/`finish_run`, `main._client_factory`.
- Produces: `POST /api/polish/regenerate` - payload `{"idx": int}` →
  `{"styled": str, "findings": list[dict], "reason_types": list[str]}` -
  NIC nezapisuje do `chapters`/historie (`runs`/`llm_calls` bookkeeping
  ANO, viz "Poznámka k zámku"). 404 pro neexistující kapitolu, 400 pro
  status mimo `_EDITABLE_STATUSES` (Task 9), 503 pro preflight/zámek.
  `main._client_factory` dostává NOVÝ volitelný parametr `require_lock`
  (kolo 11 BLOCKING) - `None` výchozí (`_cmd_run`/`scan`/`_cmd_polish_review`
  preflight volání beze změny), server ho vyplní `app.state.require_lock`,
  `_cmd_polish` (Task 5 Step 8, kolo 13 IMPORTANT) `main._lock_still_
  owned`. `PipelineLLMClient` (`src/llm/client.py`) dostává STEJNÉ jméno
  parametru, kontroluje ho PŘED každým `.complete()` voláním A TĚSNĚ
  před `record_llm_call` (kolo 12 BLOCKING).

**Poznámka k zámku:** tenhle endpoint nemění `chapters`/historii, ale
`_client_factory`/`state.create_run`/`finish_run` VŽDY zapisují audit
řádky (`runs`, `llm_calls`) - NENÍ tedy pravda, že "nic nezapisuje".
Nepotřebuje `write_lock` (ten serializuje jen zápisy, co se mohou
překrývat na STEJNÉ kapitole/knize - dva souběžné `regenerate` na RŮZNÝCH
kapitolách si nepřekáží), ale MUSÍ ověřit, že server ještě vlastní
zámek (`app.state.require_lock()`, BEZ `write_lock` kolem - jen levná
kontrola, ne serializace), než jakýkoli DB zápis (i auditní) provede -
**NA VŠECH třech místech, ne jen jednou na začátku (kolo 11 BLOCKING):**
před `create_run`/`_client_factory` (na začátku handleru), PŘED KAŽDÝM
`.complete()` voláním uvnitř `_polish_one_chapter` (kritik/stylist_check,
přes nový `require_lock` parametr `PipelineLLMClient`/`_client_factory`,
viz Step 3 níž), a znovu těsně před `finish_run` (kolo 10, `finally`
blok). Dlouhé Codex volání (`stylist.polish()`) mezi těmihle body může
trvat dost dlouho na to, aby zámek mezitím (vzácně - existující heartbeat
vlákno riziko z větší části kryje) skutečně ztratil.
`_client_factory(rid, interactive=False)` - NIKDY `interactive=True` na
serveru (`PipelineLLMClient`'s cost guard by na `input()` zablokoval
HTTP request bez připojeného terminálu, `src/llm/client.py:152-169`);
`interactive=False` cost-guard překročení vyhodí `FatalRunError` místo
čekání na vstup, endpoint to zachytí a vrátí 500.

- [ ] **Step 1: Napiš test**

`tests/test_polish_server.py` dnes nemá `import main`/`import config` na
úrovni modulu (jen lazy `import main` uvnitř endpointů) - přidej OBOJÍ
nahoru k existujícím importům (`import json`, `import os`, ...), tenhle
task je bude potřebovat napřímo:

```python
import config
import main
```

```python
def test_regenerate_returns_styled_text_without_writing(tmp_path, monkeypatch):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)   # `_client_factory` účtuje SEM
                                                  # (main.py:56 - natvrdo
                                                  # `config.DB_PATH`, ne
                                                  # parametr), jinak by
                                                  # `runs`/`llm_calls`
                                                  # zápisy mířily do
                                                  # SKUTEČNÉ projektové DB
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    # Kolo 6 IMPORTANT oprava - endpoint teď volá `_polish_one_chapter`
    # i s `rendered_terms=rt` (kolo 5) - mock BEZ tohohle keyword parametru
    # by spadl na `TypeError: unexpected keyword argument`, endpoint by
    # to zachytil a vrátil 500 místo očekávaných 200/styled dat.
    seen = {}
    def _fake_polish_one_chapter(c, gr, cf, db_, model, codex_cmd, rendered_terms=None):
        seen["rendered_terms"] = rendered_terms
        return {"idx": 1, "title": "K1", "cz_before": "Věta 1.",
               "styled": "Vylepšená věta 1.", "revision_rounds": 0,
               "reason_types": [], "findings": [], "rendered_terms": [],
               "draft_id": "d1"}
    monkeypatch.setattr("main._polish_one_chapter", _fake_polish_one_chapter)
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert seen["rendered_terms"] == []   # `_preferred_rendered_terms` bez historie = živá DB (fixture prázdná)
    assert r.status_code == 200
    assert r.json()["styled"] == "Vylepšená věta 1."
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Věta 1."   # NEZMĚNĚNO


def test_regenerate_404_for_missing_chapter(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 99})
    assert r.status_code == 404


def test_regenerate_400_for_pending_chapter(tmp_path):
    """`pending` nemá smysluplný `translated_text` k polishi - `flagged`/
    `needs_human`/`error` naopak PROJDOU (stejné `_EDITABLE_STATUSES`
    jako Task 9 save)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='pending' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 400


def test_regenerate_400_for_error_status_without_translated_text(tmp_path):
    """Kolo 5 IMPORTANT - `status='error'` je v `_EDITABLE_STATUSES`,
    ale `run` ho může nastavit i s `translated_text=NULL` (první
    neúspěšný pokus o překlad) - musí to dostat čitelnou 400, ne spadnout
    hluboko v `_polish_one_chapter`."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='error', translated_text=NULL WHERE idx=1")
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


def test_regenerate_503_when_lock_lost_inside_polish_one_chapter(tmp_path, monkeypatch):
    """Kolo 16 IMPORTANT (test OPRAVEN kolo 17 BLOCKING - dřív mockoval
    `_polish_one_chapter` tak, aby `LockLostError` vyhodilo PŘÍMO, což
    obcházelo REÁLNÉ `except FatalRunError` uvnitř tý funkce a skrylo
    skutečný bug: ten blok `LockLostError` přebaloval na obyčejný
    `FatalRunError`, typ se ztrácel, `except main.LockLostError` v
    endpointu ho nikdy nechytilo. Tenhle test jde přes SKUTEČNOU
    `_polish_one_chapter` → `PipelineLLMClient.complete()` → `require_
    lock` kontrolu, aby tenhle konkrétní bug pokryl."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    from src.llm.client import FakeLLMClient
    # `AnthropicClient()` nahrazen - `_client_factory` (main.py:52) ji
    # volá NATVRDO uvnitř `factory(agent)`, i když se nikdy nepoužije
    # (require_lock kontrola vyhodí LockLostError PŘED `self._inner.
    # complete()`, viz PipelineLLMClient.complete() výš) - prázdná
    # fronta odpovědí stačí, `FakeLLMClient([]).complete()` se nikdy
    # nezavolá.
    monkeypatch.setattr(main, "AnthropicClient", lambda: FakeLLMClient([]))
    calls = {"n": 0}
    def _require_lock():
        calls["n"] += 1
        return calls["n"] == 1   # True JEN napoprvé (start handleru)
    app.state.require_lock = _require_lock
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503
    assert "Zámek ztracen" in r.json()["error"]


def test_regenerate_returns_json_500_when_create_run_raises(tmp_path, monkeypatch):
    """Kolo 14 IMPORTANT - `state.create_run` bylo mimo `try` - selhání
    (SQLite chyba apod.) by propadlo jako NEZACHYCENÝ traceback (holý
    500 bez JSON těla) místo řízené odpovědi jako u každého jiného
    selhání v tomhle handleru."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr(state, "create_run",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk plný")))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 500
    assert "error" in r.json()   # řízená JSON odpověď, ne holý traceback


def test_regenerate_503_and_no_run_created_when_lock_lost_before_create_run(tmp_path, monkeypatch):
    """Kolo 13 IMPORTANT - `require_lock()` kontrola musí být POSLEDNÍ
    věc PŘED `state.create_run(...)`, ne mít mezi sebou další volání
    (`glossary.all_terms` bylo dřív AŽ PO kontrole - přesunuto PŘED).
    Ověř, že `require_lock() == False` zastaví PŘED jakýmkoli zápisem -
    žádný `runs` řádek nevznikne."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM runs"))
    assert rows == []   # `create_run` se vůbec nezavolalo


def test_regenerate_uses_client_factory_with_require_lock_callback(tmp_path, monkeypatch):
    """Kolo 11 BLOCKING - endpoint MUSÍ `_client_factory` zavolat s
    `require_lock=app.state.require_lock`, jinak `PipelineLLMClient`
    uvnitř `_polish_one_chapter` nemá jak zámek ověřit PŘED KAŽDÝM LLM
    voláním (viz `tests/test_pipeline_client.py` pro samotné chování
    `PipelineLLMClient` - tenhle test ověřuje jen DRÁTOVÁNÍ na úrovni
    endpointu)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    seen = {}
    def _fake_client_factory(rid, *, interactive, require_lock=None):
        seen["require_lock"] = require_lock
        return lambda agent: None   # nepoužije se, _polish_one_chapter se mockuje níž
    monkeypatch.setattr("main._client_factory", _fake_client_factory)
    monkeypatch.setattr("main._polish_one_chapter",
                        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None:
                            {"idx": c["idx"], "outcome": "unchanged"})
    client = TestClient(app)
    client.post("/api/polish/regenerate", json={"idx": 1})
    assert seen["require_lock"] is app.state.require_lock


def test_regenerate_skips_finish_run_when_lock_lost_during_codex_call(tmp_path, monkeypatch):
    """Kolo 10 IMPORTANT - `require_lock()` na ZAČÁTKU handleru neručí za
    vlastnictví O CHVÍLI POZDĚJI (dlouhé Codex volání mezitím). Druhé
    volání (ve `finally`, těsně před `finish_run`) musí zámek ověřit
    ZNOVU a auditní zápis PŘESKOČIT, pokud ho mezitím ztratil - jinak by
    `runs`/`llm_calls` zápis proběhl bez ověřeného vlastnictví, což
    odporuje Global Constraints invariantu."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._polish_one_chapter",
                        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None:
                            {"idx": c["idx"], "outcome": "unchanged"})
    calls = {"n": 0}
    def _require_lock():
        calls["n"] += 1
        return calls["n"] == 1   # True napoprvé (start handleru), False podruhé (finally)
    app.state.require_lock = _require_lock
    finish_run_calls = []
    monkeypatch.setattr(state, "finish_run",
                        lambda *a, **k: finish_run_calls.append(a))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 422   # "unchanged" outcome, ale request se DOKONČÍ
    assert finish_run_calls == []   # finish_run se NEZAVOLALO - zámek ztracen


def test_regenerate_then_save_does_not_duplicate_old_resolved_finding(tmp_path, monkeypatch):
    """Kolo 19 BLOCKING, `known_ids` design opraven kolo 20 BLOCKING -
    `assign_ids` (Task 2) dává KAŽDÉ analýze nové náhodné `id` - "Znovu
    polish" vrátí nález s ÚPLNĚ JINÝM `id`, i kdyby šlo sémanticky o
    "podobný" problém jako dřív vyřešený nález (critic je navíc LLM, ne
    deterministický - nejde spolehnout na shodu TEXTU). Integrační test
    celého cyklu regenerate → save, co Task 9's `_merge_findings_by_id(
    ..., known_ids=...)` oprava řeší - `known_ids` posílá KLIENTŮV
    `PERSISTED_IDS` (co znal PŘI NAČTENÍ, viz Task 14 `btn-save`) -
    ověřuje, že STARÝ (klientem ZNÁMÝ, osiřelý, jinak navždy "vyřešený"
    na neexistujícím textu) nález NEPŘEŽIJE zápis skutečné textové
    změny, zatímco marker ano (na rozdíl od `test_save_chapter_text_
    change_does_not_wipe_finding_added_via_light_write`, kde starý
    nález klient NIKDY neznal a MUSÍ přežít - viz tamní test)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    # Simuluj PŘEDCHOZÍ uložení - kapitola má jeden reálný nález, už
    # VYŘEŠENÝ (resolved=True), plus marker z předchozí stylizace.
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1", (json.dumps([
            {"id": "old-f1", "resolved": True, "source": "critic",
             "type": "fidelity", "issue": "stará výhrada, už vyřešená"},
            {"id": "old-marker", "resolved": False, "source": "stylist",
             "type": "polish", "issue": "stylizováno (model=m), ..."},
        ]),))
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    fresh_finding = {"id": "new-f1", "resolved": False, "source": "critic",
                     "type": "fidelity", "issue": "nový, jiný problém"}
    monkeypatch.setattr(
        "main._polish_one_chapter",
        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None: {
            "idx": c["idx"], "title": "K1", "cz_before": c["translated_text"],
            "styled": "Regenerovaná věta.", "revision_rounds": 0,
            "reason_types": [], "findings": [dict(fresh_finding)],
            "rendered_terms": [], "draft_id": "d1"})
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 200
    regen_findings = r.json()["findings"]
    assert [f["id"] for f in regen_findings] == ["new-f1"]   # NOVÉ id, nesouvisí se starým

    # `known_ids: ["old-f1"]` - klient "old-f1" ZNAL (GET ho vrátil PŘED
    # regenerací, viz `PERSISTED_IDS`) - proto superseduje, ne "nikdy
    # neviděl" scénář z `test_save_chapter_text_change_does_not_wipe_...`.
    r2 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Regenerovaná věta.",
        "findings": regen_findings, "styled_by_codex": "Regenerovaná věta.",
        "known_ids": ["old-f1"]})
    assert r2.status_code == 200
    saved = json.loads(state.get_chapter(db, 1)["notes"])
    non_marker = [f for f in saved if f["source"] != "stylist"]
    marker = [f for f in saved if f["source"] == "stylist"]
    assert len(non_marker) == 1   # starý "old-f1" NEPŘEŽIL - žádná duplicita
    assert non_marker[0]["id"] == "new-f1"
    assert non_marker[0]["resolved"] is False   # nový, nevyřešený - NENÍ tiše "vyřešený"
    assert any(f["id"] == "old-marker" for f in marker)   # STARÝ marker zachován
    # nový marker od `_commit_polish_result` PŘIBYDE navíc (STEJNÝ `type`,
    # NOVÉ `id`) - staré markery se NIKDY nemažou, jen se hromadí, na
    # rozdíl od reálných nálezů výš.
    assert len(marker) == 2


def test_regenerate_reject_candidate_then_light_save_does_not_duplicate(tmp_path, monkeypatch):
    """Kolo 21 BLOCKING - STEJNÁ duplicitní chyba jako kolo 19/20, tentokrát
    na LEHKÉ větvi (`text == cz_before`) - uživatel klikne "Znovu polish"
    (fresh id nález), NEPŘIJME kandidát (textarea necha PŮVODNÍ text), ale
    STEJNĚ uloží (např. jen zaškrtne nález) - `CURRENT_FINDINGS` na
    klientovi pořád drží ČERSTVĚ regenerovaný nález (editor.html ho
    nahradí při "Znovu polish" bez ohledu na to, jestli uživatel kandidát
    later přijme). Bez `known_ids` i na lehké větvi by se osiřelý starý
    nález hromadil vedle nového PŘI KAŽDÉM takovém cyklu."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1", (json.dumps([
            {"id": "old-f1", "resolved": True, "source": "critic",
             "type": "fidelity", "issue": "stará výhrada, už vyřešená"},
        ]),))
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    fresh_finding = {"id": "new-f1", "resolved": False, "source": "critic",
                     "type": "fidelity", "issue": "nový, jiný problém"}
    monkeypatch.setattr(
        "main._polish_one_chapter",
        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None: {
            "idx": c["idx"], "title": "K1", "cz_before": c["translated_text"],
            "styled": "Odmítnutý kandidát.", "revision_rounds": 0,
            "reason_types": [], "findings": [dict(fresh_finding)],
            "rendered_terms": [], "draft_id": "d1"})
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 200
    regen_findings = r.json()["findings"]

    # Uživatel NEPŘIJAL kandidát - `text` je pořád PŮVODNÍ ("Věta 1."),
    # ale `findings` posílá ČERSTVÉ (z odmítnuté regenerace, tak jak je
    # editor.html drží v `CURRENT_FINDINGS`).
    r2 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.",
        "findings": regen_findings, "known_ids": ["old-f1"]})
    assert r2.status_code == 200
    saved = json.loads(state.get_chapter(db, 1)["notes"])
    non_marker = [f for f in saved if f["source"] != "stylist"]
    assert len(non_marker) == 1   # starý "old-f1" NEPŘEŽIL - žádná duplicita
    assert non_marker[0]["id"] == "new-f1"
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_polish_server.py -k regenerate -v`
Expected: FAIL - 404 (route neexistuje)

- [ ] **Step 2b: Napiš test na `PipelineLLMClient`'s `require_lock` (kolo 11 BLOCKING)**

Přidej DO `tests/test_pipeline_client.py` (existující soubor - viz tamní
`_db(tmp_path)` fixture a existující importy, Step 3 níž rozšiřuje
samotnou `PipelineLLMClient`, tenhle test ověřuje JEJÍ chování přímo, ne
přes HTTP jako testy výš):

```python
def test_require_lock_false_raises_fatal_before_llm_call_and_no_log_row(tmp_path):
    """Kolo 11 BLOCKING - `require_lock` callback vracející `False` MUSÍ
    zastavit PŘED skutečným voláním (žádná zbytečná útrata) A PŘED
    `record_llm_call` (žádný auditní zápis bez ověřeného vlastnictví
    zámku)."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    inner = FakeLLMClient([Completion("ok", False, 100, 50)])
    c = PipelineLLMClient(inner, run_id=rid, agent="critic", db_path=db,
                          config_mod=config, require_lock=lambda: False)
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    assert inner.calls == 0   # k reálnému volání se vůbec nedošlo
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM llm_calls"))
    assert rows == []   # žádný auditní řádek


def test_require_lock_true_proceeds_normally(tmp_path):
    """`require_lock=None` (výchozí, CLI) i `require_lock=lambda: True`
    (server, zámek pořád vlastněn) se chovají STEJNĚ - kontrola je jen
    dodatečná podmínka, ne náhrada za `_guard`/zbytek `complete()`."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    c = PipelineLLMClient(FakeLLMClient([Completion("ok", False, 100, 50)]),
                          run_id=rid, agent="critic", db_path=db,
                          config_mod=config, require_lock=lambda: True)
    c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM llm_calls"))
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"


def test_require_lock_false_blocks_before_interactive_cost_guard_prompt(tmp_path, monkeypatch):
    """Kolo 16 BLOCKING - `require_lock()==False` musí zastavit PŘED
    `_guard()`, ne jen po ní. Interaktivní cost guard (`interactive=True`)
    při překročení stropu vyzve uživatele a na potvrzení zapíše `runs.
    spend_ceiling` (`state.set_run_spend_ceiling`) - bez kontroly PŘED
    `_guard()` by tenhle zápis mohl proběhnout bez ověřeného zámku."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)   # okamžitě přes strop
    confirm_calls = {"n": 0}
    def confirm(prompt):
        confirm_calls["n"] += 1
        return "999"   # potvrdil by nový strop, KDYBY se `_guard` vůbec spustila
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, confirm=confirm,
                          require_lock=lambda: False)
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    assert confirm_calls["n"] == 0   # `_guard()` se vůbec NESPUSTILA
    assert state.get_run_spend_ceiling(db, rid) is None   # žádný zápis


def test_require_lock_lost_between_initial_check_and_user_confirm(tmp_path, monkeypatch):
    """Kolo 18 BLOCKING - zámek ztracen MEZI kolo-16 kontrolou PŘED
    `_guard()` a skutečným zápisem `set_run_spend_ceiling` uvnitř ní
    (uživatel mezitím u interaktivního promptu odpověděl, zámek zatím
    zmizel). `require_lock` vrátí `True` napoprvé (kontrola PŘED
    `_guard()`), `False` podruhé (kontrola TĚSNĚ před zápisem uvnitř
    `_guard()`) - na rozdíl od `test_require_lock_false_blocks_before_
    interactive_cost_guard_prompt` (kolo 16, zámek ztracen OD ZAČÁTKU,
    `_guard()` se vůbec nespustí) tady `confirm` callback SE zavolá -
    ověřuje jinou část okna."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    confirm_calls = {"n": 0}
    def confirm(prompt):
        confirm_calls["n"] += 1
        return "999"
    calls = {"n": 0}
    def _require_lock():
        calls["n"] += 1
        return calls["n"] == 1   # True PŘED _guard(), False těsně před zápisem uvnitř ní
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, confirm=confirm,
                          require_lock=_require_lock)
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    assert confirm_calls["n"] == 1   # `_guard()` SE spustila, uživatel odpověděl
    assert state.get_run_spend_ceiling(db, rid) is None   # ale zápis NEPROBĚHL


def test_require_lock_lost_during_call_skips_log_but_keeps_result(tmp_path):
    """Kolo 12 BLOCKING - zámek ztracen AŽ BĚHEM `_inner.complete()`
    (callback vrátí `True` napoprvé - kontrola PŘED voláním - a `False`
    podruhé - kontrola ve `finally` PŘED zápisem). Výsledek se i tak
    VRÁTÍ (peníze už utracené, výsledek nezahazuj) - jen SE NEZAPÍŠE
    auditní řádek, a NEVYHODÍ se výjimka (na rozdíl od kontroly PŘED
    voláním, kde ještě nic neproběhlo)."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    calls = {"n": 0}
    def _require_lock():
        calls["n"] += 1
        return calls["n"] == 1   # True před voláním, False těsně před zápisem
    c = PipelineLLMClient(FakeLLMClient([Completion("ok", False, 100, 50)]),
                          run_id=rid, agent="critic", db_path=db,
                          config_mod=config, require_lock=_require_lock)
    comp = c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    assert comp.text == "ok"   # výsledek se VRÁTIL, žádná výjimka
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM llm_calls"))
    assert rows == []   # ale auditní řádek se NEZAPSAL
```

(`_db`/`state`/`config`/`FakeLLMClient`/`Completion`/`PipelineLLMClient`/
`FatalRunError`/`pytest` - VŠECHNY už importované na začátku souboru,
viz existující testy tamtéž.)

- [ ] **Step 2c: Ověř selhání (`PipelineLLMClient` testy)**

Run: `pytest tests/test_pipeline_client.py -k require_lock -v`
Expected: FAIL - `TypeError: __init__() got an unexpected keyword argument 'require_lock'`

- [ ] **Step 3: Implementuj**

**Kolo 11 BLOCKING - `require_lock()` na začátku handleru (a kolo-10
re-check před `finish_run`) NEPOKRÝVÁ zápisy UVNITŘ `_polish_one_chapter`
samotné.** `cf("critic")`/`cf("stylist_check")` (main.py, uvnitř
`_polish_one_chapter`) jsou `PipelineLLMClient` instance
(`src/llm/client.py:103`) - KAŽDÉ jejich `.complete()` volání zapisuje
`llm_calls` řádek (`state.record_llm_call`, `src/llm/client.py:191-196`)
NEZÁVISLE na kontrole nahoře v handleru. Kritik i "stylist_check" mohou
udělat víc než jedno volání (retry na neplatnou odpověď) - dlouhé Codex
volání (`stylist.polish()`, samostatný subprocess, BEZE ZÁPISU do
`llm_calls` - jen `cf(...)` klienti tam zapisují) mezitím může trvat
dost dlouho na to, aby se OKNO mezi startovním checkem a těmihle
vnitřními zápisy stalo relevantní. `PipelineLLMClient`/`_client_factory`
JSOU sdílené se `_cmd_run`/`_cmd_polish` (CLI) - tam žádná per-call
kontrola nepotřeba (CLI proces drží OS zámek po celou dobu běhu, žádný
HTTP request na pozadí ho nemůže "ukrást" jinak než přes `_LOCK_STALE_
SECONDS` stárnutí, což `_cmd_polish`'s vlastní `refresh_lock` v Task 5
Step 8 už řeší). Fix: volitelný `require_lock` callback, defaultně
`None` (CLI volající ho nepředávají, chování BEZE ZMĚNY), server ho
předá.

**Kolo 16 IMPORTANT - server rozlišuje 503 (zámek) od 500 (jiná chyba),
ale ztráta zámku uvnitř `PipelineLLMClient.complete()` dnes vyhazuje
obyčejný `FatalRunError` - endpointův `except Exception` (Step 3 níž) by
ho namapoval na 500, ne 503, přestože je to STEJNÁ podmínka jako
startovní `require_lock()` kontrola (ta 503 vrací).** Přidej rozlišitelnou
podtřídu do `src/llm/client.py`, hned za `class FatalRunError(RuntimeError):`
(řádek 13):

```python
class LockLostError(FatalRunError):
    """Ztráta procesního zámku - podtřída `FatalRunError`, ať VŠECHNO,
    co dnes odchytává `except FatalRunError` (CLI `_cmd_polish`'s
    `except FatalRunError as fe: raise`), dál funguje beze změny, ale
    server (Task 10) ji umí odchytit SAMOSTATNĚ a namapovat na 503
    místo obecné 500 - stejný HTTP kód jako startovní `require_lock()`
    kontrola pro STEJNOU podmínku."""
```

`complete()`'s obě `require_lock` kontroly (viz níž, kód JIŽ upraven
tak, aby vyhazoval `LockLostError` místo obyčejného `FatalRunError`) a
regenerate endpointu (Step 3 níž, `except main.LockLostError` PŘED
obecným `except Exception` - pořadí je významné, specifičtější MUSÍ být
první) - `main.LockLostError` = main.py rozšiřuje svůj existující
`from src.llm.client import FatalRunError, PipelineLLMClient, ...`
import o `LockLostError`, ať je dostupná stejně jako zbytek.

**Kolo 17 BLOCKING - `_polish_one_chapter`'s VLASTNÍ `except FatalRunError`
(main.py:620-624, existující kód, dosud NEZMĚNĚNÝ žádným Taskem) `Lock
LostError` identitu ZAHODÍ.** Blok kolem kritika/meaning-checku (main.py:
606-624) dnes vypadá:

```python
    try:
        critic_findings, critic_failed = pipeline._run_critic(en, styled, cf("critic"))
        findings += critic_findings
        reasons = _rejection_reasons(baseline_concordance, findings, cz, styled, glossary_rows)
        if critic_failed:
            reasons = [{"source": "critic", "type": "critic_failed", ...}] + reasons
        if not reasons:
            findings += stylist.check_meaning_preserved(cz, styled, cf("stylist_check"))
            reasons = _rejection_reasons(baseline_concordance, findings, cz, styled, glossary_rows)
    except FatalRunError as fe:
        raise FatalRunError(
            f"Kontrola stylizace kapitoly {idx} selhala fatálně "
            f"({stylist._redact_detail(str(fe))}) - cost guard / chyba LLM "
            "klienta, celý běh `polish` se zastavuje.") from fe
```

`cf("critic")`/`cf("stylist_check")` (`PipelineLLMClient.complete()`,
kolo 11/16 výš) může vyhodit `LockLostError` - `except FatalRunError as
fe:` ho odchytí (je to podtřída), ale VYHAZUJE NOVOU INSTANCI OBYČEJNÉHO
`FatalRunError` (ne `raise` bez argumentu, ne `fe` samo) - typová
identita `LockLostError` je tím ZTRACENA. Regenerace endpointu (Task 10)
`except main.LockLostError` by tenhle přebalený obecný `FatalRunError`
NIKDY nechytilo (chytí ho až `except Exception` → 500, ne 503 - přesně
podmínka, co měl kolo-16 fix vyřešit, ale nevyřešil). Fix - přidej
SPECIFIČTĚJŠÍ `except LockLostError: raise` PŘED `except FatalRunError`
(pořadí je významné, Python zkouší `except` klauzule v pořadí zápisu -
specifičtější MUSÍ být první, jinak by ji ta obecnější odchytila dřív):

```python
    except LockLostError:
        raise   # kolo 17 BLOCKING - zachovej typ, NEPŘEBALUJ (server
        # potřebuje `except main.LockLostError` rozlišit od obecné
        # FatalRunError, viz Task 10 "Poznámka k zámku")
    except FatalRunError as fe:
        raise FatalRunError(
            f"Kontrola stylizace kapitoly {idx} selhala fatálně "
            f"({stylist._redact_detail(str(fe))}) - cost guard / chyba LLM "
            "klienta, celý běh `polish` se zastavuje.") from fe
```

(`LockLostError` musí být v main.py IMPORTOVANÁ - už je, viz import
řádek zmíněný výš v tomhle Kroku. CLI cesta beze změny chování -
`_cmd_polish`'s `except FatalRunError as fe: raise` výš v main.py
odchytí `LockLostError` STEJNĚ jako dřív, protože je to podtřída;
`raise` beze změny zachovává typ i tam, jen bez jména.)

V `src/llm/client.py`, `PipelineLLMClient.__init__` (řádek 108) přidej
parametr:

```python
    def __init__(self, inner: LLMClient, *, run_id: int, agent: str,
                 db_path: str, config_mod, confirm=input, interactive: bool = True,
                 require_lock=None):
        self._inner = inner
        self._run_id = run_id
        self._agent = agent
        self._db = db_path
        self._cfg = config_mod
        self._confirm = confirm
        self._interactive = interactive
        self._require_lock = require_lock   # kolo 11 BLOCKING - volitelný
        # callback `() -> bool`; `None` (výchozí, `_cmd_run`/`scan`/`_cmd_
        # polish_review` preflight) = žádná kontrola, beze změny dnešního
        # chování. `_cmd_polish` (kolo 13) a server (Task 10) HO PŘEDÁVAJÍ.
```

a v `complete()` (řádek 173) přidej DVĚ kontroly - PŘED `self._guard(...)`
(kolo 16 BLOCKING, viz výš) A hned PO ní/PŘED skutečným voláním
`self._inner.complete(...)` (původní kolo 11 umístění) - selže-li
kterákoli, `record_llm_call` se dole ve `finally` VŮBEC nezavolá (žádný
`comp`/`status` se ještě nenastavil na "proběhlo", výjimka propadne rovnou
volajícímu, stejně jako `FatalRunError`/`LockLostError` z `_guard`):

```python
    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        from src import state
        # Kolo 16 BLOCKING - kontrola PŘED `_guard()`, ne jen po ní.
        # `_guard()` v INTERAKTIVNÍM režimu (`interactive=True`, CLI
        # `_cmd_polish` od kola 13) může při překročení stropu vyzvat
        # uživatele a na potvrzení zavolat `state.set_run_spend_ceiling`
        # - SKUTEČNÝ DB zápis, co by bez tyhle kontroly PROBĚHL bez
        # ověřeného vlastnictví zámku (`_guard()` definovaná NÍŽE volání
        # kontrolu vůbec nemá). Kontrola PO `_guard()` (dál dole)
        # ZŮSTÁVÁ TAKY - `_guard()` může (v interaktivním režimu) čekat
        # na uživatelský vstup libovolně dlouho, zámek může zmizet PRÁVĚ
        # BĚHEM tohohle čekání, nezávisle na tom, jestli strop nakonec
        # zapsala.
        if self._require_lock is not None and not self._require_lock():
            raise LockLostError(
                "Zámek ztracen před LLM voláním - jiný proces teď píše "
                "do DB, zastavuji dřív, než cost guard stihne zapsat "
                "nový strop bez ověřeného vlastnictví.")
        self._guard(system, user, max_tokens, model)
        if self._require_lock is not None and not self._require_lock():
            raise LockLostError(
                "Zámek ztracen během LLM volání - jiný proces teď píše "
                "do DB, zastavuji dřív, než se stihne zapsat auditní "
                "záznam bez ověřeného vlastnictví.")
        in_rate, out_rate = self._price(model)
```

**Kolo 18 BLOCKING - kontroly VÝŠ (PŘED/PO `_guard()`) NESTAČÍ na
INTERAKTIVNÍ větev `_guard()` samotné.** V interaktivním režimu
(`interactive=True`, CLI) `_guard()` při překročení stropu volá `self.
_ask(...)` - BLOKUJE na `input()`, libovolně dlouho, dokud uživatel
neodpoví - a TEPRVE PO potvrzení zapíše `state.set_run_spend_ceiling(...)`.
Kolo-16 kontrola PŘED `self._guard(...)` proběhne PŘED tímhle čekáním;
kontrola PO `self._guard(...)` proběhne AŽ PO návratu, tedy AŽ PO
zápisu, co se mezitím (uvnitř `_guard()`) UŽ STIHL ZAPSAT. Okno "uživatel
sedí u promptu a rozmýšlí se" leží MEZI oběma kontrolami, ŽÁDNÁ ho
nepokrývá. Fix - `_guard()` (metoda STEJNÉ třídy, má přímý přístup k
`self._require_lock`) dostane VLASTNÍ kontrolu TĚSNĚ PŘED `state.
set_run_spend_ceiling(...)`. Nahraď `_guard()` (src/llm/client.py:136-171)
za:

```python
    def _guard(self, system: str, user: str, max_tokens: int, model: str) -> None:
        from src import state
        in_rate, out_rate = self._price(model)
        try:
            in_tok = self._inner.count_tokens(system=system, user=user, model=model)
        except FatalRunError:
            raise
        except Exception:
            in_tok = (len(system) + len(user)) // 2
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
        for _ in range(2):
            ans = self._ask(
                f"Cost guard: utraceno ~${spent:.2f}, odhad ~${est:.2f}, "
                f"strop ${limit:.2f}. Nový strop v $ (>= ${need:.2f}) [prázdné = stop]: ")
            if not ans:
                raise FatalRunError("Cost guard: běh zastaven uživatelem.")
            try:
                new_limit = float(ans)
            except ValueError:
                continue
            if new_limit < need:
                continue
            # Kolo 18 BLOCKING - kontrola TĚSNĚ PŘED zápisem, ne jen PŘED/
            # PO `_guard()` v `complete()` (kolo 16) - `self._ask(...)`
            # výš mohl čekat na uživatele libovolně dlouho, zámek mohl
            # mezitím zmizet PRÁVĚ v tomhle okně.
            if self._require_lock is not None and not self._require_lock():
                raise LockLostError(
                    "Zámek ztracen během čekání na potvrzení cost guardu "
                    "- jiný proces teď píše do DB, zastavuji dřív, než "
                    "se stihne zapsat nový strop bez ověřeného vlastnictví.")
            state.set_run_spend_ceiling(self._db, self._run_id, new_limit)
            return
        raise FatalRunError("Cost guard: nevalidní/nízký strop, zastavuji.")
```

(zbytek metody - `_price`/`count_tokens` odhad/non-interaktivní větev -
beze změny, jen `require_lock` kontrola PŘIDÁNA těsně před `set_run_
spend_ceiling`. `LockLostError` dostupná - `src/llm/client.py` ji
definuje výš ve STEJNÉM souboru, žádný nový import netřeba.)

**Kolo 12 BLOCKING - kontrola VÝŠ nestačí sama o sobě.** `self._inner.
complete(...)` (skutečné síťové volání) se odehrává MEZI touhle kontrolou
a `record_llm_call` (dole, ve `finally`) - zámek může zmizet PRÁVĚ BĚHEM
téhle jedné síťové výměny, ne jen mezi kontrolou na začátku handleru
(Task 10) a tímhle voláním. `finally` blok (řádek 187) proto potřebuje
VLASTNÍ, druhou kontrolu, TĚSNĚ před `record_llm_call` - ale na rozdíl od
kontroly VÝŠ (kde JEŠTĚ NIC neproběhlo, `FatalRunError` je levná) se tady
`self._inner.complete(...)` UŽ ODEHRÁLO (peníze utracené, výsledek buď
existuje, nebo padla výjimka) - zahodit HOTOVÝ výsledek jen proto, že se
nepodaří zapsat AUDITNÍ řádek, by byl HORŠÍ výsledek než jeden vynechaný
řádek v `llm_calls` (stejná filosofie jako `finish_run` re-check v Task
10, kolo 10 - "bookkeeping chyba je jen diagnostická ztráta, ne důvod
zahodit skutečný výsledek"). Nahraď `finally` blok (řádek 187-196):

```python
        finally:
            it = comp.input_tokens if comp else None
            ot = comp.output_tokens if comp else None
            cost = (it / 1e6 * in_rate + ot / 1e6 * out_rate) if comp else None
            # Kolo 12 BLOCKING - DRUHÁ kontrola, TĚSNĚ před zápisem, ne
            # jen kontrola nahoře PŘED `self._inner.complete(...)` výš -
            # to síťové volání samo mohlo trvat dost dlouho na to, aby
            # zámek mezitím zmizel. Na rozdíl od kontroly nahoře (kde
            # ještě nic neproběhlo) TADY UŽ výsledek existuje (úspěch
            # nebo chyba) - jen VYNECH auditní zápis, NEVYHAZUJ výjimku
            # (ta by v `finally` přebila i úspěšný `return comp` výš a
            # zahodila HOTOVÝ, zaplacený výsledek jen kvůli neschopnosti
            # zapsat diagnostický řádek).
            if self._require_lock is None or self._require_lock():
                state.record_llm_call(
                    self._db, run_id=self._run_id, agent=self._agent,
                    provider=getattr(self._inner, "provider", "unknown"),
                    model=model, input_tokens=it, output_tokens=ot, cost_usd=cost,
                    truncated=bool(comp.truncated) if comp else False,
                    status=status, error_class=err)
```

(zbytek `complete()` - `_price`/`try`/`except` - beze změny, jen `finally`
tělo se nahrazuje výš. Kontrola PŘED voláním na začátku funkce zůstává
TAKY - obě existují SOUČASNĚ, chrání JINÝ moment: ta na začátku ušetří
zbytečné utrácení, když už VÍME, že zámek je pryč; tahle ve `finally`
chrání moment TĚSNĚ před zápisem, kdy se to mohlo změnit MEZITÍM.)

V `main.py`'s `_client_factory` (main.py:52) přidej stejný volitelný
průchozí parametr:

```python
def _client_factory(run_id: int, *, interactive: bool, require_lock=None):
    """Klienta staví až při volání - `run` s fake pipeline nikdy nesáhne na API."""
    def factory(agent: str):
        return PipelineLLMClient(AnthropicClient(), run_id=run_id, agent=agent,
                                 db_path=config.DB_PATH, config_mod=config,
                                 interactive=interactive, require_lock=require_lock)
    return factory
```

Volání uvnitř endpointu (kód níž, uvnitř `try:`) proto MUSÍ znít
`main._client_factory(rid, interactive=False, require_lock=app.state.
require_lock)`, NE bez posledního argumentu - viz `cf = ...` řádek v
kódu níž. (`_cmd_run`/`_cmd_polish` volají `_client_factory(rid,
interactive=...)` BEZE ZMĚNY - `require_lock=None` výchozí, existující
testy na CLI se nerozbijí.)

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
        # `status not in _EDITABLE_STATUSES` NESTAČÍ (kolo 5 IMPORTANT) -
        # `run`/`_cmd_run` může nastavit `status="error"` PŘI PRVNÍM
        # neúspěšném pokusu o překlad, s `translated_text` pořád `NULL`
        # (main.py, `_cmd_run`/`pipeline.process_chapter`). `stylist.
        # polish(en, cz, ...)` s `cz=None` by spadlo na typové chybě
        # hluboko uvnitř `_polish_one_chapter`, ne na čitelné 400 tady.
        if row["status"] not in _EDITABLE_STATUSES or row["translated_text"] is None:
            return JSONResponse(
                {"error": f"kapitola má status {row['status']!r} bez použitelného "
                          "textu, nelze polishovat"}, status_code=400)
        model, codex_cmd, preflight_err = main._polish_preflight()
        if preflight_err:
            return JSONResponse({"error": preflight_err}, status_code=503)
        # Kolo 13 IMPORTANT - `glossary.all_terms` (čtení, žádný zápis)
        # PŘESUNUTO PŘED kontrolu zámku, ne po ní - kontrola má být
        # POSLEDNÍ věc před PRVNÍM zápisem (`create_run` níž), ne mít
        # mezi sebou další volání (byť rychlé/lokální), co by teoreticky
        # mohlo o chvilku prodloužit okno.
        glossary_rows = glossary.all_terms(db_path)
        # Levná kontrola vlastnictví zámku (NE `write_lock` - `runs`/
        # `llm_calls` bookkeeping se nepřekrývá s kapitolovými zápisy
        # jiných requestů, serializace by jen zbytečně blokovala save/
        # export na JINÝCH kapitolách po dobu Codex volání).
        if not app.state.require_lock():
            return JSONResponse({"error": "zámek ztracen"}, status_code=503)

        rid = None
        status = "fatal"
        # Kolo 14 IMPORTANT - `rid = state.create_run(...)` PŘESUNUTO
        # dovnitř `try` (bylo mimo, PŘED blokem) - selhání SQLite zápisu
        # (disk plný, DB zamčená JINÝM procesem navzdory našemu app-level
        # zámku, apod.) by jinak propadlo jako NEZACHYCENÝ traceback
        # (holý FastAPI 500 bez JSON těla), místo řízené chybové odpovědi
        # jako u KAŽDÉHO jiného selhání v tomhle handleru. `rid = None`
        # inicializace PŘED `try` - `finally` níž díky tomu pozná, jestli
        # `create_run` vůbec stihlo proběhnout (viz tam).
        #
        # `cf` konstrukce taky uvnitř `try` (kolo 4 IMPORTANT) - i kdyby
        # `_client_factory` samo selhalo (nepravděpodobné, ale `create_run`
        # už vytvořilo řádek v DB), `finally` níž musí dostat šanci ten
        # run uzavřít, jinak zůstane trvale "processing".
        try:
            rid = state.create_run(db_path, "polish")
            # `interactive=False` - NIKDY True na serveru (cost-guard
            # `input()` by zablokoval HTTP request bez terminálu, viz
            # "Poznámka k zámku"). `require_lock=app.state.require_lock`
            # (kolo 11 BLOCKING) - `PipelineLLMClient` teď ověří zámek
            # PŘED KAŽDÝM `.complete()` (kritik/stylist_check volání
            # uvnitř `_polish_one_chapter`), ne jen jednou na začátku
            # handleru.
            cf = main._client_factory(rid, interactive=False,
                                      require_lock=app.state.require_lock)
            c = {"idx": row["idx"], "title": row["title"], "raw_text": row["raw_text"],
                "translated_text": row["translated_text"],
                "revision_rounds": row["revision_rounds"]}
            # STEJNÁ `rendered_terms` volba jako dávka/save (kolo 5
            # IMPORTANT konzistence, viz Task 3/5) - i PŘEDBĚŽNÝ náhled
            # z regenerace má ukázat nálezy odpovídající tomu, co by
            # SKUTEČNĚ zapsalo uložení téhle regenerace.
            history, err = _try_load_history(history_path)
            if err:
                return err
            rt = main._preferred_rendered_terms(
                db_path, idx, row["translated_text"], history["entries"])
            rec = main._polish_one_chapter(c, glossary_rows, cf, db_path, model, codex_cmd,
                                           rendered_terms=rt)
            # `status="ok"` i pro `rec["outcome"] == "failed"` (Codex CLI
            # selhal, ne infrastruktura) - stejná konvence jako dávkový
            # `_cmd_polish` (per-kapitolové selhání NEznamená `run_status
            # ="fatal"`, jen `FatalRunError`/výjimka odsud výš to udělá).
            status = "ok"
        except main.LockLostError as e:
            # Kolo 16 IMPORTANT - STEJNÁ podmínka jako startovní `require_
            # lock()` kontrola výš (ta vrací 503) - ztráta zámku uvnitř
            # `PipelineLLMClient.complete()` (kritik/stylist_check volání)
            # musí dostat STEJNÝ kód, ne obecnou 500 z větve níž. `except`
            # POŘADÍ je významné - specifičtější MUSÍ být PŘED obecným
            # `except Exception`, jinak by ho ten odchytil dřív.
            return JSONResponse({"error": f"Zámek ztracen: {e}"}, status_code=503)
        except Exception as e:
            return JSONResponse(
                {"error": f"Regenerace selhala ({type(e).__name__}: {e})"},
                status_code=500)
        finally:
            # `finish_run` selhání NESMÍ přebít odpověď výš (kolo 2
            # BLOCKING) - výjimka vyhozená z `finally` by nahradila i
            # `return` z `except` bloku nezachycenou 500 bez JSON těla.
            # Bookkeeping chyba tu je jen diagnostická ztráta, ne důvod
            # zahodit skutečný výsledek regenerace.
            #
            # Kolo 10 IMPORTANT - znovu ověř zámek TĚSNĚ PŘED zápisem
            # (`app.state.require_lock()` == `_require_lock()`, viz
            # `polish_server.py:182-199` - existující, NEZMĚNĚNÁ
            # infrastruktura tohohle souboru, SYNCHRONNĚ volá `state.
            # refresh_lock` a vrací `False`, pokud zámek mezitím ztratil).
            # `_polish_one_chapter` (řádek výš) může u pomalé Codex
            # odpovědi běžet dlouho - `require_lock()` na ZAČÁTKU handleru
            # (výš) ověřilo vlastnictví PŘED voláním, ale samo o sobě
            # nezaručuje, že ho pořád vlastníme O CHVÍLI POZDĚJI. Zdejší
            # `_heartbeat` vlákno (`polish_server.py:164-180`) zámek mezitím
            # nezávisle na týhle requestu periodicky obnovuje, takže
            # ztráta uprostřed JEDNÉ regenerace je nepravděpodobná - přesto
            # kdyby k ní došlo (jiný proces zámek mezitím převzal), zápis
            # auditních řádků (`runs`/`llm_calls`) BEZ vlastnictví zámku
            # by odporoval Global Constraints invariantu ("žádný zápis
            # tenhle vzor neobchází") - radši ho v tom vzácném případě
            # PŘESKOČIT (diagnostická ztráta pár řádků) než zapsat bez
            # ověřeného vlastnictví.
            #
            # Kolo 14 IMPORTANT - `rid is not None` navíc: pokud `state.
            # create_run(...)` výš SAMO selhalo (viz nahoře), `rid`
            # zůstalo `None` - žádný run vůbec nevznikl, `finish_run` by
            # dostalo neplatné `rid` a samo by vyhodilo (i když by ho
            # tenhle `except Exception: pass` stejně potichu spolkl -
            # kontrola napřed je ale čitelnější a nezávisí na tom, že
            # `finish_run` na neplatné `rid` zrovna vyhodí místo tichého
            # no-opu).
            try:
                if rid is not None and app.state.require_lock():
                    state.finish_run(db_path, rid, status)
            except Exception:
                pass
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

Run: `pytest tests/test_polish_server.py -k regenerate -v tests/test_pipeline_client.py -v`
Expected: PASS - obojí, VČETNĚ existujících `test_pipeline_client.py`
testů (kolo 11 BLOCKING - `require_lock` parametr je čistě přídavný,
`None` výchozí, žádné existující volání se nemění).

- [ ] **Step 5: Commit**

```bash
git add src/review_ui/polish_server.py main.py src/llm/client.py \
       tests/test_polish_server.py tests/test_pipeline_client.py
git commit -m "feat: POST /api/polish/regenerate - znovu-polish jedné kapitoly bez zápisu

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: `polish_server.py` - `POST /api/findings/resolve`

**Files:**
- Modify: `src/review_ui/polish_server.py`
- Test: `tests/test_polish_server.py`

**Interfaces:**
- Consumes: `findings.set_resolved` (Task 2), `main._parse_findings`.
- Produces: `POST /api/findings/resolve` - payload
  `{"scope": "notes", "idx": int, "finding_id": str, "resolved": bool}` →
  `{"ok": true}` nebo 404 (nenalezeno) / 400 (špatný tvar) / 503 (zámek
  ztracen). **Kolo 17 IMPORTANT - `scope="history"` byla ODSTRANĚNA**
  (viz zdůvodnění pod Step 3 níž) - `scope` teď akceptuje JEN `"notes"`,
  pole zůstává (ne zjednodušeno na bezparametrový endpoint), aby byl
  kontrakt vpřed kompatibilní, kdyby se editace historie v budoucnu
  přece jen ukázala jako potřebná (samostatný, budoucí task by pak
  musel řešit i notes/history divergenci popsanou níž, ne jen přidat
  zpátky větev).

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


def test_resolve_finding_400_for_history_scope(tmp_path):
    """Kolo 17 IMPORTANT - `scope="history"` ODSTRANĚNA (byla dead code -
    žádný UI prvek ji nikdy nevolal, `renderFindings`/`toggleResolved`
    posílají VŽDY `scope: 'notes'`, viz Task 14). Editace `polish.
    history.json` nezávisle na `chapters.notes` by vytvořila DIVERGENTNÍ
    `resolved` hodnoty pro nález, co uživatel vnímá jako "stejný" - UI/
    report čtou VÝHRADNĚ `chapters.notes` (Task 8/12 design), takže
    "history" resolve by tiše vrátilo 200 a NIC viditelného by se
    nezměnilo."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "history", "idx": 1, "finding_id": "h1", "resolved": True})
    assert r.status_code == 400


def test_resolve_finding_calls_backup_db_once(tmp_path):
    """Kolo 22 IMPORTANT - `_backup_db_once` CHYBĚLO v tomhle endpointu -
    pokud je resolve PRVNÍ mutující operace session (uživatel otevře
    editor a rovnou něco zaškrtne, nikdy neuloží/neregeneruje), startovní
    snapshot by se při čistém vypnutí serveru smazal (`backup_state[
    'done']` by zůstalo `False`), i když reálný DB zápis proběhl -
    uživatel by přišel o obnovitelnou zálohu stavu PŘED touhle session."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    assert app.state.backup_state["done"] is False
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "notes", "idx": 1, "finding_id": "f1", "resolved": True})
    assert r.status_code == 200
    assert app.state.backup_state["done"] is True


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
        # Kolo 17 IMPORTANT - `scope="history"` ODSTRANĚNA. Editovala
        # `polish.history.json` NEZÁVISLE na `chapters.notes`, co ale
        # UI/report (Task 8 GET, Task 12 report) čtou jako JEDINÝ zdroj
        # "aktuálního" stavu nálezů - "history" resolve by tiše vrátilo
        # 200, žádný checkbox/počet by se ale NEZMĚNIL, a stejný nález
        # (jiné `id`, protože `assign_ids` generuje NEZÁVISLE napříč
        # `notes`/historií) by mohl mít DIVERGENTNÍ `resolved` hodnotu na
        # dvou místech. Navíc ŽÁDNÝ prvek UI ji nikdy nevolal - `toggle
        # Resolved` (Task 14) posílá VŽDY `scope: 'notes'` natvrdo -
        # mrtvý, matoucí kód. `scope` pole v payloadu ZŮSTÁVÁ (ne
        # zjednodušeno pryč) kvůli vpřed kompatibilitě kontraktu.
        if (scope != "notes" or type(idx_raw) is not int
                or not isinstance(finding_id, str) or not isinstance(resolved, bool)):
            return JSONResponse(
                {"error": "scope musí být notes, idx int, finding_id "
                          "string, resolved bool"}, status_code=400)
        idx = idx_raw

        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            import main
            row = state.get_chapter(db_path, idx)
            if row is None:
                return JSONResponse({"error": "kapitola neexistuje"}, status_code=404)
            notes_findings = main._parse_findings(row["notes"])
            if not findings.set_resolved(notes_findings, finding_id, resolved):
                return JSONResponse({"error": "nález nenalezen"}, status_code=404)
            import json as _json
            try:
                # Kolo 22 IMPORTANT - `_backup_db_once` CHYBĚLO - OBĚ
                # větve Tasku 9 ho volají (přímo nebo přes `_commit_
                # polish_result`), tenhle endpoint ne. Pokud je resolve
                # PRVNÍ mutující operace v týhle serverové session (user
                # otevře editor a rovnou něco zaškrtne, nikdy neuloží/
                # neregeneruje), `backup_state["done"]` zůstane `False` -
                # startovní snapshot (vytvořený PŘI STARTU serveru) se
                # při čistém vypnutí smaže (`finally` v `run_polish_
                # review_server`, "if not backup_state['done']: os.remove
                # (...)") a uživatel PŘIJDE o obnovitelnou zálohu stavu
                # PŘED touhle session, přestože reálný DB zápis proběhl.
                main._backup_db_once(db_path, app.state.backup_state)
                with state.connect(db_path) as conn:
                    # Kolo 18 NIT - `updated_at=CURRENT_TIMESTAMP` chybělo -
                    # seznam kapitol (Task 8/14) zobrazuje "Naposled
                    # upraveno" z tohohle sloupce, bez aktualizace by po
                    # zaškrtnutí nálezu ukazoval STARÝ čas, i když se
                    # kapitola právě změnila.
                    conn.execute("UPDATE chapters SET notes=?, "
                                "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                                (_json.dumps(notes_findings, ensure_ascii=False), idx))
            except Exception as e:
                return JSONResponse(
                    {"error": f"Zápis nálezu selhal ({type(e).__name__}: {e})"},
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
        report = findings_report.build_findings_report(db_path)
        return HTMLResponse(findings_report.render_findings_html(report))

    @app.post("/api/export")
    def post_export(payload: dict = None):
        # `write_lock` - NENÍ tu zápis do DB, ale export musí vidět
        # KONZISTENTNÍ snímek knihy (Global Constraints). Souběžný
        # `POST /api/chapter/{idx}/save` (Task 9) běží uvnitř STEJNÉHO
        # `write_lock` - bez obalení tady by export mohl přečíst část
        # kapitol PŘED a část PO souběžném uložení, kniha+report by pak
        # neodpovídaly ŽÁDNÉMU skutečnému stavu DB. `require_lock()`
        # navíc odmítne export, když tenhle proces ztratil vlastnictví
        # zámku (jiný proces teď legitimně píše mimo tenhle server).
        with write_lock:
            if not app.state.require_lock():
                return JSONResponse({"error": "zámek ztracen"}, status_code=503)
            import main
            book_path, skipped = main.export_book(db_path, only_done=False)
            report = findings_report.build_findings_report(db_path)
            findings_path = os.path.splitext(book_path)[0] + ".findings.txt"
            with open(findings_path, "w", encoding="utf-8") as f:
                f.write(findings_report.render_findings_txt(report))
        return {"book_path": book_path, "findings_path": findings_path,
               "skipped": skipped}
```

(`payload: dict = None` - FastAPI přijme prázdné tělo requestu; export
nic z requestu nečte, jen spouští export nad AKTUÁLNÍM stavem DB.
`export_book`/`findings_path` zápis samy nejsou atomické (`open(...,
"w")` přímo na finální cestu, stejně jako dnešní `_cmd_export`) -
`write_lock` serializuje VŠECHNY zápisy v rámci tohohle serveru, takže
dva rychlé kliky na "Export knihy" nikdy neběží současně; plná atomicita
napříč PROCESY - stejné zdokumentované zbytkové riziko jako u ostatních
JSON zápisů v `2026-09-11` spec - je mimo rozsah týhle spec.)

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

**Kolo 2 IMPORTANT - plošné smazání NEZNAMENÁ ztrátu ochrany.** Čtyři z
mazaných testů (`test_apply_503_when_lock_lost_no_db_or_json_write`,
`test_apply_corrupt_history_returns_500_without_db_write`, `test_apply_
pre_commit_failure_returns_500_db_and_draft_unchanged`, `test_apply_
post_commit_save_failure_db_already_updated`) testovaly reálné,
bezpečnostně relevantní chování (ztráta zámku, poškozená historie,
selhání PŘED/PO commitu) - Task 9 (tenhle plán, Step 1) UŽ obsahuje
JEJICH portovanou náhradu pro nový `POST /api/chapter/{idx}/save`
endpoint (`test_save_chapter_503_when_lock_lost_no_db_write`, `test_
save_chapter_corrupt_history_returns_500_without_db_write`, `test_save_
chapter_pre_commit_failure_returns_500_db_unchanged`, `test_save_
chapter_post_commit_history_failure_db_already_updated`) - žádná
ochrana se tímhle mazáním neztrácí, jen se přesouvá na nový endpoint.
Zbylé mazané testy (`test_apply_backs_up_db_only_once`, `test_apply_
uses_live_glossary_not_snapshot_from_draft_creation`, a další draft-
specifické) NEMAJÍ portovanou náhradu - pokud při čtení `tests/test_
polish_server.py` narazíš na test, co ověřuje NĚCO jiného než draft
frontu samotnou (ne jen `_chapter_draft`/`draft_chapters=` jako
setup), zastav se a rozhodni case-by-case, jestli si zaslouží vlastní
portovanou náhradu, místo automatického smazání.

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
- **`app.state.draft_path = draft_path`** (řádek u ostatních `app.state.*`
  přiřazení na konci `build_app`, BLOCKING nález - `build_app`'s nová
  signatura `draft_path` parametr vůbec nemá, ponechané přiřazení by
  spadlo na `NameError` hned při startu serveru). Smaž ten řádek úplně -
  nic ho nečte.

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

Revert taky musí nálezy opatřit `id`/`resolved` (IMPORTANT nález - jinak
by revertnutá kapitola měla nálezy bez stabilní identity, checkbox by
je nešel zaškrtnout). V revert handleru najdi:

```python
            findings = concordance.check_chapter(en, target, glossary_rows,
                                                 latest["rendered_terms"]) + [main._revert_marker(note)]
```

a nahraď za (POZOR - lokální proměnná v týhle funkci se dosud jmenovala
`findings`, stejně jako modul `from src import findings` importovaný na
úrovni souboru v Tasku 8; přejmenuj lokální proměnnou na
`revert_findings`, ať modul zůstane dostupný pod svým jménem):

```python
            revert_findings = findings.assign_ids(
                concordance.check_chapter(en, target, glossary_rows,
                                          latest["rendered_terms"])
                + [main._revert_marker(note)])
```

a přejmenuj VŠECHNY další odkazy na `findings` v TÉHLE FUNKCI (revert
handleru) na `revert_findings` - jsou dva: zápis do
`notes_json=_json.dumps(findings, ...)` (v `state.commit_chapter_result`
volání) a `"findings": findings` (v `history["entries"].append({...})`
bloku o pár řádků níž). Zbytek souboru (jiné funkce) se `findings` jako
modul jmenuje beze změny.

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

`Grep "POLISH_DRAFT_PATH" main.py config.py src/ tests/`.

**Kolo 14 IMPORTANT - `_cmd_init --reset` (main.py:728-744) je ZÁMĚRNÁ
VÝJIMKA, ne přehlédnuté volající místo.** `_archive_polish_file(config.
POLISH_DRAFT_PATH)` tam PŘEJMENUJE starý `polish.draft.json`, POKUD
existuje (`_archive_polish_file`, main.py:662-677, vrací `None` a nic
nedělá, když soubor neexistuje - `os.path.exists` kontrola HNED na
začátku). Tenhle projekt (uživatelova reálná `data/state.sqlite3`) má
PRAVDĚPODOBNĚ leftover `polish.draft.json` ze STARÉHO systému PŘED
touhle migrací - `init --reset` ho má dál bezpečně (archivovat, ne tiše
smazat) uklidit, i když NIC v novém systému už tenhle soubor nikdy
nezapíše. `config.POLISH_DRAFT_PATH` konstanta proto V main.py ZŮSTÁVÁ
(`_cmd_init` ji pořád potřebuje) - NESMAŽ ji, ani grep výsledek na
`_cmd_init`'s dva řádky (main.py:731, main.py:741) NEPOVAŽUJ za
regresi/nedodělek. "Žádné volající místo už `POLISH_DRAFT_PATH` nesmí
používat" platí JEN pro draft-FRONTU (`load_draft`/`save_draft`/
`is_draft_pending`, `_cmd_polish`'s incrementální zápis, `polish_server.
py`'s draft preflight) - PRO TY grep výsledek nesmí nic najít po tomhle
Tasku. `polish_server.py`'s vlastní `POLISH_DRAFT_PATH` odkazy (`build_app`
preflight `polish_store.load_draft(draft_path)`, Step 3 výš) SE mažou -
server žádnou reset/archivační roli nemá.

- [ ] **Step 8: Jednorázová migrace `id`/`resolved` u existujících nálezů**

IMPORTANT nález - reálná projektová DB (`data/state.sqlite3`) má PRAVDĚPODOBNĚ
nálezy z dřívějších `run`/`polish` běhů BEZ `id`/`resolved` polí (vznikly
před Taskem 2). Bez migrace by "seznam kapitol" (Task 14, `unresolved_
findings` počet) i checkbox v editoru fungovaly nespolehlivě - `findings.
count_unresolved`/`set_resolved` na nálezu bez `id` sice nespadnou (`f.get
("id")` je `None`), ale `id: None` sdílené NAPŘÍČ VŠEMI takovými nálezy by
znamenalo, že zaškrtnutí JEDNOHO starého nálezu (přes `/api/findings/
resolve` s `finding_id: null`... prakticky nedosažitelné z UI, protože
`renderFindings` posílá `finding.id`, ale `undefined`/`None` by se
serializovalo different - v každém případě nespolehlivé, radši
migrovat, než spoléhat na okrajové chování).

**Kolo 4 IMPORTANT - skript musí mít zámek, zálohu a validaci VSTUPU,
ne jen "věřit datům".** Přímý zápis do SKUTEČNÉ DB/historie bez
`state.acquire_lock` riskuje souběh s `run`/`polish`/`polish-review`
(žádný z nich o týhle ruční operaci neví). `assign_ids(parsed)` navíc
předpokládá, že KAŽDÝ prvek seznamu je `dict` (`f.get("id")`) - starý,
ručně netknutý `notes` sloupec může teoreticky nést i jiný tvar
(`_parse_findings` už dnes filtruje ne-dict prvky, tenhle skript
NEsmí být přísnější/křehčí než kód, co stejná data normálně čte).

Spusť JEDNOU, ručně (mimo testovací sadu, nad SKUTEČNOU `config.DB_PATH`/
`config.POLISH_HISTORY_PATH`/`config.LOCK_PATH` - NE nový trvalý CLI
příkaz, jednorázová oprava dat). **Kolo 10 IMPORTANT - NE přes
`python -c`:** skript níž je víceřádkový a obsahuje uvozovky/f-stringy -
`python -c "…"` na Windows/PowerShellu (viz Global Constraints - projekt
běží na Windows) má JINÁ pravidla escapování uvozovek než bash, a
víceřádkový blok jako string literál na příkazové řádce je nespolehlivý
až nefunkční. Ulož skript do souboru (např. `scripts/migrate_findings_ids.py`
- dočasný, smazatelný po jednorázovém spuštění, nebo přímo do dočasného
souboru mimo repo) a spusť ho jako normální skript:

```powershell
python scripts/migrate_findings_ids.py
```

**Kolo 5 IMPORTANT (oprava vlastní kola-4 opravy) - `polish_store.
load_history` validuje SCHÉMA (`_validate_dict_list` na `findings`)
DŘÍV, než skript dostane šanci cokoli tolerovat.** Obsahuje-li nějaký
historický záznam v `findings` netypovanou položku (`null` apod.),
`load_history` samo vyhodí `PolishStoreError` - skriptova vlastní
`_valid_entries` tolerance na tohle nikdy nedosáhne (soubor se vůbec
nenačte). Pořadí operací musí být: NEJDŘÍV zkusit načíst historii (než
se cokoli zapíše), teprve PO úspěchu pokračovat na `chapters.notes` -
jinak by (kolo 4 verze) `chapters.notes` mohlo být PŮLKOU migrováno,
zatímco historie by selhala a zůstala netknutá, matoucí částečný stav.
Oprava taky odstraňuje mrtvé porovnání (`entry["findings"] = valid`
PŘED `len(valid) != len(entry["findings"])` porovnávalo seznam sám se
sebou, `POZOR` hláška by NIKDY nevytiskla).

```python
import sys; sys.path.insert(0, ".")
import json
import os
import shutil
import config
import main
from src import findings, polish_store, state

def _valid_entries(raw):
    """Stejná tolerance jako `main._parse_findings` - ne-dict prvky
    se PŘESKOČÍ (nespadnou), ne odmítnou celý seznam. Použitelné jen
    pro `chapters.notes` (čte se syrovým `json.loads`, žádná schema
    validace před tím) - `polish.history.json` prochází `polish_store.
    load_history`'s PŘÍSNOU validací PŘED tímhle skriptem, viz níž."""
    return [f for f in raw if isinstance(f, dict)]

state.acquire_lock(config.LOCK_PATH)   # žádný jiný mutující příkaz souběžně
try:
    # Historie SE ZKOUŠÍ NAČÍST JAKO PRVNÍ (kolo 5 IMPORTANT) - selže-li
    # (poškozený JSON, nebo netolerovatelná položka uvnitř `findings`,
    # co `load_history`'s schema validace odmítne DŘÍV, než tenhle
    # skript dostane šanci ji ošetřit), NIC se zatím nezapsalo - žádný
    # poloviční stav. Neúspěch = ruční oprava souboru, pak skript spustit
    # znovu.
    history = None
    history_entries_before = None
    if os.path.exists(config.POLISH_HISTORY_PATH):
        try:
            history = polish_store.load_history(config.POLISH_HISTORY_PATH)
        except polish_store.PolishStoreError as e:
            print(f"STOP - {config.POLISH_HISTORY_PATH} se nedá načíst "
                 f"({e}) - oprav ho ručně, pak spusť skript znovu. "
                 "Nic se zatím NEZAPSALO.")
            raise SystemExit(1)
        history_entries_before = json.dumps(history["entries"], ensure_ascii=False)

    # Kolo 20 BLOCKING - `main._snapshot_db` (SQLite `Connection.backup()`
    # API), NE `shutil.copy2` - VLASTNÍ `_snapshot_db` docstring (main.py:
    # 319-329, existující kód, kolo 14 tamního ping-pongu) tohle výslovně
    # zakazuje: prostý souborový copy může zachytit DB UPROSTŘED zápisu
    # (nekonzistentní kopie) a neumí WAL/SHM sidecar soubory, kdyby se
    # žurnálovací režim někdy změnil. Předchozí verze tvrdila "tady to je
    # OK, není to request-driven server" - NEPRAVDIVÉ zdůvodnění, riziko
    # nesouvisí s tím, KDO zálohu spouští, ale s tím, ŽE `shutil.copy2`
    # o konzistenci SQLite souboru nic neví. `state.acquire_lock` výš
    # brání JEN jiným instancím TOHOHLE nástroje v souběžném zápisu -
    # nechrání proti obecné nekonzistenci kopírování samotné.
    #
    # Kolo 12 IMPORTANT - PEVNÉ jméno zálohy by DRUHÉ spuštění (po
    # neúspěšném prvním pokusu - viz `except` u `save_history` níž,
    # "oprav příčinu a spusť znovu") PŘEPSALO zálohu z PRVNÍHO běhu -
    # ztratila by se tím PRAVÁ zálohu stavu PŘED migrací (druhé
    # spuštění by zálohovalo UŽ ČÁSTEČNĚ migrovaný stav, ne originál).
    # `if not os.path.exists(...)` = zapiš zálohu jen JEDNOU, první
    # spuštění ji vytvoří, každé další ji nechá beze změny.
    #
    # Kolo 21 BLOCKING - zápis PŘÍMO na `backup_path` riskuje, že
    # PŘERUŠENÍ uprostřed (výpadek, Ctrl-C, OOM kill) nechá na disku
    # NEÚPLNÝ, ale EXISTUJÍCÍ soubor - `if not os.path.exists(backup_
    # path)` (kolo 12 výš) by ho na DALŠÍM spuštění považovalo za
    # PLATNOU zálohu (skip, "zachovávám PŮVODNÍ") a migrace by pokračovala
    # BEZ funkční zálohy. Fix - zapiš na DOČASNOU cestu, ověř (`_snapshot_
    # db`'s vlastní `PRAGMA integrity_check` UVNITŘ, viz jeho docstring),
    # a teprve PAK atomicky přejmenuj (`os.replace` - na stejném
    # filesystému je to atomická operace, buď se PROJEVÍ CELÁ, nebo
    # vůbec, žádný částečný mezistav na `backup_path`).
    backup_path = config.DB_PATH + ".pre-findings-migration-backup"
    if not os.path.exists(backup_path):
        tmp_backup_path = backup_path + ".tmp"
        if os.path.exists(tmp_backup_path):
            os.remove(tmp_backup_path)   # úklid po dřívějším přerušení
        try:
            main._snapshot_db(config.DB_PATH, tmp_backup_path)
            os.replace(tmp_backup_path, backup_path)
        except (OSError, TimeoutError) as e:
            try:
                os.remove(tmp_backup_path)
            except OSError:
                pass
            print(f"STOP - záloha DB selhala ({type(e).__name__}: {e}) - "
                 "MIGRACE SE NESPOUŠTÍ, dokud se nedá udělat bezpečná "
                 "záloha. Nic se zatím NEZAPSALO.")
            raise SystemExit(1)
        print(f"Záloha DB: {backup_path}")
    else:
        print(f"Záloha DB už existuje ({backup_path}) - zachovávám PŮVODNÍ "
             "(nejspíš druhé spuštění po dřívějším neúspěchu).")

    with state.connect(config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT idx, notes FROM chapters WHERE notes IS NOT NULL").fetchall()
        changed = 0
        for row in rows:
            try:
                parsed = json.loads(row["notes"])
            except ValueError:
                print(f"  přeskočeno (neplatný JSON) - kapitola {row['idx']}")
                continue
            if not isinstance(parsed, list) or not parsed:
                continue
            valid = _valid_entries(parsed)
            if len(valid) != len(parsed):
                print(f"  POZOR - kapitola {row['idx']}: "
                     f"{len(parsed) - len(valid)} ne-dict položek přeskočeno")
            before = json.dumps(valid, ensure_ascii=False)
            findings.assign_ids(valid)
            after = json.dumps(valid, ensure_ascii=False)
            if after != before or len(valid) != len(parsed):
                # Kolo 24 NIT - `updated_at=CURRENT_TIMESTAMP` doplněno,
                # stejná disciplína jako Task 11's resolve endpoint (kolo
                # 18) - seznam kapitol (Task 14) na tomhle sloupci ukazuje
                # "Naposled upraveno", notes SE skutečně mění.
                conn.execute("UPDATE chapters SET notes=?, "
                            "updated_at=CURRENT_TIMESTAMP WHERE idx=?",
                            (after, row["idx"]))
                changed += 1
        print(f"chapters.notes migrováno: {changed}")

    if history is not None:
        # Kolo 12 IMPORTANT - STEJNÁ oprava jako u DB zálohy výš: pevné
        # jméno by druhé spuštění (ať po neúspěchu, nebo prostě znovu
        # později) přepsalo zálohou UŽ MIGROVANÉHO stavu.
        #
        # Kolo 21 BLOCKING - STEJNÁ dočasný-soubor-pak-atomický-rename
        # ochrana jako u DB zálohy výš (`shutil.copy2` PŘÍMO na finální
        # cestu by přerušením mohl nechat neúplný, ale "existující" soubor,
        # co by další spuštění mylně považovalo za platnou zálohu).
        # `chapters.notes` výš UŽ JE commitnuté (smyčka o pár řádků výš
        # doběhla) - selhání TÉHLE zálohy proto NEZASTAVUJE migraci úplně
        # (nic už není co "nespustit"), jen přeskočí zápis historie se
        # STEJNOU "notes migrované, historie ne, spusť znovu" zprávou
        # jako `save_history` selhání níž (sdílený `except` blok).
        history_backup_path = config.POLISH_HISTORY_PATH + ".pre-findings-migration-backup"
        try:
            if not os.path.exists(history_backup_path):
                tmp_history_backup = history_backup_path + ".tmp"
                if os.path.exists(tmp_history_backup):
                    os.remove(tmp_history_backup)
                shutil.copy2(config.POLISH_HISTORY_PATH, tmp_history_backup)
                os.replace(tmp_history_backup, history_backup_path)
        except OSError as e:
            print(f"POZOR - chapters.notes SE ÚSPĚŠNĚ migrovalo, ale "
                 f"záloha historie selhala ({type(e).__name__}: {e}) - "
                 "historie se NEZAPISUJE (bez zálohy je to riskantní). "
                 "Oprav příčinu a SPUSŤ SKRIPT ZNOVU - je idempotentní.")
            raise SystemExit(1)
        for entry in history["entries"]:
            findings.assign_ids(entry["findings"])   # `load_history` UŽ zaručilo list[dict]
        if json.dumps(history["entries"], ensure_ascii=False) != history_entries_before:
            try:
                polish_store.save_history(config.POLISH_HISTORY_PATH, history)
            except Exception as e:
                # Kolo 11 IMPORTANT (zpřesněno kolo 12 - viz text pod
                # skriptem, "assign_ids ČISTĚ aditivní" bylo nepřesné
                # tvrzení) - `chapters.notes` výš UŽ JE zapsané (commitnuté
                # `with state.connect(...)` blokem), tenhle zápis selhal
                # AŽ POTOM. NEDĚLÁME automatický rollback `chapters.notes`
                # zpátky ze zálohy - i když `_valid_entries`/`assign_ids`
                # NEJSOU čistě aditivní (ne-dict položky se PŘESKOČÍ, typy
                # v `_STR_FIELDS` se koerzí na `str`), obojí je jen čištění
                # DAT, CO BY STEJNĚ ZŮSTALY NEPOUŽITELNÉ (ne-dict položka
                # není platný nález, netypovaná hodnota by stejně spadla
                # jinde) - žádný legitimní nález se tím neztrácí, jen
                # garbage, a je to VIDITELNĚ ohlášené (viz "POZOR" výpis
                # výš). Bezpečná oprava je PROSTĚ SKRIPT SPUSTIT ZNOVU
                # (notes migrace podruhé je no-op - stejná garbage se
                # stejně přeskočí znovu, ale nic dalšího se nezmění -
                # historie se zkusí zapsat znovu) - složitý atomický
                # rollback přes DVĚ zálohy by byl pro jednorázový, ručně
                # spouštěný skript neúměrná komplikace navíc riskující
                # VLASTNÍ chybu v rollbacku samotném.
                print(f"POZOR - chapters.notes SE ÚSPĚŠNĚ migrovalo (viz "
                     f"'chapters.notes migrováno' výš), ale zápis historie "
                     f"selhal ({type(e).__name__}: {e}). Tohle NENÍ "
                     "poškozený/nekonzistentní stav - id v chapters.notes "
                     "zůstávají platná. Oprav příčinu (místo na disku, "
                     "práva k zápisu apod.) a SPUSŤ SKRIPT ZNOVU - je "
                     "idempotentní, notes migrace podruhé nic nezmění, "
                     "historie se zkusí zapsat znovu. Zálohy pro ruční "
                     f"obnovu (jen kdybys to přesto chtěl vrátit): "
                     f"{backup_path}, {history_backup_path}")
                raise SystemExit(1)
            print("historie záznamů migrována")
        else:
            print("historie: beze změny (všechny záznamy už měly id)")
finally:
    state.release_lock(config.LOCK_PATH)
```

**Kolo 11 IMPORTANT, zpřesněno kolo 12 (částečný nesouhlas s navrženou
opravou, zdůvodněno):** Codex navrhl automatický kompenzační rollback
`chapters.notes` ze zálohy, když zápis historie selže AŽ PO úspěšné
migraci notes. Kolo 11 tvrdilo, že `findings.assign_ids` je "čistě
aditivní" - **kolo 12 správně namítlo, že to není přesné**: `_valid_
entries` (uvnitř `_cmd_polish`... vlastně uvnitř tohohle skriptu)
NE-dict položky ZE SEZNAMU ODSTRANÍ, `assign_ids` navíc koerzuje
netypované `_STR_FIELDS` hodnoty na `str` - obojí JSOU modifikace, ne
čisté přidání. Závěr (žádný automatický rollback) ale PŘESTO platí, z
PŘESNĚJŠÍHO důvodu: odstraňované ne-dict položky a koerzované netypované
hodnoty jsou VŽDY garbage/poškozená data (platný nález je vždy `dict` s
`str` poli) - žádný LEGITIMNÍ nález se tímhle čištěním neztrácí, a je to
VIDITELNĚ ohlášené (`POZOR` výpis). "Notes migrované (včetně vyčištění
garbage), historie ne" tedy pořád NENÍ nekonzistentní stav vyžadující
rollback, jen neúplný a bezpečně DOKONČITELNÝ opakovaným spuštěním
(druhé spuštění nad notes je no-op - stejná garbage se přeskočí stejně,
historie se zkusí zapsat znovu). Automatický rollback přes DVĚ nezávislé
zálohy (DB + JSON) je pro jednorázový, RUČNĚ spouštěný vývojářský skript
(viz "NE nový trvalý CLI příkaz" výš) pořád neúměrná komplikace navíc
riskující VLASTNÍ chybu v rollbacku samotném - "oprav příčinu a spusť
znovu" je jednodušší a stejně bezpečné.

**Kolo 12 IMPORTANT - REÁLNÁ chyba v samotných zálohách, přijato beze
zbytku:** Codex správně upozornil, že "další běh navíc přepíše pevně
pojmenovanou DB zálohu" - `backup_path`/`history_backup_path` MĚLY pevné
jméno, takže DRUHÉ spuštění (po neúspěšném prvním pokusu, přesně scénář
výš) by přepsalo zálohu z PRVNÍHO běhu - ztratila by se PRAVÁ záloha
stavu PŘED jakoukoli migrací (druhé spuštění by zálohovalo UŽ ČÁSTEČNĚ
migrovaný stav). Opraveno (viz skript výš) - `if not os.path.exists(...)`
kolem OBOU zálohovacích `shutil.copy2` volání, záloha se zapíše JEN
PRVNÍ spuštění, každé další ji nechá beze změny. Tohle přímo ospravedlňuje
větu "zálohy pro ruční obnovu zůstávají na disku beze změny" (v kole 11
by to platilo jen do prvního retry, teď platí opravdu).

Test na scénář "`save_history` selže" se NEPŘIDÁVÁ do pytest sady -
skript je explicitně MIMO test-pokryté zdrojové soubory tohohle Tasku
(Files/Test výš, "dočasný, smazatelný po jednorázovém spuštění", ne
trvalá součást kódové báze) - ruční ověření PŘED prvním spuštěním na
SKUTEČNÝCH datech (viz odstavec níž) tenhle konkrétní `except` blok
pokrývá dostatečně.

Spusť to PŘED prvním ostrým použitím nové `polish-review` UI. Ověř
výstup (počty migrovaných záznamů + jakákoli "POZOR"/"STOP" hlášení),
pak zkontroluj pár náhodných kapitol v UI, že nálezy mají viditelné,
stabilní `id`. Zálohy (`*.pre-findings-migration-backup`) nech ležet,
dokud si nejsi jistý, že migrace dopadla dobře.

- [ ] **Step 9: Ověř celou sadu**

Run: `pytest tests/test_polish_server.py tests/test_polish_store.py tests/test_cli.py -v`
Expected: PASS, 0 chyb, žádný test neodkazuje na draft frontu.

- [ ] **Step 10: Commit**

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
  const tbody = document.getElementById('chapters-body');
  // Kolo 14 IMPORTANT - `fetch` samotný může selhat (síť/server nedostupný),
  // ne jen vrátit non-ok status - bez `try/catch` by tenhle případ vyhodil
  // NEZACHYCENOU výjimku (nezachycené promise rejection), seznam by
  // zůstal navždy prázdný BEZ jakékoli chybové hlášky - stejný vzor jako
  // `loadChapter()` v editoru (Task 14 Step 2).
  let r, body;
  try {
    r = await fetch('/api/chapters');
    body = await r.json().catch(() => ({}));
  } catch (e) {
    tbody.textContent = '';
    tbody.appendChild(el('tr', {}, [el('td', {
      colspan: '6', text: 'Síťová chyba, zkus stránku znovu načíst.' })]));
    return;
  }
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
  // Kolo 14 IMPORTANT - stejný `try/catch` důvod jako `load()` výš -
  // bez něj by síťová chyba nechala "Exportuji..." viset navždy, žádná
  // chybová hláška, uživatel netuší, jestli export běží nebo spadl.
  let r, body;
  try {
    r = await fetch('/api/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    body = await r.json().catch(() => ({}));
  } catch (e) {
    msg.textContent = 'Síťová chyba, zkus export znovu.';
    msg.className = 'msg error';
    return;
  }
  if (r.ok) {
    const skippedNote = body.skipped && body.skipped.length
      ? ` - vynecháno: ${body.skipped.join(', ')}` : '';
    msg.textContent = `Hotovo: ${body.book_path} (+ ${body.findings_path})${skippedNote}`;
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
  .stale-msg { color: #b35c00; font-weight: 600; }
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
// `id`y nálezů, co UŽ existují v `chapters.notes` (z posledního GET) -
// `toggleResolved` podle tohohle pozná, jestli smí zavolat server
// (persistovaný nález), nebo jen změnit lokální stav (nález z čerstvé
// regenerace, co se uloží AŽ při Uložit - server o něm zatím neví,
// `/api/findings/resolve` by na něj vrátil 404, kolo 2 IMPORTANT).
let PERSISTED_IDS = new Set();
// `id`y nálezů, co MAJÍ probíhající /api/findings/resolve request (kolo
// 4 IMPORTANT) - bez tohohle by dvě rychlá kliknutí na STEJNÝ checkbox
// (nebo save uprostřed resolve requestu) mohla poslat dva souběžné
// požadavky, nebo nechat checkbox zaškrtnutý+disabled navždy po síťové
// chybě. `renderFindings`/`lockEditor` obě čtou tenhle set.
let PENDING_RESOLVE_IDS = new Set();
// `id` -> Promise probíhajícího `/api/findings/resolve` volání (kolo 8
// IMPORTANT) - Uložit/revert MUSÍ počkat, až všechny doběhnou, PŘED
// tím, než samy zavolají `loadChapter()`. Bez tohohle by pozdě příchozí
// GET odpověď (vyvolaná Uložit) mohla PŘEPSAT `CURRENT_FINDINGS` daty
// PŘED tím, než se resolve zápis na serveru vůbec stihl promítnout do
// SELECTu, i když resolve odpověď klientovi dorazila dřív a kolo-7
// oprava ji správně aplikovala - bezpodmínečné pole-přepsání uvnitř
// `loadChapter()` by tu správnou aplikaci prostě přepsalo zpátky na
// starou hodnotu.
let PENDING_RESOLVE_PROMISES = new Map();
// Editovatelné statusy (kolo 4 IMPORTANT) - ZRCADLÍ `_EDITABLE_STATUSES`
// v `polish_server.py` (Task 9/10) - čistě klientská UX vrstva (server
// je pořád jediný zdroj pravdy, viz 409 na save/regenerate), ať se
// tlačítka nezobrazují jako použitelná pro `pending`/`processing`
// kapitoly bez smysluplného textu.
const EDITABLE_STATUSES = new Set(['done', 'flagged', 'needs_human', 'error']);

function renderFindings() {
  const root = document.getElementById('findings');
  root.textContent = '';
  for (const f of CURRENT_FINDINGS) {
    const cb = el('input', { type: 'checkbox' });
    cb.checked = !!f.resolved;
    cb.dataset.findingId = f.id;   // `lockEditor` podle tohohle dohledá PENDING_RESOLVE_IDS
    // Nové vykreslení respektuje probíhající operaci NA TOMHLE KONKRÉTNÍM
    // nálezu (kolo 4 IMPORTANT - dřív jen `EDITOR_BUSY`, jeden probíhající
    // resolve request by po libovolném překreslení "zapomněl", že ještě
    // běží, a dovolil by druhé kliknutí na TENTÝŽ checkbox souběžně).
    cb.disabled = EDITOR_BUSY || PENDING_RESOLVE_IDS.has(f.id);
    cb.addEventListener('change', () => {
      // Ulož Promise (kolo 8 IMPORTANT) - Uložit/revert na ni počkají
      // PŘED svým vlastním `loadChapter()`, viz tamní handlery.
      const p = toggleResolved(f, cb, cb.checked);
      PENDING_RESOLVE_PROMISES.set(f.id, p);
      p.finally(() => PENDING_RESOLVE_PROMISES.delete(f.id));
    });
    const li = el('li', { class: f.resolved ? 'resolved' : '' }, [cb,
      document.createTextNode(`[${f.severity || '?'}] ${f.issue || '(bez popisu)'}`)]);
    root.appendChild(li);
  }
}

async function toggleResolved(finding, checkbox, resolved) {
  // Nález z ČERSTVÉ regenerace (kolo 2 IMPORTANT) ještě neexistuje v
  // `chapters.notes` - `/api/findings/resolve` by na jeho `id` vrátilo
  // 404 (server ho nezná). Pro takový nález je zaškrtnutí čistě LOKÁLNÍ
  // stav, persistuje se AŽ s "Uložit" (findings jedou v save payloadu
  // celé). Server se volá JEN pro nálezy, co UŽ jsou uložené.
  if (!PERSISTED_IDS.has(finding.id)) {
    finding.resolved = resolved;
    renderFindings();
    return;
  }
  // `scope: 'notes'` VŽDY - editor zobrazuje JEN `chapters.notes` nálezy
  // (Task 8 GET), nikdy historii (viz Task 7/8 - sloučení by zdvojilo
  // nálezy). `finding.resolved` se mění AŽ PO potvrzeném úspěchu, ne
  // předem - selhání (400/404/500/503, i síťová výjimka) se ukáže jako
  // chyba a checkbox se vrátí do PŮVODNÍHO stavu, ne tiše předstírá
  // úspěch ani nezůstane navždy zaškrtnutý+disabled (kolo 4 IMPORTANT -
  // `PENDING_RESOLVE_IDS` brání souběžnému druhému kliknutí NA TENTÝŽ
  // nález, dokud první request neskončí, ať uspěje nebo ne).
  //
  // POZOR (kolo 6 IMPORTANT, vlastní nález ověřený přímou simulací kódu -
  // Codex tohle rozjel v node.js, než narazil na usage limit, výsledek
  // ukazoval přesně tenhle bug): `checkbox` param je DOM reference
  // zachycená PŘED prvním `await`. Zatímco TENHLE request čeká, jiný
  // nález (jiné souběžné `toggleResolved` volání) může uspět a zavolat
  // `renderFindings()` - to PŘESTAVÍ CELÝ seznam `<li>`/`<input>` prvků
  // odznova, takže `checkbox` proměnná tady dál ukazuje na ODPOJENÝ
  // (z DOM odstraněný) starý element. Zápis do `checkbox.disabled`/
  // `.checked` PO `await` by pak neměl ŽÁDNÝ viditelný efekt - aktuálně
  // zobrazený checkbox (nový, z toho mezitímního `renderFindings()`)
  // by zůstal navždy disabled, i když `PENDING_RESOLVE_IDS`/`finding.
  // resolved` jsou interně správně. Fix: PO `await` už se `checkbox`
  // (parametr) nikdy nedotýkat přímo - vždy skrz `renderFindings()`,
  // co vždycky vykreslí AKTUÁLNÍ stav ze zdrojových dat, ne skrz starou
  // referenci. Synchronní `checkbox.disabled = true` HNED PO kliknutí
  // (PŘED prvním `await`) zůstává bezpečné - v tu chvíli je to ještě
  // jistě aktuální element.
  PENDING_RESOLVE_IDS.add(finding.id);
  checkbox.disabled = true;
  try {
    const r = await fetch('/api/findings/resolve', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope: 'notes', idx: IDX, finding_id: finding.id, resolved }),
    });
    if (r.ok) {
      // NEmutuj zachycený `finding` param přímo (kolo 7 IMPORTANT,
      // stejná třída bugu jako kolo 6, teď na DATECH místo DOM) -
      // zatímco tenhle request čekal, "Uložit" mohlo doběhnout DŘÍV a
      // jeho `loadChapter()` nahradil CELÉ `CURRENT_FINDINGS` novými
      // objekty. Mutace starého, už nepoužívaného objektu by byla
      // neviditelná - `renderFindings()` čte AKTUÁLNÍ pole, ne tenhle
      // uzavřený odkaz. Najdi aktuální nález podle `id` a uprav TEN.
      // (Kolo 12 NIT oprava komentáře - "Uložit" od kola 8 NA resolve
      // čeká přes `PENDING_RESOLVE_PROMISES`, ale jen na ty, co běžely
      // UŽ V OKAMŽIKU kliknutí na Uložit; nový `toggleResolved` start
      // PO tomhle okamžiku (než Uložit stihne dokončit svůj vlastní
      // fetch/loadChapter) čekáním nekrytý zůstává - proto tahle
      // ochrana (dohledání podle `id` místo mutace zachyceného objektu)
      // pořád platí jako pojistka, ne jen historický pozůstatek.)
      const current = CURRENT_FINDINGS.find(f => f.id === finding.id);
      if (current) current.resolved = resolved;
      // `current` chybí = kapitola se mezitím kompletně reloadla a
      // tenhle konkrétní nález už v novém seznamu není (řídký případ) -
      // nic k opravě, zobrazený stav odpovídá poslednímu GET.
    } else {
      const body = await r.json().catch(() => ({}));
      document.getElementById('err-box').textContent =
        `Zaškrtnutí se neuložilo: ${body.error || 'HTTP ' + r.status}`;
      // `finding.resolved` se NEMĚNÍ - `renderFindings()` níž ho
      // vykreslí zpátky v PŮVODNÍM stavu (odpovídá dřívějšímu ručnímu
      // `checkbox.checked = !resolved`, teď correctly i po re-renderu).
    }
  } catch (e) {
    // Kolo 19 IMPORTANT - STEJNÁ zásada jako Uložit/revert výš - `fetch`
    // výjimka NEZNAMENÁ "neuloženo", server mohl zápis dokončit PŘED
    // tím, než se odpověď ztratila cestou zpátky. Tichý návrat checkboxu
    // do PŮVODNÍHO stavu (jak to dělala VĚTEV `else` výš pro 400/404/
    // 500/503) by tady byl PŘÍMO ŠPATNĚ - kdyby zápis ve skutečnosti
    // prošel, editor by ukazoval OPAK skutečného stavu, dokud si toho
    // uživatel nevšimne (žádný další reload to samo neopraví, `resolved`
    // se jinak mění JEN přes tenhle handler nebo `loadChapter()`).
    // Radši nejistotu přiznat a vynutit reload, stejně jako Uložit/revert.
    //
    // Kolo 22 IMPORTANT - `window.location.reload()` NEZASTAVÍ synchronně
    // běžící JS (navigace je asynchronní) - obyčejné `return` by tuhle
    // Promise nechalo DOBĚHNOUT (vyřešenou), takže `Promise.all(PENDING_
    // RESOLVE_PROMISES.values())` v Uložit/revert handleru (kolo 8) by
    // DOKONČILO ČEKÁNÍ, a Uložit/revert by mohly poslat VLASTNÍ request
    // JEŠTĚ PŘED tím, než reload skutečně proběhne - nad stavem, co
    // právě přiznal nejistotu. Fix - NIKDY se z týhle větve nevracej
    // (zavěšená Promise, co se nikdy nevyřeší) - `await` v Uložit/revert
    // pak čeká DÁL, dokud stránka fakticky nenaviguje pryč (což celý
    // handler stejně zruší) - žádný další request tenhle konkrétní
    // handler už nepošle.
    alert('Síťová chyba - není jisté, jestli se zaškrtnutí na serveru '
         + 'uložilo. Stránka se teď načte znovu.');
    window.location.reload();
    await new Promise(() => {});   // navždy visící - stránka mezitím reloadne
  }
  PENDING_RESOLVE_IDS.delete(finding.id);
  renderFindings();   // JEDINÉ místo, co po `await` mění viditelný DOM
}

async function loadChapter() {
  // BLOCKING oprava kola 3 - `fetch` samotný může selhat (síť), ne jen
  // vrátit non-ok status - bez `try/catch` by tenhle případ vyhodil
  // nezachycenou výjimku a `lockEditor(false)` (ani chybová hláška) by
  // vůbec neproběhly, editor by zůstal navždy zamčený.
  //
  // Kolo 22 IMPORTANT - vrací `true`/`false` (dřív nic) - volající
  // (Uložit/revert) volají TEHLE funkci AŽ PO potvrzeném serverovém
  // commitu; když SAMOTNÝ reload selže, `CH`/`CURRENT_FINDINGS` zůstanou
  // STARÉ (pre-commit), i když server UŽ MÁ nová data - další editace by
  // buď skončila 409 (CAS na zastaralý `cz_before`), nebo hůř, tichým
  // pokusem uložit NAD staré, kapitolu commitem beztak přepsané. Volající
  // musí na `false` reagovat, ne to ignorovat (viz `btn-save`/`revert
  // Chapter` níž).
  let r, body;
  try {
    r = await fetch('/api/chapter/' + encodeURIComponent(IDX));
    body = await r.json().catch(() => ({}));
  } catch (e) {
    document.getElementById('err-box').textContent = 'Síťová chyba, zkus stránku znovu načíst.';
    lockEditor(false);
    return false;
  }
  if (!r.ok) {
    document.getElementById('err-box').textContent = body.error || `HTTP ${r.status}`;
    // BLOCKING oprava kola 2 - dřív `loadChapter()` po úspěšném Uložit
    // NIKDY textarea/tlačítka znovu neodemkla (`lockEditor(true)` z
    // volajícího handleru zůstalo navždy aktivní). `loadChapter()` je
    // teď JEDINÉ místo, co `lockEditor` VŽDY nuluje, ať skončí úspěchem
    // nebo chybou - `lockEditor` je NULL-SAFE (viz níž), funguje i když
    // `CH` je pořád `null` (úplně PRVNÍ načtení stránky selhalo).
    lockEditor(false);
    return false;
  }
  CH = body;
  CURRENT_FINDINGS = body.findings;
  PERSISTED_IDS = new Set(body.findings.map(f => f.id));
  CURRENT_STYLED_BY_CODEX = body.styled_by_codex_latest || '';
  document.getElementById('chapter-title').textContent = `#${body.idx} - ${body.title}`;
  document.getElementById('en-pane').textContent = body.raw_text != null ? body.raw_text : '(originál nedostupný)';
  document.getElementById('cz-pane').textContent = body.translated_text;
  document.getElementById('text-area').value = body.translated_text;
  renderFindings();
  refreshDiff();
  renderHistory(body.history);
  lockEditor(false);   // odemkne text-area/btn-regen/btn-save + btn-orig/
                       // btn-codex podle dostupnosti dat (viz `lockEditor`)
  return true;
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

// Textarea se BLOKUJE (ne jen tlačítka) během regenerace/uložení/revertu -
// všechno jsou asynchronní HTTP volání, co můžou trvat vteřiny
// (regenerace) i déle; bez zamčení textarey by psaní BĚHEM čekání
// zmizelo pod odpovědí serveru, co dorazí později a text přepíše. Sdílený
// `EDITOR_BUSY` flag (kolo 2 BLOCKING - dřív `revertChapter`/historie
// tlačítka nezamykala VŮBEC, mohla běžet i SOUBĚŽNĚ se save/regenerate)
// zabrání historickým tlačítkům (dynamicky vykreslovaným, `disabled`
// atribut na nich `lockEditor` nemůže nastavit přímo, protože v době
// volání ještě nemusí existovat v DOM) spustit revert, dokud cokoli
// jiného běží.
let EDITOR_BUSY = false;
function lockEditor(locked) {
  EDITOR_BUSY = locked;
  // NULL-SAFE + STATUS-AWARE (kolo 4 BLOCKING, rozšíření kola 3) -
  // `loadChapter()` volá `lockEditor(false)` i když PRVNÍ GET selhal
  // (`CH` je pořád `null`) - kolo 3 tohle ošetřilo jen pro btn-orig/
  // btn-codex, NE pro text-area/btn-regen/btn-save, které se tak po
  // neúspěšném prvním načtení nesprávně ODEMKLY. `noEdit` sjednocuje
  // VŠECHNY ovládací prvky na jedno pravidlo: zamčeno KDYŽ `locked`
  // NEBO `CH` neexistuje NEBO status kapitoly není editovatelný.
  // `translated_text == null` (kolo 5 IMPORTANT) - `status='error'` z
  // `run`u nezaručuje reálný text (první neúspěšný pokus o překlad).
  const noEdit = locked || !CH || !EDITABLE_STATUSES.has(CH.status)
                || CH.translated_text === null;
  document.getElementById('text-area').disabled = noEdit;
  document.getElementById('btn-regen').disabled = noEdit;
  document.getElementById('btn-save').disabled = noEdit;
  document.getElementById('btn-orig').disabled = noEdit || CH.cz_before_original === null;
  document.getElementById('btn-codex').disabled = noEdit || CH.styled_by_codex_latest === null;
  // Zaškrtávátka nálezů (kolo 3/4 IMPORTANT) - dynamicky vykreslená
  // `renderFindings`, `lockEditor` je musí dohledat v DOM přímo (nejsou
  // v ní zavřená jako ostatní pevné prvky). `PENDING_RESOLVE_IDS`
  // navíc drží zamčené konkrétní checkboxy s VLASTNÍM probíhajícím
  // požadavkem, i když `locked` je zrovna `false` (viz `toggleResolved`).
  for (const cb of document.querySelectorAll('#findings input[type=checkbox]')) {
    cb.disabled = locked || PENDING_RESOLVE_IDS.has(cb.dataset.findingId);
  }
}

document.getElementById('btn-regen').addEventListener('click', async () => {
  const errBox = document.getElementById('err-box');
  errBox.textContent = '';
  lockEditor(true);
  // `lockEditor(false)` VŽDY AŽ PO plném zpracování odpovědi (kolo 2
  // BLOCKING - dřív se odemykalo HNED po `fetch` PŘED `r.json()`, což
  // nechávalo krátké, ale reálné okno, kdy uživatel mohl začít psát
  // těsně před tím, než `body.styled` textarea přepsal).
  try {
    const r = await fetch('/api/polish/regenerate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idx: IDX }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) { errBox.textContent = body.error || `HTTP ${r.status}`; return; }
    document.getElementById('text-area').value = body.styled;
    CURRENT_FINDINGS = body.findings;   // nové id NEJSOU v PERSISTED_IDS - správně, ještě neuložené
    CURRENT_STYLED_BY_CODEX = body.styled;
    renderFindings();
    refreshDiff();
  } catch (e) {
    // Kolo 15 IMPORTANT - `fetch` samotný může selhat (síť) - `finally`
    // níž `lockEditor(false)` proběhne i tak, ale BEZE ZACHYCENÍ by
    // vznikla NEZACHYCENÁ promise rejection a `errBox` by zůstal
    // prázdný, uživatel by nevěděl, proč se nic nestalo. Regenerace
    // NIC nezapisuje do `chapters`/historie (Task 10 - "NIC nezapisuje")
    // - na rozdíl od revertu níž tu NENÍ žádná nejistota o stavu na
    // serveru, čistě zobraz chybu.
    errBox.textContent = 'Síťová chyba, zkus to znovu.';
  } finally {
    lockEditor(false);
  }
});

document.getElementById('btn-save').addEventListener('click', async () => {
  const errBox = document.getElementById('err-box');
  errBox.textContent = '';
  lockEditor(true);
  // Kolo 8 IMPORTANT - počkej na VŠECHNY rozpracované resolve požadavky
  // PŘED vlastním save (a hlavně PŘED jeho `loadChapter()`). `lockEditor
  // (true)` výš zamkl checkboxy PROTI NOVÝM kliknutím, ale požadavky
  // odeslané PŘED tímhle klikem na Uložit dál běží na pozadí - bez
  // čekání by pozdě příchozí GET (vyvolaný Uložit ÚSPĚCHEM) mohl
  // přepsat `CURRENT_FINDINGS` stavem PŘED tím, než se resolve zápis na
  // serveru vůbec promítl - i kdyby resolve odpověď klientovi dorazila
  // dřív a kolo-7 oprava ji správně aplikovala, kolo-8 bezpodmínečné
  // přepsání v `loadChapter()` by ji zase ztratilo.
  await Promise.all(PENDING_RESOLVE_PROMISES.values());
  // BLOCKING oprava kola 3 - `finally { await loadChapter() }` volalo
  // reload i po 409/503/selhání PŘED commitem, což ZAHODILO rozepsaný
  // text i lokální nálezy z regenerace, co se ještě nestihly uložit.
  // Reload smí proběhnout JEN po potvrzeném úspěchu - jinak jen odemkni.
  try {
    const r = await fetch('/api/chapter/' + encodeURIComponent(IDX) + '/save', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cz_before: CH.translated_text,
        text: document.getElementById('text-area').value,
        findings: CURRENT_FINDINGS,
        styled_by_codex: CURRENT_STYLED_BY_CODEX,
        // Kolo 20 BLOCKING - `known_ids` = co jsme znali PŘI NAČTENÍ
        // (`PERSISTED_IDS`, nastavené v `loadChapter()` z GET) - server
        // (Task 9) ho použije k rozlišení "tenhle starý nález klient
        // znal a superseduje ho" (smaž) od "tenhle nález klient NIKDY
        // neviděl, přidal ho někdo jiný mezitím" (zachovej) - viz
        // `_merge_findings_by_id` docstring.
        known_ids: Array.from(PERSISTED_IDS),
      }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
      errBox.textContent = body.error || `HTTP ${r.status}`;
      lockEditor(false);   // odemkni, ale NEPŘEPISUJ rozepsaný text/nálezy reloadem
      return;
    }
  } catch (e) {
    // Kolo 19 IMPORTANT - `fetch` výjimka NEZNAMENÁ "neuloženo" - server
    // MOHL zápis dokončit ještě PŘED tím, než síť spadla NA CESTĚ ZPÁTKY
    // (odpověď se ztratila). "zkus to znovu" (staré chování) by v tom
    // případě poslalo STEJNÉ `cz_before` znovu - CAS by ho odmítlo 409,
    // protože server UŽ MÁ jiný `translated_text` - matoucí, protože
    // uživatel neví, že se to prvně POVEDLO. Stejná zásada jako revert
    // (Task 14, kolo 15) - přiznej nejistotu, vynuť reload PŘED další
    // úpravou, ať editor vždy ukazuje SKUTEČNÝ stav, ne uhádnutý.
    alert('Síťová chyba - není jisté, jestli se uložení na serveru '
         + 'provedlo. Stránka se teď načte znovu, zkontroluj text/nálezy '
         + 'před další úpravou.');
    window.location.reload();
    return;
  }
  // Uspělo - TEĎ (a jen teď) načti čerstvý stav z DB.
  const reloaded = await loadChapter();
  if (!reloaded) {
    // Kolo 22 IMPORTANT - commit JE potvrzený (dostali jsme 200 výš),
    // ale SAMOTNÝ reload selhal - `CH`/`CURRENT_FINDINGS` zůstaly STARÉ,
    // zatímco server UŽ MÁ nová data. `loadChapter()` už `lockEditor
    // (false)` udělalo (editor je "použitelný", ale nad ZASTARALÝMI
    // daty) - to by dovolilo další editaci, co skončí buď 409 (CAS), nebo
    // hůř. Vynuť tvrdý reload celé stránky - ten buď uspěje (čerstvá
    // data), nebo ukáže poctivou chybu prohlížeče, což je pravdivější
    // než tichý zamčený-na-starých-datech stav.
    alert('Uložení proběhlo, ale nepodařilo se načíst čerstvý stav. '
         + 'Stránka se teď načte znovu.');
    window.location.reload();
  }
});

async function revertChapter(idx, to) {
  if (EDITOR_BUSY) return;   // kolo 2 BLOCKING - historie tlačítka teď respektují zámek
  lockEditor(true);
  // Kolo 8 IMPORTANT - stejný důvod jako u Uložit výš: počkej na
  // rozpracované resolve požadavky, ať revert svým `loadChapter()`
  // nepřepíše čerstvě zapsaný resolved stav starou hodnotou.
  await Promise.all(PENDING_RESOLVE_PROMISES.values());
  try {
    const r = await fetch('/api/polish/revert', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idx, to }),
    });
    if (r.ok) {
      // Kolo 22 IMPORTANT - STEJNÝ důvod jako Uložit výš - commit JE
      // potvrzený, ale když SAMOTNÝ reload selže, nesmí editor zůstat
      // tiše odemčený nad zastaralými daty.
      const reloaded = await loadChapter();
      if (!reloaded) {
        alert('Revert proběhl, ale nepodařilo se načíst čerstvý stav. '
             + 'Stránka se teď načte znovu.');
        window.location.reload();
      }
      return;
    }
    const body = await r.json().catch(() => ({}));
    alert(body.error || `HTTP ${r.status}`);
  } catch (e) {
    // Kolo 15 IMPORTANT - `fetch` může selhat PŘED odesláním (nic se
    // nestalo) NEBO PO tom, co server revert už zapsal, ale odpověď se
    // ztratila cestou zpátky (síť spadla těsně po commitu) - na rozdíl
    // od regenerace (čistě read-only, Task 10) TADY nejde z pouhé
    // `fetch` výjimky poznat, který z těch dvou případů nastal. Radši
    // NEJISTOTU přiznat a vynutit reload PŘED další úpravou, než mlčky
    // předpokládat "nic se nestalo" (a nechat uživatele editovat NAD
    // stavem, co server mezitím tiše změnil).
    alert('Síťová chyba - není jisté, jestli se revert na serveru '
         + 'provedl. Stránka se teď načte znovu, zkontroluj historii '
         + 'před další úpravou.');
    window.location.reload();
    return;
  } finally {
    lockEditor(false);
  }
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
    // POZOR (kolo 4 NIT, oprava vlastního nepřesného tvrzení z kola 3):
    // `can_revert_previous`/`can_revert_original` (`_annotate_history`)
    // NEZÁVISÍ na `stale` - obě hodnoty se počítají nezávisle na tom,
    // jestli DB odpovídá historii. Tlačítko se tedy MŮŽE zobrazit i u
    // `stale` záznamu. Bezpečnost tím netrpí - `POST /api/polish/revert`
    // má VLASTNÍ CAS kontrolu (`2026-09-11` spec), klik na tlačítko u
    // rozjetého záznamu prostě dostane 409, nikdy tiše nepřepíše špatný
    // text. VAROVÁNÍ (kolo 3 IMPORTANT - dřív `e.stale`/`e.reason` úplně
    // zahozené) se zobrazuje VEDLE tlačítek, ne místo nich - dává
    // uživateli echo "než klikneš, něco tu nesedí", ne tvrzení, že
    // tlačítko nutně selže.
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
    if (e.stale) {
      table.appendChild(el('tr', {}, [el('td', { colspan: '3', class: 'stale-msg',
        text: 'DB neodpovídá historii - poslední zápis do historie pravděpodobně '
             + 'selhal PO uložení textu do knihy. Zkontroluj text ručně; revert '
             + 'pro tuhle kapitolu nemusí fungovat spolehlivě, dokud nesoulad '
             + 'nevyřešíš.' })]));
    }
  }
  root.appendChild(table);
}

// Zamkni HNED (kolo 3 IMPORTANT) - dokud první `loadChapter()` nedoběhne,
// `CH` je `null` a kliknutí na Uložit/Znovu-polish by na něm spadlo.
lockEditor(true);
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
5b. Kolo 7 regresní scénář (race mezi resolve a save+reload) - jde těžko
   spolehlivě vynutit ručně (potřebuje pomalý resolve request), ale
   zkontroluj ASPOŇ: zaškrtni nález, OKAMŽITĚ (než se stihne request
   vrátit) klikni "Uložit" - po doběhnutí obojího zkontroluj, že
   zaškrtnutí nálezu SEDÍ s tím, co je vidět po ručním refreshi stránky
   (F5). Nesouhlasí-li, `toggleResolved`'s "najdi podle id v aktuálním
   poli" oprava (Task 14 Step 2) nefunguje správně.
5c. Kolo 22 regresní scénář (resolve síťová chyba nesmí pustit Uložit/
   revert dál) - jde těžko spolehlivě vynutit ručně bez DevTools
   "offline" simulace, ale ZKONTROLUJ kód (ne jen chování): `toggle
   Resolved`'s `catch` větev (Task 14 Step 2) musí končit `await new
   Promise(() => {})` (nikdy nevyřešená), NE prostým `return` - jinak
   `Promise.all(PENDING_RESOLVE_PROMISES.values())` v Uložit/revert
   handlerech doběhne ještě PŘED reloadem a pošle vlastní request nad
   nejistým stavem. V DevTools jde simulovat: Network tab → "Offline",
   zaškrtni nález (spustí se fetch, selže), OVĚŘ, že žádný další klik na
   "Uložit" (i po zapnutí sítě zpátky) NESTIHNE odeslat request PŘED
   tím, než `alert()`/reload z resolve chyby proběhne.
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
  no-op idempotenci vázanou na `draft_id`. V novém modelu "text beze
  změny" case (`POST /api/chapter/{idx}/save`, Task 9) řeší SVOJI
  vlastní "lehkou" zápisovou větev (`_merge_findings_by_id` + přímé
  `UPDATE chapters SET notes=..., status='done'`, BEZ nové historie
  položky) - `_kept_original_marker` v tomhle nemá roli, `draft_id`
  koncept skončil spolu s draft frontou. Pokud grep najde `_kept_
  original_marker` jen jako definici bez volajícího místa, smaž funkci
  i její testy (`Grep "_kept_original_marker" main.py tests/test_cli.py`
  pro přesná místa).
- Zbylé `"polish.draft"` zmínky mimo `docs/superpowers/specs/2026-09-11-*.md`
  (ten dokument NEmaž, je historický záznam) - **kolo 14 IMPORTANT,
  konkretizováno (bylo neurčité "oprav/smaž podle kontextu"):** JEDINÉ
  legitimní přeživší volající místo je `_cmd_init --reset`'s archivace
  (main.py:731/741, viz Task 13 Step 7 - ZÁMĚRNÁ výjimka, harmless no-op
  na čistém stavu, uklízí leftover soubor z PŘED-migračních instalací).
  Cokoli JINÉHO, co grep tady najde (draft frontu, `polish_server.py`
  draft preflight, testy na `save_draft`/`load_draft`), už mělo být
  smazáno v Tasku 13 - pokud se tu ještě objeví, je to DOŘEŠENÍ zapomenuté
  věci z Tasku 13, ne nová volba "oprav nebo smaž".

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
