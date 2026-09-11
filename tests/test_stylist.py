import json, os, sys
import pytest
import config
from src.agents import stylist
from src.llm.client import Completion, FakeLLMClient


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


# --- Task 5: stylist.polish() ------------------------------------------------

def test_polish_refuses_without_fs_risk_optin(tmp_path, monkeypatch):
    """Kolo 20 BLOCKING - PŘÍMÉ volání `polish()` (ne přes `_cmd_polish`)
    s vypnutým opt-inem MUSÍ vyhodit `StylistError`, ne spustit Codex."""
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    with pytest.raises(stylist.StylistError, match="vypnutý"):
        stylist.polish("EN", "CZ", codex_cmd=["nonexistent-binary"])
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", 1)   # truthy != True
    with pytest.raises(stylist.StylistError, match="vypnutý"):
        stylist.polish("EN", "CZ", codex_cmd=["nonexistent-binary"])


def test_polish_config_invariants(tmp_path, monkeypatch):
    """Kolo 22 IMPORTANT - `polish()` sama vynutí neprázdný codex_cmd a
    neprázdný model."""
    with pytest.raises(stylist.StylistError, match="prázdný nebo neúplný"):
        stylist.polish("EN", "CZ", codex_cmd=[])
    monkeypatch.setattr(config, "CODEX_MODEL", "")
    with pytest.raises(stylist.StylistError, match="chybí model"):
        stylist.polish("EN", "CZ", codex_cmd=["x"], codex_model="")


def _fake_codex(tmp_path, body, *, exit_code=0):
    """Fake skript simulující 'codex exec ... -o out_path ...' - najde `-o`
    v argv (přesně jak to `stylist.polish` volá) a zapíše `body` tam. Žádné
    parsování promptu - `-o` je teď skutečný CLI flag (capture poslední
    zprávy), ne cesta zmíněná uvnitř textu."""
    fake = tmp_path / "fake_codex.py"
    fake.write_text(
        "import sys\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        f"open(out, 'w', encoding='utf-8').write({body!r})\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8")
    return [sys.executable, str(fake)]


def test_polish_roundtrips_utf8_diacritics(tmp_path):
    """Kolo 5 BLOCKING: bez explicitního `encoding='utf-8'` použije
    `Popen(text=True)` na Windows lokální kódování (typicky cp1252), které
    diakritiku nezakóduje - `UnicodeEncodeError` ještě PŘED spuštěním
    Codexu. Fake skript přečte stdin, VYTÁHNE si jen český text (mezi
    značkami promptu - stejná délka/struktura jako originál, ať neselže na
    strukturální kontrole) a s drobnou úpravou ho napíše do `-o` - test tak
    ověří CELOU cestu tam (stdin) i zpět (-o), ne jen jednu stranu."""
    fake = tmp_path / "echo_codex.py"
    fake.write_text(
        "import sys, re\n"
        "out = sys.argv[sys.argv.index('-o') + 1]\n"
        "received = sys.stdin.buffer.read().decode('utf-8').replace('\\r\\n', '\\n')\n"
        "m = re.search(r'--- ČESKÝ PŘEKLAD K UPRAVENÍ ---\\n(.*?)\\n\\nOdpověz',\n"
        "             received, re.DOTALL)\n"
        "cz = m.group(1)\n"
        "open(out, 'w', encoding='utf-8').write(cz.replace('Řekl', 'Pravil'))\n",
        encoding="utf-8")
    cmd = [sys.executable, str(fake)]
    cz = "CZ: Řekl že středověká věž měří dvě stě čtyřicet stop — nikdo mu nevěřil."
    result = stylist.polish("EN text s pomlčkou — a uvozovkami „jako“ tady.",
                            cz, codex_cmd=cmd)
    assert "Pravil" in result
    assert "středověká věž" in result   # diakritika přežila stdin i zpět


def test_polish_raises_on_nonzero_exit(tmp_path):
    cmd = _fake_codex(tmp_path, "cokoli", exit_code=1)
    with pytest.raises(stylist.StylistError):
        stylist.polish("EN", "CZ", codex_cmd=cmd)


def test_polish_raises_on_missing_output_file(tmp_path):
    fake = tmp_path / "noop.py"
    fake.write_text("pass")   # nezapíše žádný výstupní soubor (-o nevznikne)
    with pytest.raises(stylist.StylistError, match="nevytvořil"):
        stylist.polish("EN", "CZ", codex_cmd=[sys.executable, str(fake)])


def test_polish_raises_on_timeout(tmp_path):
    fake = tmp_path / "slow.py"
    fake.write_text("import time; time.sleep(5)")
    with pytest.raises(stylist.StylistError, match="timeout"):
        stylist.polish("EN", "CZ", codex_cmd=[sys.executable, str(fake)], timeout=1)


def test_polish_raises_on_missing_command():
    with pytest.raises(stylist.StylistError, match="nenalezen"):
        stylist.polish("EN", "CZ", codex_cmd=["prikaz-co-neexistuje-xyz"])


def test_polish_raises_stylist_error_on_permission_error(tmp_path, monkeypatch):
    """Kolo 8 IMPORTANT: `PermissionError` (podtřída `OSError`, ne
    `FileNotFoundError`) - soubor existuje, ale není spustitelný. Musí
    dát `StylistError`, ne neošetřenou výjimku mimo modul."""
    def _boom(*a, **kw):
        raise PermissionError("Access is denied")
    monkeypatch.setattr(stylist.subprocess, "Popen", _boom)
    with pytest.raises(stylist.StylistError, match="nepodařilo spustit"):
        stylist.polish("EN", "CZ", codex_cmd=[sys.executable])


def test_polish_raises_on_paragraph_count_mismatch(tmp_path):
    """Levná strukturální kontrola - jeden odstavec místo dvou = podezřele
    zkrácený výstup, i kdyby exit kód byl 0 a soubor neprázdný."""
    cmd = _fake_codex(tmp_path, "Jen jeden odstavec, podobně dlouhý jako vstup celkem.")
    with pytest.raises(stylist.StylistError, match="odstavců"):
        stylist.polish("EN", "Prvni odstavec.\n\nDruhy odstavec.", codex_cmd=cmd)


def test_polish_raises_on_wildly_different_length(tmp_path):
    cmd = _fake_codex(tmp_path, "X")   # jeden znak místo dlouhého textu, ale STEJNÝ počet odstavců (1)
    with pytest.raises(stylist.StylistError, match="délka"):
        stylist.polish("EN", "Dost dlouhý český text pro porovnání délky výstupu.", codex_cmd=cmd)


def test_polish_raises_on_chapter_too_long(tmp_path, monkeypatch):
    """Kolo 17 IMPORTANT - kapitola nad `config.STYLIST_MAX_CHARS` selže
    OKAMŽITĚ s jasnou zprávou, NE až po vyčerpání `timeout` (fake Codex se
    tu vůbec nezavolá - test to ověří tím, že `codex_cmd` míří na
    neexistující cestu, a přesto test neselže na `FileNotFoundError`,
    protože `_resolve_codex_cmd` se vůbec nedostane ke slovu)."""
    monkeypatch.setattr(config, "STYLIST_MAX_CHARS", 100)
    long_cz = "Odstavec. " * 20   # přes 100 znaků
    with pytest.raises(stylist.StylistError, match="moc dlouhá"):
        stylist.polish("EN", long_cz, codex_cmd=["nonexistent-codex-binary"])


def test_polish_allows_chapter_at_size_limit(tmp_path, monkeypatch):
    """Hraniční případ - PŘESNĚ na limitu (ne nad ním) projde dál k
    samotnému volání Codexu, guard neodmítne rovnost (`>`, ne `>=`)."""
    cz = "X" * 50
    monkeypatch.setattr(config, "STYLIST_MAX_CHARS", len("EN") + len(cz))
    cmd = _fake_codex(tmp_path, cz)
    result = stylist.polish("EN", cz, codex_cmd=cmd)
    assert result == cz


def test_polish_raises_on_changed_number(tmp_path):
    """Kolo 6 IMPORTANT: přehozená číslice ("12"→"21") zůstává čitelná pro
    LLM kontroly, ale je to faktická změna - deterministická kontrola
    čísel to musí chytit sama, bez spoléhání na kritika."""
    cz = "Bylo jich 12 a čekali od rána."
    cmd = _fake_codex(tmp_path, "Bylo jich 21 a čekali od rána.")
    with pytest.raises(stylist.StylistError, match="čísla"):
        stylist.polish("EN", cz, codex_cmd=cmd)


def test_polish_raises_on_swapped_numbers_same_set(tmp_path):
    """Kolo 13 BLOCKING: DVĚ RŮZNÁ čísla prohozená mezi dvěma místy v
    textu dají STEJNOU seřazenou množinu ({"3","5"} oběma směry) - dřívější
    `_number_multiset` (řadila výstup) by tohle NEZACHYTILA. `_number_
    sequence` (bez řazení, v pořadí výskytu) rozdíl vidí."""
    cz = "Anna měla 3 jablka, Petr 5 hrušek."
    cmd = _fake_codex(tmp_path, "Anna měla 5 jablek, Petr 3 hrušek.")
    with pytest.raises(stylist.StylistError, match="čísla"):
        stylist.polish("EN", cz, codex_cmd=cmd)


def test_polish_raises_on_decimal_separator_change(tmp_path):
    """Kolo 14 IMPORTANT - INVERTUJE dřívější kolo-13 test, co tvrdil OPAK:
    dřív se tečka/čárka normalizovaly jako stejný token, aby stylistova
    oprava anglicismu ("3.5" → "3,5") neprošla jako falešný poplach. "Python
    3.5" (verzové číslo) → "Python 3,5" by normalizace tiše PŘIJALA jako
    "jen formátování", i když jde o poškození technického identifikátoru -
    regex nemá jak rozlišit desetinné číslo od identifikátoru, co jako
    desetinné číslo vypadá."""
    cz = "Věž měřila 3.5 metru."
    cmd = _fake_codex(tmp_path, "Věž měřila 3,5 metru.")
    with pytest.raises(stylist.StylistError, match="čísla"):
        stylist.polish("EN", cz, codex_cmd=cmd)


def test_polish_raises_on_markdown_fence_wrapper(tmp_path):
    """Model navzdory promptu obalí odpověď do ``` bloku - deterministická
    kontrola to musí odmítnout, ne spoléhat na to, že se poslechne pokyn."""
    cmd = _fake_codex(tmp_path, "```\nPrvni odstavec.\n\nDruhy odstavec.\n```")
    with pytest.raises(stylist.StylistError, match="markdown"):
        stylist.polish("EN", "Prvni odstavec.\n\nDruhy odstavec.", codex_cmd=cmd)


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


# --- Task 6: stylist.check_meaning_preserved() -------------------------------

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
