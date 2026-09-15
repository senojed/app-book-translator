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
