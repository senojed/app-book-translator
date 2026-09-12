import json
import os
import threading
import pytest
from fastapi.testclient import TestClient
from src import polish_store, state
from src.review_ui import polish_server


def _db(tmp_path, chapters=1):
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        for i in range(1, chapters + 1):
            conn.execute(
                "INSERT INTO chapters (idx,title,raw_text,translated_text,"
                "status,revision_rounds) VALUES (?,?,?,?,'done',0)",
                (i, f"K{i}", "EN", f"Věta {i}."))
    return db


def _draft(path, chapters):
    polish_store.save_draft(path, {
        "schema_version": 1, "generated_at": polish_store.utc_now_z(),
        "codex_model": "m", "chapters": chapters})


def _chapter_draft(idx=1, cz_before="A", styled="B", **over):
    base = {"idx": idx, "title": f"K{idx}", "cz_before": cz_before,
            "styled": styled, "revision_rounds": 0, "reason_types": [],
            "findings": [], "rendered_terms": [], "draft_id": f"draft-{idx}"}
    base.update(over)
    return base


_LIVE_APPS = []   # kolo 16 plán-ping-pongu NIT - viz `_stop_heartbeats` níž


def _app(tmp_path, chapters=1, draft_chapters=None):
    db = _db(tmp_path, chapters)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    state.acquire_lock(lock_path)
    if draft_chapters is not None:
        _draft(draft_path, draft_chapters)
    app = polish_server.build_app(db, draft_path, history_path, lock_path)
    _LIVE_APPS.append(app)
    return app, db, draft_path, history_path, lock_path


@pytest.fixture(autouse=True)
def _stop_heartbeats():
    """Kolo 16 plán-ping-pongu NIT - `_app()` staví REÁLNÝ server přes
    `build_app`, co spustí heartbeat daemon vlákno (Task 8). Bez úklidu
    by se přes celou testovací sadu hromadila nezastavená vlákna -
    neškodné (`daemon=True`, proces skončí i tak), ale zbytečné. Používá
    STEJNÝ `shutdown_heartbeat`/`join()` mechanismus jako `run_polish_
    review_server`'s vlastní `finally` (kolo 14)."""
    yield
    while _LIVE_APPS:
        app = _LIVE_APPS.pop()
        app.state.shutdown_heartbeat.set()
        app.state.heartbeat_thread.join(timeout=5)


def test_get_polish_returns_pending_and_history(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.")])
    client = TestClient(app)
    r = client.get("/api/polish")
    assert r.status_code == 200
    body = r.json()
    assert body["chapters"][0]["idx"] == 1
    assert body["history"] == []


def test_heartbeat_thread_calls_refresh_lock_periodically(tmp_path, monkeypatch):
    """Code review nález IMPORTANT (Task 8 review kolo 1) - dřív nic
    neověřovalo, že heartbeat vlákno SKUTEČNĚ volá `state.refresh_lock`
    (jen že po ztraceném zámku existuje terminální stav, ne že se
    zámek za normálního běhu doopravdy periodicky obnovuje). Zrychlí
    interval na 10 ms (monkeypatch PŘED `build_app`, protože heartbeat
    vlákno startuje UVNITŘ `build_app`) a čeká na SKUTEČNÉ volání přes
    `threading.Event`, ne přes spánek/polling s pevnou dobou."""
    db = _db(tmp_path, chapters=1)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    state.acquire_lock(lock_path)
    monkeypatch.setattr(polish_server, "_LOCK_REFRESH_INTERVAL", 0.01)
    real_refresh_lock = state.refresh_lock
    called = threading.Event()

    def _spy(path):
        real_refresh_lock(path)
        called.set()
    monkeypatch.setattr(polish_server.state, "refresh_lock", _spy)

    app = polish_server.build_app(db, draft_path, history_path, lock_path)
    _LIVE_APPS.append(app)
    assert called.wait(timeout=2) is True
    assert app.state.require_lock() is True   # zámek zůstává zdravý


def test_heartbeat_lock_error_sets_lock_lost_and_shutdown(tmp_path, monkeypatch):
    """Code review nález IMPORTANT (Task 8 review kolo 1) - dřív žádný
    test nepokrýval PŘECHOD do ztraceného stavu (jen stav PO něm).
    Ověřuje, že `state.LockError` z heartbeatu skutečně nastaví
    `lock_lost` I `shutdown` (probuzení vlákna okamžitě, kolo 14), a že
    `_require_lock()` po tomhle přechodu vrátí `False`."""
    db = _db(tmp_path, chapters=1)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    state.acquire_lock(lock_path)
    monkeypatch.setattr(polish_server, "_LOCK_REFRESH_INTERVAL", 0.01)

    def _boom(path):
        raise state.LockError("zámek ztracen (simulováno testem)")
    monkeypatch.setattr(polish_server.state, "refresh_lock", _boom)

    app = polish_server.build_app(db, draft_path, history_path, lock_path)
    _LIVE_APPS.append(app)
    assert app.state.lock_lost.wait(timeout=2) is True
    assert app.state.shutdown_heartbeat.is_set() is True
    assert app.state.require_lock() is False


def test_require_lock_is_terminal_after_lock_lost(tmp_path, monkeypatch):
    """Kolo 9 plán-ping-pongu IMPORTANT - jednou ztracený zámek je
    TERMINÁLNÍ stav serveru do restartu, ne stav, co se zkouší obnovit
    na KAŽDÉM dalším requestu - jinak by cizí proces mohl nechtěně
    způsobit nekonzistentní 503/200 střídání místo jednoho trvalého
    odmítnutí."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    app.state.lock_lost.set()

    def _boom(path):
        raise AssertionError("refresh_lock nemá být volané, když je lock_lost už nastavený")
    monkeypatch.setattr(polish_server.state, "refresh_lock", _boom)
    assert app.state.require_lock() is False


def test_get_polish_flags_stale_entry_with_matching_history(tmp_path):
    """Kolo 15 plán-ping-pongu IMPORTANT - `already_committed_has_history`
    matchuje i podle `draft_id` (ne jen textu), takže historie-záznam
    musí mít STEJNÝ `draft_id` jako draft (`_chapter_draft`'s default
    "draft-{idx}"), aby test opravdu ověřil zamýšlenou cestu."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.")])
    # DB se mezitím posunulo na "Věta 1. upravena" a historie o tom VÍ
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text=? WHERE idx=1",
                     ("Věta 1. upravena",))
    polish_store.save_history(history_path, {"schema_version": 1, "entries": [{
        "idx": 1, "applied_at": polish_store.utc_now_z(), "cz_before": "Věta 1.",
        "cz_after": "Věta 1. upravena", "styled_by_codex": "Věta 1. upravena",
        "title": "K1", "findings": [], "rendered_terms": [], "source": "polish-review",
        "draft_id": "draft-1"}]})
    client = TestClient(app)
    body = client.get("/api/polish").json()
    ch = body["chapters"][0]
    assert ch["stale"] is True and ch["reason"] == "already_committed_has_history"


def test_get_polish_flags_stale_entry_without_history(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.")])
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text=? WHERE idx=1",
                     ("Věta 1. jinak",))
    client = TestClient(app)
    body = client.get("/api/polish").json()
    ch = body["chapters"][0]
    assert ch["stale"] is True and ch["reason"] == "likely_committed_without_history"


def test_get_polish_unrelated_history_entry_with_same_text_does_not_match(tmp_path):
    """Kolo 15 plán-ping-pongu IMPORTANT - historie-záznam se STEJNÝM
    `cz_after` textem, ale JINÝM `draft_id` (typicky z NESOUVISEJÍCÍHO
    dřívějšího commitu pro tenhle idx), nesmí falešně vysvětlit stav
    TOHOHLE draftu jako `already_committed_has_history` - spadne správně
    do `likely_committed_without_history` (draft je pořád stale, jen s
    přesnější zprávou - historie tenhle KONKRÉTNÍ výsledek nezná)."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.")])
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text=? WHERE idx=1",
                     ("Věta 1. upravena",))
    polish_store.save_history(history_path, {"schema_version": 1, "entries": [{
        "idx": 1, "applied_at": polish_store.utc_now_z(), "cz_before": "Něco jiného",
        "cz_after": "Věta 1. upravena", "styled_by_codex": "Věta 1. upravena",
        "title": "K1", "findings": [], "rendered_terms": [], "source": "polish-review",
        "draft_id": "unrelated-draft"}]})
    client = TestClient(app)
    body = client.get("/api/polish").json()
    ch = body["chapters"][0]
    assert ch["stale"] is True and ch["reason"] == "likely_committed_without_history"


def test_get_polish_flags_stale_kept_original_when_draft_removal_failed(tmp_path):
    """Kolo 6 plán-ping-pongu IMPORTANT - no-op apply (`text == cz_before`)
    commitne `kept_original` marker BEZ textové změny; selže-li následně
    `save_draft`, řádek zůstane v draftu a textová shoda sama by ho
    ukázala jako "nerozhodnuto". Simuluje přesně tenhle stav ručně
    (marker v DB, draft pořád obsahuje položku SE STEJNÝM `draft_id`,
    jaký marker nese - kolo 10 match podle `draft_id`, ne hashe textu)
    a ověří, že GET ho přesto pozná."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1,
        draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", draft_id="draft-1")])
    import main
    import json as _json
    marker = main._kept_original_marker("Věta 1.", "model-x", "draft-1")
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (_json.dumps([marker], ensure_ascii=False),))
    client = TestClient(app)
    body = client.get("/api/polish").json()
    ch = body["chapters"][0]
    assert ch["stale"] is True and ch["reason"] == "already_committed_kept_original"


def test_get_polish_history_flags_db_diverged_from_history(tmp_path):
    """Kolo 6 plán-ping-pongu BLOCKING - selže-li zápis nového historie-
    záznamu AŽ PO úspěšném DB commitu (typicky u `revert`, co žádný
    draft netouchuje), historie dál končí STARÝM `cz_after`, DB má
    NOVÝ text. `_annotate_history` musí tenhle nesoulad aktivně
    najít, ne se spoléhat na draftovou `_stale_info` (revert žádný
    draft nemá)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1, draft_chapters=[])
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text=? WHERE idx=1", ("X (revertováno)",))
    polish_store.save_history(history_path, {"schema_version": 1, "entries": [{
        "idx": 1, "applied_at": polish_store.utc_now_z(), "cz_before": "Věta 1.",
        "cz_after": "Věta 1. stylizovaná", "styled_by_codex": "Věta 1. stylizovaná",
        "title": "K1", "findings": [], "rendered_terms": [], "source": "polish-review",
        "draft_id": "draft-1"}]})
    client = TestClient(app)
    body = client.get("/api/polish").json()
    row = body["history"][0]
    assert row["stale"] is True and row["reason"] == "db_diverged_from_history"


def test_get_polish_idx_filter_flags_latest_regardless_of_array_position(tmp_path):
    """Kolo 12 plán-ping-pongu BLOCKING - `?idx=N` vrací záznamy v POŘADÍ
    VLOŽENÍ (nejstarší první), NA ROZDÍL od nefiltrovaného GETu (nejnovější
    první). UI (Task 13) teď čte `can_revert_previous`/`can_revert_
    original`/`stale` PŘÍMO z každého řádku bez vlastní "je tohle
    nejnovější" heuristiky - tenhle test dokazuje, že `_annotate_history`
    OPRAVDU označí SPRÁVNÝ (poslední v čase, ne poslední v poli) záznam,
    ať uz je jeho POZICE v odpovědi jakákoli."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1, draft_chapters=[])
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='B' WHERE idx=1")
    polish_store.save_history(history_path, {"schema_version": 1, "entries": [
        {"idx": 1, "applied_at": "2026-01-01T00:00:00Z", "cz_before": "Věta 1.",
         "cz_after": "A", "styled_by_codex": "A", "title": "K1", "findings": [],
         "rendered_terms": [], "source": "polish-review", "draft_id": "draft-old"},
        {"idx": 1, "applied_at": "2026-01-02T00:00:00Z", "cz_before": "A",
         "cz_after": "B", "styled_by_codex": "B", "title": "K1", "findings": [],
         "rendered_terms": [], "source": "polish-review", "draft_id": "draft-new"},
    ]})
    client = TestClient(app)
    body = client.get("/api/polish?idx=1").json()
    rows = body["history"]
    assert [r["cz_after"] for r in rows] == ["A", "B"]   # vloženo nejstarší-první
    assert rows[0]["can_revert_previous"] is False   # NEJSTARŠÍ záznam - žádné tlačítko
    assert rows[1]["can_revert_previous"] is True    # SKUTEČNĚ poslední - tlačítko tady


def test_get_polish_idx_query_returns_full_chapter_history(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    entries = [{"idx": 1, "applied_at": polish_store.utc_now_z(), "cz_before": "X",
               "cz_after": "A", "styled_by_codex": "A", "title": "K1",
               "findings": [], "rendered_terms": [], "source": "polish-review",
               "draft_id": f"draft-{i}"}
              for i in range(25)]
    polish_store.save_history(history_path, {"schema_version": 1, "entries": entries})
    client = TestClient(app)
    body = client.get("/api/polish", params={"idx": 1}).json()
    assert len(body["history"]) == 25   # obchází globální limit N=20


def test_get_polish_hides_can_revert_original_at_chain_length_one(tmp_path):
    """Kolo 2 plán-ping-pongu IMPORTANT - u jediného záznamu je "original"
    cíl VŽDY stejný jako "previous" - server nesmí nabízet obě jako
    smysluplně různé volby (spec kolo 19/20)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    polish_store.save_history(history_path, {"schema_version": 1, "entries": [{
        "idx": 1, "applied_at": polish_store.utc_now_z(), "cz_before": "X",
        "cz_after": "A", "styled_by_codex": "A", "title": "K1",
        "findings": [], "rendered_terms": [], "source": "polish-review",
        "draft_id": "draft-1"}]})
    client = TestClient(app)
    row = client.get("/api/polish").json()["history"][0]
    assert row["can_revert_previous"] is True
    assert row["can_revert_original"] is False


def test_get_polish_shows_can_revert_original_at_chain_length_two(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='B' WHERE idx=1")
    polish_store.save_history(history_path, {"schema_version": 1, "entries": [
        # Explicitně ROZDÍLNÉ `applied_at` (code review nález IMPORTANT -
        # dva bare `utc_now_z()` volání za sebou mohou dát IDENTICKÝ
        # string, protože časové rozlišení není dost jemné; test by pak
        # se ~7% šancí ověřoval `history[0]` == STARŠÍ záznam místo
        # zamýšleného nejnovějšího). Stejný princip jako sousední test
        # `test_get_polish_idx_filter_flags_latest_regardless_of_array_
        # position` výš.
        {"idx": 1, "applied_at": "2026-01-01T00:00:00Z", "cz_before": "X",
         "cz_after": "A", "styled_by_codex": "A", "title": "K1", "findings": [],
         "rendered_terms": [], "source": "polish-review", "draft_id": "draft-1a"},
        {"idx": 1, "applied_at": "2026-01-02T00:00:00Z", "cz_before": "A",
         "cz_after": "B", "styled_by_codex": "B", "title": "K1", "findings": [],
         "rendered_terms": [], "source": "polish-review", "draft_id": "draft-1b"}]})
    client = TestClient(app)
    row = client.get("/api/polish").json()["history"][0]
    assert row["can_revert_previous"] is True
    assert row["can_revert_original"] is True


def test_polish_review_server_snapshots_db_at_startup(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    assert os.path.exists(db + ".pre-polish-review-snapshot")


def test_build_app_rejects_corrupt_draft_at_startup(tmp_path):
    """Kolo 2 plán-ping-pongu BLOCKING - server se nesmí spustit s
    poškozeným draft/historií, musí selhat HNED, ne uprostřed prvního
    requestu (kdy už mohl DB commit proběhnout)."""
    db = _db(tmp_path, chapters=1)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    open(draft_path, "w", encoding="utf-8").write("{not valid json")
    with pytest.raises(polish_store.PolishStoreError):
        polish_server.build_app(db, draft_path, history_path, lock_path)


def test_build_app_rejects_corrupt_history_at_startup(tmp_path):
    db = _db(tmp_path, chapters=1)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    open(history_path, "w", encoding="utf-8").write("{not valid json")
    with pytest.raises(polish_store.PolishStoreError):
        polish_server.build_app(db, draft_path, history_path, lock_path)


def test_get_polish_corrupt_draft_after_startup_returns_500(tmp_path):
    """Kolo 5 plán-ping-pongu IMPORTANT - poškození AŽ ZA BĚHU (obchází
    startovní preflight) musí dát jednotnou čitelnou 500, ne neřízený pád."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    open(draft_path, "w", encoding="utf-8").write("{not valid json")
    client = TestClient(app)
    r = client.get("/api/polish")
    assert r.status_code == 500
    assert "draft" in r.json()["error"].lower()


def test_run_polish_review_server_cleans_up_unpromoted_snapshot(tmp_path, monkeypatch):
    db = _db(tmp_path, chapters=1)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")

    class _FakeServer:
        def __init__(self, config): pass
        def run(self): pass   # nesimuluje skutečné naslouchání, jen návrat

    # `polish_server.uvicorn` NEEXISTUJE jako modulový atribut - `import
    # uvicorn` je uvnitř `run_polish_review_server`, ne na úrovni modulu
    # (stejný vzor jako existující `src/review_ui/server.py`). Patchuje
    # se PŘÍMO skutečný `uvicorn` modul přes cestu jako string (kolo 4
    # plán-ping-pongu IMPORTANT) - funguje bez ohledu na to, jak/kde se
    # v `polish_server.py` importuje, protože `import uvicorn` uvnitř
    # funkce jen znovu odkáže na TENTÝŽ objekt v `sys.modules`.
    monkeypatch.setattr("uvicorn.Server", _FakeServer)
    monkeypatch.setattr(polish_server.threading, "Timer",
                        lambda *a, **k: type("T", (), {"start": lambda self: None})())
    rc = polish_server.run_polish_review_server(db, draft_path, history_path, lock_path)
    assert rc == 0
    assert not os.path.exists(db + ".pre-polish-review-snapshot")


def test_run_polish_review_server_stops_heartbeat_before_returning(tmp_path, monkeypatch):
    """Kolo 14 plán-ping-pongu IMPORTANT - heartbeat vlákno se dřív při
    ČISTÉM vypnutí serveru nikdy explicitně nezastavovalo (jen `daemon=
    True`) - kdyby `server.run()` vrátilo právě v okamžiku, kdy heartbeat
    volá `refresh_lock`, mohlo by zámek obnovit TĚSNĚ PO tom, co volající
    (`main()`) zavolá `release_lock`. Ověřuje deterministicky (bez spánku/
    pollingu), že `run_polish_review_server` vlákno PROKAZATELNĚ zastaví
    (`.join()`) DŘÍV, než samo vrátí řízení."""
    db = _db(tmp_path, chapters=1)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")

    class _FakeServer:
        def __init__(self, config): pass
        def run(self): pass

    monkeypatch.setattr("uvicorn.Server", _FakeServer)
    monkeypatch.setattr(polish_server.threading, "Timer",
                        lambda *a, **k: type("T", (), {"start": lambda self: None})())
    captured = {}
    real_build_app = polish_server.build_app
    def _spy_build_app(*a, **k):
        app = real_build_app(*a, **k)
        captured["app"] = app
        return app
    monkeypatch.setattr(polish_server, "build_app", _spy_build_app)

    rc = polish_server.run_polish_review_server(db, draft_path, history_path, lock_path)
    assert rc == 0
    assert captured["app"].state.heartbeat_thread.is_alive() is False


def test_run_polish_review_server_returns_0_when_bind_raises_systemexit(tmp_path, monkeypatch):
    """Code review nález IMPORTANT (Task 8 review kolo 1) - uvicorn volá
    `sys.exit(1)` uvnitř `Server.startup()`, když selže bind (port už
    obsazený apod.). Bez `except (KeyboardInterrupt, SystemExit)` by
    `SystemExit` propagoval MIMO funkci a porušil garanci "vrací VŽDY
    0" ze spec - `finally` (úklid snapshotu/heartbeatu) by sice proběhl,
    ale `return 0` už ne."""
    db = _db(tmp_path, chapters=1)
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")

    class _FakeServer:
        def __init__(self, config): pass
        def run(self):
            raise SystemExit(1)   # simuluje selhání bindu uvnitř uvicorn

    monkeypatch.setattr("uvicorn.Server", _FakeServer)
    monkeypatch.setattr(polish_server.threading, "Timer",
                        lambda *a, **k: type("T", (), {"start": lambda self: None})())
    rc = polish_server.run_polish_review_server(db, draft_path, history_path, lock_path)
    assert rc == 0
    assert not os.path.exists(db + ".pre-polish-review-snapshot")
