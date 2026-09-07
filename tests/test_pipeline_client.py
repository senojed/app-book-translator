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
