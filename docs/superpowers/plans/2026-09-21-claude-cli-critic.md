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
- **Kolo 3 BLOCKING (plan-consensus) - `stylist_check` NENÍ v rozsahu:**
  `_polish_one_chapter()` (`main.py:698`, `_cmd_polish`/polish-server)
  volá NAVÍC `cf("stylist_check")` - TŘETÍ agent typ (ne "translator",
  ne "critic"), používaný `stylist.check_meaning_preserved()`. Rozsah
  tohohle plánu (brainstorming 2026-09-21 - "Jen kritik") ho NEMĚNÍ -
  zůstává `AnthropicClient`/`ANTHROPIC_API_KEY`. `run` (translator +
  kritik) po tomhle plánu API klíč VŮBEC nepotřebuje; `polish`
  (translator/kritik JE v dávce, PLUS `stylist_check`) klíč STÁLE
  potřebuje - eager kontrola pro `stylist_check`'s `ANTHROPIC_API_KEY`
  se PŘIDÁVÁ (Task 3) vedle nové `claude` CLI kontroly, ať `polish`
  taky neplatí za Codex stylizaci zbytečně, než zjistí chybějící klíč.
- `claude -p --safe-mode --tools ""` - `--safe-mode` (NE `--bare`,
  ověřeno spikem 2026-09-21 - `--bare` vynucuje `ANTHROPIC_API_KEY`/
  `apiKeyHelper` auth, OAuth/keychain se v něm NEČTE, což by celý smysl
  týhle změny popřelo). `--tools ""` vypíná VŠECHNY nástroje (žádný
  přístup k disku/Bash) - žádná FS-risk pojistka jako u Codexu potřeba.
- **Kolo 1 BLOCKING (plan-consensus)** - `system`/`user` se NESMÍ spojit
  do jednoho stdin blobu (`f"{system}\n\n{user}"`, CodexLLMClient's
  vzor) - `system` (kritikovy instrukce, `critic.SYSTEM_PROMPT`, 805
  znaků, statické) jde přes `--system-prompt` CLI flag (bezpečně pod
  Windows argv limitem), `user` (kapitola EN+CZ, může být velké) jde
  PŘES STDIN. Ověřeno spikem 2026-09-21 - `--system-prompt X` + stdin
  user obsah funguje SPRÁVNĚ dohromady (systémová priorita zachovaná).
  Spojení do jednoho stdin blobu by kritikovy instrukce degradovalo na
  "jen další text" bez systémové priority - přesně to, co `critic.
  SYSTEM_PROMPT`/`AnthropicClient`'s `system=` parametr zaručuje a co by
  se týmhle plánem tiše ztratilo.
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
- Chybové stavy (nenulový exit kód, nečitelný/špatně TVAROVANÝ JSON
  výstup, `is_error: true` nebo `subtype != "success"` v JSON) → nová
  `ClaudeCliFatalError(FatalRunError)` (`src/llm/client.py`, HNED ZA
  `CodexTranslatorFatalError`) - zpráva přes `stylist._redact_detail()`
  (existující funkce, beze změny).
  **Kolo 1 IMPORTANT (plan-consensus) - TIMEOUT je VÝJIMKA z tohohle
  seznamu, NE fatální:** timeout jednoho volání je PER-CALL/transientní
  (stejné zdůvodnění jako `stylist.StylistTimeoutError` u Codexu,
  minulý plán, kolo 9 IMPORTANT) - `_run_critic()`'s vlastní `except
  Exception: pseudo-nález, critic_failed=True` větev ho zpracuje
  nefatálně, kapitola pokračuje. `ClaudeCliTimeoutError` (Task 2)
  zůstává SAMOSTATNÝ typ, co `ClaudeCliClient.complete()` NEpřebaluje
  na `ClaudeCliFatalError`.
  `_run_critic()` (`pipeline.py`) beze změny - `except FatalRunError:
  raise` zachytí `ClaudeCliFatalError` stejně jako dnešní
  `AnthropicClient`'s chyby, `_cmd_run`'s existující `except
  FatalRunError: raise` větev (main.py) to zachytí (mimo
  `CodexTranslatorFatalError`'s speciální flagged/redakci - kritikova
  chyba není translator-specifická).
- `_cmd_run`'s eager `ANTHROPIC_API_KEY` kontrola (main.py, zavedená
  minulým plánem "kolo 22") se RUŠÍ - kritik už žádný API klíč
  nepotřebuje, kontrola by ověřovala něco, na čem nezáleží.
- **Kolo 1 IMPORTANT (plan-consensus) - NOVÁ eager `claude` CLI
  preflight kontrola nahrazuje tu zrušenou:** kritik je teď VŽDY
  `ClaudeCliClient`, ale dostupnost/přihlášení `claude` CLI se dřív
  ověřovalo jen LÍNĚ, až při prvním `client_factory("critic")` volání -
  PO scénovém překladu první kapitoly (u `--translator codex` PO
  ZAPLACENÉM Codex volání). `_cmd_run` teď PŘED frontou (stejné místo
  jako Codexova eager kontrola, ALE NEZÁVISLE na `args.translator` -
  kritik je vždy aktivní) zavolá NOVOU `_claude_cli_preflight()`
  (Task 3) - resolvne `claude` binárku (`shutil.which`) A ověří
  přihlášení (`claude auth status --json`, ~0.5s, žádné tokeny/API
  volání) - `loggedIn: true` v odpovědi. Selhání = `return 1` PŘED
  frontou, stejně jako Codexova eager kontrola.
- **Kolo 1 IMPORTANT (plan-consensus) - `truncated` čte SKUTEČNÝ
  `stop_reason` z JSON výstupu, ne natvrdo `False`:** `claude -p
  --output-format json` vrací `stop_reason` pole (ověřeno spikem -
  `"stop_reason":"end_turn"`) - STEJNÝ signál jako Anthropic API's
  `resp.stop_reason` (`AnthropicClient.complete()` už `truncated=
  (resp.stop_reason == "max_tokens")` čte). `ClaudeCliClient.complete()`
  MUSÍ tenhle signál použít, ne tvrdit `truncated=False` vždy (na
  rozdíl od `CodexLLMClient`, co `truncated=False` má jako ZDOKUMENTOVANÝ
  limit - Codex CLI žádný ekvivalent signál nemá, `claude` CLI ANO).
  **Známý, přijatý limit:** `max_tokens` parametr `ClaudeCliClient.
  complete()` NEMÁ CLI ekvivalent (`claude -p` nenabízí žádný limit
  flag) - `critic.review()`'s retry-na-truncation (`tokens = tokens *
  2; continue`) detekci truncation SPRÁVNĚ zachytí (přes `stop_reason`),
  ale samotný retry limit NEZVÝŠÍ (stejná třída limitu jako Codex -
  žádný proaktivní limit navíc, jen zjištění PO faktu).

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
- Produces: `claude_cli._exec_claude(system: str, user: str, *,
  claude_cmd: list[str], model: str, timeout: int) -> dict` - `system`
  jde přes `--system-prompt` CLI flag, `user` přes STDIN (kolo 1
  BLOCKING, plan-consensus - NIKDY nespojovat do jednoho stdin blobu,
  viz Global Constraints). Vrací ROZPARSOVANÝ a VALIDOVANÝ JSON výstup
  (`--output-format json`), NE surový text (na rozdíl od `_exec_codex`,
  co vrací text - kritik potřebuje `result`/`usage`/`stop_reason` pole
  zvlášť).
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


def test_exec_claude_calls_popen_with_system_prompt_flag_and_stdin_user(monkeypatch):
    """Kolo 1 BLOCKING (plan-consensus) - `system` MUSÍ jít přes
    `--system-prompt` CLI flag (systémová priorita), `user` STDINEM -
    NIKDY spojené do jednoho blobu (na rozdíl od CodexLLMClient - tam
    `codex exec` žádný `--system-prompt` ekvivalent nemá, tady ANO,
    ověřeno spikem)."""
    seen = {}
    class FakeProc:
        pid = 4242
        returncode = 0
        def communicate(self, input, timeout):
            seen["stdin"] = input
            seen["timeout"] = timeout
            return ('{"result": "ok", "is_error": false, "subtype": "success", '
                    '"stop_reason": "end_turn", '
                    '"usage": {"input_tokens": 10, "output_tokens": 5}}', "")
    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        return FakeProc()
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    result = claude_cli._exec_claude("SYS", "USR", claude_cmd=["claude"],
                                     model="claude-sonnet-5", timeout=30)
    assert result["result"] == "ok"
    assert result["usage"]["input_tokens"] == 10
    assert seen["stdin"] == "USR"          # JEN user, ne "SYS\n\nUSR"
    assert seen["timeout"] == 30
    assert "-p" in seen["cmd"] and "--safe-mode" in seen["cmd"]
    assert "--tools" in seen["cmd"]
    tools_idx = seen["cmd"].index("--tools")
    assert seen["cmd"][tools_idx + 1] == ""
    assert "--model" in seen["cmd"]
    model_idx = seen["cmd"].index("--model")
    assert seen["cmd"][model_idx + 1] == "claude-sonnet-5"
    assert "--system-prompt" in seen["cmd"]
    sp_idx = seen["cmd"].index("--system-prompt")
    assert seen["cmd"][sp_idx + 1] == "SYS"


def test_exec_claude_raises_on_nonzero_exit(monkeypatch):
    class FakeProc:
        pid = 1
        returncode = 1
        def communicate(self, input, timeout):
            return ("", "auth expired")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError, match="auth expired"):
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_unparseable_json(monkeypatch):
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ("not json at all", "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError):
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_is_error_true(monkeypatch):
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ('{"result": null, "is_error": true, "subtype": "error_during_execution"}', "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError, match="error_during_execution"):
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_subtype_not_success_even_if_is_error_false(monkeypatch):
    """Kolo 1 IMPORTANT (plan-consensus) - `is_error` samo nestačí -
    kontrolujeme i `subtype == "success"` pro případy, kdy CLI vrátí
    neúspěšný `subtype` bez explicitního `is_error: true`."""
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ('{"result": "castecny vysledek", "is_error": false, '
                    '"subtype": "error_max_turns"}', "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError, match="error_max_turns"):
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_non_dict_payload(monkeypatch):
    """Kolo 1 IMPORTANT (plan-consensus) - `extract_json()`'s vlastní
    precedent (kolo 7 BLOCKING minulého plánu, critic.py) - validní JSON
    může být `[]`/`null`/string na nejvyšší úrovni, ne jen objekt."""
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ("[]", "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError):
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_non_string_result(monkeypatch):
    """Kolo 1 IMPORTANT (plan-consensus) - `result` musí být string -
    `ClaudeCliClient.complete()`'s `Completion.text` jde dál do
    `critic.review()`'s `extract_json()`, co string očekává."""
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ('{"result": 42, "is_error": false, "subtype": "success"}', "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError):
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_non_numeric_usage_fields(monkeypatch):
    """Kolo 2 IMPORTANT (plan-consensus) - `isinstance(usage, dict)`
    (kolo 1's fix) nestačí - `input_tokens`/`output_tokens` musí být
    nezáporná celá čísla, jinak `PipelineLLMClient`'s aritmetika
    (`it / 1e6 * in_rate`) spadne UVNITŘ `finally` bloku."""
    for bad_usage in ('"5"', "-3", "true", "1.5"):
        class FakeProc:
            pid = 1
            returncode = 0
            def communicate(self, input, timeout, _u=bad_usage):
                return (f'{{"result": "ok", "is_error": false, '
                        f'"subtype": "success", '
                        f'"usage": {{"input_tokens": {_u}, "output_tokens": 1}}}}', "")
        monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
        with pytest.raises(claude_cli.ClaudeCliExecError):
            claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


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
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=1)
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


def _exec_claude(system: str, user: str, *, claude_cmd: list, model: str,
                 timeout: int) -> dict:
    """Jedno volání `claude -p` - vrací rozparsovaný a VALIDOVANÝ JSON
    výstup. Kolo 1 BLOCKING (plan-consensus) - `system` jde přes
    `--system-prompt` CLI flag (systémová priorita zachovaná, kritikovy
    instrukce jsou statické, 805 znaků - bezpečně pod Windows argv
    limitem), `user` (kapitola EN+CZ, může být velké) STDINEM - NIKDY
    spojené do jednoho blobu (ověřeno spikem 2026-09-21 - obojí
    dohromady funguje správně)."""
    cmd = _resolve_claude_cmd(claude_cmd) + [
        "-p", "--safe-mode", "--tools", "", "--output-format", "json",
        "--model", model, "--system-prompt", system,
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
        stdout, stderr = proc.communicate(input=user, timeout=timeout)
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
    # Kolo 1 IMPORTANT (plan-consensus) - validace CELÉHO kontraktu
    # payloadu, ne jen `is_error` - `extract_json()`'s vlastní precedent
    # (critic.py, kolo 7 BLOCKING minulého plánu): validní JSON může být
    # cokoli ([]/null/string na nejvyšší úrovni), ne jen objekt. Chybějící/
    # neřetězcový `result` nebo nečíselné `usage` by jinak unikly jako
    # AttributeError/TypeError MIMO `ClaudeCliExecError` kontrakt, nebo
    # by rozbily audit log (`Completion.input_tokens`/`output_tokens`
    # musí být čísla).
    if not isinstance(payload, dict):
        raise ClaudeCliExecError(
            f"claude -p vrátilo {type(payload).__name__} na nejvyšší "
            "úrovni, ne objekt.")
    if payload.get("is_error") or payload.get("subtype") != "success":
        raise ClaudeCliExecError(
            f"claude -p vrátilo chybu ({payload.get('subtype')}): "
            f"{payload.get('result')}")
    if not isinstance(payload.get("result"), str):
        raise ClaudeCliExecError(
            f"claude -p's 'result' pole musí být řetězec, ne "
            f"{type(payload.get('result')).__name__}.")
    usage = payload.get("usage")
    if usage is not None:
        if not isinstance(usage, dict):
            raise ClaudeCliExecError(
                f"claude -p's 'usage' pole musí být objekt, ne "
                f"{type(usage).__name__}.")
        # Kolo 2 IMPORTANT (plan-consensus) - `isinstance(usage, dict)`
        # samo nestačí - `input_tokens`/`output_tokens` mohou být
        # string/bool/float/záporné číslo. `PipelineLLMClient.complete()`
        # s nimi počítá aritmeticky VE `finally` bloku (`it / 1e6 *
        # in_rate`) - string tam spadne na `TypeError` UVNITŘ finally
        # (maskuje původní výjimku), `bool` projde tiše (Python `bool`
        # je `int` podtřída, ale sémanticky nesmyslné), záporné číslo
        # by zapsalo nesmyslný audit řádek (záporná cena/tokeny).
        for field in ("input_tokens", "output_tokens"):
            value = usage.get(field)
            if value is not None and (isinstance(value, bool)
                                      or not isinstance(value, int)
                                      or value < 0):
                raise ClaudeCliExecError(
                    f"claude -p's usage.{field} musí být nezáporné "
                    f"celé číslo, ne {value!r}.")
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
    def fake_exec(system, user, *, claude_cmd, model, timeout):
        seen.update(system=system, user=user, claude_cmd=claude_cmd,
                    model=model, timeout=timeout)
        return {"result": "nálezy: []", "is_error": False, "subtype": "success",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 123, "output_tokens": 45}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "claude-sonnet-5", timeout=42)
    comp = c.complete(system="SYS", user="USR", max_tokens=1000, model="claude-sonnet-5")
    assert comp.text == "nálezy: []"
    assert comp.truncated is False
    assert comp.input_tokens == 123
    assert comp.output_tokens == 45
    # Kolo 1 BLOCKING (plan-consensus) - system/user jdou ODDĚLENĚ do
    # _exec_claude, NIKDY spojené.
    assert seen["system"] == "SYS"
    assert seen["user"] == "USR"
    assert seen["claude_cmd"] == ["claude"]
    assert seen["model"] == "claude-sonnet-5"
    assert seen["timeout"] == 42


def test_claude_cli_client_truncated_true_when_stop_reason_is_max_tokens(monkeypatch):
    """Kolo 1 IMPORTANT (plan-consensus) - `truncated` čte SKUTEČNÝ
    `stop_reason` z JSON výstupu (stejný signál jako Anthropic API's
    `resp.stop_reason`), ne natvrdo `False` (na rozdíl od `CodexLLMClient`,
    kde `claude` CLI ekvivalent PROSTĚ EXISTUJE, na rozdíl od Codexu)."""
    from src.llm.client import ClaudeCliClient
    def fake_exec(system, user, *, claude_cmd, model, timeout):
        return {"result": "usknuty text", "is_error": False, "subtype": "success",
                "stop_reason": "max_tokens",
                "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "m")
    comp = c.complete(system="s", user="u", max_tokens=10, model="m")
    assert comp.truncated is True


def test_claude_cli_client_default_timeout_from_config(monkeypatch):
    from src.llm.client import ClaudeCliClient
    import config
    monkeypatch.setattr(config, "CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS", 99)
    seen = {}
    def fake_exec(system, user, *, claude_cmd, model, timeout):
        seen["timeout"] = timeout
        return {"result": "ok", "is_error": False, "subtype": "success",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "m")   # timeout NEZADÁN
    c.complete(system="s", user="u", max_tokens=10, model="m")
    assert seen["timeout"] == 99


def test_claude_cli_client_billed_model_has_cli_suffix():
    from src.llm.client import ClaudeCliClient
    c = ClaudeCliClient(["claude"], "claude-sonnet-5")
    assert c.billed_model == "claude-sonnet-5-cli"


def test_claude_cli_client_count_tokens_is_conservative_estimate():
    """Kolo 2 BLOCKING (plan-consensus) - `//4` (implementace), ne
    `//2` (CodexLLMClient's jiná aproximace) - `(4+4)//4 == 2`."""
    from src.llm.client import ClaudeCliClient
    c = ClaudeCliClient(["claude"], "m")
    assert c.count_tokens(system="abcd", user="efgh", model="m") == 2   # (4+4)//4


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


def test_claude_cli_client_wraps_os_and_unicode_errors_as_fatal_run_error(monkeypatch):
    """Kolo 1 IMPORTANT (plan-consensus) - `_exec_claude()`'s vlastní
    `except BaseException: _kill_process_tree(proc); raise` (kill-tree
    na Ctrl+C, ale JINAK holé re-raise) nechá `UnicodeDecodeError`
    (poškozené kódování stdout) i `OSError` unikat NEREDIGOVANÉ z
    `ClaudeCliClient.complete()`, protože jeho `except` klauzule dřív
    chytala jen `(ClaudeCliUnavailable, ClaudeCliExecError)`. Rozšířeno
    na `(ClaudeCliUnavailable, ClaudeCliExecError, OSError, UnicodeError)` -
    stejný vzor jako `CodexLLMClient.complete()`'s `except (StylistError,
    OSError, UnicodeError)`."""
    from src.llm.client import ClaudeCliClient, ClaudeCliFatalError
    for exc in (OSError("soubor je zamčený"),
               UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")):
        def boom(*a, _exc=exc, **k):
            raise _exc
        monkeypatch.setattr("src.llm.claude_cli._exec_claude", boom)
        c = ClaudeCliClient(["claude"], "m")
        with pytest.raises(ClaudeCliFatalError):
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
    (nenulový exit kód, nečitelný/špatně tvarovaný JSON výstup, `OSError`/
    `UnicodeError` při čtení výstupu) - podtřída `FatalRunError`. NENÍ
    translator-specifická jako `CodexTranslatorFatalError` - kritik je
    teď VŽDY tenhle backend, nezávisle na `--translator`, takže
    `_cmd_run` (main.py) ji NEROZLIŠUJE zvlášť, spadá do obecné `except
    FatalRunError: raise` větve stejně jako dřívější `AnthropicClient`
    chyby (auth, rate limit atd.). Timeout NENÍ součástí týhle třídy -
    `ClaudeCliTimeoutError` zůstává samostatná, nefatální (viz Global
    Constraints)."""
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
        # Kolo 1 BLOCKING (plan-consensus) - `system`/`user` se posílají
        # ODDĚLENĚ do `_exec_claude()` (`--system-prompt` flag +
        # STDIN), NIKDY spojené do jednoho blobu - viz Global Constraints.
        timeout = self._timeout or config.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS
        try:
            payload = claude_cli._exec_claude(
                system, user, claude_cmd=self._claude_cmd, model=self._model,
                timeout=timeout)
        except claude_cli.ClaudeCliTimeoutError:
            # Timeout NEpřebalujeme - `_run_critic()` (pipeline.py) má
            # VLASTNÍ `except FatalRunError: raise` / `except Exception:
            # pseudo-nález, critic_failed=True` rozlišení; timeout jako
            # obyčejná výjimka spadne do TÉ druhé větve (nefatální,
            # kapitola pokračuje s pseudo-nálezem), stejně jako každá
            # jiná dnešní kritikova chyba PŘED týmhle plánem.
            raise
        except (claude_cli.ClaudeCliUnavailable, claude_cli.ClaudeCliExecError,
               OSError, UnicodeError) as e:
            # Kolo 1 IMPORTANT (plan-consensus) - `_exec_claude()`'s
            # `except BaseException: ... raise` (kill-tree na Ctrl+C)
            # nechá `OSError`/`UnicodeDecodeError` (poškozené kódování
            # stdout) propadnout NEZABALENÉ - stejná třída rizika jako
            # `CodexLLMClient`'s kolo 7 IMPORTANT (minulý plán), stejná
            # oprava (širší `except`, stejná redakce).
            from src.agents import stylist
            raise ClaudeCliFatalError(stylist._redact_detail(str(e))) from e
        usage = payload.get("usage") or {}
        # Kolo 1 IMPORTANT (plan-consensus) - `truncated` čte SKUTEČNÝ
        # `stop_reason` (ověřeno spikem - `claude -p --output-format
        # json` ho vrací, stejný signál jako Anthropic API's `resp.
        # stop_reason`), ne natvrdo `False`. NA ROZDÍL od `CodexLLMClient`
        # (Codex CLI žádný ekvivalent nemá, `truncated=False` je tam
        # ZDOKUMENTOVANÝ limit) - `claude` CLI signál MÁ, takže se
        # POUŽÍVÁ. `max_tokens` parametr samotný STÁLE nemá CLI
        # ekvivalent (žádný limit flag) - `critic.review()`'s retry na
        # truncation detekci správně zachytí, ale limit nezvýší (stejný
        # přijatý limit jako Codex).
        return Completion(
            text=payload.get("result") or "",
            truncated=payload.get("stop_reason") == "max_tokens",
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
- Modify: `main.py`, `src/review_ui/polish_server.py`
- Test: `tests/test_cli.py`, `tests/test_polish_server.py`

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


def test_client_factory_critic_uses_preflight_resolved_claude_cmd(monkeypatch):
    """Kolo 3 IMPORTANT (plan-consensus) - `_claude_cli_preflight()`
    (Task 3) resolvne `claude` na ABSOLUTNÍ cestu A ověří přihlášení
    PRO TENHLE KONKRÉTNÍ binární soubor. Bez threadování téhle hodnoty
    do `_client_factory`/`ClaudeCliClient` by se PATH lookup provedl
    ZNOVU, líně, uvnitř `_exec_claude()` - TOCTOU mezera (PATH se mezi
    preflightem a prvním skutečným voláním teoreticky může změnit) a
    zbytečná duplicitní práce."""
    from src.llm.client import ClaudeCliClient
    factory = main._client_factory(1, interactive=False,
                                   claude_cmd=["/resolved/path/claude"])
    client = factory("critic")
    assert client._inner._claude_cmd == ["/resolved/path/claude"]


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

Nejdřív `_client_factory`'s SIGNATURU - najdi:

```python
def _client_factory(run_id: int, *, interactive: bool, require_lock=None,
                    translator_backend: str = "claude"):
```

nahraď:

```python
def _client_factory(run_id: int, *, interactive: bool, require_lock=None,
                    translator_backend: str = "claude", claude_cmd=None):
```

(Kolo 3 IMPORTANT, plan-consensus - `claude_cmd` volitelný parametr,
default `None` → `factory()` spadne na `["claude"]` a `ClaudeCliClient`
si binárku resolvne LÍNĚ sám - stejné chování jako dřív pro volající,
co eager preflight nedělají. Volající, co `_claude_cli_preflight()`
UŽ zavolali (`_cmd_run`/`_cmd_polish`/polish-server, viz níž), předají
JEHO resolvnutou hodnotu - žádná duplicitní práce, žádná TOCTOU mezera.)

**Kolo 5 IMPORTANT (plan-consensus) - existující fake/spy `_client_
factory` náhrady v testech NEMAJÍ `claude_cmd` parametr:** Nová
`claude_cmd=claude_cmd` keyword na volajících stranách (`_cmd_run`/
`_cmd_polish`/polish-server, viz níž) rozbije KAŽDÝ existující test, co
`main._client_factory`/`main._client_factory` monkeypatchuje na
VLASTNÍ fake/spy funkci BEZ tohohle parametru - `TypeError:
got an unexpected keyword argument 'claude_cmd'`. Najdi VŠECHNY (grep
`def _fake_client_factory\|def spy_factory` napříč `tests/`) a přidej
jim `claude_cmd=None` (nepoužitý, jen ať signatura sedí) NEBO (tam, kde
spy PŘEDÁVÁ argumenty dál do `real_factory`, viz `spy_factory` v
`tests/test_cli.py:1709,1728`) ho zachyť a přepošli:

- `tests/test_cli.py:1048` (`_fake_client_factory` v `test_cmd_polish_
  passes_require_lock_callback_to_client_factory`) - přidej
  `claude_cmd=None` do signatury.
- `tests/test_cli.py:1709,1728` (`spy_factory` ve dvou `test_run_
  translator_flag_*` testech) - přidej `claude_cmd=None` do signatury
  A do `real_factory(...)` předávaného volání (`real_factory(rid,
  interactive=interactive, require_lock=require_lock, translator_
  backend=translator_backend, claude_cmd=claude_cmd)`).
- `tests/test_polish_server.py:914` (`_fake_client_factory` v
  regenerate testu) - přidej `claude_cmd=None` do signatury.

Žádný z těchhle čtyř testů claude_cmd HODNOTU needeleguje/needeleguje
(jsou o JINÉM aspektu drátování) - stačí, aby signatura přijala
argument, ať volání nespadne. Přidán SAMOSTATNÝ nový test (`tests/
test_cli.py`, viz Step 1 výš), co claude_cmd threadování SKUTEČNĚ
ověřuje End-to-End přes `_cmd_run`.

Pak `_client_factory`'s `factory()`, najdi:

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
            # design.md). Kolo 3 IMPORTANT (plan-consensus) - `claude_cmd`
            # PŘEDANÝ volajícím (resolvnutý `_claude_cli_preflight()`
            # UŽ jednou, viz `_cmd_run`/`_cmd_polish`/polish-server níž) -
            # `or ["claude"]` fallback JEN pro volající bez eager
            # preflightu. `ClaudeCliClient.complete()` (Task 2) si i tak
            # binárku ZNOVU resolvne PŘI KAŽDÉM volání (`_exec_claude`'s
            # `_resolve_claude_cmd`) - vyhodí `ClaudeCliUnavailable` →
            # `ClaudeCliFatalError`, pokud přestala existovat MEZI
            # preflightem a skutečným voláním.
            inner = ClaudeCliClient(claude_cmd or ["claude"], config.MODEL_CRITIC)
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
se NAHRAZUJE - kolo 1 IMPORTANT, plan-consensus, viz Global Constraints
"NOVÁ eager `claude` CLI preflight kontrola"):

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

nahraď (kritik je teď VŽDY `claude` CLI, NEZÁVISLE na `args.translator` -
kontrola tedy jde MIMO `if args.translator == "codex":` blok, běží se
při KAŽDÉM `run`u):

```python
    claude_cmd, preflight_err = _claude_cli_preflight()
    if preflight_err:
        _say(f"Kritik vyžaduje funkční claude CLI: {preflight_err}")
        return 1
```

Přidej NOVOU `_claude_cli_preflight()` funkci do main.py (HNED PŘED
`_cmd_run`, vedle existující `_polish_preflight()`):

```python
def _claude_cli_preflight() -> tuple:
    """Kritik je VŽDY `claude` CLI (žádný fallback) - ověř DŘÍV, než
    `run` začne zpracovávat frontu, ať se u `--translator codex`
    nepřeloží (a nezaplatí) celá kapitola, než kritik zjistí chybějící/
    nepřihlášené CLI. Vrací `(claude_cmd, None)` při úspěchu,
    `(None, chybová_hláška)` při selhání - stejný tvar jako existující
    `_polish_preflight()`. `claude auth status --json` (~0.5s, žádné
    tokeny/API volání, ověřeno spikem 2026-09-21) je jediný levný
    způsob, jak ověřit PŘIHLÁŠENÍ (na rozdíl od `_polish_preflight()`'s
    Codex kontrol, co jsou čistě config/PATH - `claude` CLI dostupnost
    samotná NEZARUČUJE platnou OAuth session)."""
    from src.llm import claude_cli
    try:
        claude_cmd = claude_cli._resolve_claude_cmd(["claude"])
    except claude_cli.ClaudeCliUnavailable as e:
        return None, str(e)
    # Kolo 4 IMPORTANT (plan-consensus) - `auth status` samo neověří,
    # že nainstalovaná verze podporuje flagy, co `_exec_claude()`
    # SKUTEČNĚ používá (`--safe-mode`/`--tools`/`--system-prompt`/
    # `--output-format`) - starší/nekompatibilní CLI MŮŽE být přihlášené
    # (auth je nezávislá na verzi), ale selhat AŽ na PRVNÍM `.complete()`
    # volání (PO zaplaceném Codex překladu). `claude --help` (žádné
    # tokeny/API volání, stejně levné jako `auth status`) obsahuje
    # NÁZVY VŠECH podporovaných flagů - ověřeno spikem 2026-09-21 -
    # substring kontrola je jednoduchá a nevyžaduje hádat verzní čísla.
    _REQUIRED_FLAGS = ("--safe-mode", "--tools", "--system-prompt", "--output-format")
    try:
        help_result = subprocess.run(claude_cmd + ["--help"],
                                     capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, (f"Nepodařilo se ověřit verzi claude CLI "
                      f"({type(e).__name__}: {e}).")
    # Kolo 5 IMPORTANT (plan-consensus) - `returncode` se PŘED touhle
    # opravou nekontroloval - neúspěšné `--help` (nenulový exit kód) se
    # stdoutem, co náhodou/částečně obsahuje flagové názvy, by prošlo
    # jako "úspěch" (stejná třída chyby jako `auth status`'s vlastní
    # returncode kontrola níž).
    if help_result.returncode != 0:
        return None, (f"`claude --help` skončilo s kódem "
                      f"{help_result.returncode}: {help_result.stderr.strip()}")
    missing = [f for f in _REQUIRED_FLAGS if f not in help_result.stdout]
    if missing:
        return None, (f"claude CLI nepodporuje potřebné volby "
                      f"({', '.join(missing)}) - aktualizuj Claude Code "
                      "na novější verzi.")
    try:
        result = subprocess.run(claude_cmd + ["auth", "status", "--json"],
                                capture_output=True, text=True, timeout=10)
        # Kolo 2 IMPORTANT (plan-consensus) - `returncode` se PŘED touhle
        # opravou vůbec nekontroloval - nenulový exit kód (např. `claude`
        # binárka existuje, ale je rozbitá/nekompatibilní verze) by
        # nechal `json.loads` selhat na PRÁZDNÉM/nesmyslném stdoutu
        # matoucím způsobem, MÍSTO jasné "returncode != 0" hlášky.
        if result.returncode != 0:
            return None, (f"`claude auth status` skončilo s kódem "
                          f"{result.returncode}: {result.stderr.strip()}")
        status = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        return None, (f"Nepodařilo se ověřit přihlášení claude CLI "
                      f"({type(e).__name__}: {e}).")
    # Kolo 2 IMPORTANT (plan-consensus) - STEJNÁ třída chyby jako
    # `_exec_claude()`'s kolo-1 payload validace (viz Task 2) - validní
    # JSON může být `[]`/`null`/string na nejvyšší úrovni, ne jen objekt.
    # `status.get(...)` na non-dict by spadlo na neklasifikovaný
    # `AttributeError`, MIMO tenhle funkce zdokumentovaný `(None,
    # chyba)` kontrakt.
    if not isinstance(status, dict):
        return None, (f"`claude auth status` vrátilo neočekávaný JSON "
                      f"tvar ({type(status).__name__}, ne objekt).")
    # Kolo 5 IMPORTANT (plan-consensus) - `not status.get("loggedIn")`
    # by NEODMÍTLO `"loggedIn": "false"` (neprázdný STRING je v Pythonu
    # truthy!) - striktní `is not True` kontrola vyžaduje SKUTEČNÝ
    # bool `true` z JSON, ne cokoli truthy.
    if status.get("loggedIn") is not True:
        return None, "claude CLI není přihlášené - spusť `claude login`."
    return claude_cmd, None
```

Přidej `import subprocess` k existujícím importům na main.py (pokud
tam ještě není - `json` už tam je).

**Kolo 3 IMPORTANT (plan-consensus) - provlékni preflightem resolvnutý
`claude_cmd` do `_client_factory()`, nezahazuj ho:** V `_cmd_run`
(main.py), najdi:

```python
        cf = _client_factory(rid, interactive=True,
                             translator_backend=args.translator)
```

nahraď:

```python
        cf = _client_factory(rid, interactive=True,
                             translator_backend=args.translator,
                             claude_cmd=claude_cmd)
```

Existující testy, co ANTHROPIC_API_KEY blok mockovaly/ověřovaly
(`test_run_translator_codex_missing_anthropic_key_fails_eager` a
jakékoli `monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")`
řádky přidané JEN kvůli týhle kontrole) - najdi je (`grep -rn
"ANTHROPIC_API_KEY" tests/test_cli.py`) a smaž/uprav podle toho, co
zbylo z jejich PŮVODNÍHO účelu. `test_run_translator_codex_missing_
anthropic_key_fails_eager` testovalo PŘESNĚ tenhle zrušený blok - smaž
ho celý. VŠECHNY existující `_run(["run", ...])`/`_run(["run"])` testy
(`test_cli.py`, i ty BEZ `--translator codex`) teď navíc potřebují
mock `_claude_cli_preflight()` na úspěch (nová kontrola běží PRO
KAŽDÝ `run`, ne jen `--translator codex`) - přidej `monkeypatch.
setattr("main._claude_cli_preflight", lambda: (["claude"], None))`
všude, kde dřív chyběl `ANTHROPIC_API_KEY` mock nebo kde test dřív
spoléhal na to, že kritik se vůbec nezavolá (grep `_run\(\["run"` v
`tests/test_cli.py` a projdi VŠECHNY výskyty).

Přidej regresní test pro NOVOU preflight kontrolu:

```python
def test_run_claude_cli_preflight_failure_blocks_queue_before_translation(
        tmp_path, monkeypatch):
    """Kolo 1 IMPORTANT (plan-consensus) - bez eager kontroly by
    chybějící/nepřihlášené `claude` CLI nechalo proběhnout celý
    (u --translator codex zaplacený) překlad, než by run selhal na
    kritikovi - stejné riziko jako `ANTHROPIC_API_KEY` (minulý plán,
    zrušeno) i jako Codexova FS-risk eager kontrola."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight",
                        lambda: (None, "claude CLI není přihlášené."))
    import src.pipeline as P
    calls = {"n": 0}
    def boom(db_path, chapter, *, client_factory, guide):
        calls["n"] += 1
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", boom)
    assert _run(["run"], tmp_path, monkeypatch) == 1
    assert calls["n"] == 0   # zadny preklad se vubec nespustil


def test_run_threads_preflight_resolved_claude_cmd_into_client_factory(
        tmp_path, monkeypatch):
    """Kolo 5 IMPORTANT (plan-consensus) - end-to-end ověření, že
    `_cmd_run` SKUTEČNĚ předá `_claude_cli_preflight()`'s resolvnutou
    hodnotu do `_client_factory(..., claude_cmd=...)`, ne jen že
    `_client_factory` sama umí parametr přijmout (to ověřují Task 2/3's
    unit testy zvlášť)."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr("main._claude_cli_preflight",
                        lambda: (["/resolved/claude"], None))
    import src.pipeline as P
    monkeypatch.setattr(P, "process_chapter",
                        lambda db_path, chapter, *, client_factory, guide: {
                            "idx": chapter["idx"], "status": "done", "revision_rounds": 0})
    real_factory = main._client_factory
    captured = {}
    def spy_factory(rid, *, interactive, require_lock=None,
                    translator_backend="claude", claude_cmd=None):
        captured["claude_cmd"] = claude_cmd
        return real_factory(rid, interactive=interactive, require_lock=require_lock,
                            translator_backend=translator_backend, claude_cmd=claude_cmd)
    monkeypatch.setattr(main, "_client_factory", spy_factory)
    assert _run(["run"], tmp_path, monkeypatch) == 0
    assert captured["claude_cmd"] == ["/resolved/claude"]


def _fake_help_result():
    """Sdílená pomocná - `_claude_cli_preflight()` (kolo 4) volá
    `subprocess.run` DVAKRÁT (`--help` PAK `auth status --json`) - testy
    níž potřebují ÚSPĚŠNOU `--help` odpověď (obsahující VŠECHNY
    požadované flagy), aby se vůbec dostaly k testovanému DRUHÉMU
    volání."""
    class FakeHelpResult:
        returncode = 0
        stdout = "--safe-mode --tools --system-prompt --output-format"
        stderr = ""
    return FakeHelpResult()


def test_claude_cli_preflight_missing_flags_returns_error(monkeypatch):
    """Kolo 4 IMPORTANT (plan-consensus) - `auth status` samo neověří,
    že CLI podporuje flagy, co `_exec_claude()` skutečně používá -
    starší/nekompatibilní verze MŮŽE být přihlášená, ale selže AŽ na
    prvním `.complete()` volání, PO zaplaceném Codex překladu."""
    import subprocess
    class FakeHelpResultMissingFlags:
        returncode = 0
        stdout = "-p --model"   # chybí --safe-mode/--tools/--system-prompt/--output-format
        stderr = ""
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeHelpResultMissingFlags())
    claude_cmd, err = main._claude_cli_preflight()
    assert claude_cmd is None
    assert "--safe-mode" in err


def test_claude_cli_preflight_help_nonzero_exit_returns_error(monkeypatch):
    """Kolo 5 IMPORTANT (plan-consensus) - `--help`'s VLASTNÍ returncode
    se musí kontrolovat stejně jako `auth status`'s - neúspěšné `--help`
    s náhodou/částečně obsaženými flagovými názvy ve stdoutu by jinak
    prošlo jako "úspěch"."""
    import subprocess
    class FakeHelpResultFailed:
        returncode = 1
        stdout = "--safe-mode --tools --system-prompt --output-format"
        stderr = "segfault"
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeHelpResultFailed())
    claude_cmd, err = main._claude_cli_preflight()
    assert claude_cmd is None
    assert "1" in err or "segfault" in err


def test_claude_cli_preflight_logged_in_truthy_string_is_rejected(monkeypatch):
    """Kolo 5 IMPORTANT (plan-consensus) - `"loggedIn": "false"` (STRING,
    ne bool) je v Pythonu TRUTHY - `not status.get("loggedIn")` by ho
    chybně přijalo jako přihlášené. Striktní `is not True` to odmítne."""
    import subprocess
    class FakeResult:
        returncode = 0
        stdout = '{"loggedIn": "false"}'
        stderr = ""
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        return _fake_help_result() if calls["n"] == 1 else FakeResult()
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", fake_run)
    claude_cmd, err = main._claude_cli_preflight()
    assert claude_cmd is None
    assert "přihlášené" in err


def test_claude_cli_preflight_nonzero_exit_returns_error(monkeypatch):
    """Kolo 2 IMPORTANT (plan-consensus) - `claude auth status` může
    selhat (rozbitá instalace, nekompatibilní verze) s nenulovým exit
    kódem, aniž by stdout obsahoval JSON vůbec."""
    import subprocess
    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "unknown command"
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        return _fake_help_result() if calls["n"] == 1 else FakeResult()
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", fake_run)
    claude_cmd, err = main._claude_cli_preflight()
    assert claude_cmd is None
    assert "1" in err or "unknown command" in err


def test_claude_cli_preflight_non_dict_json_returns_error(monkeypatch):
    """Kolo 2 IMPORTANT (plan-consensus) - validní JSON, ale ne objekt
    (`[]`) - `status.get("loggedIn")` by jinak spadlo na `AttributeError`
    MIMO tenhle funkce zdokumentovaný `(None, chyba)` kontrakt."""
    import subprocess
    class FakeResult:
        returncode = 0
        stdout = "[]"
        stderr = ""
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        return _fake_help_result() if calls["n"] == 1 else FakeResult()
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", fake_run)
    claude_cmd, err = main._claude_cli_preflight()
    assert claude_cmd is None
    assert err is not None


def test_claude_cli_preflight_malformed_json_returns_error(monkeypatch):
    import subprocess
    class FakeResult:
        returncode = 0
        stdout = "not json"
        stderr = ""
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        return _fake_help_result() if calls["n"] == 1 else FakeResult()
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", fake_run)
    claude_cmd, err = main._claude_cli_preflight()
    assert claude_cmd is None
    assert err is not None


def test_claude_cli_preflight_not_logged_in_returns_error(monkeypatch):
    import subprocess
    class FakeResult:
        returncode = 0
        stdout = '{"loggedIn": false}'
        stderr = ""
    calls = {"n": 0}
    def fake_run(*a, **k):
        calls["n"] += 1
        return _fake_help_result() if calls["n"] == 1 else FakeResult()
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", fake_run)
    claude_cmd, err = main._claude_cli_preflight()
    assert claude_cmd is None
    assert "přihlášené" in err
```

**Kolo 2 IMPORTANT (plan-consensus) - `_claude_cli_preflight()` patří
i do `polish`/polish-server, NE JEN `run`:** `_run_critic()` (a tedy
`agent=="critic"` → `ClaudeCliClient`) se volá i z `_polish_one_
chapter` (`_cmd_polish`'s dávka - "kolo 15 NIT" v `critic.review()`'s
docstring to výslovně zmiňuje) A z `polish_server.py`'s regenerate
endpointu (`main._client_factory(rid, ...)` volání tam, řádek ~379) -
OBOJÍ nejdřív provede DRAHÉ Codex stylizační volání, PAK teprve
kritika. Bez eager kontroly na těchhle DVOU dalších místech by
chybějící/nepřihlášené `claude` CLI nechalo proběhnout celou (draze
zaplacenou) stylizaci, než by selhalo na kritikovi - STEJNÉ riziko,
co `_cmd_run`'s kontrola řeší, jen jinde.

**Oprava:** Stejná `_claude_cli_preflight()` volaná i v `_cmd_polish`
(main.py) a `polish_server.py`'s regenerate handleru, HNED ZA jejich
existující `_polish_preflight()` kontrolou.

V `main.py`, `_cmd_polish`, najdi:

```python
def _cmd_polish(args) -> int:
    db = config.DB_PATH
    model, codex_cmd, preflight_err = _polish_preflight()
    if preflight_err:
        _say(preflight_err)
        return 1
```

nahraď:

```python
def _cmd_polish(args) -> int:
    db = config.DB_PATH
    model, codex_cmd, preflight_err = _polish_preflight()
    if preflight_err:
        _say(preflight_err)
        return 1
    # Kolo 2 IMPORTANT (plan-consensus) - stejný důvod jako `_cmd_run`'s
    # kontrola (viz Global Constraints/Task 3 výš) - `_polish_one_
    # chapter` volá kritika PO drahé Codex stylizaci, ne před ní.
    claude_cmd, claude_preflight_err = _claude_cli_preflight()
    if claude_preflight_err:
        _say(f"Kritik vyžaduje funkční claude CLI: {claude_preflight_err}")
        return 1
    # Kolo 3 BLOCKING (plan-consensus) - `_polish_one_chapter()` volá
    # NAVÍC `cf("stylist_check")` (`stylist.check_meaning_preserved()`,
    # main.py:698) - TENHLE agent zůstává MIMO rozsah tohohle plánu
    # (jen kritik přechází na `claude` CLI, viz spec "Rozsah") - pořád
    # `AnthropicClient`/`ANTHROPIC_API_KEY`. Bez týhle kontroly by
    # chybějící klíč nechal proběhnout DRAHOU Codex stylizaci CELÉ
    # dávky, než by selhalo na PRVNÍM `stylist_check` volání - STEJNÉ
    # riziko jako `claude` CLI výš, jen pro JINOU, MIMO-ROZSAH závislost.
    if not config.ANTHROPIC_API_KEY:
        _say("polish vyžaduje funkční Claude API pro stylist_check: "
            "Chybí ANTHROPIC_API_KEY v prostředí.")
        return 1
```

V `_cmd_polish`, najdi:

```python
        cf = _client_factory(rid, interactive=True,
                             require_lock=lambda: _lock_still_owned(config.LOCK_PATH))
```

nahraď:

```python
        cf = _client_factory(rid, interactive=True,
                             require_lock=lambda: _lock_still_owned(config.LOCK_PATH),
                             claude_cmd=claude_cmd)
```

V `src/review_ui/polish_server.py`, regenerate handler, najdi:

```python
        model, codex_cmd, preflight_err = main._polish_preflight()
        if preflight_err:
            return JSONResponse({"error": preflight_err}, status_code=503)
```

nahraď:

```python
        model, codex_cmd, preflight_err = main._polish_preflight()
        if preflight_err:
            return JSONResponse({"error": preflight_err}, status_code=503)
        # Kolo 2 IMPORTANT (plan-consensus) - stejný důvod jako `_cmd_
        # run`/`_cmd_polish` (main.py) - regenerate taky volá kritika
        # PO drahé Codex stylizaci.
        claude_cmd, claude_preflight_err = main._claude_cli_preflight()
        if claude_preflight_err:
            return JSONResponse({"error": claude_preflight_err}, status_code=503)
        # Kolo 3 BLOCKING (plan-consensus) - `stylist_check` (main.py's
        # `_polish_one_chapter`) zůstává MIMO rozsah (pořád `Anthropic
        # Client`/`ANTHROPIC_API_KEY`) - stejný důvod jako `_cmd_polish`
        # (main.py) výš.
        if not main.config.ANTHROPIC_API_KEY:
            return JSONResponse(
                {"error": "polish vyžaduje funkční Claude API pro "
                          "stylist_check: Chybí ANTHROPIC_API_KEY "
                          "v prostředí."}, status_code=503)
```

V `src/review_ui/polish_server.py`, regenerate handler, najdi:

```python
            cf = main._client_factory(rid, interactive=False,
                                      require_lock=app.state.require_lock)
```

nahraď:

```python
            cf = main._client_factory(rid, interactive=False,
                                      require_lock=app.state.require_lock,
                                      claude_cmd=claude_cmd)
```

Přidej regresní testy (`tests/test_cli.py` pro `_cmd_polish`,
`tests/test_polish_server.py` pro regenerate) analogické `test_run_
claude_cli_preflight_failure_blocks_queue_before_translation` výš -
mockni `_claude_cli_preflight` na selhání, ověř že se `stylist.polish`/
Codex volání VŮBEC nespustí. Přidej i test pro chybějící
`ANTHROPIC_API_KEY` (`stylist_check`, kolo 3 BLOCKING) na OBOU místech -
ověř, že se `stylist.polish` (Codex) VŮBEC nespustí, i když `claude`
CLI preflight uspěje.

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py tests/test_polish_server.py -v`
Expected: PASS (zkontroluj especially, že KAŽDÝ existující `_run(["run"...`
test má `_claude_cli_preflight` mockovanou na úspěch, jinak selže na
NOVÉ eager kontrole, ne na tom, co skutečně testuje - STEJNĚ pro
existující `_cmd_polish`/polish-server testy)

- [ ] **Step 5: Commit**

```bash
git add main.py src/review_ui/polish_server.py tests/test_cli.py tests/test_polish_server.py
git commit -m "feat: kritik natvrdo pres claude CLI, zrusena ANTHROPIC_API_KEY eager kontrola

_client_factory's agent==critic vetev staví ClaudeCliClient MISTO
AnthropicClient, nezavisle na translator_backend - pouziva preflightem
resolvnuty claude_cmd (novy volitelny _client_factory parametr), ne
duplicitni lazy resolve. _cmd_run's eager ANTHROPIC_API_KEY kontrola
(zavedena minulym planem pro kritika) se rusi, nahrazena novou
_claude_cli_preflight() (resolvne binarku + overi claude auth status
--json) - volana v _cmd_run, _cmd_polish I polish_server.py's
regenerate handleru. _cmd_polish/regenerate dostaly i eager kontrolu
ANTHROPIC_API_KEY pro stylist_check (treti agent typ, MIMO rozsah
tohohle planu, stale Anthropic API) - jinak by draha Codex stylizace
probehla zbytecne pred zjistenim chybejiciho klice.

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

**Kolo 3 BLOCKING (plan-consensus) - `polish` NENÍ součástí týhle
záruky:** `python main.py polish` (a polish-server regenerate) VOLÁ
`stylist_check` (`main.py:698`), co zůstává MIMO rozsah tohohle plánu -
STÁLE vyžaduje `ANTHROPIC_API_KEY`. Ověř SAMOSTATNĚ (s `ANTHROPIC_
API_KEY` NASTAVENÝM): `python main.py polish --only <idx>` na kapitole,
co `run` výš dokončil - kritik uvnitř (pokud `_polish_one_chapter`
kritika volá) běží přes `claude` CLI (`llm_calls` `agent='critic'`
řádek `provider='claude-cli'`), `stylist_check` běží přes
`AnthropicClient` (`agent='stylist_check'` řádek `provider='anthropic'`,
NENULOVÁ cena) - OBOJÍ ve STEJNÉM `polish` běhu, různé backends, přesně
podle plánu.

- [ ] **Step 3: Invoke `superpowers:finishing-a-development-branch`**

Ověř testy, prezentuj možnosti (merge/PR/nechat), proveď podle volby
uživatele.
