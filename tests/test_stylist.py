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
    for variant in ("12 %", "12 %", "12 %"):
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
