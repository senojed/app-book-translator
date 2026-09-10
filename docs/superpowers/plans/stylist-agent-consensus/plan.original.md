# Stylistický průchod přes Codex - implementační plán

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Přidat příkaz `python main.py polish`, který HOTOVOU, už schválenou českou kapitolu (`status=="done"`) prožene stylistickým průchodem přes `codex exec` a výsledek přijme JEN když projde stejnou kontrolou jako původní překlad (konkordance + kritik) plus dodatečnými sítěmi (sekvence čísel, počet odstavců, CZ-před vs. CZ-po kontrola významu a rejstříku).

**Architecture:** Nový modul `src/agents/stylist.py` je JEDINÉ místo, co mluví s Codexem - je provider-agnosticky izolovaný (Popen + stdin vstup + `-o` capture výstupu, read-only sandbox, izolovaný `-C`, `--ephemeral`, `--ignore-user-config`). Orchestrace, guardraily, DB záloha a report žijí v `main.py` (`_cmd_polish` a pomocné funkce) a v `pipeline._run_critic`/`concordance` (beze změny volané). Zamítnutá stylizace nemění text ani status kapitoly; přijatá dostane audit marker do `notes`. Každý běh zapíše JSON report do `polish-reports/` jako měřicí přístroj pro v1.

**Tech Stack:** Python 3.11+, `subprocess` (Popen), `sqlite3` (`Connection.backup()`), `anthropic` přes `src/llm/client.py` (kritik a kontrola významu), `pytest`. Codex CLI je RUNTIME nástroj mimo Python - v testech vždy mockovaný fake skriptem, nikdy volaný doopravdy.

**Spec:** `docs/superpowers/specs/2026-09-08-stylist-agent-design.md` - plán argumentuje ze specu a cituje z něj rozsahy řádků pro velké bloky kódu. Executor čte OBA: spec nese plné zdůvodnění každého řádku (38 konsensuálních kol), plán nese pořadí, testy a hranice tasků.

## Global Constraints

- **Python 3.11+.** Žádné nové runtime závislosti. `subprocess`, `sqlite3`, `hashlib`, `datetime`, `time`, `tempfile`, `shutil` jsou stdlib.
- **Import layout:** moduly v `src/` importují sourozence jako `from src import X`, kořenový `config` jako `import config`. `src/agents/stylist.py` importuje `import config` a `from src.llm.parsing import extract_json`. `main.py` přidá modulové importy `datetime as _dt`, `hashlib`, `sqlite3`, `time`, `from src import concordance, glossary` (dnes jsou `concordance`/`glossary` v `main.py` jen lokálně v `_cmd_review`).
- **UTF-8:** testy i CLI musí projít v `cp1252` konzoli. `Popen` v `stylist.polish` MÁ `text=True, encoding="utf-8"` EXPLICITNĚ (bez toho `UnicodeEncodeError` na českém promptu ještě před spuštěním Codexu). Fake skripty v testech píšou `fake.write_text(..., encoding="utf-8")`.
- **`codex_cmd` je VŽDY seznam** (`[sys.executable, str(fake)]`), nikdy string.
- **Bezpečnostní brána:** `stylist.polish()` HNED na začátku vyhodí `StylistError`, když `config.STYLIST_ACCEPT_FS_RISK is not True` (`is not True`, ne `if not` - `1`/truthy NEprojde). `_cmd_polish` má NAVÍC vlastní časnou hlášku jako hezčí UX, ale závazná brána je v `polish()`.
- **Redakce U ZDROJE:** každá chybová hláška nesoucí hodnotu odvozenou z Codexova výstupu (stderr, sekvence čísel, počet odstavců, poměr délky, `str(e)` neočekávané výjimky, `FatalRunError` z LLM klienta volaného s `styled`) jde přes `stylist._redact_detail(...)`, co vrátí konkrétní hodnotu JEN za `config.STYLIST_REPORT_REJECTED_TEXT is True`, jinak `_REDACTED` konstantu.
- **Diagnostické výpisy:** VŠECHNY `print` v runtime cestě `polish` (`_polish_one_chapter`, `_cmd_polish` smyčka i `finally`, `_backup_db_once`, `_write_polish_report`) jdou přes `_say(msg)` (`try: print(msg) except Exception: pass`). Jediný holý `print` co v `polish` cestě zůstává je uvnitř `_say`. `BrokenPipeError` z výpisu NESMÍ změnit `outcome` kapitoly ani stav běhu.
- **Invariant "1 report záznam / iterace smyčky" je STRUKTURNÍ:** `_polish_one_chapter` vrací `dict`, `report` NEpřijímá ani nemutuje. `_cmd_polish` appendne přesně jednou za iteraci. Žádný dedup.
- **Codex volání se NEpočítá do `MAX_SPEND_USD`/`llm_calls`** (jiný poskytovatel). Kritik a `check_meaning_preserved` jsou normální Anthropic volání přes `_client_factory` a DO `llm_calls` se počítají - proto `polish` běží `interactive=True` jako `run`.
- **Konfigurační výchozí hodnoty** (v `config.py`): `CODEX_MODEL = ""`, `STYLIST_TIMEOUT_SECONDS = 180`, `STYLIST_MAX_CHARS = 60_000`, `STYLIST_ACCEPT_FS_RISK = False`, `STYLIST_REPORT_REJECTED_TEXT = False`.
- **Testy se spouští:** `python -m pytest tests/<soubor>::<test> -v`.
- **Commity často** - každý task končí commitnutým, samostatně testovatelným deliverable. Commit message končí `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

## Task 1: konfigurační hodnoty + modulové importy `main.py`

**Files:**
- Modify: `config.py` (přidat blok stylist hodnot na konec)
- Modify: `main.py:13-26` (přidat modulové importy)
- Test: `tests/test_config_env.py`

**Interfaces:**
- Consumes: nic
- Produces:
  - `config.CODEX_MODEL: str` (`""`), `config.STYLIST_TIMEOUT_SECONDS: int` (`180`), `config.STYLIST_MAX_CHARS: int` (`60_000`), `config.STYLIST_ACCEPT_FS_RISK: bool` (`False`), `config.STYLIST_REPORT_REJECTED_TEXT: bool` (`False`)
  - `main.py` má na modulové úrovni k dispozici `_dt` (datetime), `hashlib`, `sqlite3`, `time`, `concordance`, `glossary`

- [ ] **Step 1: Write the failing test** — přidej do `tests/test_config_env.py`

```python
def test_stylist_config_defaults_present():
    import config
    assert config.CODEX_MODEL == ""
    assert config.STYLIST_TIMEOUT_SECONDS == 180
    assert config.STYLIST_MAX_CHARS == 60_000
    assert config.STYLIST_ACCEPT_FS_RISK is False
    assert config.STYLIST_REPORT_REJECTED_TEXT is False


def test_main_has_module_level_imports_for_polish():
    import main
    for attr in ("_dt", "hashlib", "sqlite3", "time", "concordance", "glossary"):
        assert hasattr(main, attr), attr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config_env.py::test_stylist_config_defaults_present tests/test_config_env.py::test_main_has_module_level_imports_for_polish -v`
Expected: FAIL - `AttributeError: module 'config' has no attribute 'CODEX_MODEL'`

- [ ] **Step 3: Add config values** — připoj na konec `config.py` blok VERBATIM ze specu, řádky 344-401 (`# --- stylistický průchod přes Codex ---` až `STYLIST_REPORT_REJECTED_TEXT = False`, včetně všech komentářů).

- [ ] **Step 4: Add main.py imports** — do `main.py`, k existujícím importům (za `import sys` a za `from src import ...`), přidej přesně tento blok ze specu (řádky 409-413):

```python
import datetime as _dt
import hashlib
import sqlite3
import time
from src import concordance, glossary
```

Umísti `import datetime as _dt` / `import hashlib` / `import sqlite3` / `import time` mezi stdlib importy (za `import os`, `import sys`); `from src import concordance, glossary` mezi `from src import` řádky.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_config_env.py -v && python -m pytest tests/test_cli.py -q`
Expected: PASS (nové testy zelené, žádná regrese CLI z nových importů)

- [ ] **Step 6: Commit**

```bash
git add config.py main.py tests/test_config_env.py
git commit -m "feat: konfigurační hodnoty stylist průchodu + modulové importy main.py"
```

---

## Task 2: oprava `critic.review()` - validace verdiktu (PŘEDEXISTUJÍCÍ mezera)

**Proč:** `critic.review()` dnes zahazuje `verdict` a čte jen `data.get("findings")`. Odpověď `{"verdict": "revise", "findings": []}` projde jako "pass" - `has_revise_triggers` i `_polish_rejected` o rozporu nevědí. Mezera postihuje `run` i `polish`; oprava patří do `critic.py` (prospěje oběma). Detaily spec řádky 131-286.

**Files:**
- Modify: `src/agents/critic.py:50-74` (celý rewrite `review()`)
- Modify: `src/agents/critic.py:10` (import - přidat `from src.llm.client import FatalRunError` NENÍ potřeba; `OutputTruncated` už je)
- Test: `tests/test_critic.py`

**Interfaces:**
- Consumes: `critic._to_finding` (beze změny), `extract_json`, `OutputTruncated`
- Produces: `critic.review(en_chapter, cz_chapter, client, *, model=None, max_tokens=None) -> list` - vrací seznam findings; useknutý/rozbitý/nekonzistentní výstup zkusí jednou znovu, pak vyhodí výjimku (`ValueError` nebo `OutputTruncated`). Nově: nedict top-level, non-list `findings`, nedict položka, neplatný `severity`/`type` enum, neplatný `verdict` enum → celá odpověď rozbitá. `verdict=="revise"` bez žádného `action=="revise"` nálezu → syntetický `revise` finding připojen.

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_critic.py` (nahoře už je `import json, pytest`, `from src.agents import critic`, `from src.llm.client import Completion, FakeLLMClient, OutputTruncated`):

```python
def _dbl(text):
    """Kritik má retry smyčku (2 pokusy) - vrať stejnou vadnou odpověď dvakrát."""
    return FakeLLMClient([Completion(text, False, 5, 5), Completion(text, False, 5, 5)])


def test_review_revise_verdict_without_revise_finding_synthesizes_one():
    resp = json.dumps({"verdict": "revise", "findings": []})
    out = critic.review("EN", "CZ", FakeLLMClient([Completion(resp, False, 5, 5)]))
    assert any(f["action"] == "revise" for f in out)
    assert out[0]["source"] == "critic"


def test_review_findings_as_string_is_broken_not_char_iteration():
    resp = json.dumps({"verdict": "pass", "findings": "ok"})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_findings_with_non_dict_item_invalidates_whole_response():
    resp = json.dumps({"verdict": "pass", "findings": [1]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_invalid_verdict_is_broken_even_with_empty_findings():
    for bad in ("maybe", None, 42):
        resp = json.dumps({"verdict": bad, "findings": []})
        with pytest.raises((ValueError, OutputTruncated)):
            critic.review("EN", "CZ", _dbl(resp))


def test_review_top_level_non_dict_is_broken():
    resp = json.dumps([{"verdict": "pass"}])
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_finding_missing_severity_invalidates_response():
    resp = json.dumps({"verdict": "revise",
                       "findings": [{"type": "fidelity", "issue": "x"}]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_finding_invalid_severity_value_invalidates_response():
    resp = json.dumps({"verdict": "revise",
                       "findings": [{"severity": 0, "type": "fidelity", "issue": "x"}]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_finding_invalid_type_value_invalidates_response():
    resp = json.dumps({"verdict": "revise",
                       "findings": [{"severity": "critical", "type": "grammar",
                                     "issue": "x"}]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_critic.py -v`
Expected: nové testy FAIL (dnešní `review()` je nevaliduje); staré testy `test_critic.py` musí zůstat zelené i po rewriteu.

- [ ] **Step 3: Rewrite `review()`** — nahraď `src/agents/critic.py:50-74` funkcí VERBATIM ze specu, řádky 146-246 (od `def review(en_chapter: str, cz_chapter: str, client, *, model=None,` po `raise last_error`). `_to_finding` a `SYSTEM_PROMPT` NEMĚŇ.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_critic.py -v && python -m pytest tests/test_pipeline.py -q`
Expected: PASS (nové i staré, žádná regrese pipeline která `_run_critic` volá)

- [ ] **Step 5: Commit**

```bash
git add src/agents/critic.py tests/test_critic.py
git commit -m "fix: critic.review validuje verdict/findings/severity/type a synteticky vynutí revizi"
```

---

## Task 3: `state.chapter_mentions()` getter (BLOCKING - slepá skvrna konkordance)

**Proč:** `_polish_one_chapter` bez `rendered_terms` by termín zachycený VÝHRADNĚ translatorovým hlášením vůbec nezkoumal (ne jen ztráta metadat - úplná slepá skvrna). Spec řádky 288-329.

**Files:**
- Modify: `src/state.py` (přidat `chapter_mentions` k ostatním getterům, poblíž `all_term_mentions` na řádku 435)
- Test: `tests/test_state_chapters.py`

**Interfaces:**
- Consumes: `state.connect`
- Produces: `state.chapter_mentions(db_path: str, chapter_idx: int) -> list[dict]` - vrátí řádky `term_mentions` JEN dané kapitoly, ve vloženém pořadí (`ORDER BY id`), každý řádek dict s klíči `term_id`, `cz_form`, `scene_idx`, `source`.

- [ ] **Step 1: Write the failing test** — přidej do `tests/test_state_chapters.py`:

```python
def test_chapter_mentions_returns_only_that_chapter_in_insert_order(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1), _Ch(2)])
    # glosář musí mít term_id kvůli FK
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES "
                     "('t/a','A','Á'),('t/b','B','Bé')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Áčko", "scene_idx": 0, "source": "rendered"},
        {"term_id": "t/b", "cz_form": "Béčko", "scene_idx": 1, "source": "detected"},
    ])
    state.replace_term_mentions(db, 2, [
        {"term_id": "t/a", "cz_form": "jiné", "scene_idx": 0, "source": "rendered"},
    ])
    rows = state.chapter_mentions(db, 1)
    assert [r["term_id"] for r in rows] == ["t/a", "t/b"]
    assert rows[0]["source"] == "rendered" and rows[1]["source"] == "detected"
    assert rows[0]["cz_form"] == "Áčko"
    assert len(state.chapter_mentions(db, 2)) == 1
```

(Ověř, jak `replace_term_mentions` bere mentions - `src/state.py:407-424`. Pokud bere objekty s atributy místo dictů, uprav vstup testu na odpovídající tvar; getter samotný to neovlivňuje.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state_chapters.py::test_chapter_mentions_returns_only_that_chapter_in_insert_order -v`
Expected: FAIL - `AttributeError: module 'src.state' has no attribute 'chapter_mentions'`

- [ ] **Step 3: Implement** — přidej do `src/state.py` (za `all_term_mentions`) funkci VERBATIM ze specu, řádky 307-316:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state_chapters.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/state.py tests/test_state_chapters.py
git commit -m "feat: state.chapter_mentions - mentions jedné kapitoly pro polish"
```

---

## Task 4: `stylist.py` - modul, deterministické helpery, argv, kill

**Files:**
- Create: `src/agents/stylist.py`
- Test: `tests/test_stylist.py`

**Interfaces:**
- Consumes: `config`, `extract_json` (v tomhle tasku nepoužit, ale importuj rovnou - Task 5/6 ho potřebují), `config.STYLIST_REPORT_REJECTED_TEXT`
- Produces:
  - `stylist.StylistError(Exception)`
  - `stylist._paragraph_count(text: str) -> int` - normalizuje CRLF, dělí na prázdném řádku (i s bílými znaky), počítá neprázdné bloky
  - `stylist._NUMBER_RE` (regex), `stylist._number_sequence(text: str) -> list[str]` - čísla/procenta v POŘADÍ VÝSKYTU, neseřazená; mezerové varianty (obyčejná, NBSP U+00A0, úzká U+202F) před `%` se odstraňují; desetinný oddělovač se NEnormalizuje
  - `stylist._REDACTED: str`, `stylist._redact_detail(detail: str) -> str` - vrátí `detail` jen za `config.STYLIST_REPORT_REJECTED_TEXT is True`, jinak `_REDACTED`
  - `stylist._resolve_codex_cmd(codex_cmd: list) -> list` - rozřeší `codex_cmd[0]` přes `shutil.which` (jen když není absolutní), `StylistError` když nenajde
  - `stylist._CODEX_STATIC_FLAGS: list[str]` = `["exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config"]`
  - `stylist._codex_argv(codex_cmd, work_dir, out_path, codex_model) -> list`
  - `stylist._kill_process_tree(proc) -> None` - `taskkill /F /T /PID` na win32 (s `timeout=10`), fallback `proc.kill()`

- [ ] **Step 1: Write the failing tests** — `tests/test_stylist.py`:

```python
import json, os, sys
import pytest
import config
from src.agents import stylist


@pytest.fixture(autouse=True)
def _stylist_test_config(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "gpt-5-codex")


def test_paragraph_count_normalizes_crlf_and_whitespace_blank_lines():
    assert stylist._paragraph_count("A\r\n\r\nB") == 2
    assert stylist._paragraph_count("A\n  \nB") == 2
    assert stylist._paragraph_count("Jen jeden.") == 1


def test_number_sequence_preserves_order_and_is_unsorted():
    assert stylist._number_sequence("bylo 3 a pak 5") == ["3", "5"]
    assert stylist._number_sequence("bylo 5 a pak 3") == ["5", "3"]


def test_number_sequence_percent_space_variants_equal():
    a = stylist._number_sequence("12%")
    for variant in ("12 %", "12 %", "12 %"):
        assert stylist._number_sequence(variant) == a
    # ztráta % je změna
    assert stylist._number_sequence("12") != a


def test_number_sequence_does_not_normalize_decimal_separator():
    assert stylist._number_sequence("3.5") != stylist._number_sequence("3,5")


def test_redact_detail_gates_on_is_true(monkeypatch):
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", True)
    assert stylist._redact_detail("SECRET") == "SECRET"
    for falsey in (False, 1, "False", None):
        monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", falsey)
        assert stylist._redact_detail("SECRET") == stylist._REDACTED


def test_resolve_codex_cmd_uses_absolute_path_directly():
    cmd = stylist._resolve_codex_cmd([sys.executable, "-c", "pass"])
    assert cmd[0] == sys.executable


def test_resolve_codex_cmd_raises_clear_error_for_missing_bare_name():
    with pytest.raises(stylist.StylistError, match="nenalezen"):
        stylist._resolve_codex_cmd(["prikaz-co-opravdu-neexistuje-xyz"])


def test_codex_argv_exact_shape(tmp_path):
    argv = stylist._codex_argv(["codex"], str(tmp_path), str(tmp_path / "out.txt"),
                               "gpt-5-codex")
    assert argv == ["codex", "exec", "--sandbox", "read-only",
                    "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                    "-C", str(tmp_path), "-o", str(tmp_path / "out.txt"),
                    "-m", "gpt-5-codex", "-"]
    assert "--ignore-rules" not in argv


def test_kill_process_tree_falls_back_to_proc_kill_when_taskkill_fails(monkeypatch):
    monkeypatch.setattr(stylist.sys, "platform", "win32")

    class _FakeCompletedProcess:
        returncode = 1

    monkeypatch.setattr(stylist.subprocess, "run",
                        lambda *a, **kw: _FakeCompletedProcess())
    killed = {"called": False}

    class _FakeProc:
        pid = 12345
        def kill(self):
            killed["called"] = True

    stylist._kill_process_tree(_FakeProc())
    assert killed["called"]


def test_kill_process_tree_falls_back_when_taskkill_itself_times_out(monkeypatch):
    monkeypatch.setattr(stylist.sys, "platform", "win32")

    def _boom(*a, **kw):
        raise stylist.subprocess.TimeoutExpired(cmd="taskkill", timeout=10)

    monkeypatch.setattr(stylist.subprocess, "run", _boom)
    killed = {"called": False}

    class _FakeProc:
        pid = 12345
        def kill(self):
            killed["called"] = True

    stylist._kill_process_tree(_FakeProc())
    assert killed["called"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stylist.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'src.agents.stylist'`

- [ ] **Step 3: Create `src/agents/stylist.py`** — modul VERBATIM ze specu, řádky 433-715 (od docstringu `"""Stylistický průchod přes Codex CLI. ...` po konec `_codex_argv` a `_kill_process_tree` na řádku 746). Konkrétně zahrň:
  - modulový docstring (řádky 434-522) a importy (523-532): `import json, os, re, shutil, subprocess, sys, tempfile`, `import config`, `from src.llm.parsing import extract_json`
  - `SYSTEM_PROMPT_TEMPLATE` (534-559)
  - `class StylistError(Exception)` (562-565)
  - `_LINE_ENDING_RE`, `_paragraph_count` (568-579)
  - `_NUMBER_RE` (komentář 582-607 + regex 608)
  - `_REDACTED` (611), `_redact_detail` (614-623)
  - `_number_sequence` (626-669)
  - `_resolve_codex_cmd` (672-683)
  - `_CODEX_STATIC_FLAGS` (komentář 686-698 + 699-700)
  - `_codex_argv` (703-715)
  - `_kill_process_tree` (718-746)

  V tomhle tasku NEPIŠ `polish()` ani `check_meaning_preserved()` (Task 5/6). `MEANING_CHECK_PROMPT` taky ne.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stylist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/stylist.py tests/test_stylist.py
git commit -m "feat: stylist.py modul - deterministické guardy, codex argv, kill process tree"
```

---

## Task 5: `stylist.polish()`

**Files:**
- Modify: `src/agents/stylist.py` (přidat `polish()` za `_kill_process_tree`)
- Test: `tests/test_stylist.py`

**Interfaces:**
- Consumes: `_codex_argv`, `_resolve_codex_cmd`, `_kill_process_tree`, `_paragraph_count`, `_number_sequence`, `_redact_detail`, `SYSTEM_PROMPT_TEMPLATE`, `config.STYLIST_ACCEPT_FS_RISK`, `config.STYLIST_MAX_CHARS`, `config.CODEX_MODEL`, `config.STYLIST_TIMEOUT_SECONDS`
- Produces: `stylist.polish(en_text, cz_text, *, timeout: int | None = None, codex_cmd: list[str] | None = None, codex_model: str | None = None, guide_block: str = "") -> str`
  - Pořadí vynucení: `STYLIST_ACCEPT_FS_RISK is not True` → `StylistError("... vypnutý ...")`; `len(en)+len(cz) > STYLIST_MAX_CHARS` → `StylistError("... moc dlouhá ...")`; `codex_cmd is None` → `["codex"]`, prázdný/neúplný → `StylistError("prázdný nebo neúplný ...")`; `codex_model` = `((codex_model if not None else config.CODEX_MODEL) or "").strip()`, prázdný → `StylistError("chybí model")`; `timeout is None` → config; `_resolve_codex_cmd`; TemporaryDirectory; `Popen`(text, utf-8) + `communicate(input=prompt, timeout)`; nonzero exit → `StylistError(... {_redact_detail(stderr[:500])})`; chybí out soubor → `StylistError("nevytvořil")`; prázdný → `StylistError("prázdnou")`; markdown fence → `StylistError("markdown")`; `_paragraph_count` mismatch (redakce); ratio mimo 0.5-1.5 (redakce); `_number_sequence` mismatch (redakce). Vrací `styled`.

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_stylist.py` VERBATIM ze specu:
  - `_fake_codex` helper (řádky 2106-2124)
  - `test_polish_refuses_without_fs_risk_optin` (2054-2062)
  - `test_polish_config_invariants` (2065-2072)
  - `test_polish_uses_config_timeout_and_strips_model` (2075-2103)
  - `test_polish_returns_output_file_contents` (2127-2132)
  - `test_polish_invokes_codex_with_expected_argv` (2135-2189)
  - `test_polish_roundtrips_utf8_diacritics` (2192-2215)
  - `test_polish_long_input_goes_through_stdin_not_argv` (2218-2258)
  - `test_polish_raises_on_nonzero_exit` (2261-2264)
  - `test_polish_raises_on_missing_output_file` (2267-2271)
  - `test_polish_raises_on_timeout` (2274-2278)
  - `test_polish_raises_on_missing_command` (2281-2283)
  - `test_polish_raises_stylist_error_on_permission_error` (2286-2294)
  - `test_polish_raises_on_paragraph_count_mismatch` (2342-2347)
  - `test_polish_raises_on_wildly_different_length` (2350-2353)
  - `test_polish_raises_on_chapter_too_long` (2356-2365)
  - `test_polish_allows_chapter_at_size_limit` (2368-2375)
  - `test_polish_raises_on_changed_number` (2378-2385)
  - `test_polish_raises_on_swapped_numbers_same_set` (2388-2396)
  - `test_polish_raises_on_decimal_separator_change` (2399-2415)
  - `test_polish_raises_on_markdown_fence_wrapper` (2418-2423)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stylist.py -k polish -v`
Expected: FAIL - `AttributeError: module 'src.agents.stylist' has no attribute 'polish'`

- [ ] **Step 3: Implement `polish()`** — přidej do `src/agents/stylist.py` funkci VERBATIM ze specu, řádky 749-949 (od `def polish(en_text: str, cz_text: str, *, timeout: int | None = None,` po `return styled`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stylist.py -v`
Expected: PASS (všechny, včetně Task 4 testů)

- [ ] **Step 5: Commit**

```bash
git add src/agents/stylist.py tests/test_stylist.py
git commit -m "feat: stylist.polish - volání codex exec + strukturální kontrola výstupu"
```

---

## Task 6: `stylist.check_meaning_preserved()`

**Files:**
- Modify: `src/agents/stylist.py` (přidat `MEANING_CHECK_PROMPT` + `check_meaning_preserved` za `polish`)
- Test: `tests/test_stylist.py`

**Interfaces:**
- Consumes: `extract_json`, `config.MODEL_CRITIC`, `config.MAX_TOKENS_CRITIC`, `client.complete(...)` (stejné rozhraní jako `critic.review` - `FakeLLMClient`)
- Produces: `stylist.check_meaning_preserved(cz_before, cz_after, client, *, model=None, max_tokens=None) -> list`
  - Vrací seznam findings tvaru `{"source": "stylist_check", "type": "meaning_drift"|"register_drift", "severity": "critical", "action": "revise", "term_id": None, "expected": None, "actual": None, "cz_excerpt": None, "issue": <str>, "suggestion": None}`. Prázdný seznam = beze změny.
  - Useknutá / nečitelná / neplatný tvar odpovědi → `meaning_drift` finding ("nevím" = "radši zamítnout"). `isinstance(..., bool)`, ne `in (True, False)`.

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_stylist.py` (vzor `FakeLLMClient` jako `test_critic.py`):

```python
from src.llm.client import Completion, FakeLLMClient


def _mc(d):
    return FakeLLMClient([Completion(json.dumps(d), False, 5, 5)])


def test_check_meaning_clean_returns_empty():
    out = stylist.check_meaning_preserved(
        "A", "A", _mc({"meaning_changed": False, "register_changed": False}))
    assert out == []


def test_check_meaning_drift_flagged():
    out = stylist.check_meaning_preserved(
        "A", "B", _mc({"meaning_changed": True, "register_changed": False,
                       "issue": "změna faktu"}))
    assert len(out) == 1 and out[0]["type"] == "meaning_drift"


def test_check_register_drift_flagged_standalone():
    out = stylist.check_meaning_preserved(
        "A", "B", _mc({"meaning_changed": False, "register_changed": True,
                       "issue": "ty -> vy"}))
    assert len(out) == 1 and out[0]["type"] == "register_drift"


def test_check_both_flags_yield_both_findings():
    out = stylist.check_meaning_preserved(
        "A", "B", _mc({"meaning_changed": True, "register_changed": True,
                       "issue": "obojí"}))
    assert {f["type"] for f in out} == {"meaning_drift", "register_drift"}


def test_check_truncated_is_treated_as_drift():
    out = stylist.check_meaning_preserved(
        "A", "B", FakeLLMClient([Completion("{partial", True, 5, 5)]))
    assert out and out[0]["type"] == "meaning_drift"


def test_check_unreadable_json_is_drift():
    out = stylist.check_meaning_preserved(
        "A", "B", FakeLLMClient([Completion("not json", False, 5, 5)]))
    assert out and out[0]["type"] == "meaning_drift"


def test_check_numeric_bool_is_invalid_shape_treated_as_drift():
    out = stylist.check_meaning_preserved(
        "A", "B", _mc({"meaning_changed": 0, "register_changed": 0}))
    assert out and out[0]["type"] == "meaning_drift"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stylist.py -k check_ -v`
Expected: FAIL - `AttributeError: ... has no attribute 'check_meaning_preserved'`

- [ ] **Step 3: Implement** — přidej do `src/agents/stylist.py` VERBATIM ze specu, řádky 952-1024: `MEANING_CHECK_PROMPT` (952-971) + `check_meaning_preserved` (974-1024).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stylist.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/stylist.py tests/test_stylist.py
git commit -m "feat: stylist.check_meaning_preserved - třetí síť (CZ-před vs CZ-po, význam + rejstřík)"
```

---

## Task 7: `main.py` malé pomocné funkce (`_say`, `_parse_findings`, `_already_styled`, `_stylist_marker`, `_finding_key`)

**Files:**
- Modify: `main.py` (přidat funkce - umísti je za `_print_usage`, před `# --- příkazy ---`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `json`, `hashlib` (modulové importy z Tasku 1)
- Produces:
  - `main._say(msg: str) -> None` - `try: print(msg) except Exception: pass`
  - `main._parse_findings(notes_json: str | None) -> list` - platný JSON co není list → `[]`; rozbitý JSON → `[]`; filtruje na dict položky
  - `main._already_styled(notes_json: str | None) -> bool` - `any(f.get("source") == "stylist" ...)`
  - `main._stylist_marker(cz_before: str, model: str) -> dict` - `{"source": "stylist", "type": "polish", "severity": "info", "action": "note", "term_id": None, "expected": None, "actual": None, "cz_excerpt": None, "issue": f"stylizováno přes Codex (model={model}), původní délka {len} znaků, hash {sha256}.", "suggestion": None}`
  - `main._finding_key(f: dict) -> tuple` - `(f.get("type"), f.get("term_id"), f.get("actual"))`

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_cli.py`:

```python
def test_say_swallows_broken_pipe(monkeypatch):
    def _boom(*a, **kw):
        raise BrokenPipeError()
    monkeypatch.setattr("builtins.print", _boom)
    main._say("cokoli")   # nesmí vyhodit


def test_parse_findings_tolerates_non_list_and_broken_json():
    assert main._parse_findings("{}") == []
    assert main._parse_findings("nonsense") == []
    assert main._parse_findings(None) == []
    assert main._parse_findings('[{"source":"x"},1,"y"]') == [{"source": "x"}]


def test_already_styled_detects_marker():
    assert main._already_styled('[{"source":"stylist","type":"polish"}]') is True
    assert main._already_styled('[{"source":"concordance"}]') is False
    assert main._already_styled(None) is False


def test_stylist_marker_shape_and_hash():
    m = main._stylist_marker("Ahoj světe", "gpt-5-codex")
    assert m["source"] == "stylist" and m["action"] == "note" and m["severity"] == "info"
    import hashlib
    assert hashlib.sha256("Ahoj světe".encode("utf-8")).hexdigest() in m["issue"]
    assert "model=gpt-5-codex" in m["issue"]


def test_finding_key_includes_actual():
    f = {"type": "inconsistency", "term_id": "t/a", "actual": "špatně"}
    assert main._finding_key(f) == ("inconsistency", "t/a", "špatně")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k "say_swallows or parse_findings or already_styled or stylist_marker or finding_key" -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_say'`

- [ ] **Step 3: Implement** — přidej do `main.py` funkce VERBATIM ze specu:
  - `_say` (řádky 1123-1133)
  - `_parse_findings` (1136-1149)
  - `_already_styled` (1152-1153)
  - `_stylist_marker` (1156-1169)
  - `_finding_key` (1172-1177)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: main.py pomocné funkce pro polish (_say, _parse_findings, marker, finding_key)"
```

---

## Task 8: `main._rejection_reasons` + `main._polish_rejected`

**Proč:** JEDNA rozhodovací logika zamítnutí (seznam důvodů); bool wrapper nad ní. Srovnává PROTI ČERSTVĚ přepočítané baseline, ne absolutně. Spec řádky 1180-1330 + testovací scénáře 2602-2652, 2817-2826.

**Files:**
- Modify: `main.py` (přidat za `_finding_key`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `concordance.find_form_occurrences`, `_finding_key`
- Produces:
  - `main._rejection_reasons(baseline_concordance: list, after_findings: list, cz_before: str, cz_after: str, glossary_rows: list) -> list` - seznam findings odůvodňujících zamítnutí (prázdný = nezamítat). Tři pravidla: (1) `meaning_drift`/`register_drift` vždy; (2) kritikův `source=="critic"` + `action=="revise"` vždy; (3) konkordanční `source=="concordance"` s NOVÝM `_finding_key` proti baseline; (4) navíc pro pre-existující `leak`/`inconsistency` počet výskytů zakázaných povrchů přes `find_form_occurrences` v `cz_before` vs `cz_after` (leak: canonical + aliasy termínu, jen když se termín má překládat; inconsistency: `actual`). Dedup na `_finding_key`.
  - `main._polish_rejected(baseline_concordance, after_findings, cz_before, cz_after, glossary_rows) -> bool` - `bool(_rejection_reasons(...))`

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_cli.py`:

```python
def _term(tid="t/wc", canonical="White Council", cz="Bílá rada", aliases=None):
    return {"term_id": tid, "canonical_en": canonical, "cz": cz,
            "aliases": aliases or []}


def test_rejection_meaning_drift_always_rejects():
    after = [{"source": "stylist_check", "type": "meaning_drift", "issue": "x"}]
    r = main._rejection_reasons([], after, "A", "B", [])
    assert len(r) == 1 and r[0]["type"] == "meaning_drift"
    assert main._polish_rejected([], after, "A", "B", []) is True


def test_rejection_register_drift_standalone_rejects():
    after = [{"source": "stylist_check", "type": "register_drift", "issue": "ty->vy"}]
    assert main._polish_rejected([], after, "A", "B", []) is True


def test_rejection_clean_input_is_not_rejected():
    assert main._rejection_reasons([], [], "A", "A", []) == []
    assert main._polish_rejected([], [], "A", "A", []) is False


def test_rejection_preexisting_concordance_key_not_rejected():
    base = [{"source": "concordance", "type": "omission", "term_id": "t/x",
             "actual": None}]
    after = [dict(base[0])]
    assert main._polish_rejected(base, after, "A", "A", []) is False


def test_rejection_new_concordance_key_rejected():
    base = [{"source": "concordance", "type": "omission", "term_id": "t/x",
             "actual": None}]
    after = base + [{"source": "concordance", "type": "inconsistency",
                     "term_id": "t/y", "actual": "špatný tvar"}]
    assert main._polish_rejected(base, after, "A", "A", []) is True


def test_rejection_critic_minor_note_accepted_revise_rejected():
    minor = [{"source": "critic", "action": "note", "severity": "minor",
              "type": "fluency"}]
    assert main._polish_rejected([], minor, "A", "A", []) is False
    revise = [{"source": "critic", "action": "revise", "severity": "critical",
               "type": "fluency"}]
    assert main._polish_rejected([], revise, "A", "A", []) is True


def test_rejection_leak_occurrence_increase_in_text_rejected():
    # stejný klíč v baseline i after, ale povrch přibyl v cz_after
    key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
           "actual": "White Council"}
    base, after = [dict(key)], [dict(key)]
    before = "Byla to White Council."
    a = "Byla to White Council a pak zas White Council."
    assert main._polish_rejected(base, after, before, a, [_term()]) is True
    # opačný směr - výskytů míň - není odmítnuto
    assert main._polish_rejected(base, after, a, before, [_term()]) is False


def test_rejection_new_alias_leak_rejected():
    key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
           "actual": "White Council"}
    base, after = [dict(key)], [dict(key)]
    before = "Byla to White Council."
    a = "Byla to White Council, totiž the Council."
    assert main._polish_rejected(base, after, before, a,
                                 [_term(aliases=["the Council"])]) is True


def test_rejection_keep_untranslated_term_added_occurrence_not_leak():
    key = {"source": "concordance", "type": "leak", "term_id": "t/mouse",
           "actual": "Mouse"}
    base, after = [dict(key)], [dict(key)]
    t = _term(tid="t/mouse", canonical="Mouse", cz="Mouse")
    assert main._polish_rejected(base, after, "Mouse tu byl.",
                                 "Mouse tu byl, Mouse zas.", [t]) is False


def test_rejection_dedup_new_key_and_occurrence_increase_counted_once():
    key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
           "actual": "White Council"}
    base = []                       # klíč NENÍ v baseline -> nový
    after = [dict(key)]
    before = "text"
    a = "White Council a White Council"
    r = main._rejection_reasons(base, after, before, a, [_term()])
    leak_keys = [x for x in r if x.get("type") == "leak"]
    assert len(leak_keys) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k rejection -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_rejection_reasons'`

- [ ] **Step 3: Implement** — přidej do `main.py` VERBATIM ze specu: `_rejection_reasons` (řádky 1180-1319) a `_polish_rejected` (1322-1330).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -k rejection -v`
Expected: PASS. Pokud test na `find_form_occurrences` chování překvapí, ověř skutečné chování `src/concordance.py:43` a uprav OČEKÁVÁNÍ testu (ne implementaci ze specu) - `find_form_occurrences` stemuje + lowercasuje obě strany.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: main._rejection_reasons/_polish_rejected - rozhodovací brána zamítnutí vs baseline"
```

---

## Task 9: `main._snapshot_db` + `main._backup_db_once`

**Files:**
- Modify: `main.py` (přidat za `_polish_rejected`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `sqlite3`, `time`, `os`, `_say`
- Produces:
  - `main._snapshot_db(db: str, snapshot_path: str, *, timeout: float = 30.0) -> None` - `sqlite3.connect(db).backup(dst, pages=100, progress=<deadline check>)` + `PRAGMA integrity_check` na výsledku; `TimeoutError` z progress callbacku po `timeout` s; `OSError` když integrity_check != "ok"
  - `main._backup_db_once(db: str, backup_state: dict) -> None` - když `backup_state["done"]` → return; jinak `os.replace(backup_state["snapshot_path"], db + ".pre-polish-backup")`, `backup_state["done"] = True` HNED, pak `_say(...)`

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_cli.py`:

```python
def test_snapshot_db_produces_logically_equal_copy(tmp_path):
    src = str(tmp_path / "s.sqlite3")
    state.init_db(src)
    with state.connect(src) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t/a','A','Á')")
    snap = str(tmp_path / "snap.sqlite3")
    main._snapshot_db(src, snap)
    with state.connect(snap) as conn:
        rows = conn.execute("SELECT term_id FROM glossary").fetchall()
    assert [r["term_id"] for r in rows] == ["t/a"]


def test_snapshot_db_backup_called_with_pages_100(tmp_path, monkeypatch):
    src = str(tmp_path / "s.sqlite3"); state.init_db(src)
    seen = []
    real_connect = main.sqlite3.connect

    class _Proxy:
        def __init__(self, real): self._real = real
        def backup(self, dst, **kw):
            seen.append(kw.get("pages"))
            return self._real.backup(dst._real if isinstance(dst, _Proxy) else dst, **kw)
        def __getattr__(self, n): return getattr(self._real, n)
        def close(self): self._real.close()

    monkeypatch.setattr(main.sqlite3, "connect", lambda p: _Proxy(real_connect(p)))
    main._snapshot_db(src, str(tmp_path / "snap.sqlite3"))
    assert 100 in seen


def test_snapshot_db_deadline_interrupts(tmp_path, monkeypatch):
    src = str(tmp_path / "s.sqlite3"); state.init_db(src)
    real_connect = main.sqlite3.connect
    times = iter([0.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr(main.time, "monotonic", lambda: next(times))

    class _Proxy:
        def __init__(self, real): self._real = real
        def backup(self, dst, *, pages=None, progress=None):
            progress(0, 5, 10)   # deadline check uvnitř vyhodí
        def __getattr__(self, n): return getattr(self._real, n)
        def close(self): self._real.close()

    monkeypatch.setattr(main.sqlite3, "connect", lambda p: _Proxy(real_connect(p)))
    with pytest.raises(TimeoutError):
        main._snapshot_db(src, str(tmp_path / "snap.sqlite3"))


def test_snapshot_db_integrity_check_failure_raises_oserror(tmp_path, monkeypatch):
    src = str(tmp_path / "s.sqlite3"); state.init_db(src)
    real_connect = main.sqlite3.connect
    calls = {"n": 0}

    class _Proxy:
        def __init__(self, real): self._real = real
        def execute(self, sql, *a):
            if "integrity_check" in sql:
                class _C:
                    def fetchone(self): return ("not ok",)
                return _C()
            return self._real.execute(sql, *a)
        def backup(self, dst, **kw): return self._real.backup(dst._real, **kw)
        def __getattr__(self, n): return getattr(self._real, n)
        def close(self): self._real.close()

    monkeypatch.setattr(main.sqlite3, "connect", lambda p: _Proxy(real_connect(p)))
    with pytest.raises(OSError):
        main._snapshot_db(src, str(tmp_path / "snap.sqlite3"))


def test_backup_db_once_promotes_snapshot_atomically(tmp_path):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    snap = db + ".pre-polish-snapshot"
    main._snapshot_db(db, snap)
    bs = {"done": False, "snapshot_path": snap}
    main._backup_db_once(db, bs)
    assert bs["done"] is True
    assert os.path.exists(db + ".pre-polish-backup")
    assert not os.path.exists(snap)
    # druhé volání je no-op
    main._backup_db_once(db, bs)


def test_backup_db_once_promotion_survives_broken_print(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    snap = db + ".pre-polish-snapshot"
    main._snapshot_db(db, snap)
    monkeypatch.setattr("builtins.print", lambda *a, **k: (_ for _ in ()).throw(BrokenPipeError()))
    bs = {"done": False, "snapshot_path": snap}
    main._backup_db_once(db, bs)   # nesmí vyhodit
    assert bs["done"] is True and os.path.exists(db + ".pre-polish-backup")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k "snapshot_db or backup_db_once" -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_snapshot_db'`

- [ ] **Step 3: Implement** — přidej do `main.py` VERBATIM ze specu: `_snapshot_db` (řádky 1333-1384) a `_backup_db_once` (1387-1462).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -k "snapshot_db or backup_db_once" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: main._snapshot_db/_backup_db_once - konzistentní záloha DB před polish"
```

---

## Task 10: `main._write_polish_report` + report konstanty

**Files:**
- Modify: `main.py` (přidat za `_backup_db_once`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `_dt`, `json`, `os`, `_say`
- Produces:
  - `main._REPORT_SCHEMA_VERSION = 1`
  - `main._REPORT_OUTCOMES = ("polished", "unchanged", "rejected", "failed", "fatal", "interrupted")`
  - `main._write_polish_report(db: str, rid: int, report: list, *, codex_model: str, planned_count: int, batch_completed: bool, run_status: str, run_error: str | None = None, finalization_error: str | None = None) -> None` - zapíše `polish-reports/run-<rid>-<stamp>-<8hex>.json` atomicky (tmp + `os.replace`). Hlavička: `schema_version`, `run_id`, `codex_model`, `generated_at` (timezone-aware ISO), `planned_count`, `attempted_count` (= `len(report)`), `batch_completed`, `run_status`, `run_error`, `finalization_error`, `summary` (dict count per `_REPORT_OUTCOMES`), `chapters` (= `report`). Celé sestavení + zápis v `except Exception` (best-effort), selhání jen `_say` + úklid `.tmp`.

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_cli.py`:

```python
def _read_only_report(dirpath):
    import glob
    files = glob.glob(os.path.join(dirpath, "polish-reports", "run-*.json"))
    assert len(files) == 1, files
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


def test_write_polish_report_shape(tmp_path):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    report = [{"idx": 1, "outcome": "polished"},
              {"idx": 2, "outcome": "rejected", "reason_types": ["critic/critic_failed"]},
              {"idx": 3, "outcome": "failed", "error": "boom"}]
    main._write_polish_report(db, 7, report, codex_model="gpt-5-codex",
                              planned_count=4, batch_completed=True, run_status="ok")
    r = _read_only_report(str(tmp_path))
    assert r["schema_version"] == 1 and r["run_id"] == 7
    assert r["codex_model"] == "gpt-5-codex"
    assert r["planned_count"] == 4 and r["attempted_count"] == 3
    assert r["batch_completed"] is True and r["run_status"] == "ok"
    assert r["run_error"] is None and r["finalization_error"] is None
    assert r["summary"] == {"polished": 1, "unchanged": 0, "rejected": 1,
                            "failed": 1, "fatal": 0, "interrupted": 0}
    assert r["generated_at"]


def test_write_polish_report_best_effort_on_json_typeerror(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    monkeypatch.setattr(main.json, "dump",
                        lambda *a, **k: (_ for _ in ()).throw(TypeError("x")))
    main._write_polish_report(db, 1, [], codex_model="m", planned_count=0,
                              batch_completed=True, run_status="ok")   # nesmí vyhodit
    import glob
    assert glob.glob(os.path.join(str(tmp_path), "polish-reports", "*.tmp")) == []
    assert glob.glob(os.path.join(str(tmp_path), "polish-reports", "*.json")) == []


def test_write_polish_report_best_effort_on_makedirs_oserror(tmp_path, monkeypatch):
    db = str(tmp_path / "state.sqlite3"); state.init_db(db)
    monkeypatch.setattr(main.os, "makedirs",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    main._write_polish_report(db, 1, [], codex_model="m", planned_count=0,
                              batch_completed=True, run_status="ok")   # nesmí vyhodit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k write_polish_report -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_write_polish_report'`

- [ ] **Step 3: Implement** — přidej do `main.py` VERBATIM ze specu: `_REPORT_SCHEMA_VERSION` (řádek 1637), `_REPORT_OUTCOMES` (1640-1641), `_write_polish_report` (1644-1743).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -k write_polish_report -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: main._write_polish_report - JSON report běhu polish (měřicí přístroj v1)"
```

---

## Task 11: `main._polish_one_chapter`

**Proč:** zpracování JEDNÉ kapitoly: `stylist.polish` → `styled==cz` short-circuit → baseline + after konkordance → kritik + `_rejection_reasons` (fail-fast) → `check_meaning_preserved` → přijetí (marker + `_backup_db_once` + `commit_chapter_result`) nebo zamítnutí. Vrací `dict`, `report` NEmutuje. Spec řádky 1465-1634 + scénáře 2661-2677, 2723-2729, 2744-2751.

**Files:**
- Modify: `main.py` (přidat za `_write_polish_report`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `stylist.polish`, `stylist.check_meaning_preserved`, `stylist._redact_detail`, `stylist.StylistError`, `state.chapter_mentions`, `state.commit_chapter_result`, `concordance.check_chapter`, `concordance.build_mentions`, `pipeline._run_critic`, `_rejection_reasons`, `_stylist_marker`, `_backup_db_once`, `_say`, `FatalRunError`, `config.STYLIST_TIMEOUT_SECONDS`, `config.STYLIST_REPORT_REJECTED_TEXT`
- Produces: `main._polish_one_chapter(c, glossary_rows, cf, db, model: str, guide_block: str, codex_cmd: list, backup_state: dict) -> dict`
  - Tvary návratu: `{"idx", "outcome": "polished"|"unchanged"}`; `{"idx", "outcome": "failed", "error": <str>}`; `{"idx", "outcome": "rejected", "reason_types": [...]}` (+ `reasons`/`findings`/`styled` jen za `STYLIST_REPORT_REJECTED_TEXT is True`)
  - `FatalRunError` (selhání commitu NEBO fatální chyba klienta z kritika/meaning-checku) NEobaluje do dictu - propaguje ven s hláškou REDIGOVANOU U ZDROJE. `KeyboardInterrupt` propaguje.

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_cli.py`. Vzor: monkeypatch `main.stylist.polish`, `main.stylist.check_meaning_preserved`, `main.pipeline._run_critic`, `main.concordance.check_chapter`/`build_mentions`. Pomocná kapitola `c = {"idx": 1, "raw_text": "EN", "translated_text": "Původní věta.", "revision_rounds": 0, "notes": None}`.

```python
import pytest
import main
from src import state
from src.llm.client import FatalRunError
from src.agents import stylist as _stylist


def _polish_db(tmp_path):
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,translated_text,"
                     "status,revision_rounds) VALUES (1,'K1','EN','Původní věta.','done',0)")
    return db


def _c():
    return {"idx": 1, "raw_text": "EN", "translated_text": "Původní věta.",
            "revision_rounds": 0, "notes": None}


def _cf_stub(agent):
    return object()


def _bs(db):
    snap = db + ".pre-polish-snapshot"
    main._snapshot_db(db, snap)
    return {"done": False, "snapshot_path": snap}


def test_polish_one_chapter_unchanged(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Původní věta.")
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert rec == {"idx": 1, "outcome": "unchanged"}


def test_polish_one_chapter_stylist_error_is_failed(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    def _boom(*a, **k): raise _stylist.StylistError("nope")
    monkeypatch.setattr(main.stylist, "polish", _boom)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert rec["outcome"] == "failed" and "nope" in rec["error"]
    assert state.get_chapter(db, 1)["translated_text"] == "Původní věta."


def test_polish_one_chapter_accepts_and_commits(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "gpt-5-codex", "",
                                   ["codex"], _bs(db))
    assert rec == {"idx": 1, "outcome": "polished"}
    ch = state.get_chapter(db, 1)
    assert ch["translated_text"] == "Vylepšená věta." and ch["status"] == "done"
    assert main._already_styled(ch["notes"]) is True
    assert os.path.exists(db + ".pre-polish-backup")


def test_polish_one_chapter_rejected_default_hides_detail(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta se SECRET.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: ([{"source": "critic", "action": "revise",
                                           "severity": "critical", "type": "fidelity",
                                           "issue": "SECRET"}], False))
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", False)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert rec["outcome"] == "rejected"
    assert rec["reason_types"] == ["critic/fidelity"]
    assert "reasons" not in rec and "findings" not in rec and "styled" not in rec
    assert state.get_chapter(db, 1)["translated_text"] == "Původní věta."


def test_polish_one_chapter_rejected_full_detail_when_opted_in(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved",
                        lambda *a, **k: [{"source": "stylist_check",
                                          "type": "meaning_drift", "issue": "x"}])
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", True)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert rec["outcome"] == "rejected" and rec["styled"] == "Jiná věta."
    assert "reasons" in rec and "findings" in rec


def test_polish_one_chapter_commit_failure_is_fatal_redacted(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    monkeypatch.setattr(main.state, "commit_chapter_result",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("SECRET123")))
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", False)
    with pytest.raises(FatalRunError) as ei:
        main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert "Zápis výsledku kapitoly" in str(ei.value)
    assert "SECRET123" not in str(ei.value)


def test_polish_one_chapter_critic_fatal_is_wrapped_redacted(tmp_path, monkeypatch):
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Vylepšená věta.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: (_ for _ in ()).throw(FatalRunError("SECRET123")))
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", False)
    with pytest.raises(FatalRunError) as ei:
        main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert "Kontrola stylizace kapitoly" in str(ei.value)
    assert "SECRET123" not in str(ei.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k polish_one_chapter -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_polish_one_chapter'`

- [ ] **Step 3: Implement** — přidej do `main.py` funkci VERBATIM ze specu, řádky 1465-1634 (`def _polish_one_chapter(...)` po `return {"idx": idx, "outcome": "polished"}`). Import `from src.agents import stylist` je uvnitř funkce (spec řádek 1500) - `main.stylist` proto v testech monkeypatchni přes `monkeypatch.setattr("main.stylist.polish", ...)` NEBO importuj `stylist` i modulově; DRŽ SE způsobu ve specu (lokální import) a testy monkeypatchují `src.agents.stylist` atributy přímo. **Pozn.:** pokud lokální import brání monkeypatchování v testech výše (které dělají `main.stylist`), přidej `from src.agents import stylist` na modulovou úroveň `main.py` VEDLE lokálního - obojí ukazuje na stejný modul, monkeypatch atributu modulu funguje z obou.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -k polish_one_chapter -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: main._polish_one_chapter - zpracování jedné kapitoly + tři kontrolní sítě"
```

---

## Task 12: `main._cmd_polish` + registrace příkazu

**Proč:** orchestrace celé dávky: bezpečnostní hláška → kontrola modelu → preflight → snapshot DB → smyčka kapitol s per-kapitolovou izolací (ale `FatalRunError`/`KeyboardInterrupt` propagují) → `finish_run` + report ve `finally`. Spec řádky 1746-2024 + scénáře 2503-2843, tabulka 2845-2879.

**Files:**
- Modify: `main.py` (přidat `_cmd_polish` mezi příkazy; do `_build_parser()` přidat `p_pol`; přidat `"polish"` do `_MUTATING`; doplnit modulový docstring "Fáze běhu:")
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `_polish_one_chapter`, `_snapshot_db`, `_write_polish_report`, `_already_styled`, `_say`, `stylist._resolve_codex_cmd`, `state.chapters_by_status`, `state.create_run`, `state.finish_run`, `state.get_chapter`, `glossary.all_terms`, `guide_mod.load_guide`/`guide_as_prompt_block`, `_client_factory`, `_print_usage`, `FatalRunError`, `config.STYLIST_ACCEPT_FS_RISK`, `config.CODEX_MODEL`, `config.GUIDE_PATH`, `config.DB_PATH`
- Produces: `main._cmd_polish(args) -> int` - `args.only: list[int] | None`, `args.force: bool`. Návrat 0 (ok) / 1 (fatal, chybí model, preflight selhal, všechny kapitoly failed). Parser: `polish [--only IDX...] [--force]`.

- [ ] **Step 1: Write the failing tests** — přidej do `tests/test_cli.py`. Použij `_run` helper (nahoře v souboru), který monkeypatchuje config cesty a volá `main.main(argv)`. Pro polish scénáře je čistší volat `main._cmd_polish` přímo s malým `args` stubem po nastavení `config.DB_PATH`.

```python
class _Args:
    def __init__(self, only=None, force=False):
        self.only = only
        self.force = force


def _polish_env(tmp_path, monkeypatch, n_done=1):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "state.sqlite3"))
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "gpt-5-codex")
    monkeypatch.setattr(config, "GUIDE_PATH", str(tmp_path / "guide.json"))
    state.init_db(config.DB_PATH)
    with state.connect(config.DB_PATH) as conn:
        for i in range(1, n_done + 1):
            conn.execute("INSERT INTO chapters (idx,title,raw_text,translated_text,"
                         "status,revision_rounds) VALUES (?,?,?,?,'done',0)",
                         (i, f"K{i}", "EN", f"Věta {i}."))
    monkeypatch.setattr(main.stylist, "_resolve_codex_cmd", lambda c: ["codex", "resolved"])
    monkeypatch.setattr(main.guide_mod, "load_guide", lambda p: {})
    monkeypatch.setattr(main.guide_mod, "guide_as_prompt_block", lambda g: "")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    monkeypatch.setattr(main, "_print_usage", lambda *a, **k: None)
    monkeypatch.setattr(main, "_client_factory", lambda rid, *, interactive: (lambda a: object()))
    return config.DB_PATH


def _report(db):
    import glob
    files = glob.glob(os.path.join(os.path.dirname(db), "polish-reports", "run-*.json"))
    assert len(files) == 1, files
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


def test_cmd_polish_refuses_without_fs_risk_optin(tmp_path, monkeypatch, capsys):
    _polish_env(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", 1)   # truthy != True
    assert main._cmd_polish(_Args()) == 1
    assert "vypnutý" in capsys.readouterr().out


def test_cmd_polish_refuses_without_model(tmp_path, monkeypatch):
    _polish_env(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "CODEX_MODEL", "  ")
    assert main._cmd_polish(_Args()) == 1
    with state.connect(config.DB_PATH) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"] == 0


def test_cmd_polish_preflight_failure_returns_1(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch)
    def _boom(c): raise _stylist.StylistError("Codex nenalezen")
    monkeypatch.setattr(main.stylist, "_resolve_codex_cmd", _boom)
    assert main._cmd_polish(_Args()) == 1


def test_cmd_polish_happy_path_polishes_and_reports(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    monkeypatch.setattr(main.stylist, "polish",
                        lambda en, cz, **k: cz.replace("Věta", "Lepší věta"))
    assert main._cmd_polish(_Args()) == 0
    assert state.get_chapter(db, 1)["translated_text"] == "Lepší věta 1."
    r = _report(db)
    assert r["run_status"] == "ok" and r["batch_completed"] is True
    assert r["planned_count"] == 2 and r["attempted_count"] == 2
    assert r["summary"]["polished"] == 2
    with state.connect(db) as conn:
        assert conn.execute("SELECT status FROM runs").fetchone()["status"] == "ok"


def test_cmd_polish_all_failed_is_fatal_but_batch_completed(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(_stylist.StylistError("x")))
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is True
    assert r["attempted_count"] == 3 and r["summary"]["failed"] == 3


def test_cmd_polish_fatal_commit_midbatch_stops_and_reports(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    calls = {"n": 0}
    real = main.state.commit_chapter_result
    def _wrap(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise Exception("disk full")
        return real(*a, **k)
    monkeypatch.setattr(main.state, "commit_chapter_result", _wrap)
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is False
    assert r["attempted_count"] == 2 and r["planned_count"] == 3
    outcomes = [c["outcome"] for c in r["chapters"]]
    assert outcomes == ["polished", "fatal"]


def test_cmd_polish_skips_already_styled_without_force(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"source": "stylist", "type": "polish"}]),))
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("nemá se volat")))
    assert main._cmd_polish(_Args()) == 0


def test_cmd_polish_only_reports_skipped_non_done(tmp_path, monkeypatch, capsys):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " x")
    assert main._cmd_polish(_Args(only=[1, 99])) == 0
    assert "99" in capsys.readouterr().out


def test_cmd_polish_report_survives_broken_stdout(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " x")
    monkeypatch.setattr("builtins.print",
                        lambda *a, **k: (_ for _ in ()).throw(BrokenPipeError()))
    assert main._cmd_polish(_Args()) == 0
    r = _report(db)
    assert r["summary"]["polished"] == 1


def test_cmd_polish_snapshot_failure_is_fatal_no_run_row(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main, "_snapshot_db",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no space")))
    assert main._cmd_polish(_Args()) == 1
    with state.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"] == 0


def test_cmd_polish_keyboardinterrupt_during_chapter(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    def _ki(*a, **k): raise KeyboardInterrupt()
    monkeypatch.setattr(main.stylist, "polish", _ki)
    with pytest.raises(KeyboardInterrupt):
        main._cmd_polish(_Args())
    r = _report(db)
    assert r["run_status"] == "interrupted"
    assert r["chapters"][0]["outcome"] == "interrupted"
    assert r["chapters"][0]["stage"] == "processing"


def test_cmd_polish_finish_run_failure_does_not_mask_result(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " x")
    monkeypatch.setattr(main.state, "finish_run",
                        lambda *a, **k: (_ for _ in ()).throw(Exception("db locked")))
    assert main._cmd_polish(_Args()) == 0
    r = _report(db)
    assert r["finalization_error"] and r["run_status"] == "ok"


def test_polish_command_registered_and_mutating():
    p = main._build_parser()
    ns = p.parse_args(["polish", "--only", "1", "2", "--force"])
    assert ns.func is main._cmd_polish
    assert ns.only == [1, 2] and ns.force is True
    assert "polish" in main._MUTATING
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k "cmd_polish or polish_command" -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_cmd_polish'`

- [ ] **Step 3: Implement** — do `main.py`:
  1. Přidej `_cmd_polish` VERBATIM ze specu, řádky 1746-2005 (`def _cmd_polish(args) -> int:` po konec `finally` bloku).
  2. Do `_build_parser()` (za `p_run` blok, před `sub.add_parser("status", ...)`) přidej VERBATIM ze specu řádky 2011-2016:
     ```python
     p_pol = sub.add_parser("polish", help="stylistický průchod přes Codex (nad hotovými kapitolami)")
     p_pol.add_argument("--only", nargs="+", type=int, default=None,
                        help="jen tyhle kapitoly (musí být status=='done')")
     p_pol.add_argument("--force", action="store_true",
                        help="stylizuj i kapitoly, co už prošly (přepíše dřívější stylizaci)")
     p_pol.set_defaults(func=_cmd_polish)
     ```
  3. Do `_MUTATING` (řádek 28) přidej `"polish"`: `_MUTATING = {"init", "scan", "run", "answer", "review", "reference", "polish"}`
  4. Do modulového docstringu `main.py` "Fáze běhu:" sekce přidej řádek (za `run`):
     `    polish [--only IDX...] [--force]   stylistický průchod přes Codex (status=="done", volitelné, za STYLIST_ACCEPT_FS_RISK)`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v && python -m pytest -q`
Expected: PASS (celá sada zelená, žádná regrese)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: main._cmd_polish + příkaz polish - orchestrace stylistické dávky + report"
```

---

## Task 13: manuální ověření + POVINNÝ CANARY TEST

**Proč:** všechny automatizované testy mockují Codex CLI - je to test LOGIKY, ne skutečného kontraktu reálného `codex exec`. Spec řádky 2450-2501.

**Files:**
- žádné změny kódu - ověřovací běh + zápis poznámky

- [ ] **Step 1: Preflight a flagy** — na cílovém stroji ověř:
  - `shutil.which("codex")` najde executable
  - `codex exec --help` uvádí `--ephemeral`, `--ignore-user-config`, `-o`, `-C`, `-m`, pozicionální `-` (stdin)

- [ ] **Step 2: Reálný běh nad jednou kapitolou** — nastav `config.CODEX_MODEL` a `config.STYLIST_ACCEPT_FS_RISK = True`, spusť `python main.py polish --only <IDX jedné done kapitoly>`. Zkontroluj OKEM:
  - výstup je česky plynulejší, beze změny faktů/jmen/čísel/počtu odstavců
  - kapitola buď `polished` (a `notes` má `stylist` marker), nebo `rejected` s vypsanými `reason_types`
  - vznikl `polish-reports/run-<rid>-*.json` se správnou hlavičkou
  - diakritika prošla stdin i zpět nepoškozená

- [ ] **Step 3: POVINNÝ CANARY TEST (bezpečnostně kritické - NEPŘESKAKOVAT)** — spusť `codex exec` s PŘESNĚ tím, co vrací `stylist._codex_argv(stylist._resolve_codex_cmd(["codex"]), <izolovaný dočasný adresář>, <out.txt v tom adresáři>, config.CODEX_MODEL)` - tedy s rozřešeným příkazem a včetně `--ephemeral`, `--ignore-user-config`, `-m <model>`, koncového `-`. Prompt (stdinem) žádá přečíst a vrátit obsah souboru MIMO `-C` adresář (jiný soubor v `%TEMP%`).
  - `--ignore-rules` NESMÍ být v argv (regrese, pokud tam je)
  - Zaznamenej výsledek: pokud Codex soubor mimo `-C` PŘEČETL, je prompt-injection riziko z textu knihy POTVRZENÉ (ne jen teoretické) - to je očekávané chování `--sandbox read-only` na dosavadní verzi CLI. Rozhodnutí nasadit `polish` s tímhle rizikem patří uživateli (opt-in `STYLIST_ACCEPT_FS_RISK` už tohle vyjadřuje).

- [ ] **Step 4: Zápis výsledku** — do commit message nebo krátké poznámky do `docs/superpowers/specs/2026-09-08-stylist-agent-design.md` (sekce "Manuální ověření") zapiš datum, verzi Codex CLI, a výsledek canary testu.

- [ ] **Step 5: Commit** (jen pokud jsi upravil spec poznámku)

```bash
git add docs/superpowers/specs/2026-09-08-stylist-agent-design.md
git commit -m "docs: výsledek manuálního ověření + canary testu stylist průchodu"
```

---

## Self-review (proti specu)

**1. Spec coverage:**
- `config.py` hodnoty (spec 342-401) → Task 1 ✓
- `main.py` modulové importy (403-429) → Task 1 ✓
- `critic.review()` oprava + 8 testů (131-286) → Task 2 ✓
- `state.chapter_mentions` + test (288-329) → Task 3 ✓
- `stylist.py` helpery, argv, kill (433-746) → Task 4 ✓
- `stylist.polish()` + ~20 testů (749-949, 2054-2435) → Task 5 ✓
- `stylist.check_meaning_preserved` + testy (952-1024, 2438-2448) → Task 6 ✓
- `main` malé helpery (1123-1177) → Task 7 ✓
- `_rejection_reasons`/`_polish_rejected` (1180-1330, 2602-2652) → Task 8 ✓
- `_snapshot_db`/`_backup_db_once` (1333-1462, 2544-2589) → Task 9 ✓
- `_write_polish_report` + konstanty (1637-1743, 2703-2843) → Task 10 ✓
- `_polish_one_chapter` (1465-1634, 2661-2677) → Task 11 ✓
- `_cmd_polish` + parser + `_MUTATING` + docstring (1746-2024, 2503-2843) → Task 12 ✓
- Manuální ověření + canary (2450-2501) → Task 13 ✓
- Tabulka chybových stavů (2845-2879) → pokryta scénáři v Task 8/11/12 ✓

**2. Placeholder scan:** velké bloky kódu jsou v plánu odkázané VERBATIM na konkrétní rozsahy řádků specu (ne "TODO"/"implement later") - spec cestuje s plánem (viz hlavička). Všechny testy jsou inline s plným kódem. Signatury a invarianty v Interfaces blocích jsou explicitní.

**3. Type consistency:** `_polish_one_chapter` vrací `dict` a `_cmd_polish` appendne jednou za iteraci (Task 11 + 12 konzistentní). `_rejection_reasons` vrací `list`, `_polish_rejected` `bool` wrapper (Task 8). `stylist.polish` signatura stejná v Task 5 Interfaces i v Task 11 volání (`codex_cmd=`, `codex_model=`, `guide_block=`, `timeout=`). `_finding_key` = `(type, term_id, actual)` v Task 7 i Task 8. `_write_polish_report` kwargs stejné v Task 10 i Task 12 `finally`.

**Riziková místa pro executora:**
- Task 11: lokální `from src.agents import stylist` uvnitř `_polish_one_chapter` vs. monkeypatch v testech - plán říká přidat i modulový import do `main.py`. Ověř, že to nerozbije monkeypatch v existujících `test_cli.py` testech.
- Task 8: přesné chování `concordance.find_form_occurrences` (stemování/lowercasing) - když test neprojde, uprav OČEKÁVÁNÍ testu, ne kód ze specu.
- Task 12: `_cmd_polish` čte `c["notes"]`, `c["raw_text"]`, `c["translated_text"]`, `c["revision_rounds"]` z řádků `chapters_by_status` - všechny sloupce existují (`src/state.py:7-16`).
