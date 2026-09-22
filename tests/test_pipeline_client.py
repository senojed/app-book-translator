import pytest
from src import state
from src.llm.client import Completion, FakeLLMClient, PipelineLLMClient, FatalRunError
import config


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p); return p


def test_logs_call_on_success(tmp_path):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    inner = FakeLLMClient([Completion("ok", False, 100, 50)])
    c = PipelineLLMClient(inner, run_id=rid, agent="translator",
                          db_path=db, config_mod=config)
    c.complete(system="s", user="u", max_tokens=1000, model="claude-sonnet-5")
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM llm_calls"))
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["agent"] == "translator"
    assert rows[0]["cost_usd"] > 0


def test_logs_call_on_exception(tmp_path):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    def boom(**kw): raise RuntimeError("net down")
    c = PipelineLLMClient(FakeLLMClient(boom), run_id=rid, agent="critic",
                          db_path=db, config_mod=config)
    with pytest.raises(RuntimeError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    with state.connect(db) as conn:
        row = conn.execute("SELECT * FROM llm_calls").fetchone()
    assert row["status"] == "error"
    assert row["error_class"] == "RuntimeError"


def test_cost_guard_pauses_and_confirm_raises_on_empty(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)  # okamžitě přes strop
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, confirm=lambda prompt: "")
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=1000, model="claude-sonnet-5")


def test_cost_guard_new_ceiling_persists_and_stops_asking(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    calls = {"n": 0}
    def confirm(prompt):
        calls["n"] += 1
        return "999"
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1),
                                        Completion("y", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, confirm=confirm)
    c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    assert calls["n"] == 1  # zeptá se jen jednou
    assert state.get_run_spend_ceiling(db, rid) == 999.0


def test_cost_guard_non_interactive_hard_stops(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "scan")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db,
                          config_mod=config, interactive=False)
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")


def test_unknown_model_price_raises_fatal(tmp_path):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="translator", db_path=db, config_mod=config)
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="gpt-neexistuje")


def test_cost_guard_invalid_ceiling_input_raises_fatal(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db, config_mod=config,
                          confirm=lambda _: "abc")
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")


def test_cost_guard_rejects_ceiling_below_need(tmp_path, monkeypatch):
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)
    c = PipelineLLMClient(FakeLLMClient([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="scout", db_path=db, config_mod=config,
                          confirm=lambda _: "0.0001")   # pod spent+est
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=100000, model="claude-sonnet-5")


def test_count_tokens_failure_uses_conservative_estimate(tmp_path, monkeypatch):
    db = _db(tmp_path); rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "MAX_SPEND_USD", 100.0)   # dost velký strop
    class FlakyInner(FakeLLMClient):
        def count_tokens(self, **kw): raise RuntimeError("count_tokens down")
    c = PipelineLLMClient(FlakyInner([Completion("x", False, 1, 1)]),
                          run_id=rid, agent="translator", db_path=db, config_mod=config)
    # nespadne, ale odhad použije (len(s)+len(u))//2, ne //4
    big = "x" * 2_000_000
    monkeypatch.setattr(config, "MAX_SPEND_USD", 1.0)
    with pytest.raises(FatalRunError):   # //2 odhad překročí strop, //4 by možná neprošlo
        c.complete(system=big, user="u", max_tokens=1, model="claude-sonnet-5")


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
    """Kolo 12 BLOCKING - zámek ztracen AŽ BĚHEM `_inner.complete()`.
    `complete()` má DVĚ kontroly PŘED skutečným voláním (kolo 16 - PŘED
    `_guard()`, kolo 11 - PO ní/před voláním) - obě musí projít (`True`),
    ať se vůbec dostaneme k `_inner.complete()`; TŘETÍ kontrola (ve
    `finally`, kolo 12) vrátí `False` - zámek zmizel PRÁVĚ během síťového
    volání. Výsledek se i tak VRÁTÍ (peníze už utracené, výsledek
    nezahazuj) - jen SE NEZAPÍŠE auditní řádek, a NEVYHODÍ se výjimka
    (na rozdíl od kontrol PŘED voláním, kde ještě nic neproběhlo)."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    calls = {"n": 0}
    def _require_lock():
        calls["n"] += 1
        return calls["n"] <= 2   # obě kontroly PŘED voláním True, finally False
    c = PipelineLLMClient(FakeLLMClient([Completion("ok", False, 100, 50)]),
                          run_id=rid, agent="critic", db_path=db,
                          config_mod=config, require_lock=_require_lock)
    comp = c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    assert comp.text == "ok"   # výsledek se VRÁTIL, žádná výjimka
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM llm_calls"))
    assert rows == []   # ale auditní řádek se NEZAPSAL


def test_codex_llm_client_calls_exec_codex_and_wraps_result(monkeypatch):
    from src.llm.client import CodexLLMClient
    seen = {}
    def fake_exec(prompt, *, codex_cmd, codex_model, timeout, label):
        seen.update(prompt=prompt, codex_cmd=codex_cmd, codex_model=codex_model,
                    timeout=timeout, label=label)
        return "===PREKLAD===\ntext\n===METADATA===\n{}"
    monkeypatch.setattr("src.agents.stylist._exec_codex", fake_exec)
    c = CodexLLMClient(["codex"], "gpt-5.6-terra", timeout=42)
    # Kolo 7 IMPORTANT (plan-consensus) - `model=` ÚMYSLNĚ JINÝ než
    # `codex_model` ("claude-sonnet-5", přesně to, co translator.py
    # reálně posílá vždy - žádný explicitní model= argument z
    # pipeline.py). Test se STEJNÝM modelem na obou místech by nezachytil
    # regresi, kdy implementace omylem použije caller-supplied `model`
    # místo `self._codex_model` pro `_exec_codex()`'s `codex_model=`.
    comp = c.complete(system="SYS", user="USR", max_tokens=1000, model="claude-sonnet-5")
    assert comp.text == "===PREKLAD===\ntext\n===METADATA===\n{}"
    assert comp.truncated is False
    # Kolo 5 IMPORTANT (plan-consensus) - NENULOVÝ odhad (konzervativní,
    # stejný vzor jako count_tokens()), ne natvrdo 0 - jinak _print_usage()
    # ukáže "0 tokenů" i po zpracování celé knihy, přestože cena je
    # správně $0 (billed_model price entry, ne nulový objem).
    # Kolo 6 BLOCKING (plan-consensus) - vzorec MUSÍ sedět s implementací
    # (`len(system)+len(user)`, BEZ `"\n\n"` oddělovače mezi nimi - ten
    # je jen v samotném promptu pro Codex, ne v tomhle odhadu) - `len
    # ("SYS")+len("USR")=6`, NE `len("SYS\n\nUSR")=8`.
    assert comp.input_tokens == (len("SYS") + len("USR")) // 2
    assert comp.output_tokens == len("===PREKLAD===\ntext\n===METADATA===\n{}") // 2
    assert seen["prompt"] == "SYS\n\nUSR"
    assert seen["codex_cmd"] == ["codex"]
    assert seen["codex_model"] == "gpt-5.6-terra"
    assert seen["timeout"] == 42


def test_codex_llm_client_default_timeout_from_config(monkeypatch):
    from src.llm.client import CodexLLMClient
    import config
    monkeypatch.setattr(config, "CODEX_TRANSLATE_TIMEOUT_SECONDS", 111)
    seen = {}
    def fake_exec(prompt, *, codex_cmd, codex_model, timeout, label):
        seen["timeout"] = timeout
        return "ok"
    monkeypatch.setattr("src.agents.stylist._exec_codex", fake_exec)
    c = CodexLLMClient(["codex"], "m")   # timeout NEZADÁN
    c.complete(system="s", user="u", max_tokens=10, model="m")
    assert seen["timeout"] == 111


def test_codex_llm_client_count_tokens_is_conservative_estimate():
    from src.llm.client import CodexLLMClient
    c = CodexLLMClient(["codex"], "m")
    assert c.count_tokens(system="abcd", user="efgh", model="m") == 4   # (4+4)//2


def test_codex_llm_client_billed_model_is_codex_model_not_caller_model():
    from src.llm.client import CodexLLMClient
    c = CodexLLMClient(["codex"], "gpt-5.6-terra")
    assert c.billed_model == "gpt-5.6-terra"


def test_codex_llm_client_wraps_stylist_error_as_fatal_run_error(monkeypatch):
    """Kolo 2 BLOCKING (plan-consensus) - viz vysvětlení výš u Tasku 2 -
    `_exec_codex` selhání (rozbitý CLI, timeout, špatný exit kód) NESMÍ
    propadnout jako obyčejná výjimka, co by `_cmd_run` zpracoval jako
    per-kapitolový `error` (automaticky retrying přes `state.queue_for_
    run`) - musí zastavit CELÝ běh.

    Kolo 8 IMPORTANT (plan-consensus) - zpráva jde přes `stylist.
    _redact_detail()`, takže defaultně (`STYLIST_REPORT_REJECTED_TEXT`
    `False`, test fixture default) NEOBSAHUJE raw text - ověřuje
    REDIGOVANOU podobu, ne `match="auth expired"` (to ověřuje samostatný
    test níž s explicitním opt-inem).

    Kolo 11 IMPORTANT (plan-consensus) - ověřuje PŘESNÝ typ
    `CodexTranslatorFatalError`, ne jen `FatalRunError` - `_cmd_run`
    (Task 5) na TOMHLE typu rozlišuje flagged/redakci od obecného
    `FatalRunError` (kritikův cost guard atd.)."""
    from src.llm.client import CodexLLMClient, CodexTranslatorFatalError
    from src.agents.stylist import StylistError
    def boom(*a, **k):
        raise StylistError("codex exec skončil s kódem 1: auth expired")
    monkeypatch.setattr("src.agents.stylist._exec_codex", boom)
    c = CodexLLMClient(["codex"], "m")
    with pytest.raises(CodexTranslatorFatalError) as exc_info:
        c.complete(system="s", user="u", max_tokens=10, model="m")
    assert "auth expired" not in str(exc_info.value)
    assert "potlačeny" in str(exc_info.value)


def test_codex_llm_client_fatal_error_shows_detail_when_report_rejected_text_true(
        monkeypatch):
    """Kolo 8 IMPORTANT (plan-consensus) - explicitní opt-in
    (`config.STYLIST_REPORT_REJECTED_TEXT = True`) ukáže PŮVODNÍ zprávu -
    stejná brána, co `_cmd_polish`'s chybové cesty už používají."""
    from src.llm.client import CodexLLMClient
    from src.agents.stylist import StylistError
    monkeypatch.setattr(config, "STYLIST_REPORT_REJECTED_TEXT", True)
    def boom(*a, **k):
        raise StylistError("codex exec skončil s kódem 1: auth expired")
    monkeypatch.setattr("src.agents.stylist._exec_codex", boom)
    c = CodexLLMClient(["codex"], "m")
    with pytest.raises(FatalRunError, match="auth expired"):
        c.complete(system="s", user="u", max_tokens=10, model="m")


def test_codex_llm_client_wraps_os_and_unicode_errors_as_fatal_run_error(monkeypatch):
    """Kolo 7 IMPORTANT (plan-consensus) - `_exec_codex()`'s výstupní
    soubor se čte BEZ vlastního try/except, mimo `StylistError`
    kontrakt - `OSError` (zámek/oprávnění) i `UnicodeDecodeError`
    (poškozený zápis) musí projít STEJNOU cestou jako `StylistError`
    výš, jinak by unikly jako obyčejná výjimka a `state.queue_for_run`
    by je tiše retryovalo navěky."""
    from src.llm.client import CodexLLMClient
    for exc in (OSError("soubor je zamčený"),
               UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")):
        def boom(*a, _exc=exc, **k):
            raise _exc
        monkeypatch.setattr("src.agents.stylist._exec_codex", boom)
        c = CodexLLMClient(["codex"], "m")
        with pytest.raises(FatalRunError):
            c.complete(system="s", user="u", max_tokens=10, model="m")


def test_codex_llm_client_does_not_wrap_timeout_as_fatal_run_error(monkeypatch):
    """Kolo 9 IMPORTANT (plan-consensus) - timeout jednoho volání je
    PER-CALL/transientní, ne nutně systémové selhání celého Codex
    backendu jako auth/launch/exit-kód výš - NESMÍ se stát FatalRunError
    (to by zahodilo i hotový scénový překlad při selhání revize, viz
    Task 2, a zbytečně zastavilo celý run kvůli jednomu pomalému
    volání). Necháváme propadnout jako StylistTimeoutError beze změny -
    scénová smyčka ji zpracuje jako per-kapitolový error (auto-retry
    příští run je tady správně), revizní smyčka (Task 2) ji zachytí a
    kapitolu označí flagged s posledním platným překladem."""
    from src.llm.client import CodexLLMClient
    from src.agents.stylist import StylistTimeoutError
    def boom(*a, **k):
        raise StylistTimeoutError("codex exec překročil timeout 300s. [translator]")
    monkeypatch.setattr("src.agents.stylist._exec_codex", boom)
    c = CodexLLMClient(["codex"], "m")
    with pytest.raises(StylistTimeoutError):
        c.complete(system="s", user="u", max_tokens=10, model="m")


def test_codex_llm_client_refuses_without_fs_risk_optin(monkeypatch):
    """Kolo 14 IMPORTANT (plan-consensus) - obrana do hloubky -
    CodexLLMClient jde zkonstruovat a zavolat PŘÍMO, mimo `_client_
    factory`'s `_polish_preflight()` gate (Task 4) - `complete()` musí
    mít VLASTNÍ kontrolu, stejný vzor jako `stylist.polish()`."""
    from src.llm.client import CodexLLMClient, CodexTranslatorFatalError
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    def boom(*a, **k):
        raise AssertionError("_exec_codex se nemá volat bez FS_RISK opt-inu")
    monkeypatch.setattr("src.agents.stylist._exec_codex", boom)
    c = CodexLLMClient(["codex"], "m")
    with pytest.raises(CodexTranslatorFatalError):
        c.complete(system="s", user="u", max_tokens=10, model="m")


def test_pipeline_client_uses_billed_model_for_price_not_caller_model(monkeypatch, tmp_path):
    """Kolo 1 BLOCKING (plan-consensus) - jádro opravy. `PipelineLLMClient`
    dostane `model="claude-sonnet-5"` (přesně to, co `translator.py`
    reálně posílá), ale `self._inner` (Codex) má `billed_model="codex-x"`
    s NULOVOU cenou - cena/audit MUSÍ použít `billed_model`, ne
    `"claude-sonnet-5"` (co by mělo nenulovou cenu a spadlo by na
    přísahu FatalRunError "nemá sazby", protože `"claude-sonnet-5"`
    sazby MÁ, ale skutečně běžel Codex, ne Claude)."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "PRICE_IN_PER_MTOK",
                        {**config.PRICE_IN_PER_MTOK, "codex-x": 0.0})
    monkeypatch.setattr(config, "PRICE_OUT_PER_MTOK",
                        {**config.PRICE_OUT_PER_MTOK, "codex-x": 0.0})

    class FakeCodexInner:
        provider = "codex"
        billed_model = "codex-x"
        def complete(self, *, system, user, max_tokens, model):
            return Completion(text="ok", truncated=False, input_tokens=100, output_tokens=50)
        def count_tokens(self, *, system, user, model):
            return 10

    c = PipelineLLMClient(FakeCodexInner(), run_id=rid, agent="translator",
                          db_path=db, config_mod=config)
    # `model="claude-sonnet-5"` - PŘESNĚ to, co `translator.py` reálně
    # posílá (žádný explicitní `model=` argument z `pipeline.py`).
    c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    with state.connect(db) as conn:
        row = conn.execute("SELECT * FROM llm_calls").fetchone()
    assert row["model"] == "codex-x"        # NE "claude-sonnet-5"
    assert row["cost_usd"] == 0.0            # nulová cena z `billed_model`


def test_pipeline_client_guard_uses_billed_model_price_not_caller_model(
        monkeypatch, tmp_path):
    """Kolo 8 IMPORTANT (plan-consensus) - test výš ověřuje jen VÝSLEDNÝ
    audit řádek (`llm_calls`), ne že `_guard()` (cost-limit kontrola
    PŘED voláním) taky použije `effective_model`. Bez týhle části opravy
    by `_guard()` mohl počítat s Claude cenou pro Codex volání a
    zbytečně/chybně zastavit běh (false-positive cost-limit stop), i
    když efektivní cena Codexu je $0."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "PRICE_IN_PER_MTOK",
                        {**config.PRICE_IN_PER_MTOK, "codex-x": 0.0})
    monkeypatch.setattr(config, "PRICE_OUT_PER_MTOK",
                        {**config.PRICE_OUT_PER_MTOK, "codex-x": 0.0})
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)

    class FakeCodexInner:
        provider = "codex"
        billed_model = "codex-x"
        def complete(self, *, system, user, max_tokens, model):
            return Completion(text="ok", truncated=False, input_tokens=100, output_tokens=50)
        def count_tokens(self, *, system, user, model):
            return 10

    c = PipelineLLMClient(FakeCodexInner(), run_id=rid, agent="translator",
                          db_path=db, config_mod=config, interactive=False)
    # NESMÍ vyhodit FatalRunError - s effective_model="codex-x" (cena $0)
    # je odhad $0, MAX_SPEND_USD=0.0 projde. Kdyby _guard() použil
    # "claude-sonnet-5" (nenulová cena) místo effective_model, velký
    # max_tokens by vygeneroval nenulový odhad a FatalRunError by
    # vyletěl i s $0 utraceno.
    c.complete(system="s", user="u", max_tokens=100000, model="claude-sonnet-5")


def test_pipeline_client_missing_price_for_codex_inner_raises_codex_translator_fatal(
        monkeypatch, tmp_path):
    """Kolo 15 IMPORTANT (plan-consensus) - `_price()`'s "nemá sazby"
    `MissingPriceError` (kolo 16 - nová podtřída, viz níž) musí být pro
    Codex-backed inner klient (`.provider == "codex"`) přebalená na
    `CodexTranslatorFatalError`, jinak by `_cmd_run` (Task 5) tenhle pád
    nezachytil typovou větví a kapitola by zůstala v `processing` limbu
    (stejná třída díry jako kolo 12's `factory()` fix, jen jiné místo)."""
    from src.llm.client import CodexTranslatorFatalError
    db = _db(tmp_path)
    rid = state.create_run(db, "run")

    class FakeCodexInner:
        provider = "codex"
        billed_model = "codex-missing-price"   # ŽÁDNÝ záznam v PRICE_*_PER_MTOK
        def complete(self, *, system, user, max_tokens, model):
            raise AssertionError("nemá se zavolat - guard selže dřív")
        def count_tokens(self, *, system, user, model):
            return 10

    c = PipelineLLMClient(FakeCodexInner(), run_id=rid, agent="translator",
                          db_path=db, config_mod=config, interactive=False)
    with pytest.raises(CodexTranslatorFatalError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")


def test_pipeline_client_codex_normal_cost_guard_stop_stays_plain_fatal_run_error(
        monkeypatch, tmp_path):
    """Kolo 16 IMPORTANT (plan-consensus) - kolo-15's PŮVODNÍ fix
    (`except FatalRunError`) by chytlo VŠECHNY `_guard()` příčiny, i
    normální cost-guard stop (limit překročen, non-interactive) - to
    NENÍ Codex-specifická chyba (Claude by dopadl identicky), takže
    NESMÍ dostat `CodexTranslatorFatalError` zacházení. Zúženo na
    `MissingPriceError` (přesně jeden konkrétní `_guard()` raise-site)."""
    from src.llm.client import CodexTranslatorFatalError
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "PRICE_IN_PER_MTOK",
                        {**config.PRICE_IN_PER_MTOK, "codex-x": 100.0})
    monkeypatch.setattr(config, "PRICE_OUT_PER_MTOK",
                        {**config.PRICE_OUT_PER_MTOK, "codex-x": 100.0})
    monkeypatch.setattr(config, "MAX_SPEND_USD", 0.0)

    class FakeCodexInner:
        provider = "codex"
        billed_model = "codex-x"
        def complete(self, *, system, user, max_tokens, model):
            raise AssertionError("nemá se zavolat - guard selže dřív")
        def count_tokens(self, *, system, user, model):
            return 10

    c = PipelineLLMClient(FakeCodexInner(), run_id=rid, agent="translator",
                          db_path=db, config_mod=config, interactive=False)
    # Cena JE definovaná (žádný MissingPriceError) - guard zastaví na
    # PŘEKROČENÍ stropu, obyčejný FatalRunError, NE CodexTranslatorFatalError.
    with pytest.raises(FatalRunError) as exc_info:
        c.complete(system="s", user="u", max_tokens=100000, model="claude-sonnet-5")
    assert not isinstance(exc_info.value, CodexTranslatorFatalError)


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


def test_claude_cli_client_complete_preserves_zero_usage(monkeypatch):
    """Kolo 10 IMPORTANT (plan-consensus) - validní `input_tokens: 0`
    (např. triviální/cachovaný prompt) se NESMÍ přepsat na `1` -
    dřívější `usage.get("input_tokens") or 1` by nulu (falsy v
    Pythonu) tiše nahradilo jedničkou, znehodnocující audit
    `llm_calls`."""
    from src.llm.client import ClaudeCliClient
    def fake_exec(system, user, *, claude_cmd, model, timeout):
        return {"result": "ok", "is_error": False, "subtype": "success",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 0, "output_tokens": 3}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "claude-sonnet-5")
    comp = c.complete(system="s", user="u", max_tokens=100, model="claude-sonnet-5")
    assert comp.input_tokens == 0
    assert comp.output_tokens == 3


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


def test_claude_cli_client_appends_reinforcement_to_user_when_set(monkeypatch):
    """`--translator claude-cli` (spike 2026-09-22) - `claude -p --safe-mode`
    nedodrží striktní výstupní formát ze samotného system promptu (ověřeno
    0/4 selhání bez reinforcementu), ale s reinforcementem PŘIPOJENÝM na
    konec USER zprávy uspěl 5/5. Kritik reinforcement NEPOUŽÍVÁ (`None`
    default) - jen translator ho potřebuje."""
    from src.llm.client import ClaudeCliClient
    seen = {}
    def fake_exec(system, user, *, claude_cmd, model, timeout):
        seen["user"] = user
        return {"result": "ok", "is_error": False, "subtype": "success",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "m", reinforcement="DODRŽ FORMÁT")
    c.complete(system="s", user="USR", max_tokens=10, model="m")
    assert seen["user"] == "USRDODRŽ FORMÁT"


def test_claude_cli_client_no_reinforcement_by_default(monkeypatch):
    from src.llm.client import ClaudeCliClient
    seen = {}
    def fake_exec(system, user, *, claude_cmd, model, timeout):
        seen["user"] = user
        return {"result": "ok", "is_error": False, "subtype": "success",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1}}
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", fake_exec)
    c = ClaudeCliClient(["claude"], "m")
    c.complete(system="s", user="USR", max_tokens=10, model="m")
    assert seen["user"] == "USR"


def test_claude_cli_client_uses_custom_fatal_error_cls(monkeypatch):
    """`--translator claude-cli` potřebuje ROZLIŠIT translator-side selhání
    od kritikova (stejný důvod jako `CodexTranslatorFatalError` u Codexu) -
    `_client_factory` (main.py) předá jinou třídu při stavbě translator-role
    klienta, kritik zůstává na výchozí `ClaudeCliFatalError`."""
    from src.llm.client import ClaudeCliClient, ClaudeCliFatalError
    from src.llm.claude_cli import ClaudeCliExecError

    class _CustomFatal(ClaudeCliFatalError):
        pass

    def boom(*a, **k):
        raise ClaudeCliExecError("claude -p skončilo s kódem 1: X")
    monkeypatch.setattr("src.llm.claude_cli._exec_claude", boom)
    c = ClaudeCliClient(["claude"], "m", fatal_error_cls=_CustomFatal)
    with pytest.raises(_CustomFatal):
        c.complete(system="s", user="u", max_tokens=10, model="m")
