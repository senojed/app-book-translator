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
    dohromady funguje správně).

    Kolo 9 IMPORTANT (plan-consensus) - `--no-session-persistence`
    DOPLNĚN: bez něj `claude` CLI persistuje CELÝ prompt (kapitola
    EN+CZ) do lokální historie relací - ověřeno přímo
    (`claude --help` má `--no-session-persistence - Disable session
    persistence`), `--safe-mode` tohle NEŘEŠÍ (jen vypíná CLAUDE.md/
    pluginy/hooky, ne perzistenci relace)."""
    cmd = _resolve_claude_cmd(claude_cmd) + [
        "-p", "--safe-mode", "--no-session-persistence", "--tools", "",
        "--output-format", "json", "--model", model,
        "--system-prompt", system,
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
    # Kolo 10 IMPORTANT (plan-consensus) - `usage` NENÍ volitelné pro
    # ÚSPĚŠNÝ výstup (spec i spike 2026-09-21 potvrzují, že
    # `--output-format json` vrací `usage` VŽDY) - dřívější "if usage is
    # not None" nechávalo CHYBĚJÍCÍ `usage`/pole TICHE projít, a
    # `ClaudeCliClient.complete()`'s `usage.get(...) or 1` pak
    # PŘEPISOVALA i SKUTEČNOU nulu (validní `input_tokens: 0`) na `1` -
    # zaznamenaný audit cost by neodpovídal realitě. Teď je `usage`
    # dict s oběma poli POVINNÝ požadavek stejné síly jako `result`.
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise ClaudeCliExecError(
            f"claude -p's 'usage' pole musí být objekt, ne "
            f"{type(usage).__name__ if usage is not None else 'None'} "
            "(chybí nebo má špatný typ).")
    for field in ("input_tokens", "output_tokens"):
        value = usage.get(field)
        # Kolo 2 IMPORTANT (plan-consensus) - `isinstance(usage, dict)`
        # samo nestačí - `input_tokens`/`output_tokens` mohou být
        # string/bool/float/záporné číslo. `PipelineLLMClient.complete()`
        # s nimi počítá aritmeticky VE `finally` bloku (`it / 1e6 *
        # in_rate`) - string tam spadne na `TypeError` UVNITŘ finally
        # (maskuje původní výjimku), `bool` projde tiše (Python `bool`
        # je `int` podtřída, ale sémanticky nesmyslné), záporné číslo
        # by zapsalo nesmyslný audit řádek (záporná cena/tokeny).
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ClaudeCliExecError(
                f"claude -p's usage.{field} musí být nezáporné celé "
                f"číslo, ne {value!r}.")
    return payload
