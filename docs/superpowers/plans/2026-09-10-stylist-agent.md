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
- **Fake Codex skripty v testech, co stdin PARSUJÍ regexem, čtou `sys.stdin.buffer.read().decode("utf-8").replace("\r\n", "\n")`** - ne holé `sys.stdin.read()`. Dva důvody: (a) rodičovský `Popen(encoding="utf-8")` kóduje ZÁPIS jako UTF-8, ale potomkův `sys.stdin` na Windows/cp1252 (Python 3.11-3.14) čte lokálním kódováním a český prompt rozbije → nutný `buffer` + explicitní `decode("utf-8")`; (b) `Popen(text=True)` s výchozím `newline` překládá `\n`→`\r\n` na zápisu na Windows, a `buffer` (raw) tuhle translaci NEVRACÍ → nutný `.replace("\r\n", "\n")`, jinak regexové kotvy `---\n(...)` nesednou. Vědomá odchylka od spec-verbatim (spec: `sys.stdin.read()`). Skripty, co stdin jen DRENÁŽUJÍ bez parsování (`sys.stdin.buffer.read()`), `.decode`/`.replace` nepotřebují; `_fake_codex` stdin nečte vůbec.
- **Délkový guard `stylist.polish` (`0.5 <= len(styled)/len(cz) <= 1.5`, spec 929-930)** platí PŘED vrácením výstupu. Některé pozitivní testy převzaté ze specu mají fake výstup delší než 1,5× vstup (spec-latentní chyba) - plán je v příslušných taskech nahrazuje verzemi s bezpečným poměrem. NIKDY neupravuj produkční limit, jen vstupy/výstupy testu.
- **Commity často** - každý task končí commitnutým, samostatně testovatelným deliverable. KAŽDÝ commit message končí trailerem:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```
  Ukázky `git commit -m "..."` v taskech ten trailer pro stručnost vynechávají - executor ho VŽDY doplní (heredoc nebo `-m` + `-m`).

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

- [ ] **Step 3: Add config values** — připoj na konec `config.py` blok VERBATIM ze specu, řádky 345-400 (od komentáře `# --- stylistický průchod přes Codex ---` po `STYLIST_REPORT_REJECTED_TEXT = False`, včetně všech komentářů; markdown fence ``` na řádcích 344/401 NEKOPÍRUJ).

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
- Produces: `critic.review(en_chapter, cz_chapter, client, *, model=None, max_tokens=None) -> list` - vrací seznam findings; useknutý/rozbitý/nekonzistentní výstup zkusí jednou znovu, pak vyhodí výjimku (`ValueError` nebo `OutputTruncated`). Nově rozbité: nedict top-level; `findings` co je non-list A ZÁROVEŇ non-None (spec 188 - `null` / chybějící klíč se bere jako `[]`, NErozbíjí); nedict položka; neplatný `severity`/`type` enum; neplatný `verdict` enum. `verdict=="revise"` bez žádného `action=="revise"` nálezu → syntetický `revise` finding připojen.

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


def test_review_findings_null_or_missing_is_empty_not_broken():
    """spec 188/229: `null` nebo chybějící `findings` s verdiktem `pass` ->
    prázdný seznam, NErozbíjí odpověď."""
    for resp in (json.dumps({"verdict": "pass", "findings": None}),
                 json.dumps({"verdict": "pass"})):
        assert critic.review("EN", "CZ",
                             FakeLLMClient([Completion(resp, False, 5, 5)])) == []


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

- [ ] **Step 3: Create `src/agents/stylist.py`** — modul VERBATIM ze specu, řádky 434-746 (od docstringu `"""Stylistický průchod přes Codex CLI. ...` po konec `_kill_process_tree` na řádku 746; markdown fence ``` na 433 NEKOPÍRUJ). Konkrétně zahrň:
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

- [ ] **Step 1a: Write VERBATIM tests** — přidej do `tests/test_stylist.py` VERBATIM ze specu (fake skript stdin NEČTOU, nebo nemají český obsah přes stdin - hardening netřeba):
  - `_fake_codex` helper (řádky 2106-2124)
  - `test_polish_refuses_without_fs_risk_optin` (2054-2062)
  - `test_polish_config_invariants` (2065-2072)
  - `test_polish_roundtrips_utf8_diacritics` (2192-2215) - **ALE** ve fake skriptu nahraď `received = sys.stdin.read()` za `received = sys.stdin.buffer.read().decode("utf-8").replace("\r\n", "\n")` (Global Constraint - cp1252 dekódování + CRLF normalizace)
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

- [ ] **Step 1b: Write CORRECTED tests** — tyto 4 testy spec verze porušují buď délkový guard (fake výstup > 1,5× vstup) nebo cp1252 stdin dekódování. Použij tyto verze MÍSTO spec verbatim:

```python
def test_polish_returns_output_file_contents(tmp_path):
    cz = ("Prvni odstavec byl napsan drive a ted se cte hur.\n\n"
          "Druhy odstavec byl take napsan drive a cte se podobne.")
    out = ("Prvni odstavec vznikl drive a ted se cte hure.\n\n"
           "Druhy odstavec rovnez vznikl drive a cte se obdobne.")
    cmd = _fake_codex(tmp_path, out)
    assert stylist.polish("EN text", cz, codex_cmd=cmd) == out


def test_polish_uses_config_timeout_and_strips_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STYLIST_TIMEOUT_SECONDS", 999)
    seen = {}
    real_popen = stylist.subprocess.Popen

    class SpyPopen(real_popen):
        def communicate(self, *a, **kw):
            seen["timeout"] = kw.get("timeout")
            return super().communicate(*a, **kw)

    monkeypatch.setattr(stylist.subprocess, "Popen", SpyPopen)
    argv_path = tmp_path / "argv.json"
    fake = tmp_path / "f.py"
    fake.write_text(
        "import sys, json\n"
        f"json.dump(sys.argv, open({str(argv_path)!r}, 'w'))\n"
        "sys.stdin.buffer.read()\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'w', encoding='utf-8').write('Prvni odstavec je tu upraveny jemne.')\n",
        encoding="utf-8")
    stylist.polish("EN", "Prvni odstavec je tu napsany proste.",
                   codex_cmd=[sys.executable, str(fake)], codex_model="  gpt-5-codex  ")
    assert seen["timeout"] == 999
    argv = json.loads(argv_path.read_text())
    assert argv[argv.index("-m") + 1] == "gpt-5-codex"


def test_polish_invokes_codex_with_expected_argv(tmp_path):
    argv_path = tmp_path / "argv.json"
    fake = tmp_path / "argv_codex.py"
    fake.write_text(
        "import sys, json\n"
        f"json.dump(sys.argv, open({str(argv_path)!r}, 'w'))\n"
        "sys.stdin.buffer.read()\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "open(out, 'w', encoding='utf-8').write("
        "'Prvni odstavec je upraveny.\\n\\nDruhy odstavec je take upraveny.')\n",
        encoding="utf-8")
    cmd = [sys.executable, str(fake)]
    stylist.polish("EN text", "Prvni odstavec je puvodni.\n\nDruhy odstavec je take puvodni.",
                   codex_cmd=cmd, codex_model="gpt-5-codex")
    argv = json.loads(argv_path.read_text())
    tail = argv[1:]
    work_dir = tail[tail.index("-C") + 1]
    out_path = tail[tail.index("-o") + 1]
    assert tail == [
        "exec", "--sandbox", "read-only", "--skip-git-repo-check",
        "--ephemeral", "--ignore-user-config",
        "-C", work_dir, "-o", out_path, "-m", "gpt-5-codex", "-",
    ]
    assert out_path == os.path.join(work_dir, "out.txt")


def test_polish_long_input_goes_through_stdin_not_argv(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STYLIST_MAX_CHARS", 1_000_000)
    long_cz = "\n\n".join(["Odstavec o delce, co by se do argv nevesla. " * 800
                           for _ in range(3)])
    assert len(long_cz) > 32 * 1024
    fake = tmp_path / "echo_stdin_codex.py"
    fake.write_text(
        "import sys, re\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "received = sys.stdin.buffer.read().decode('utf-8').replace('\\r\\n', '\\n')\n"
        "m = re.search(r'--- ČESKÝ PŘEKLAD K UPRAVENÍ ---\\n"
        "(.*?)\\n\\nOdpověz upravenou', received, re.DOTALL)\n"
        "cz = m.group(1)\n"
        "open(out, 'w', encoding='utf-8').write("
        "cz.replace('Odstavec', 'Upraveny odstavec'))\n",
        encoding="utf-8")
    result = stylist.polish("EN", long_cz, codex_cmd=[sys.executable, str(fake)])
    assert "Upraveny odstavec" in result
    assert len(result) == len(long_cz.replace("Odstavec", "Upraveny odstavec").strip())
```

  (Pozn.: `long_cz` úmyslně bez diakritiky ve slově "delce" - regexový kotvicí text `ČESKÝ PŘEKLAD K UPRAVENÍ` a `Odpověz upravenou` musí přesně sedět na `SYSTEM_PROMPT_TEMPLATE` ze specu; ověř znění šablony, řádky 534-559, a případně kotvy uprav.)

- [ ] **Step 1c: Write redaction-wiring tests** — dokazují, že `_redact_detail` je SKUTEČNĚ zapojený ve VŠECH čtyřech Codexem-řízených chybových větvích `polish()` (spec 2810-2816), ne jen že helper funguje. Bez nich by odstranění `_redact_detail(...)` z kterékoli větve prošlo:

```python
def _fake_codex_stderr(tmp_path, stderr_text, *, exit_code=1):
    fake = tmp_path / "fake_codex_err.py"
    fake.write_text(
        "import sys\n"
        f"sys.stderr.write({stderr_text!r})\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8")
    return [sys.executable, str(fake)]


@pytest.mark.parametrize("flag,is_redacted", [(False, True), (1, True),
                                              ("False", True), (None, True), (True, False)])
def test_polish_redacts_all_codex_derived_error_values(tmp_path, monkeypatch, flag, is_redacted):
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", flag)

    # 1) nenulový exit + secret na stderr
    with pytest.raises(stylist.StylistError) as e1:
        stylist.polish("EN", "Veta jedna je tady.\n\nVeta dva je take tady.",
                       codex_cmd=_fake_codex_stderr(tmp_path, "TAJNY-STDERR-42"))
    assert ("TAJNY-STDERR-42" not in str(e1.value)) == is_redacted
    assert (stylist._REDACTED in str(e1.value)) == is_redacted

    # 2) změněné číslo - `after_nums` pochází ze stylizovaného textu
    with pytest.raises(stylist.StylistError) as e2:
        stylist.polish("EN", "Bylo jich 12 tady.",
                       codex_cmd=_fake_codex(tmp_path, "Bylo jich 21 tady."))
    assert ("21" in str(e2.value)) == (not is_redacted)

    # 3) jiný počet odstavců
    with pytest.raises(stylist.StylistError) as e3:
        stylist.polish("EN", "Prvni odstavec.\n\nDruhy odstavec.",
                       codex_cmd=_fake_codex(tmp_path, "Jen jeden odstavec podobne dlouhy jako vstup."))
    assert (stylist._REDACTED in str(e3.value)) == is_redacted

    # 4) poměr délky
    with pytest.raises(stylist.StylistError) as e4:
        stylist.polish("EN", "Dost dlouhy cesky text na porovnani delky vystupu.",
                       codex_cmd=_fake_codex(tmp_path, "X"))
    assert (stylist._REDACTED in str(e4.value)) == is_redacted
```

  (Ověř, že fake výstup v případě 3 dá poměr délky v pásmu 0.5-1.5, aby test spadl na počtu odstavců, ne dřív na poměru - `polish()` kontroluje odstavce PŘED poměrem, spec 924/929.)

```python
def test_polish_forwards_guide_block_into_prompt(tmp_path):
    """spec 2520-2523: `guide_block` (schválená pravidla rejstříku) MUSÍ dorazit
    do promptu na stdin. Bez tohohle testu by odstranění `guide_block` /
    `{guide_section}` prošlo."""
    fake = tmp_path / "guide_check.py"
    fake.write_text(
        "import sys\n"
        "received = sys.stdin.buffer.read().decode('utf-8').replace('\\r\\n', '\\n')\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "assert 'NEPORUS-VYKANI-XYZ' in received\n"
        "open(out, 'w', encoding='utf-8').write("
        "'Prvni veta je tady.\\n\\nDruha veta je take tady.')\n",
        encoding="utf-8")
    result = stylist.polish("EN", "Prvni veta je tady.\n\nDruha veta je take tady.",
                            codex_cmd=[sys.executable, str(fake)],
                            guide_block="NEPORUS-VYKANI-XYZ")
    assert "Druha veta" in result   # fake zapsal výstup => assert v něm prošel


def test_polish_kills_process_tree_on_keyboard_interrupt(monkeypatch):
    """Odchylka od specu: Ctrl+C během communicate() musí zabít potomka
    (ne sirotek čerpající kvótu), zavolat omezený wait a re-raisnout původní
    výjimku. Kompletní fake Popen - žádný skutečný proces, deterministické
    pořadí."""
    events = []

    class FakePopen:
        def __init__(self, *a, **kw):
            self.pid = 4242
        def communicate(self, *a, **kw):
            events.append("communicate")
            raise KeyboardInterrupt()
        def wait(self, timeout=None):
            events.append(f"wait:{timeout}")
        def kill(self):
            events.append("kill")

    monkeypatch.setattr(stylist.subprocess, "Popen", lambda *a, **kw: FakePopen())
    monkeypatch.setattr(stylist, "_kill_process_tree",
                        lambda proc: events.append("kill_tree"))
    with pytest.raises(KeyboardInterrupt):
        stylist.polish("EN", "Nejaka veta tady je.", codex_cmd=[sys.executable])
    assert events == ["communicate", "kill_tree", "wait:10"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stylist.py -k polish -v`
Expected: FAIL - `AttributeError: module 'src.agents.stylist' has no attribute 'polish'`

- [ ] **Step 3: Implement `polish()`** — přidej do `src/agents/stylist.py` funkci VERBATIM ze specu, řádky 749-949 (od `def polish(en_text: str, cz_text: str, *, timeout: int | None = None,` po `return styled`).

  **Odchylka od specu (sirotčí proces):** spec (880-891) ukončuje potomka JEN při `subprocess.TimeoutExpired`. Při `KeyboardInterrupt` z `communicate()` (Ctrl+C) by `polish()` skončila bez zabití potomka - `codex.cmd`/`node.exe` běží dál a čerpá kvótu (stejný problém, kvůli kterému `_kill_process_tree` existuje, viz jeho docstring). Přidej ZA `except subprocess.TimeoutExpired` blok ještě:
  ```python
      except BaseException:
          # KeyboardInterrupt / cokoli po startu procesu - nenech sirotka
          _kill_process_tree(proc)
          try:
              proc.wait(timeout=10)
          except subprocess.TimeoutExpired:
              pass
          raise
  ```
  (`BaseException` chytá i `KeyboardInterrupt`; `raise` bez argumentu zachová původní výjimku a její traceback.)

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
- Modify: `main.py` (přidat modulový import `from src.agents import stylist`; přidat funkce - umísti je za `_print_usage`, před `# --- příkazy ---`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `json`, `hashlib` (modulové importy z Tasku 1)
- Produces (kromě funkcí níž): `main.stylist` je modulově-importovaný `src.agents.stylist` - `_polish_one_chapter`/`_cmd_polish` (Task 11/12) ho tak volají jako `stylist.polish(...)` a testy monkeypatchují `main.stylist.<attr>` jednotně. (Modul `src/agents/stylist.py` už existuje z Tasku 4-6.)
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

- [ ] **Step 3: Add module import** — do `main.py` k `from src import ...` řádkům přidej `from src.agents import stylist` (modul existuje od Tasku 4). Ověř `python -c "import main"` projde.

- [ ] **Step 4: Implement helpers** — přidej do `main.py` funkce VERBATIM ze specu:
  - `_say` (řádky 1123-1133)
  - `_parse_findings` (1136-1149)
  - `_already_styled` (1152-1153)
  - `_stylist_marker` (1156-1169)
  - `_finding_key` (1172-1177)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

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


def test_rejection_keep_untranslated_term_no_leak_finding_not_rejected():
    """keep-untranslated termín (cz == canonical_en): `concordance.check_chapter`
    pro něj `leak` nález neemituje (ověř `src/concordance.py` - `leak` větev je
    pod `if cz != canonical`), takže `after_findings` žádný leak pro "Mouse"
    neobsahuje - přidaný výskyt "Mouse" není důvod k zamítnutí. Scénář spec
    2631-2633; `_rejection_reasons` kód by leak ZAMÍTL, kdyby dorazil - test to
    odráží tím, že leak v `after_findings` NENÍ."""
    t = _term(tid="t/mouse", canonical="Mouse", cz="Mouse")
    assert main._polish_rejected([], [], "Mouse tu byl.",
                                 "Mouse tu byl, Mouse zas.", [t]) is False


def test_rejection_added_occurrence_in_different_case_or_declension_rejected():
    """find_form_occurrences stemuje + lowercasuje - přidaný výskyt v jiném pádu /
    s jinou velikostí písmen se počítá (str.count by ho minul). Spec 2617-2622."""
    key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
           "actual": "White Council"}
    base, after = [dict(key)], [dict(key)]
    before = "Byla to White Council."
    a = "Byla to White Council a pak jeste white councilu."
    assert main._polish_rejected(base, after, before, a, [_term()]) is True


def test_rejection_dedup_new_bad_surface_B_and_grown_surface_A_both_kept(monkeypatch):
    """Spec 2821-2826: termín má NOVÝ chybný povrch B (nový klíč) A SOUČASNĚ
    narostl výskyt UŽ EXISTUJÍCÍHO povrchu A. V `reasons` musí být OBA (dedup je
    na _finding_key, ne na celý termín)."""
    # A: pre-existující leak povrch "White Council" (baseline klíč), naroste 1->2
    # B: nový leak povrch aliasu "the Council" (nový klíč)
    a_key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
             "actual": "White Council"}
    b_key = {"source": "concordance", "type": "leak", "term_id": "t/wc",
             "actual": "the Council"}
    base = [dict(a_key)]
    after = [dict(a_key), dict(b_key)]
    before = "White Council byla tam."
    a = "White Council a White Council, totiz the Council."
    r = main._rejection_reasons(base, after, before, a,
                                [_term(aliases=["the Council"])])
    actuals = sorted(x.get("actual") for x in r if x.get("type") == "leak")
    assert actuals == ["White Council", "the Council"]


def test_rejection_integration_real_check_chapter_occurrence_increase(tmp_path):
    """Spec 2638-2642: sama množina findings NESTAČÍ. Reálný `check_chapter`
    vrátí JEDEN `leak` nález i pro termín leaklý 2×; `_polish_rejected` musí
    přes find_form_occurrences rozdíl v počtu zachytit."""
    from src import concordance, glossary
    db = str(tmp_path / "g.sqlite3"); state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,aliases,cz,"
                     "accepted_alt,type,status) VALUES "
                     "('t/wc','White Council','[]','Bílá rada','[]','term','approved')")
    grows = glossary.all_terms(db)
    en = "The White Council met again."
    cz_before = "Sešla se White Council."
    cz_after = "Sešla se White Council a znovu se sešla White Council."
    base = concordance.check_chapter(en, cz_before, grows, [])
    after = concordance.check_chapter(en, cz_after, grows, [])
    # předpoklad testu: check_chapter DEDUPUJE - baseline i after mají PRÁVĚ
    # JEDEN leak se SHODNÝM _finding_key. `_polish_rejected` True tak může
    # přijít JEN z počtu výskytů, ne z nového klíče (spec 2638-2642).
    base_leaks = [f for f in base if f.get("type") == "leak"]
    after_leaks = [f for f in after if f.get("type") == "leak"]
    assert len(base_leaks) == 1 and len(after_leaks) == 1
    assert {main._finding_key(f) for f in base_leaks} == {main._finding_key(f) for f in after_leaks}
    assert main._polish_rejected(base, after, cz_before, cz_after, grows) is True
    # bez nárůstu (stejný text před i po) -> nezamítnuto
    assert main._polish_rejected(base, base, cz_before, cz_before, grows) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k rejection -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_rejection_reasons'`

- [ ] **Step 3: Implement** — přidej do `main.py` VERBATIM ze specu: `_rejection_reasons` (řádky 1180-1319) a `_polish_rejected` (1322-1330).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -k rejection -v`
Expected: PASS. Pokud reálný `find_form_occurrences`/`check_chapter` chování v integračním testu překvapí (víceslovné povrchy, stemování), ověř `src/concordance.py:43,91,160` a uprav VSTUPNÍ TEXTY testu tak, aby SCÉNÁŘ (nárůst výskytu → zamítnuto) platil - NIKDY neupravuj očekávaný výsledek ani kód ze specu.

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


def test_polish_one_chapter_critic_failed_skips_meaning_check(tmp_path, monkeypatch):
    """critic_failed=True -> rejected s critic/critic_failed, meaning-check se
    NEVOLÁ (fail-fast, spec 2827-2830)."""
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta tady.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], True))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("nemá se volat")))
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert rec["outcome"] == "rejected"
    assert "critic/critic_failed" in rec["reason_types"]


def test_polish_one_chapter_real_critic_failure_redacts_by_default(tmp_path, monkeypatch, capsys):
    """Kolo 7: SKUTEČNÝ `critic.review` + `pipeline._run_critic` (bez mocku).
    Kritik vrátí neplatný verdikt 'SECRET123' → `critic.review` raisne
    `ValueError` se secretem → `_run_critic` pseudo finding
    (`issue="kritik selhal: ...SECRET123..."`). Při
    `STYLIST_REPORT_REJECTED_TEXT=False` se secret NESMÍ objevit v `rec`
    ani na konzoli - pseudo finding jde jen do `findings`, ne do `rec`."""
    from src.llm.client import Completion, FakeLLMClient
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jina veta uplne jinak.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", False)
    bad = json.dumps({"verdict": "SECRET123", "findings": []})
    def _cf(agent):
        return FakeLLMClient([Completion(bad, False, 5, 5), Completion(bad, False, 5, 5)])
    rec = main._polish_one_chapter(_c(), [], _cf, db, "m", "", ["codex"], _bs(db))
    assert rec["outcome"] == "rejected"
    assert "critic/critic_failed" in rec["reason_types"]
    assert "SECRET123" not in json.dumps(rec)
    assert "SECRET123" not in capsys.readouterr().out


@pytest.mark.parametrize("flag", [False, 1, "False", None])
def test_polish_one_chapter_rejected_detail_gated_is_true_only(tmp_path, monkeypatch, flag):
    """STYLIST_REPORT_REJECTED_TEXT: jen literál True odemkne plný detail;
    1/"False"/None se chovají jako False (spec 2805-2809)."""
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta se SECRET123.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: ([{"source": "critic", "action": "revise",
                                           "severity": "critical", "type": "fidelity",
                                           "issue": "SECRET123"}], False))
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", flag)
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert rec["outcome"] == "rejected"
    assert "reasons" not in rec and "findings" not in rec and "styled" not in rec


def test_polish_one_chapter_forwards_only_rendered_mentions_as_rendered_terms(tmp_path, monkeypatch):
    """Spec 5 BLOCKING / kolo 20 IMPORTANT / 323-329: `rendered_terms` předané
    do check_chapter/build_mentions se staví z `state.chapter_mentions` a
    obsahuje JEN mention se `source=='rendered'` a neprázdným `cz_form` - termín
    zachycený jen kódem (`detected`) se NEforwarduje (jinak by se po commitu
    uložil jako 'rendered' = falešná provenience). Protože `detected` termín B
    není ve `rendered_terms`, `build_mentions` ho jako 'rendered' přeznačit
    NEMŮŽE."""
    db = _polish_db(tmp_path)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,aliases,cz,"
                     "accepted_alt,type,status) VALUES "
                     "('t/a','Aterm','[]','Áčko','[]','term','approved'),"
                     "('t/b','Bterm','[]','Béčko','[]','term','approved')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Áčko", "scene_idx": 3, "source": "rendered"},
        {"term_id": "t/b", "cz_form": "Béčko", "scene_idx": 0, "source": "detected"},
        {"term_id": "t/a", "cz_form": "", "scene_idx": 0, "source": "rendered"},  # prázdný cz_form se zahodí
    ])
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav.")
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    seen = {"check": [], "build": []}
    monkeypatch.setattr(main.concordance, "check_chapter",
                        lambda en, cz, gl, rendered: seen["check"].append(list(rendered)) or [])
    monkeypatch.setattr(main.concordance, "build_mentions",
                        lambda en, cz, gl, rendered: seen["build"].append(list(rendered)) or [])
    rec = main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], _bs(db))
    assert rec["outcome"] == "polished"
    expected = [{"term_id": "t/a", "cz_as_used": "Áčko", "scene_idx": 3}]
    assert seen["check"] and all(call == expected for call in seen["check"])
    assert seen["build"] and all(call == expected for call in seen["build"])


def test_polish_one_chapter_no_backup_promotion_on_reject(tmp_path, monkeypatch):
    """Zamítnutá kapitola nesmí promovat snapshot na .pre-polish-backup."""
    db = _polish_db(tmp_path)
    monkeypatch.setattr(main.stylist, "polish", lambda *a, **k: "Jiná věta tady je.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: ([{"source": "critic", "action": "revise",
                                           "severity": "critical", "type": "fidelity"}], False))
    bs = _bs(db)
    main._polish_one_chapter(_c(), [], _cf_stub, db, "m", "", ["codex"], bs)
    assert bs["done"] is False
    assert not os.path.exists(db + ".pre-polish-backup")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -k polish_one_chapter -v`
Expected: FAIL - `AttributeError: module 'main' has no attribute '_polish_one_chapter'`

- [ ] **Step 3: Implement** — přidej do `main.py` funkci VERBATIM ze specu, řádky 1465-1634 (`def _polish_one_chapter(...)` po `return {"idx": idx, "outcome": "polished"}`). Dvě odchylky od specu:
  - vynech lokální `from src.agents import stylist` (spec řádek 1500) - `main` má `stylist` importovaný modulově z Tasku 7, funkce ho použije přímo. Tím je monkeypatch `main.stylist.<attr>` v testech jednotný. (`concordance`, `pipeline`, `state` jsou v `main` taky modulové.)
  - v docstringu (spec 1476-1479) uprav větu o `_cmd_polish` "tři `report.append` větve ... na každé cestě smyčkou proběhne jen jedna" na aktuální strukturu: `_cmd_polish` má JEDEN `report.append` ve `finally` na iteraci, `rec` se v něm dopočítá z DB, když ho žádná větev nesestavila (viz Task 12 odchylka). Invariant "1 záznam / iteraci" zůstává, jen mechanismus je jiný.

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
    monkeypatch.setattr(main, "_client_factory", lambda rid, *, interactive: (lambda a: object()))
    # `_print_usage` se ZÁMĚRNĚ NEmockuje - reálná verze jen čte prázdné llm_calls
    # z testovací DB a vypíše 0; test rozbitého stdout ji tak skutečně projede.
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


def test_cmd_polish_passes_nonempty_guide_block(tmp_path, monkeypatch):
    """spec 2520-2523 / kolo 6 IMPORTANT: když `guide.json` má pravidla,
    `_cmd_polish` je předá jako neprázdný `guide_block` do `stylist.polish`."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.guide_mod, "load_guide", lambda p: {"rules": ["vykani"]})
    monkeypatch.setattr(main.guide_mod, "guide_as_prompt_block",
                        lambda g: "NAVOD: vykani mezi X a Y")
    seen = {}
    def _spy_polish(en, cz, **k):
        seen["guide"] = k.get("guide_block")
        return cz + " uprav"
    monkeypatch.setattr(main.stylist, "polish", _spy_polish)
    assert main._cmd_polish(_Args()) == 0
    assert seen["guide"] == "NAVOD: vykani mezi X a Y"


def test_cmd_polish_all_failed_is_fatal_but_batch_completed(tmp_path, monkeypatch):
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(_stylist.StylistError("x")))
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is True
    assert r["attempted_count"] == 3 and r["summary"]["failed"] == 3


def test_cmd_polish_all_generic_exceptions_is_fatal(tmp_path, monkeypatch):
    """Kolo 6: kapitoly padnou na NEOČEKÁVANÉ výjimce (ne StylistError - tu
    helper převádí na normální failed návrat). Souhrn se odvozuje z `report`,
    takže 'všechno selhalo' → fatal / return 1 i tady (spec 2678-2680, 2868)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.concordance, "check_chapter",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is True
    assert r["attempted_count"] == 3 and r["summary"]["failed"] == 3
    assert all(c["outcome"] == "failed" for c in r["chapters"])


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


def test_cmd_polish_backup_predates_run_bookkeeping(tmp_path, monkeypatch):
    """Snapshot se pořizuje PŘED state.create_run (spec kolo 9 BLOCKING /
    2524-2536) - .pre-polish-backup proto NEobsahuje 'runs' řádek tohoto běhu.
    Test by selhal, kdyby executor snapshot omylem přesunul za create_run."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    with state.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"] == 0
    assert main._cmd_polish(_Args()) == 0
    with state.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"] == 1
    with state.connect(db + ".pre-polish-backup") as conn:
        assert conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"] == 0


def test_cmd_polish_generic_exception_is_failed_batch_continues(tmp_path, monkeypatch, capsys):
    """Neočekávaná (ne-Fatal) výjimka u JEDNÉ kapitoly -> failed, dávka jede
    dál (spec 2667-2669); str(e) redigované v reportu i stdout (spec 2810-2816)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", False)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    def _boom_on_2(en, cz, gl, rendered):
        if "2" in cz:
            raise ValueError("SECRET-boom")
        return []
    monkeypatch.setattr(main.concordance, "check_chapter", _boom_on_2)
    assert main._cmd_polish(_Args()) == 0
    out = capsys.readouterr().out
    r = _report(db)
    assert r["run_status"] == "ok" and r["batch_completed"] is True
    outcomes = {c["idx"]: c["outcome"] for c in r["chapters"]}
    assert outcomes == {1: "polished", 2: "failed", 3: "polished"}
    assert "SECRET-boom" not in json.dumps(r) and "SECRET-boom" not in out


def test_cmd_polish_keyboardinterrupt_after_commit_is_polished(tmp_path, monkeypatch):
    """Interrupt PO úspěšném commitu -> commit-detekce přes translated_text ->
    outcome 'polished', PRÁVĚ JEDEN záznam (spec 2759-2764)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    real = main.state.commit_chapter_result
    calls = {"n": 0}
    def _wrap(*a, **k):
        calls["n"] += 1
        out = real(*a, **k)
        if calls["n"] == 1:
            raise KeyboardInterrupt()
        return out
    monkeypatch.setattr(main.state, "commit_chapter_result", _wrap)
    with pytest.raises(KeyboardInterrupt):
        main._cmd_polish(_Args())
    r = _report(db)
    assert r["run_status"] == "interrupted"
    ch1 = [c for c in r["chapters"] if c["idx"] == 1]
    assert len(ch1) == 1 and ch1[0]["outcome"] == "polished"


def test_cmd_polish_force_interrupt_before_new_commit_is_interrupted(tmp_path, monkeypatch):
    """--force nad už-stylizovanou kapitolou, interrupt PŘED novým commitem ->
    translated_text nezměněn -> 'interrupted', ne 'polished' (spec 2765-2772)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"source": "stylist", "type": "polish"}]),))
    monkeypatch.setattr(main.stylist, "polish",
                        lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        main._cmd_polish(_Args(force=True))
    r = _report(db)
    ch1 = [c for c in r["chapters"] if c["idx"] == 1]
    assert len(ch1) == 1 and ch1[0]["outcome"] == "interrupted"


def test_cmd_polish_client_factory_failure_after_create_run_still_reports(tmp_path, monkeypatch):
    """Pád PŘED smyčkou (po create_run) -> report VZNIKNE z finally,
    attempted_count 0 (spec 2780-2788)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    def _boom(rid, *, interactive):
        raise RuntimeError("no client")
    monkeypatch.setattr(main, "_client_factory", _boom)
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["attempted_count"] == 0 and r["planned_count"] == 2
    assert r["run_error"] and r["run_status"] == "fatal"


def test_cmd_polish_critic_fatalrunerror_stops_whole_batch(tmp_path, monkeypatch):
    """FatalRunError z kritika -> celý polish končí, zbylé kapitoly nezpracované
    (spec 2675-2677)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=3)
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    from src.llm.client import FatalRunError
    calls = {"n": 0}
    def _crit(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise FatalRunError("cost guard")
        return ([], False)
    monkeypatch.setattr(main.pipeline, "_run_critic", _crit)
    assert main._cmd_polish(_Args()) == 1
    r = _report(db)
    assert r["run_status"] == "fatal" and r["batch_completed"] is False
    assert r["attempted_count"] == 2
    assert [c["outcome"] for c in r["chapters"]] == ["polished", "fatal"]


def test_cmd_polish_nothing_accepted_preserves_previous_backup(tmp_path, monkeypatch):
    """Dávka, kde nic není přijato (vše rejected) -> stará .pre-polish-backup
    zůstane nedotčená, dočasný snapshot se uklidí (spec 2538-2543)."""
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    with open(db + ".pre-polish-backup", "w") as f:
        f.write("STARA-ZALOHA")
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: cz + " uprav")
    monkeypatch.setattr(main.pipeline, "_run_critic",
                        lambda *a, **k: ([{"source": "critic", "action": "revise",
                                           "severity": "critical", "type": "fidelity"}], False))
    assert main._cmd_polish(_Args()) == 0
    with open(db + ".pre-polish-backup") as f:
        assert f.read() == "STARA-ZALOHA"
    assert not os.path.exists(db + ".pre-polish-snapshot")


def test_cmd_polish_report_records_every_iteration(tmp_path, monkeypatch):
    """append je v `finally` (kolo 4 odchylka) - žádná iterace se z reportu
    neztratí a žádná se nezapíše dvakrát. Mock `_polish_one_chapter` vrací
    pevnou sekvenci; kontroluje se úplnost + pořadí."""
    db = _polish_env(tmp_path, monkeypatch, n_done=4)
    seq = iter([{"idx": 1, "outcome": "polished"},
                {"idx": 2, "outcome": "unchanged"},
                {"idx": 3, "outcome": "rejected", "reason_types": ["critic/fidelity"]},
                {"idx": 4, "outcome": "failed", "error": "x"}])
    monkeypatch.setattr(main, "_polish_one_chapter", lambda *a, **k: next(seq))
    assert main._cmd_polish(_Args()) == 0
    r = _report(db)
    assert [c["idx"] for c in r["chapters"]] == [1, 2, 3, 4]
    assert r["attempted_count"] == 4
    assert r["summary"] == {"polished": 1, "unchanged": 1, "rejected": 1,
                            "failed": 1, "fatal": 0, "interrupted": 0}


def test_cmd_polish_ki_during_error_logging_records_exactly_once(tmp_path, monkeypatch):
    """Kolo 5: helper vyhodí běžnou výjimku, KI padne během `_say` v
    `except Exception` (než/když je rec sestavené). Report musí mít PRÁVĚ
    JEDEN záznam té kapitoly, běh se zastaví."""
    db = _polish_env(tmp_path, monkeypatch, n_done=2)
    monkeypatch.setattr(main, "_polish_one_chapter",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    real_say = main._say
    def _say_ki(msg):
        if "neočekávaná chyba" in msg:
            raise KeyboardInterrupt()
        return real_say(msg)
    monkeypatch.setattr(main, "_say", _say_ki)
    with pytest.raises(KeyboardInterrupt):
        main._cmd_polish(_Args())
    r = _report(db)
    ch1 = [c for c in r["chapters"] if c["idx"] == 1]
    assert len(ch1) == 1
    assert r["run_status"] == "interrupted"


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
  0. Uprav `_print_usage` (řádky 52-59): nahraď oba `print(...)` za `_say(...)`. `_cmd_polish` (spec 1919) ji volá bez guardu; kdyby raw `print` vyhodil `BrokenPipeError`, vnější `except Exception` by z toho udělal `run_error`/`return 1` navzdory úspěšné dávce. `grep -n "_print_usage" main.py` - volají ji `_cmd_run` i `_cmd_polish`, obě z převodu na `_say` jen těží (žádná regrese).
  1. Přidej `_cmd_polish` VERBATIM ze specu, řádky 1746-2005 (`def _cmd_polish(args) -> int:` po konec `finally` bloku). **Dvě odchylky od specu:**

     **(a) Append invariant (kolo 4-6 IMPORTANT).** Spec má `report.append(rec)` (řádek 1913) MIMO `try`, in-loop `except KeyboardInterrupt` navázaný na už dokončený `try`, a `counts[rec["outcome"]] += 1` na sdíleném dně. `KeyboardInterrupt` KDEKOLI v těle iterace (i během `_say` v `except Exception`, než je `rec` sestavené) kapitolu z reportu ztratí. NAHRAĎ celé tělo `for c in chapters:` smyčky (spec řádky ~1866-1914) tímhle - jeden `try/except/finally`, append bezpodmínečný ve `finally`, `rec` se ve `finally` dopočítá z DB, když ho žádná větev nesestavila:
     ```python
     for c in chapters:
         rec = None
         try:
             rec = _polish_one_chapter(c, glossary_rows, cf, db, model,
                                       guide_block, codex_cmd, backup_state)
         except FatalRunError as fe:
             rec = {"idx": c["idx"], "outcome": "fatal", "error": str(fe)}
             raise
         except Exception as e:
             # rec PŘED `_say` - kdyby `_say` dostalo KeyboardInterrupt, rec už je
             rec = {"idx": c["idx"], "outcome": "failed",
                    "error": f"{type(e).__name__}: {stylist._redact_detail(str(e))}"}
             _say(f"Kapitola {c['idx']}: neočekávaná chyba "
                  f"({type(e).__name__}), ponechávám původní.")
         finally:
             if rec is None:
                 # KeyboardInterrupt (BaseException) propadla ven z
                 # `_polish_one_chapter` dřív, než se rec sestavil. Stav DB je
                 # zdroj pravdy: commit proběhl <=> translated_text se změnil
                 # (spec kolo 35).
                 try:
                     row = state.get_chapter(db, c["idx"])
                     committed = (row is not None
                                  and row["translated_text"] != c["translated_text"])
                 except Exception:
                     committed = False
                 rec = ({"idx": c["idx"], "outcome": "polished"} if committed
                        else {"idx": c["idx"], "outcome": "interrupted",
                              "stage": "processing"})
             report.append(rec)
     ```
     Přesně jeden `try/except/finally` a jeden `report.append` na iteraci → invariant STRUKTURNÍ.

     **(b) Souhrn z reportu, ne z `counts` (kolo 6 IMPORTANT).** `counts` už ve smyčce není (viz (a)), takže `failed` z neočekávané výjimky by se nezapočítal. SMAŽ `counts = {"polished": 0, ...}` inicializaci (spec řádek 1864). NAHRAĎ spec řádky 1917-1935 (od `_say(f"Vylepšeno:...` po `return 0`) tímhle:
     ```python
       tally = {k: sum(1 for rec in report if rec.get("outcome") == k)
                for k in _REPORT_OUTCOMES}
       _say(f"Vylepšeno: {tally['polished']}, beze změny: {tally['unchanged']}, "
            f"zamítnuto kontrolou: {tally['rejected']}, selhalo: {tally['failed']}")
       _print_usage(db, rid)
       if tally["failed"] == len(chapters) and tally["failed"] > 0:
           _say("POZOR: všechny kapitoly selhaly - zkontroluj Codex CLI "
                "(přihlášení, config.CODEX_MODEL, síť).")
           status = "fatal"
           return 1
       status = "ok"
       return 0
     ```
     "Všechno selhalo" tak pokrývá i kapitoly spadlé na neočekávané výjimce (ne jen `StylistError`) - spec 2678-2680, 2868.
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

**Bezpečné provedení (kolo 2 IMPORTANT):** ověření NIKDY neupravuje `config.py` (přerušení mezi kroky by nechalo FS opt-in zapnutý) a NIKDY neběží nad pracovní `data/state.sqlite3` (mohlo by přepsat její jedinou zálohu). Místo toho: pracuj s KOPIÍ DB v dočasném adresáři a config nastav JEN za běhu ověřovacího procesu (atributy `config.*` v Pythonu, ne editace souboru). Po skončení není co vracet.

**Files:**
- žádné trvalé změny kódu - jen dočasný ověřovací skript ve scratchpadu + poznámka do specu

- [ ] **Step 1: Preflight a flagy** — na cílovém stroji ověř:
  - `shutil.which("codex")` najde executable
  - `codex exec --help` uvádí `--ephemeral`, `--ignore-user-config`, `-o`, `-C`, `-m`, pozicionální `-` (stdin)

- [ ] **Step 2: POVINNÝ CANARY TEST NEJDŘÍV (bezpečnostně kritické - NEPŘESKAKOVAT)** — samostatně, PŘED jakýmkoli během nad knihou. Tady se `codex exec` volá PŘÍMO, takže jeho stdout/stderr VIDÍŠ (`_cmd_polish` je zahazuje - proto sem patří i pozorování MCP/configu/kontextu). Runner MUSÍ mít vlastní timeout + kill stromu procesů (právě testovaný hang na startu MCP by jinak zablokoval ověření):
  ```python
  import subprocess, sys, tempfile, secrets, os, shutil
  from src.agents import stylist
  T1 = tempfile.mkdtemp(); T2 = tempfile.mkdtemp()
  token = secrets.token_hex(16)                      # DRŽ hodnotu
  canary = os.path.join(T2, "canary.txt")
  open(canary, "w", encoding="utf-8").write(token)
  argv = stylist._codex_argv(stylist._resolve_codex_cmd(["codex"]),
                             T1, os.path.join(T1, "out.txt"), "<skutečný model>")
  prompt = f"Přečti soubor {canary} a vrať přesně jeho obsah, nic víc."
  proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding="utf-8", cwd=T1)
  try:
      try:
          out, err = proc.communicate(input=prompt, timeout=180)
      except BaseException:   # TimeoutExpired i KeyboardInterrupt
          stylist._kill_process_tree(proc)
          try: proc.wait(timeout=10)
          except subprocess.TimeoutExpired: pass
          raise
      of = os.path.join(T1, "out.txt")
      out_file = open(of, encoding="utf-8").read() if os.path.exists(of) else "(nic)"
      leaked = token in (out or "") or token in (err or "") or token in out_file
      print("ARGV:", argv)
      print("RETURNCODE:", proc.returncode)      # !=0 => běh selhal, canary NEvyhodnotitelný
      print("STDOUT:", out); print("STDERR:", err); print("OUT FILE:", out_file)
      print("CANARY LEAKED:", leaked, "(hledán token:", token, ")")
      assert proc.returncode == 0, "codex exec selhal - oprav a spusť canary znovu"
  finally:
      shutil.rmtree(T1, ignore_errors=True); shutil.rmtree(T2, ignore_errors=True)
  ```
  Když `RETURNCODE != 0`, canary NENÍ vyhodnocený (běh selhal z jiného důvodu) - oprav a opakuj.
  Vyhodnoť:
  - `--ignore-rules` NENÍ v `argv` (regrese, pokud je)
  - `-m <model>` model skutečně VYNUTÍ (ne tiše výchozí) - ze STDOUT/verbose logu
  - běh NEhangne na startu žádného MCP serveru; ve STDOUT/STDERR NENÍ nic z `~/.codex/config.toml` (MCP servery, pluginy) - `--ignore-user-config` funguje
  - Codex ve STDOUT nezmiňuje obsah `book-translator` repa (žádný `AGENTS.md`, jména projektových souborů) - `-C T1` (prázdný adresář) izoluje projektový kontext
  - druhý běh: stejný Popen runner, `prompt` = reálný EN+CZ text jedné `done` kapitoly obalený `stylist.SYSTEM_PROMPT_TEMPLATE.format(...)` - eyeball, že Codex vrátí rozumnou českou prózu bez halucinací
  - **výsledek canary:** pokud OUT FILE / STDOUT obsahuje obsah `canary.txt`, je prompt-injection riziko z textu knihy POTVRZENÉ (ne teoretické) - očekávané chování `--sandbox read-only`. Rozhodnutí nasadit `polish` patří uživateli (opt-in `STYLIST_ACCEPT_FS_RISK` to vyjadřuje).
  - (`T1`/`T2` uklidí `finally` v runneru; druhý běh s reálnou kapitolou si vytvoří vlastní dočasné adresáře)

- [ ] **Step 3: Reálný běh `polish` nad KONZISTENTNÍ KOPIÍ DB** — ověřuje CELÝ řetězec (guardraily, commit, report), ne jen Codex. Napiš do scratchpadu jednorázový skript:
  ```python
  import config, main
  main._snapshot_db("data/state.sqlite3", "<TMP>/verify.sqlite3")  # NE shutil.copy2 - spec 1333+ (WAL/souběžné zápisy)
  config.DB_PATH = "<TMP>/verify.sqlite3"
  config.CODEX_MODEL = "<skutečný model>"
  config.STYLIST_ACCEPT_FS_RISK = True
  config.STYLIST_REPORT_REJECTED_TEXT = True   # jen tady (TMP, ne synced) - ať jde zamítnutý text posoudit okem
  raise SystemExit(main._cmd_polish(type("A", (), {"only": [<IDX done kapitoly>], "force": True})()))
  ```
  `--force` (force=True) je POVINNÉ - jinak by už-stylizovaná kapitola byla přeskočena a ověření by nic nedokázalo. Spusť (`data/` `main.py` klidné - žádný souběžný `run`). `config.py` na disku se NEMĚNÍ. Ověř:
  - report `<TMP>/polish-reports/run-<rid>-*.json` má `attempted_count >= 1` a `planned_count >= 1` - vybraná kapitola SKUTEČNĚ prošla (ne přeskočena)
  - per-kapitola `outcome` je jedno z:
    - `polished` - `notes` v `<TMP>/verify.sqlite3` má `stylist` marker, `translated_text` je nový; eyeball: česky plynulejší, beze změny faktů/jmen/čísel/počtu odstavců, diakritika OK
    - `rejected` - report má `reason_types` + `styled`; eyeball `styled`: byl reject oprávněný?
    - `unchanged` - model vrátil totožný text; LEGITIMNÍ výsledek (spec), ověřil short-circuit větev. Chceš-li živě prohnat i guardraily+commit, spusť znovu na JINÉ `done` kapitole.
  - `codex_model` v reportu == model, co jsi nastavil

- [ ] **Step 4: Úklid + zápis** — smaž `<TMP>` (kopie DB, report se zamítnutým textem). `config.py` beze změny (`git diff config.py` ukáže jen blok z Tasku 1 s `STYLIST_ACCEPT_FS_RISK = False`, `STYLIST_REPORT_REJECTED_TEXT = False`). Do sekce "Manuální ověření" specu (`docs/superpowers/specs/2026-09-08-stylist-agent-design.md`) zapiš datum, verzi Codex CLI, výsledek canary testu.

- [ ] **Step 5: Commit** (jen pokud jsi upravil spec poznámku)

```bash
git add docs/superpowers/specs/2026-09-08-stylist-agent-design.md
git commit -m "docs: výsledek manuálního ověření + canary testu stylist průchodu"
```

---

## Self-review (proti specu)

**1. Spec coverage:**
- `config.py` hodnoty (spec 345-400) → Task 1 ✓
- `main.py` modulové importy (403-429) → Task 1 + `from src.agents import stylist` Task 7 ✓
- `critic.review()` oprava + testy (146-286) → Task 2; +`null`/chybějící `findings` = `[]` (spec 188) ✓
- `state.chapter_mentions` + test (307-329) → Task 3; provenience test (323-329) přesunut do Task 11 (potřebuje `_polish_one_chapter`) ✓
- `stylist.py` helpery, argv, kill (434-746) → Task 4 ✓
- `stylist.polish()` + testy (749-949, 2054-2435) → Task 5; 3 spec testy s vadným délkovým poměrem + cp1252 stdin nahrazeny opravenými verzemi; +odchylka: `except BaseException` kill sirotčího procesu při Ctrl+C ✓
- `stylist.check_meaning_preserved` + testy (952-1024, 2438-2448) → Task 6 ✓
- `guide_block` předání (spec 2520-2523) → Task 5 (`polish` → stdin) + Task 12 (`_cmd_polish` → `polish` kwarg) ✓
- `main` malé helpery (1123-1177) → Task 7 ✓
- `_rejection_reasons`/`_polish_rejected` (1180-1330) + scénáře 2602-2652, 2817-2826, integrace 2638-2642 → Task 8 ✓
- `_snapshot_db`/`_backup_db_once` (1333-1462, 2544-2589) → Task 9; timing/zachování staré zálohy/úklid snapshotu (2524-2543) → Task 11/12 ✓
- `_write_polish_report` + konstanty (1637-1743, 2703-2843) → Task 10 ✓
- `_polish_one_chapter` (1465-1634) + scénáře 2661-2677, 2723-2729, 2744-2751, 2827-2830 → Task 11 ✓
- `_cmd_polish` + parser + `_MUTATING` + docstring (1746-2024) + scénáře 2503-2843, tabulka 2845-2879 → Task 12; +odchylky: (a) JEDEN `finally` na iteraci, append bezpodmínečný, `rec` se v `finally` dopočítá z DB (uzavře KI-okno); (b) souhrn/all-failed podmínka z `report`, ne z `counts` slovníku (spec `counts` v kolo-5 struktuře nešel bezpečně inkrementovat; report je jediný zdroj pravdy); +redakční matice (Task 5 Step 1c) ✓
- Manuální ověření + canary (2450-2501) → Task 13 ✓

**Vědomě NEplné pokrytí testy (přijatelné, spec je autorita):** `_polish_one_chapter`/`_cmd_polish` mají ve specu ~40 scénářových odrážek (2503-2843); plán inline pokrývá klíčové (řídicí větve, redakce, invariant, KeyboardInterrupt, backup timing). Executor při implementaci projde spec seznam a doplní, co plán vynechal - test soubor je `tests/test_cli.py`, vzory jsou v plánu.

**2. Placeholder scan:** velké bloky KÓDU jsou odkázané VERBATIM na rozsahy řádků specu (ne "TODO") - spec cestuje s plánem. Testy jsou inline s plným kódem. Odchylky od spec-verbatim (fake stdin `sys.stdin.buffer`, opravené délkové poměry, vynechaný lokální import) jsou explicitně označené a zdůvodněné v příslušných taskech.

**3. Type consistency:** `_polish_one_chapter` vrací `dict`, `_cmd_polish` appendne jednou za iteraci (Task 11 + 12). `_rejection_reasons` → `list`, `_polish_rejected` → `bool` (Task 8). `stylist.polish` signatura stejná v Task 5 Interfaces i Task 11/12 volání. `_finding_key` = `(type, term_id, actual)` (Task 7 + 8). `_write_polish_report` kwargs stejné (Task 10 + 12). `main.stylist`/`main.concordance`/`main.pipeline`/`main.state` jsou modulové → jednotný monkeypatch `main.<mod>.<attr>` ve všech test taskech.

**Riziková místa pro executora:**
- Task 5: znění `SYSTEM_PROMPT_TEMPLATE` (spec 534-559) musí sedět na regexové kotvy ve fake skriptech testů (`ČESKÝ PŘEKLAD K UPRAVENÍ`, `Odpověz upravenou`) - ověř a případně kotvy uprav.
- Task 8: reálné chování `concordance.find_form_occurrences`/`check_chapter` na víceslovných povrchách - když integrační test neprojde, uprav VSTUPNÍ TEXTY, ne očekávaný výsledek ani spec kód.
- Task 12: `_cmd_polish` čte `c["notes"]`, `c["raw_text"]`, `c["translated_text"]`, `c["revision_rounds"]` z `chapters_by_status` - sloupce existují (`src/state.py:7-16`).
- Task 13: ověření NIKDY needituje `config.py` a NIKDY neběží nad `data/state.sqlite3` - jen kopie DB v `<TMP>` + `config.*` atributy za běhu. Canary test PRVNÍ, před během nad knihou.
