# Kritik přes `claude` CLI místo Anthropic API - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (nebo superpowers:subagent-driven-development) k implementaci tohohle plánu task-by-task. Kroky používají checkbox (`- [ ]`) syntax pro sledování.

**Goal:** Kritik (`_run_critic()`/`critic.review()`) přestává volat placené
Anthropic API (`AnthropicClient`, `ANTHROPIC_API_KEY`) a místo toho běží
přes `claude` CLI (Claude Code), co využívá uživatelovo existující
předplatné (OAuth session) - stejný princip jako `--translator codex`,
teď pro kritika. Translator zůstává BEZE ZMĚNY (`--translator claude|codex`).

**Architecture:** Nová `ClaudeCliClient` (`src/llm/client.py`), stejný
`LLMClient` protokol jako `AnthropicClient`/`CodexLLMClient`. Subprocess
detaily (`_resolve_claude_cmd`, `_exec_claude`) v NOVÉM modulu
`src/llm/claude_cli.py` - odděleně od `stylist.py` (ten je Codex-
specifický, FS-risk gate a spol., kritický klient nic z toho nepotřebuje).
`_client_factory`'s `agent=="critic"` větev staví `ClaudeCliClient`
MÍSTO `AnthropicClient`, natvrdo, bez fallbacku - kritik už žádný API
klíč nepotřebuje.

**Tech Stack:** Python, `subprocess.Popen` (stejný vzor jako
`stylist._exec_codex` - Popen+communicate, ne `subprocess.run(timeout=)`,
kvůli Windows process-tree killing), `claude` CLI (`claude -p
--safe-mode --tools "" --output-format json`).

**Spec:** `docs/superpowers/specs/2026-09-21-claude-cli-critic-design.md`

## Global Constraints

- Kritik VŽDY `ClaudeCliClient` po tomhle plánu - žádný fallback na
  `AnthropicClient`/API klíč. `config.ANTHROPIC_API_KEY`/`AnthropicClient`
  zůstávají v kódu (translator může být `--translator claude`), jen
  kritik je přestává používat.
- `claude -p --safe-mode --tools ""` - `--safe-mode` (NE `--bare`,
  ověřeno spikem 2026-09-21 - `--bare` vynucuje `ANTHROPIC_API_KEY`/
  `apiKeyHelper` auth, OAuth/keychain se v něm NEČTE, což by celý smysl
  týhle změny popřelo). `--tools ""` vypíná VŠECHNY nástroje (žádný
  přístup k disku/Bash) - žádná FS-risk pojistka jako u Codexu potřeba.
- Prompt jde přes STDIN, NE jako pozicní argument (ověřeno spikem -
  `claude -p` bez pozicního argumentu čte prompt ze stdin) - kapitola
  EN+CZ text může snadno přesáhnout Windows argv limit (~8191 znaků),
  stejný důvod jako Codexův stdin vzor v `stylist._exec_codex`.
- `billed_model` MUSÍ být ODLIŠNÝ string od `config.MODEL_CRITIC`
  ("claude-sonnet-5") - ten string se STÁLE používá pro SKUTEČNÉ,
  placené Claude API volání (translator při `--translator claude`,
  `config.MODEL_TRANSLATOR` má STEJNOU hodnotu "claude-sonnet-5").
  Kdyby `ClaudeCliClient.billed_model` byl taky "claude-sonnet-5" a
  jeho cena v `PRICE_IN_PER_MTOK` se nastavila na `0.0`, VYNULOVALO by
  to i cenu SKUTEČNÝCH, placených translator-přes-API volání se
  STEJNÝM model stringem. `billed_model = f"{config.MODEL_CRITIC}-cli"`
  ("claude-sonnet-5-cli") - vlastní, oddělený klíč v cenové tabulce.
- Windows process-tree killing: `claude.cmd` (npm wrapper) spouští
  `claude.exe` PŘÍMO (ověřeno - na rozdíl od `codex.cmd`, co spouští
  `node.exe` jako dalšího potomka) - přesto `_exec_claude()` používá
  STEJNÝ `Popen`+`communicate()`+timeout+`_kill_process_tree` vzor jako
  `_exec_codex()` (import `stylist._kill_process_tree`, needuplikovat) -
  obranné chování, i kdyby `claude.exe` sám interně spouštěl další
  procesy (MCP servery apod.), timeout na `communicate()` musí něco
  ukončit, ne nechat viset.
- Chybové stavy (nenulový exit kód, timeout, nečitelný JSON výstup,
  `is_error: true` v JSON) → nová `ClaudeCliFatalError(FatalRunError)`
  (`src/llm/client.py`, HNED ZA `CodexTranslatorFatalError`) - zpráva
  přes `stylist._redact_detail()` (existující funkce, beze změny).
  `_run_critic()` (`pipeline.py`) beze změny - `except FatalRunError:
  raise` zachytí `ClaudeCliFatalError` stejně jako dnešní
  `AnthropicClient`'s chyby, `_cmd_run`'s existující `except
  FatalRunError: raise` větev (main.py) to zachytí (mimo
  `CodexTranslatorFatalError`'s speciální flagged/redakci - kritikova
  chyba není translator-specifická).
- `_cmd_run`'s eager `ANTHROPIC_API_KEY` kontrola (main.py, zavedená
  minulým plánem "kolo 22") se RUŠÍ - kritik už žádný API klíč
  nepotřebuje, kontrola by ověřovala něco, na čem nezáleží.

---

### Task 1: `config.py` - timeout + nulová cena pro `claude` CLI kritika

**Files:**
- Modify: `config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS` (int),
  `config.PRICE_IN_PER_MTOK[f"{config.MODEL_CRITIC}-cli"] == 0.0`,
  `config.PRICE_OUT_PER_MTOK[f"{config.MODEL_CRITIC}-cli"] == 0.0`.

- [ ] **Step 1: Napiš test**

Přidej do `tests/test_config.py`:

```python
def test_claude_cli_critic_model_has_zero_price_entries():
    key = f"{config_module.MODEL_CRITIC}-cli"
    assert config_module.PRICE_IN_PER_MTOK[key] == 0.0
    assert config_module.PRICE_OUT_PER_MTOK[key] == 0.0


def test_claude_cli_critic_timeout_seconds_is_positive_int():
    assert isinstance(config_module.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS, int)
    assert config_module.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS > 0
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_config.py -k "claude_cli_critic" -v`
Expected: FAIL - `KeyError`/`AttributeError` (config.py ještě nemá ani
`CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS`, ani cenu pro `f"{MODEL_CRITIC}-cli"`)

- [ ] **Step 3: Implementuj**

V `config.py` najdi (dnes hned za `STYLIST_TIMEOUT_SECONDS = 180` a
před `CODEX_TRANSLATE_TIMEOUT_SECONDS`'s komentářem - vlož NOVÝ blok
za CELÝ Codex-translator blok, tj. za `CODEX_TRANSLATE_TIMEOUT_SECONDS
= 300`):

```python
CODEX_TRANSLATE_TIMEOUT_SECONDS = 300
```

přidej HNED ZA NĚJ:

```python
# `claude` CLI (Claude Code) jako backend pro kritika - běží na
# uživatelově předplatném (OAuth session), ne za token přes API (viz
# docs/superpowers/specs/2026-09-21-claude-cli-critic-design.md).
# `MODEL_CRITIC` samotné ("claude-sonnet-5") si NECHÁVÁME nedotčené v
# cenové tabulce - translator (--translator claude, default) volá
# SKUTEČNÉ, placené Claude API se STEJNÝM model stringem
# (MODEL_TRANSLATOR má taky "claude-sonnet-5") - kdyby `billed_model`
# kritika byl STEJNÝ string s nulovou cenou, vynulovalo by to omylem
# i translatorovu SKUTEČNOU cenu. `-cli` suffix drží oddělený klíč.
PRICE_IN_PER_MTOK[f"{MODEL_CRITIC}-cli"] = 0.0
PRICE_OUT_PER_MTOK[f"{MODEL_CRITIC}-cli"] = 0.0
# Kratší než CODEX_TRANSLATE_TIMEOUT_SECONDS - kritický průchod
# (posouzení už přeložené kapitoly) je kratší úkol než generování
# celé kapitoly (spike 2026-09-21).
CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS = 180
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config pro claude CLI kritika - timeout + nulova cena

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `ClaudeCliClient` + `src/llm/claude_cli.py` subprocess wrapper

**Files:**
- Create: `src/llm/claude_cli.py` (`_resolve_claude_cmd`, `_exec_claude`)
- Modify: `src/llm/client.py` (`ClaudeCliFatalError`; nová `ClaudeCliClient`)
- Test: `tests/test_claude_cli.py` (nový), `tests/test_pipeline_client.py`

**Interfaces:**
- Consumes: `stylist._kill_process_tree` (existující, beze změny -
  Windows-specifický proces-strom killer, NENÍ Codex-specifický -
  bezpečné znovupoužít), `stylist._redact_detail` (existující).
- Produces: `claude_cli.ClaudeCliFatalError` NENÍ tady - žije v
  `src/llm/client.py` (podtřída `FatalRunError`, stejná vrstva jako
  `CodexTranslatorFatalError`/`MissingPriceError`).
- Produces: `claude_cli._resolve_claude_cmd(claude_cmd: list[str]) ->
  list[str]` - stejný vzor jako `stylist._resolve_codex_cmd`
  (`shutil.which` pro holé jméno, `PermissionError`-styl zprávu při
  nenalezení).
- Produces: `claude_cli._exec_claude(prompt_text: str, *, claude_cmd:
  list[str], model: str, timeout: int) -> dict` - vrací ROZPARSOVANÝ
  JSON výstup (`--output-format json`), NE surový text (na rozdíl od
  `_exec_codex`, co vrací text - kritik potřebuje `result`/`usage`/
  `is_error` pole zvlášť).
- Produces: `client.ClaudeCliClient(claude_cmd: list[str], model: str,
  timeout: int | None = None)` - `complete()`/`count_tokens()` stejný
  `LLMClient` protokol, `.provider == "claude-cli"`,
  `.billed_model == f"{model}-cli"`.

- [ ] **Step 1: Napiš testy pro `claude_cli.py`**

Vytvoř `tests/test_claude_cli.py`:

```python
import subprocess
import pytest
from src.llm import claude_cli


def test_resolve_claude_cmd_uses_absolute_path_directly(tmp_path):
    fake = tmp_path / "fake_claude.exe"
    fake.write_text("")
    assert claude_cli._resolve_claude_cmd([str(fake)]) == [str(fake)]


def test_resolve_claude_cmd_raises_clear_error_for_missing_bare_name():
    with pytest.raises(claude_cli.ClaudeCliUnavailable, match="claude"):
        claude_cli._resolve_claude_cmd(["nope-not-a-real-binary-xyz"])


def test_exec_claude_calls_popen_with_stdin_prompt_and_expected_argv(monkeypatch):
    seen = {}
    class FakeProc:
        pid = 4242
        returncode = 0
        def communicate(self, input, timeout):
            seen["stdin"] = input
            seen["timeout"] = timeout
            return ('{"result": "ok", "is_error": false, "subtype": "success", '
                    '"usage": {"input_tokens": 10, "output_tokens": 5}}', "")
    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        return FakeProc()
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = claude_cli._exec_claude("SYS\n\nUSR", claude_cmd=["claude"],
                                     model="claude-sonnet-5", timeout=30)
    assert result["result"] == "ok"
    assert result["usage"]["input_tokens"] == 10
    assert seen["stdin"] == "SYS\n\nUSR"
    assert seen["timeout"] == 30
    assert "-p" in seen["cmd"] and "--safe-mode" in seen["cmd"]
    assert "--tools" in seen["cmd"]
    tools_idx = seen["cmd"].index("--tools")
    assert seen["cmd"][tools_idx + 1] == ""
    assert "--model" in seen["cmd"]
    model_idx = seen["cmd"].index("--model")
    assert seen["cmd"][model_idx + 1] == "claude-sonnet-5"


def test_exec_claude_raises_on_nonzero_exit(monkeypatch):
    class FakeProc:
        pid = 1
        returncode = 1
        def communicate(self, input, timeout):
            return ("", "auth expired")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError, match="auth expired"):
        claude_cli._exec_claude("s", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_unparseable_json(monkeypatch):
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ("not json at all", "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError):
        claude_cli._exec_claude("s", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_is_error_true(monkeypatch):
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ('{"result": null, "is_error": true, "subtype": "error_during_execution"}', "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError, match="error_during_execution"):
        claude_cli._exec_claude("s", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_kills_process_tree_on_timeout(monkeypatch):
    killed = {"n": 0}
    class FakeProc:
        pid = 99
        returncode = None
        def communicate(self, input, timeout):
            raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)
        def wait(self, timeout=None):
            pass
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    monkeypatch.setattr(claude_cli, "_kill_process_tree",
                        lambda proc: killed.__setitem__("n", killed["n"] + 1))
    with pytest.raises(claude_cli.ClaudeCliTimeoutError):
        claude_cli._exec_claude("s", claude_cmd=["claude"], model="m", timeout=1)
    assert killed["n"] == 1
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_claude_cli.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'src.llm.claude_cli'`

- [ ] **Step 3: Implementuj `src/llm/claude_cli.py`**

```python
"""Subprocess vrstva nad `claude` CLI (Claude Code) - kritik jede přes
uživatelovo předplatné (OAuth session), ne přes placené Anthropic API.
Analogie `stylist._exec_codex`/`_resolve_codex_cmd`, ale JEDNODUŠŠÍ -
kritik nepotřebuje FS-risk gate (`--tools ""` vypíná VŠECHNY nástroje,
žádný přístup k disku), žádný `-C`/`-o` souborový výstup (`--output-
format json` na stdout stačí), žádnou markdown-obal kontrolu.
"""
import json
import os
import shutil
import subprocess

from src.agents.stylist import _kill_process_tree


class ClaudeCliUnavailable(RuntimeError):
    """`claude` CLI nenalezené na PATH ani jako absolutní cesta."""


class ClaudeCliExecError(RuntimeError):
    """`claude -p` selhalo (nenulový exit kód, nečitelný JSON výstup,
    nebo `is_error: true` v odpovědi)."""


class ClaudeCliTimeoutError(RuntimeError):
    """`claude -p` překročilo timeout - podtřída odlišná od `ClaudeCliExecError`
    ze stejného důvodu jako `stylist.StylistTimeoutError` u Codexu:
    volající (`ClaudeCliClient.complete()`) je může chtít rozlišit."""


def _resolve_claude_cmd(claude_cmd: list) -> list:
    """Stejný vzor jako `stylist._resolve_codex_cmd` - `claude_cmd[0]`
    se hledá přes `shutil.which`, jen když je to holé jméno bez cesty."""
    exe = claude_cmd[0]
    resolved = exe if os.path.isabs(exe) else shutil.which(exe)
    if not resolved:
        raise ClaudeCliUnavailable(
            f"příkaz {exe!r} nenalezen - je Claude Code CLI nainstalované "
            "a přihlášené (`claude login`)?")
    return [resolved] + claude_cmd[1:]


def _exec_claude(prompt_text: str, *, claude_cmd: list, model: str,
                 timeout: int) -> dict:
    """Jedno volání `claude -p` s daným promptem (SYSTEM+USER spojené,
    stejně jako Codexova `_exec_codex`'s `prompt`) - vrací rozparsovaný
    JSON výstup. Prompt jde STDINEM (ne pozicním argumentem) - kapitola
    EN+CZ text může snadno přesáhnout Windows argv limit (~8191 znaků)."""
    cmd = _resolve_claude_cmd(claude_cmd) + [
        "-p", "--safe-mode", "--tools", "", "--output-format", "json",
        "--model", model,
    ]
    try:
        # Popen+communicate (NE subprocess.run(timeout=)) - stejný důvod
        # jako `_exec_codex` (kolo 5 IMPORTANT tamtéž): timeout musí umět
        # ukončit CELÝ proces strom, ne jen přímého potomka.
        # `encoding="utf-8"` explicitně - Windows lokální kódování
        # (cp1252) by český prompt nezakódovalo.
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8")
    except OSError as e:
        raise ClaudeCliUnavailable(
            f"příkaz {claude_cmd!r} se nepodařilo spustit "
            f"({type(e).__name__}: {e}) - je Claude Code CLI nainstalované "
            "a přihlášené?")
    try:
        stdout, stderr = proc.communicate(input=prompt_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise ClaudeCliTimeoutError(f"claude -p překročilo timeout {timeout}s.")
    except BaseException:
        # Ctrl+C během communicate() nesmí nechat proces běžet dál -
        # stejný důvod jako _exec_codex's kolo 2 IMPORTANT odchylka.
        _kill_process_tree(proc)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise
    if proc.returncode != 0:
        raise ClaudeCliExecError(
            f"claude -p skončilo s kódem {proc.returncode}: {stderr.strip()}")
    try:
        payload = json.loads(stdout)
    except ValueError as e:
        raise ClaudeCliExecError(
            f"claude -p vrátilo nerozparsovatelný JSON výstup: {e}") from e
    if payload.get("is_error"):
        raise ClaudeCliExecError(
            f"claude -p vrátilo chybu ({payload.get('subtype')}): "
            f"{payload.get('result')}")
    return payload
```

- [ ] **Step 4: Ověř úspěch (claude_cli.py)**

Run: `pytest tests/test_claude_cli.py -v`
Expected: PASS

- [ ] **Step 5: Napiš testy pro `ClaudeCliClient`**

Přidej do `tests/test_pipeline_client.py`:

```python
def test_claude_cli_client_calls_exec_claude_and_wraps_result(monkeypatch):
    from src.llm.client import ClaudeCliClient
    seen = {}
    def fake_exec(prompt, *, claude_cmd, model, timeout):
        seen.update(prompt=prompt, claude_cmd=claude_cmd, model=model, timeout=timeout)
        return {"result": "nálezy: []", "is_error": False, "subtype": "success",
                "usage": {"input_tokens": 123, "output_tokens": 45}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "claude-sonnet-5", timeout=42)
    comp = c.complete(system="SYS", user="USR", max_tokens=1000, model="claude-sonnet-5")
    assert comp.text == "nálezy: []"
    assert comp.truncated is False
    assert comp.input_tokens == 123
    assert comp.output_tokens == 45
    assert seen["prompt"] == "SYS\n\nUSR"
    assert seen["claude_cmd"] == ["claude"]
    assert seen["model"] == "claude-sonnet-5"
    assert seen["timeout"] == 42


def test_claude_cli_client_default_timeout_from_config(monkeypatch):
    from src.llm.client import ClaudeCliClient
    import config
    monkeypatch.setattr(config, "CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS", 99)
    seen = {}
    def fake_exec(prompt, *, claude_cmd, model, timeout):
        seen["timeout"] = timeout
        return {"result": "ok", "is_error": False, "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "m")   # timeout NEZADÁN
    c.complete(system="s", user="u", max_tokens=10, model="m")
    assert seen["timeout"] == 99


def test_claude_cli_client_billed_model_has_cli_suffix():
    from src.llm.client import ClaudeCliClient
    c = ClaudeCliClient(["claude"], "claude-sonnet-5")
    assert c.billed_model == "claude-sonnet-5-cli"


def test_claude_cli_client_count_tokens_is_conservative_estimate():
    from src.llm.client import ClaudeCliClient
    c = ClaudeCliClient(["claude"], "m")
    assert c.count_tokens(system="abcd", user="efgh", model="m") == 4   # (4+4)//2


def test_claude_cli_client_wraps_exec_errors_as_fatal_run_error(monkeypatch):
    from src.llm.client import ClaudeCliClient, ClaudeCliFatalError
    from src.llm.claude_cli import ClaudeCliExecError
    def boom(*a, **k):
        raise ClaudeCliExecError("claude -p skončilo s kódem 1: auth expired")
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", boom)
    c = ClaudeCliClient(["claude"], "m")
    with pytest.raises(ClaudeCliFatalError) as exc_info:
        c.complete(system="s", user="u", max_tokens=10, model="m")
    assert "auth expired" not in str(exc_info.value)   # redigováno
    assert "potlačeny" in str(exc_info.value)


def test_claude_cli_client_fatal_error_shows_detail_when_report_rejected_text_true(
        monkeypatch):
    from src.llm.client import ClaudeCliClient, ClaudeCliFatalError
    from src.llm.claude_cli import ClaudeCliExecError
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", True)
    def boom(*a, **k):
        raise ClaudeCliExecError("claude -p skončilo s kódem 1: auth expired")
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", boom)
    c = ClaudeCliClient(["claude"], "m")
    with pytest.raises(ClaudeCliFatalError, match="auth expired"):
        c.complete(system="s", user="u", max_tokens=10, model="m")


def test_claude_cli_client_does_not_wrap_timeout_as_fatal_run_error(monkeypatch):
    """Timeout jednoho volání je per-call/transientní - kritik selže na
    `_run_critic()`'s existující `except Exception` větev (pseudo-nález,
    critic_failed=True), NE zastaví celý run. NEmá stejný `except
    (FatalRunError, KeyboardInterrupt)` checkpoint-rozsah jako Codex
    translator (Task 2 minulého plánu), protože `_run_critic()` už
    tohle rozlišení SAMO dělá - viz `pipeline.py:52-63`."""
    from src.llm.client import ClaudeCliClient
    from src.llm.claude_cli import ClaudeCliTimeoutError
    def boom(*a, **k):
        raise ClaudeCliTimeoutError("claude -p překročilo timeout 180s.")
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", boom)
    c = ClaudeCliClient(["claude"], "m")
    with pytest.raises(ClaudeCliTimeoutError):
        c.complete(system="s", user="u", max_tokens=10, model="m")
```

- [ ] **Step 6: Ověř selhání (ClaudeCliClient)**

Run: `pytest tests/test_pipeline_client.py -k claude_cli_client -v`
Expected: FAIL - `ImportError: cannot import name 'ClaudeCliClient'`

- [ ] **Step 7: Implementuj `ClaudeCliClient` v `src/llm/client.py`**

V `src/llm/client.py`, HNED ZA `class CodexTranslatorFatalError(FatalRunError): ...`
(za `MissingPriceError`), přidej:

```python
class ClaudeCliFatalError(FatalRunError):
    """Fatální chyba VZNIKLÁ PŘÍMO v `ClaudeCliClient.complete()` volání
    (nenulový exit kód, nečitelný JSON výstup) - podtřída `FatalRunError`.
    NENÍ translator-specifická jako `CodexTranslatorFatalError` - kritik
    je teď VŽDY tenhle backend, nezávisle na `--translator`, takže
    `_cmd_run` (main.py) ji NEROZLIŠUJE zvlášť, spadá do obecné `except
    FatalRunError: raise` větve stejně jako dřívější `AnthropicClient`
    chyby (auth, rate limit atd.)."""
```

HNED ZA `class CodexLLMClient: ...` (před `class FakeLLMClient`), přidej:

```python
class ClaudeCliClient:
    """`LLMClient` obal nad `claude -p` subprocess voláním
    (`src.llm.claude_cli._exec_claude`) - kritik jede přes uživatelovo
    předplatné (OAuth session), ne přes placené Anthropic API. Používá
    se VŽDY pro `agent="critic"` (main.py `_client_factory`), nezávisle
    na `--translator` - viz docs/superpowers/specs/2026-09-21-claude-cli-
    critic-design.md."""
    provider = "claude-cli"

    def __init__(self, claude_cmd: list[str], model: str,
                 timeout: int | None = None):
        self._claude_cmd = claude_cmd
        self._model = model
        self._timeout = timeout
        # `-cli` suffix - viz Global Constraints v plánu - NESMÍ
        # kolidovat s `config.MODEL_CRITIC`'s SKUTEČNÝM API cenovým
        # záznamem (translator při --translator claude volá STEJNÝ
        # model string se SKUTEČNOU cenou).
        self.billed_model = f"{model}-cli"

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        import config
        from src.llm import claude_cli
        prompt = f"{system}\n\n{user}"
        timeout = self._timeout or config.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS
        try:
            payload = claude_cli._exec_claude(
                prompt, claude_cmd=self._claude_cmd, model=self._model,
                timeout=timeout)
        except claude_cli.ClaudeCliTimeoutError:
            # Timeout NEpřebalujeme - `_run_critic()` (pipeline.py) má
            # VLASTNÍ `except FatalRunError: raise` / `except Exception:
            # pseudo-nález, critic_failed=True` rozlišení; timeout jako
            # obyčejná výjimka spadne do TÉ druhé větve (nefatální,
            # kapitola pokračuje s pseudo-nálezem), stejně jako každá
            # jiná dnešní kritikova chyba PŘED týmhle plánem.
            raise
        except (claude_cli.ClaudeCliUnavailable, claude_cli.ClaudeCliExecError) as e:
            from src.agents import stylist
            raise ClaudeCliFatalError(stylist._redact_detail(str(e))) from e
        usage = payload.get("usage") or {}
        return Completion(
            text=payload.get("result") or "",
            truncated=False,
            input_tokens=usage.get("input_tokens") or 1,
            output_tokens=usage.get("output_tokens") or 1,
        )

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        return max(1, (len(system) + len(user)) // 4)
```

- [ ] **Step 8: Ověř úspěch**

Run: `pytest tests/test_claude_cli.py tests/test_pipeline_client.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/llm/claude_cli.py src/llm/client.py tests/test_claude_cli.py tests/test_pipeline_client.py
git commit -m "feat: ClaudeCliClient - kritik pres claude CLI misto Anthropic API

Nova src/llm/claude_cli.py subprocess vrstva (analogie stylist._exec_
codex, ale bez FS-risk gate - --tools \"\" vypina vsechny nastroje).
ClaudeCliClient implementuje stejny LLMClient protokol, billed_model
ma '-cli' suffix (odlisny od config.MODEL_CRITIC, co translator pres
--translator claude pouziva se SKUTECNOU cenou).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: `main._client_factory` - kritik natvrdo na `ClaudeCliClient`

**Files:**
- Modify: `main.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ClaudeCliClient` (Task 2).
- Produces: `_client_factory`'s `agent=="critic"` větev vrací klienta
  obalující `ClaudeCliClient` MÍSTO `AnthropicClient`. `agent=="translator"`
  větve (claude/codex) BEZE ZMĚNY.

- [ ] **Step 1: Napiš test**

Přidej do `tests/test_cli.py`:

```python
def test_client_factory_critic_always_uses_claude_cli_client(monkeypatch):
    from src.llm.client import ClaudeCliClient
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    factory = main._client_factory(1, interactive=False)
    client = factory("critic")
    assert isinstance(client._inner, ClaudeCliClient)
    assert client._inner.billed_model == f"{config.MODEL_CRITIC}-cli"


def test_client_factory_critic_uses_claude_cli_even_with_codex_translator(monkeypatch):
    """Kritik zůstává na `claude` CLI NEZÁVISLE na `translator_backend` -
    žádný fallback, žádná podmínka na `--translator`."""
    from src.llm.client import ClaudeCliClient
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    factory = main._client_factory(1, interactive=False, translator_backend="codex")
    client = factory("critic")
    assert isinstance(client._inner, ClaudeCliClient)


def test_client_factory_translator_default_claude_unaffected_by_critic_change(
        monkeypatch):
    """Translator (--translator claude, default) zůstává na AnthropicClient -
    tenhle plán mění JEN kritika."""
    from src.llm.client import AnthropicClient
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    factory = main._client_factory(1, interactive=False)
    client = factory("translator")
    assert isinstance(client._inner, AnthropicClient)
```

(`import shutil` potřeba na začátku `tests/test_cli.py`, pokud tam
ještě není.)

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_cli.py -k client_factory_critic -v`
Expected: FAIL - `AssertionError` (`client._inner` je pořád `AnthropicClient`)

- [ ] **Step 3: Implementuj**

V `main.py`, `_client_factory`'s `factory()`, najdi:

```python
            inner = CodexLLMClient(codex_cmd, config.CODEX_MODEL)
        else:
            inner = AnthropicClient()
```

nahraď:

```python
            inner = CodexLLMClient(codex_cmd, config.CODEX_MODEL)
        elif agent == "critic":
            # Kritik VŽDY `claude` CLI (předplatné) - žádný fallback na
            # AnthropicClient/API klíč, nezávisle na `translator_backend`
            # (viz docs/superpowers/specs/2026-09-21-claude-cli-critic-
            # design.md). `_resolve_claude_cmd` (uvnitř `ClaudeCliClient.
            # complete()`, líně - stejný lazy vzor jako Codex) vyhodí
            # `ClaudeCliUnavailable` → `ClaudeCliFatalError`, pokud
            # `claude` CLI není nainstalované/na PATH.
            inner = ClaudeCliClient(["claude"], config.MODEL_CRITIC)
        else:
            inner = AnthropicClient()
```

Rozšiř import na main.py o `ClaudeCliClient`:

```python
from src.llm.client import (AnthropicClient, ClaudeCliClient, CodexLLMClient,
                           CodexTranslatorFatalError, FatalRunError,
                           LockLostError, OutputTruncated, PipelineLLMClient)
```

V `_cmd_run` (main.py), najdi CELÝ blok (zaveden minulým plánem, teď
se ruší):

```python
        # Kolo 22 IMPORTANT (plan-consensus) - eager preflight výš
        # ověří JEN Codex stranu - kritik zůstává VŽDY `AnthropicClient`
        # (Global Constraints), i při `--translator codex`, a ten se
        # konstruuje LÍNĚ (`_client_factory`'s `factory("critic")`) až
        # při PRVNÍM volání - PO dokončení scénového překladu první
        # kapitoly. Bez týhle kontroly by chybějící `ANTHROPIC_API_KEY`
        # nechal proběhnout celý (zaplacený) Codex překlad, než by run
        # selhal na kritikovi.
        # Kolo 22 (plan-consensus, self-review): PŘÍMÁ kontrola `config.
        # ANTHROPIC_API_KEY` (stejná podmínka jako `AnthropicClient.
        # __init__`, src/llm/client.py:51-58), NE konstrukce skutečného
        # `AnthropicClient()` - ta by nově vyžadovala `ANTHROPIC_API_KEY`
        # mock v ~6 existujících testech (Task 5), co dnes mockují
        # `_polish_preflight` na úspěch a `pipeline.process_chapter`
        # samotné (takže se `client_factory("critic")` nikdy reálně
        # nezavolá) - bez závislosti na klíči. Přímá kontrola stejnou
        # podmínku ověří bez týhle vedlejší závislosti.
        if not config.ANTHROPIC_API_KEY:
            _say("--translator codex stále vyžaduje funkční Claude API "
                "pro kritika: Chybí ANTHROPIC_API_KEY v prostředí.")
            return 1
```

smaž CELÝ tenhle blok (nic ho nenahrazuje - kritik už API klíč
nepotřebuje, kontrola by ověřovala něco, na čem nezáleží).

Existující testy, co tenhle blok mockovaly/ověřovaly (`test_run_
translator_codex_missing_anthropic_key_fails_eager` a jakékoli
`monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")` řádky
přidané JEN kvůli týhle kontrole) - najdi je (`grep -rn
"ANTHROPIC_API_KEY" tests/test_cli.py`) a smaž/uprav podle toho, co
zbylo z jejich PŮVODNÍHO účelu (většina mocků zůstává neškodná i po
smazání, protože nikdo `ANTHROPIC_API_KEY` už nekontroluje - ale
`test_run_translator_codex_missing_anthropic_key_fails_eager` samo
testovalo PŘESNĚ tenhle zrušený blok, ten test smaž celý).

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (zkontroluj especially, že žádný zbylý test needěpendí
na zrušené `ANTHROPIC_API_KEY` eager kontrole)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: kritik natvrdo pres claude CLI, zrusena ANTHROPIC_API_KEY eager kontrola

_client_factory's agent==critic vetev staví ClaudeCliClient MISTO
AnthropicClient, nezavisle na translator_backend. _cmd_run's eager
ANTHROPIC_API_KEY kontrola (zavedena minulym planem pro kritika) se
rusi - kritik uz zadny API klic nepotrebuje.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Manuální ověření + dokončení branch

**Files:** žádné nové - ověřovací krok.

- [ ] **Step 1: Spusť celou sadu**

Run: `pytest -v`
Expected: PASS, 0 chyb.

- [ ] **Step 2: Manuální ověření na reálné kapitole**

Stejný izolační mechanismus jako minulý plán (`BOOK_TRANSLATOR_
PROJECT_DIR`, `sqlite3.Connection.backup()`, NE prostý `cp`) - viz
minulý plán's Task 6 pro přesné příkazy. Spusť `run` (BEZ
`--translator codex` je taky OK - kritik se aktivuje při KAŽDÉM
`run`u, translator může být `claude` nebo `codex`) na jedné `pending`
kapitole, zkontroluj:

- `llm_calls` řádek pro `agent='critic'` má `provider='claude-cli'`,
  `model='claude-sonnet-5-cli'`, `cost_usd=0.0`.
- Kapitola dostala smysluplné nálezy (pokud nějaké critic vygeneroval) -
  `notes` sloupec, ne prázdné/nesmyslné.
- Žádný `ANTHROPIC_API_KEY` v prostředí (`unset ANTHROPIC_API_KEY` /
  `Remove-Item Env:ANTHROPIC_API_KEY`) - `run` musí projít i BEZ něj
  (to je celý smysl týhle změny).

- [ ] **Step 3: Invoke `superpowers:finishing-a-development-branch`**

Ověř testy, prezentuj možnosti (merge/PR/nechat), proveď podle volby
uživatele.
