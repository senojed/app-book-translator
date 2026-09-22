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
    assert "--no-session-persistence" in seen["cmd"]  # kolo 9 IMPORTANT
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


def test_exec_claude_raises_on_missing_usage(monkeypatch):
    """Kolo 10 IMPORTANT (plan-consensus) - `usage` NENÍ volitelné na
    ÚSPĚŠNÉ cestě (spec/spike potvrzují, že `--output-format json` ho
    vrací VŽDY) - CHYBĚJÍCÍ `usage` u JINAK úspěšného payloadu musí
    selhat hlasitě, ne tiše dopadnout na `ClaudeCliClient.complete()`'s
    dřívější `or 1` fallback."""
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ('{"result": "ok", "is_error": false, "subtype": "success"}', "")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: FakeProc())
    with pytest.raises(claude_cli.ClaudeCliExecError):
        claude_cli._exec_claude("s", "u", claude_cmd=["claude"], model="m", timeout=30)


def test_exec_claude_raises_on_usage_missing_one_field(monkeypatch):
    """Kolo 10 IMPORTANT (plan-consensus) - `usage` dict PŘÍTOMNÝ, ale
    chybí JEN `output_tokens` - musí selhat stejně jako úplně chybějící
    `usage` (ne tiše dopadnout na `or 1`)."""
    class FakeProc:
        pid = 1
        returncode = 0
        def communicate(self, input, timeout):
            return ('{"result": "ok", "is_error": false, "subtype": "success", '
                    '"usage": {"input_tokens": 7}}', "")
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
