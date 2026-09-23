import json
import os
import threading
import pytest
from fastapi.testclient import TestClient
import config
import main
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


_LIVE_APPS = []   # kolo 16 plán-ping-pongu NIT - viz `_stop_heartbeats` níž


def _app(tmp_path, chapters=1):
    db = _db(tmp_path, chapters)
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    guide_path = str(tmp_path / "guide.json")
    from src import guide as guide_mod
    guide_mod.save_guide(guide_path, {"characters": [], "places": [], "terms": [],
                                      "relationships": [], "style": "", "rules": []})
    state.acquire_lock(lock_path)
    app = polish_server.build_app(db, history_path, lock_path, guide_path=guide_path)
    _LIVE_APPS.append(app)
    return app, db, history_path, lock_path


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


def test_heartbeat_thread_calls_refresh_lock_periodically(tmp_path, monkeypatch):
    """Code review nález IMPORTANT (Task 8 review kolo 1) - dřív nic
    neověřovalo, že heartbeat vlákno SKUTEČNĚ volá `state.refresh_lock`
    (jen že po ztraceném zámku existuje terminální stav, ne že se
    zámek za normálního běhu doopravdy periodicky obnovuje). Zrychlí
    interval na 10 ms (monkeypatch PŘED `build_app`, protože heartbeat
    vlákno startuje UVNITŘ `build_app`) a čeká na SKUTEČNÉ volání přes
    `threading.Event`, ne přes spánek/polling s pevnou dobou."""
    db = _db(tmp_path, chapters=1)
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

    app = polish_server.build_app(db, history_path, lock_path)
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
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    state.acquire_lock(lock_path)
    monkeypatch.setattr(polish_server, "_LOCK_REFRESH_INTERVAL", 0.01)

    def _boom(path):
        raise state.LockError("zámek ztracen (simulováno testem)")
    monkeypatch.setattr(polish_server.state, "refresh_lock", _boom)

    app = polish_server.build_app(db, history_path, lock_path)
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
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    app.state.lock_lost.set()

    def _boom(path):
        raise AssertionError("refresh_lock nemá být volané, když je lock_lost už nastavený")
    monkeypatch.setattr(polish_server.state, "refresh_lock", _boom)
    assert app.state.require_lock() is False


def test_polish_review_server_snapshots_db_at_startup(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    assert os.path.exists(db + ".pre-polish-review-snapshot")


def test_build_app_rejects_corrupt_history_at_startup(tmp_path):
    """Kolo 2 plán-ping-pongu BLOCKING - server se nesmí spustit s
    poškozenou historií, musí selhat HNED, ne uprostřed prvního
    requestu (kdy už mohl DB commit proběhnout)."""
    db = _db(tmp_path, chapters=1)
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    open(history_path, "w", encoding="utf-8").write("{not valid json")
    with pytest.raises(polish_store.PolishStoreError):
        polish_server.build_app(db, history_path, lock_path)


def test_run_polish_review_server_cleans_up_unpromoted_snapshot(tmp_path, monkeypatch):
    db = _db(tmp_path, chapters=1)
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
    rc = polish_server.run_polish_review_server(db, history_path, lock_path)
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

    rc = polish_server.run_polish_review_server(db, history_path, lock_path)
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
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")

    class _FakeServer:
        def __init__(self, config): pass
        def run(self):
            raise SystemExit(1)   # simuluje selhání bindu uvnitř uvicorn

    monkeypatch.setattr("uvicorn.Server", _FakeServer)
    monkeypatch.setattr(polish_server.threading, "Timer",
                        lambda *a, **k: type("T", (), {"start": lambda self: None})())
    rc = polish_server.run_polish_review_server(db, history_path, lock_path)
    assert rc == 0
    assert not os.path.exists(db + ".pre-polish-review-snapshot")


def _seed_history(history_path, entries):
    polish_store.save_history(history_path, {"schema_version": 1, "entries": entries})


def _hist_entry(idx=1, cz_before="X", cz_after="A", **over):
    base = {"idx": idx, "applied_at": polish_store.utc_now_z(), "cz_before": cz_before,
            "cz_after": cz_after, "styled_by_codex": cz_after, "title": "K1",
            "findings": [], "rendered_terms": [], "source": "polish-review",
            "draft_id": f"draft-{idx}"}
    base.update(over)
    return base


def test_revert_previous_restores_cz_before_of_latest(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 200 and r.json().get("ok") is True
    assert state.get_chapter(db, 1)["translated_text"] == "X"
    entries = polish_store.load_history(history_path)["entries"]
    assert entries[-1] == {**entries[-1], "cz_before": "A", "cz_after": "X", "source": "revert"}


def test_revert_marker_note_names_target_history_entry(tmp_path):
    """Review nález IMPORTANT - DB audit marker (`main._revert_marker`)
    musí říct, KTERÝ historie-záznam byl cílem revertu (pozice v poli +
    `applied_at`), ne jen obecnou slovní frázi bez identifikace."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    target_entry = _hist_entry(1, cz_before="X", cz_after="A")
    _seed_history(history_path, [target_entry])
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 200
    entries = polish_store.load_history(history_path)["entries"]
    marker = next(f for f in entries[-1]["findings"]
                 if f.get("source") == "stylist" and f.get("type") == "revert")
    assert "idx=0" in marker["issue"]
    assert target_entry["applied_at"] in marker["issue"]


def test_revert_preserves_live_revision_rounds(tmp_path):
    """Kolo 1 plán-ping-pongu IMPORTANT - revert nesmí přepsat
    `revision_rounds` natvrdo na 0, musí zachovat živou DB hodnotu
    (stejný princip jako apply, spec kolo 2)."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A', revision_rounds=3 WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    client = TestClient(app)
    client.post("/api/polish/revert", json={"idx": 1})
    assert state.get_chapter(db, 1)["revision_rounds"] == 3


def test_revert_uses_stored_rendered_terms_not_narrowed_live_mentions(tmp_path, monkeypatch):
    """Spec kolo 18 / kolo 1 plán-ping-pongu IMPORTANT - `rendered_terms`
    je NEMĚNNÁ hodnota přenášená přes celý řetězec, NIKDY přepočítaná z
    `state.chapter_mentions` (ta by po apply mohla být OKLESANÁ -
    `build_mentions` jen emituje to, co SKUTEČNĚ najde v KONKRÉTNÍM
    textu). Test: DB má po apply zúženou (jinou) sadu mentions, revert
    MUSÍ i tak použít PŮVODNÍ `rendered_terms` uložené v historii."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    original_terms = [{"term_id": "t/a", "cz_as_used": "Áčko", "scene_idx": 0}]
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t/a','A','Á')")
    _seed_history(history_path, [_hist_entry(
        1, cz_before="X", cz_after="A", rendered_terms=original_terms)])
    # DB má TEĎ prázdnou sadu mentions - kdyby revert četl `state.
    # chapter_mentions` znovu místo použití historie, dostal by TOHLE
    # místo `original_terms`.
    state.replace_term_mentions(db, 1, [])
    seen = {}
    def _bm(en, cz, glossary_rows, rendered_terms):
        seen["build"] = list(rendered_terms)
        return []
    def _cc(en, cz, glossary_rows, rendered_terms):
        seen["check"] = list(rendered_terms)
        return []
    monkeypatch.setattr(polish_server.concordance, "build_mentions", _bm)
    monkeypatch.setattr(polish_server.concordance, "check_chapter", _cc)
    client = TestClient(app)
    client.post("/api/polish/revert", json={"idx": 1})
    assert seen["build"] == original_terms
    assert seen["check"] == original_terms


def test_revert_uses_live_glossary_not_snapshot_from_history(tmp_path, monkeypatch):
    """Kolo 13 plán-ping-pongu IMPORTANT - stejné jako u apply: `glossary_
    rows` se natahuje ŽIVĚ uvnitř handleru, NIKDY z doby, kdy záznam vznikl
    v historii - na rozdíl od `rendered_terms` (ty JSOU zmrazené, test
    výš). Term přidaný do glosáře MEZI historickým commitem a revertem
    musí být vidět v `mentions`."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    seen = {}
    def _bm(en, cz, glossary_rows, rendered_terms):
        seen["glossary_rows"] = list(glossary_rows)
        return []
    monkeypatch.setattr(polish_server.concordance, "build_mentions", _bm)
    monkeypatch.setattr(polish_server.concordance, "check_chapter", lambda *a, **k: [])
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES "
                     "('t/new','New','Nový')")
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 200
    assert any(g["term_id"] == "t/new" for g in seen["glossary_rows"])


def test_revert_pre_commit_failure_returns_500_db_and_history_unchanged(tmp_path, monkeypatch):
    """Kolo 12 plán-ping-pongu IMPORTANT - stejné jako u apply: selhání
    `commit_chapter_result` SAMOTNÉHO (SQLite transakce - nic se
    necommitne) musí vrátit ŘÍZENOU 500 s jasným "text NEBYL vrácen",
    ne propadnout jako neřízená výjimka."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    monkeypatch.setattr(polish_server.state, "commit_chapter_result",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")))
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 500
    assert "nebyl" in r.json()["error"].lower()
    assert state.get_chapter(db, 1)["translated_text"] == "A"
    assert len(polish_store.load_history(history_path)["entries"]) == 1   # jen seedovaný záznam


def test_revert_post_commit_save_failure_db_already_updated(tmp_path, monkeypatch):
    """Kolo 5 plán-ping-pongu IMPORTANT - stejné jako u apply: selhání
    zápisu historie AŽ PO commitu musí jasně říct, že text v knize se
    už změnil, ne jen vrátit generickou 500."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    monkeypatch.setattr(polish_server.polish_store, "save_history",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 500
    assert "vrátil" in r.json()["error"].lower() or "vrat" in r.json()["error"].lower()
    assert state.get_chapter(db, 1)["translated_text"] == "X"


def test_revert_original_walks_back_full_chain(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='B' WHERE idx=1")
    _seed_history(history_path, [
        _hist_entry(1, cz_before="X", cz_after="A"),
        _hist_entry(1, cz_before="A", cz_after="B")])
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1, "to": "original"})
    assert r.status_code == 200
    assert state.get_chapter(db, 1)["translated_text"] == "X"


def test_revert_noop_when_target_equals_current_db_text(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='X' WHERE idx=1")
    # X->A (entry1), pak revert A->X (entry2) - "original" teď == aktuální DB (X)
    _seed_history(history_path, [
        _hist_entry(1, cz_before="X", cz_after="A"),
        _hist_entry(1, cz_before="A", cz_after="X", source="revert")])
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1, "to": "original"})
    assert r.status_code == 200 and r.json().get("noop") is True
    entries_before = polish_store.load_history(history_path)["entries"]
    assert len(entries_before) == 2   # žádný nový záznam


def test_revert_404_when_no_history_for_idx(tmp_path):
    app, *_ = _app(tmp_path, chapters=1)
    client = TestClient(app)
    assert client.post("/api/polish/revert", json={"idx": 1}).status_code == 404


def test_revert_503_when_lock_lost_no_db_or_json_write(tmp_path, monkeypatch):
    """Kolo 7 plán-ping-pongu IMPORTANT - stejný princip jako u apply/
    discard: end-to-end důkaz, že ztracený zámek zablokuje zápis, ne jen
    unit test `refresh_lock` samotného. Revertu dřív chyběl tenhle
    regresní test."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 503
    assert state.get_chapter(db, 1)["translated_text"] == "A"
    assert len(polish_store.load_history(history_path)["entries"]) == 1


def test_revert_reads_history_only_while_holding_write_lock(tmp_path, monkeypatch):
    """Kolo 3 plán-ping-pongu BLOCKING - revert MUSÍ číst historii UVNITŘ
    `write_lock`, ne PŘED ním - jinak by souběžný save mohl proběhnout
    MEZI čtením a získáním zámku a revert by rozhodoval podle
    zastaralého stavu. Draft-frontová verze tohohle testu (Task 13)
    ověřovala navíc i `load_draft` - draft fronta skončila (Task 13),
    historie zůstává jediné, co revert čte."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    real_load_history = polish_server.polish_store.load_history
    seen = {"history_locked": None}
    def _spy_load_history(path):
        if path == history_path:
            seen["history_locked"] = app.state.write_lock.locked()
        return real_load_history(path)
    monkeypatch.setattr(polish_server.polish_store, "load_history", _spy_load_history)
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 200
    assert seen["history_locked"] is True


def test_revert_400_on_bool_idx(tmp_path):
    """Kolo 3 plán-ping-pongu BLOCKING - viz stejný test pro apply."""
    app, *_ = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": True})
    assert r.status_code == 400


def test_revert_409_when_db_moved_since_latest_entry(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='Jinak' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 409


# --- Task 8: GET /api/chapters + GET /api/chapter/{idx} ---------------------

def test_get_chapters_lists_all_with_unresolved_count(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=2)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    body = client.get("/api/chapters").json()
    by_idx = {c["idx"]: c for c in body["chapters"]}
    assert by_idx[1]["unresolved_findings"] == 1
    assert by_idx[2]["unresolved_findings"] == 0


def test_get_chapter_detail_returns_current_text_and_findings(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    body = client.get("/api/chapter/1").json()
    assert body["idx"] == 1
    assert body["translated_text"] == "Věta 1."
    assert body["cz_before_original"] is None    # žádná historie zatím
    assert body["styled_by_codex_latest"] is None


def test_get_chapter_detail_includes_open_questions(tmp_path):
    """Otázky vázané na tuhle kapitolu (i drift, co ji zasahuje mezi
    jinými) se ukážou přímo v odpovědi GET /api/chapter/{idx} - editor
    je má rovnou s EN/CZ kontextem (2026-09-23 sloučení)."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    state.upsert_open_question(db, {"chapter_idx": 1, "kind": "term",
        "text": "Sedí to?", "scope_key": "Nový povrch", "guess_answer": "X",
        "severity": "guess"})
    client = TestClient(app)
    body = client.get("/api/chapter/1").json()
    assert len(body["open_questions"]) == 1
    assert body["open_questions"][0]["text"] == "Sedí to?"
    assert body["open_questions"][0]["affected_chapters"] == []


def test_post_answer_on_polish_server_writes_and_requeues(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=2)
    from src import glossary as glossary_mod
    tid = glossary_mod.add_candidate(db, "Bob", "Bob")
    state.replace_term_mentions(db, 2, [
        {"term_id": tid, "cz_form": "Bobem", "scene_idx": None, "source": "detected"}])
    qid = state.upsert_open_question(db, {"chapter_idx": 2, "kind": "term",
        "text": "Bob?", "scope_key": tid, "guess_answer": "Bob", "severity": "guess"})
    client = TestClient(app)
    r = client.post("/api/answer", json={"qid": qid, "text": "Robert"})
    assert r.status_code == 200
    assert 2 in r.json()["requeued"]
    assert state.get_chapter(db, 2)["status"] == "pending"


def test_post_dismiss_on_polish_server(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    qid = state.upsert_open_question(db, {"chapter_idx": 1, "kind": "term",
        "text": "Šum?", "scope_key": "x", "guess_answer": "x", "severity": "guess"})
    client = TestClient(app)
    r = client.post("/api/dismiss", json={"qid": qid, "note": "šum"})
    assert r.status_code == 200
    assert state.get_question(db, qid)["answer"] is not None


def test_get_chapter_detail_includes_draft_fields(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    body = client.get("/api/chapter/1").json()
    assert body["draft_text"] is None
    assert body["draft_updated_at"] is None


def test_post_draft_saves_without_changing_status_or_translated_text(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/draft", json={"text": "rozpracovaný text"})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    assert row["draft_text"] == "rozpracovaný text"
    assert row["status"] == "done"          # beze změny
    assert row["translated_text"] == "Věta 1."   # beze změny

    body = client.get("/api/chapter/1").json()
    assert body["draft_text"] == "rozpracovaný text"
    assert body["draft_updated_at"] is not None


def test_post_draft_404_for_missing_chapter(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/99/draft", json={"text": "x"})
    assert r.status_code == 404


def test_post_draft_400_on_bad_shape(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/draft", json={})
    assert r.status_code == 400


def test_post_discard_draft_clears_without_touching_translated_text(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    client.post("/api/chapter/1/draft", json={"text": "koncept k zahození"})
    r = client.post("/api/chapter/1/draft/discard")
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    assert row["draft_text"] is None
    assert row["translated_text"] == "Věta 1."   # beze změny


def test_post_discard_draft_404_for_missing_chapter(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/99/draft/discard")
    assert r.status_code == 404


def test_save_chapter_clears_draft_on_finalize(tmp_path):
    """Uložením "a dokončit" se koncept smaže - je teď součástí
    translated_text, staré znění by matlo příští otevření."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    client.post("/api/chapter/1/draft", json={"text": "starý koncept"})
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Finální věta.", "findings": []})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    assert row["draft_text"] is None
    assert row["translated_text"] == "Finální věta."


def test_get_chapter_detail_404_for_missing_chapter(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.get("/api/chapter/99")
    assert r.status_code == 404


def test_get_chapter_detail_includes_history_baselines(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "Věta 1.", "cz_after": "Lepší věta.",
            "styled_by_codex": "Lepší věta.", "title": "K1", "findings": [],
            "rendered_terms": [], "source": "polish-batch", "draft_id": "d1"}]})
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text=? WHERE idx=1",
                     ("Lepší věta.",))
    client = TestClient(app)
    body = client.get("/api/chapter/1").json()
    assert body["cz_before_original"] == "Věta 1."
    assert body["styled_by_codex_latest"] == "Lepší věta."


def test_save_chapter_commits_and_writes_history(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Lepší věta 1.",
        "findings": [{"id": "f1", "resolved": False, "source": "critic",
                     "type": "fidelity", "issue": "x"}]})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Lepší věta 1."
    history = polish_store.load_history(history_path)
    assert history["entries"][0]["source"] == "polish-review"
    assert history["entries"][0]["cz_before"] == "Věta 1."


def test_save_chapter_noop_when_text_unchanged(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.", "findings": []})
    assert r.json() == {"ok": True, "noop": True}
    history = polish_store.load_history(history_path)
    assert history["entries"] == []   # žádný zbytečný záznam


def test_save_chapter_persists_findings_and_approves_flagged_without_text_change(tmp_path):
    """Kolo 2 IMPORTANT - text beze změny NEZNAMENÁ nulová operace,
    pokud kapitola byla `flagged` (uživatel ji Uložit tlačítkem ručně
    schválil) NEBO nese nové (dosud neuložené) nálezy z regenerace."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='flagged' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.",
        "findings": [{"id": "new1", "resolved": False,
                     "source": "critic", "type": "fidelity"}]})
    assert r.json() == {"ok": True, "noop": False}
    row = state.get_chapter(db, 1)
    assert row["status"] == "done"
    assert json.loads(row["notes"])[0]["id"] == "new1"
    history = polish_store.load_history(history_path)
    assert history["entries"] == []   # žádná NOVÁ historie položka - text se nezměnil


def test_save_chapter_allows_pending_with_existing_translation(tmp_path):
    """`pending` po odpovědi na otázku (requeue) NEMAŽE `translated_text`
    (viz `state.commit_answer` - jen mění `status`) - ruční oprava přímo
    v editoru bez čekání na `run` je platná cesta, pokud text existuje."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='pending' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Opravená věta 1.", "findings": []})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Opravená věta 1."
    assert row["status"] == "done"   # uložením se stav posune, jako u done/flagged


def test_save_chapter_409_on_pending_without_translation(tmp_path):
    """`pending`, co NIKDY nebyla přeložena (translated_text NULL) - není
    co editovat, stejná 409 cesta jako jiné needitovatelné stavy."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute(
            "UPDATE chapters SET status='pending', translated_text=NULL WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "", "text": "X", "findings": []})
    assert r.status_code == 409


def test_save_chapter_409_on_cas_mismatch(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Něco jiného.", "text": "X", "findings": []})
    assert r.status_code == 409


def test_save_chapter_400_on_bad_shape(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={"cz_before": "Věta 1."})   # chybí text
    assert r.status_code == 400


# Následující 4 testy PORTUJÍ ochranné scénáře ze starého draft-based
# `POST /api/polish/apply` (odstraněného Taskem 13) - Task 13 Step 1
# tyhle staré testy MAŽE (draft fronta končí), ale SAMOTNÁ OCHRANA, co
# testovaly, dál platí pro nový endpoint a MUSÍ zůstat pokrytá - proto
# tady, ne zapomenutá.

def test_save_chapter_503_when_lock_lost_no_db_write(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 503
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_corrupt_history_returns_500_without_db_write(tmp_path):
    """Historie se validuje PŘED commitem (`_commit_polish_result`, kolo 2
    BLOCKING) - poškozený `polish.history.json` nesmí nechat DB změněnou."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    open(history_path, "w", encoding="utf-8").write("{not valid json")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 500
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_pre_commit_failure_returns_500_db_unchanged(tmp_path, monkeypatch):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(polish_server.state, "commit_chapter_result",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 500
    assert "nebyl" in r.json()["error"].lower()
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_post_commit_history_failure_db_already_updated(tmp_path, monkeypatch):
    """Selhání ZÁPISU historie AŽ PO úspěšném DB commitu je jiná třída
    chyby (`main.HistoryWriteFailedAfterCommit`) - DB SE ZMĚNILA a
    zpráva to musí říct, ne tvrdit "nebyl uložen"."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(polish_server.polish_store, "save_history",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 500
    assert "uloži" in r.json()["error"].lower() or "ulož" in r.json()["error"].lower()
    assert state.get_chapter(db, 1)["translated_text"] == "Nová."   # DB SE PŘESTO ZMĚNILA


def test_save_chapter_keeps_resolved_true_even_with_stale_client_payload(tmp_path):
    """Karta B mezitím vyřešila nález přes /api/findings/resolve; karta A
    ukládá se STARÝM (resolved=False) stavem téhož nálezu - uložení
    nesmí vyřešení ztratit."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": True,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.",
        "findings": [{"id": "f1", "resolved": False,
                     "source": "critic", "type": "fidelity"}]})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    saved = json.loads(row["notes"])
    assert next(f for f in saved if f["id"] == "f1")["resolved"] is True


def test_save_chapter_server_resolved_false_wins_over_stale_client_true(tmp_path):
    """Opačný směr téhož race (kolo 2 BLOCKING - kolo 1 chránilo jen
    false→true): karta B nález ZNOVU OTEVŘELA (server má false), karta A
    má ve své paměti STARÉ true a s ním uloží - server musí zůstat u
    false, ne se nechat přepsat zastaralým true."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.",
        "findings": [{"id": "f1", "resolved": True,
                     "source": "critic", "type": "fidelity"}]})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    saved = json.loads(row["notes"])
    assert next(f for f in saved if f["id"] == "f1")["resolved"] is False


def test_save_chapter_text_change_does_not_wipe_finding_added_via_light_write(tmp_path):
    """Kolo 4 BLOCKING - karta B (lehká větev, text beze změny) přidá
    nový nález; karta A pak uloží SKUTEČNOU změnu textu se STARÝM
    (bez B's nálezu) seznamem findings - textový CAS na tohle nekouká,
    ale merge-podle-id ho i tak musí zachovat."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    # Karta B: lehká větev přidá nález "b1" (text beze změny).
    r1 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.",
        "findings": [{"id": "b1", "resolved": False, "source": "critic", "type": "fidelity"}]})
    assert r1.status_code == 200
    # Karta A: STARÝ payload (bez b1), ale SKUTEČNÁ změna textu.
    r2 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nový text A.", "findings": []})
    assert r2.status_code == 200
    row = state.get_chapter(db, 1)
    saved_ids = {f["id"] for f in json.loads(row["notes"])}
    assert "b1" in saved_ids   # PŘEŽILO, i když ho karta A vůbec neznala


def test_save_chapter_400_on_invalid_finding_shape(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [None]})
    assert r.status_code == 400


def test_save_chapter_400_on_invalid_known_ids_shape(tmp_path):
    """Kolo 20 BLOCKING - `known_ids` (nové, volitelné pole) musí být
    pole stringů, pokud je PŘÍTOMNÉ - stejná disciplína jako `findings`."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [],
        "known_ids": [1, 2]})
    assert r.status_code == 400


def test_save_chapter_400_on_falsy_but_present_known_ids(tmp_path):
    """Kolo 21 NIT - `known_ids: false`/`0`/`""`/`{}` jsou PŘÍTOMNÉ, ale
    ne-list hodnoty - musí dostat 400, ne se tiše proměnit na `[]`
    (`payload.get("known_ids") or []` by tohle mylně propustilo)."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [],
        "known_ids": False})
    assert r.status_code == 400


def test_save_chapter_missing_known_ids_defaults_to_empty(tmp_path):
    """Kolo 20 BLOCKING - CHYBĚJÍCÍ `known_ids` (starší klient/API
    volání) NESMÍ selhat ani nic ztratit - bezpečný fallback na `[]`
    (= "nic neznámo", nic se nemaže, viz `_merge_findings_by_id`)."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": []})
    assert r.status_code == 200


def test_save_chapter_allows_flagged_status(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='flagged' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Opraveno.", "findings": []})
    assert r.status_code == 200
    assert state.get_chapter(db, 1)["status"] == "done"


def test_save_chapter_preserves_rendered_terms_from_history_not_narrowed_live_mentions(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    polish_store.save_history(history_path, {
        "schema_version": 1, "entries": [{
            "idx": 1, "applied_at": polish_store.utc_now_z(),
            "cz_before": "Původní.", "cz_after": "Věta 1.", "styled_by_codex": "Věta 1.",
            "title": "K1", "findings": [],
            "rendered_terms": [{"term_id": "t/a", "cz_as_used": "Á", "scene_idx": 0},
                               {"term_id": "t/b", "cz_as_used": "Bé", "scene_idx": 1}],
            "source": "polish-batch", "draft_id": "d1"}]})
    # živá `term_mentions` je ÚŽŠÍ (jen jeden termín) - simuluje předchozí
    # commit, co glosářově zúžil hlášené tvary.
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES ('t/a','A','Á')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Á", "scene_idx": 0, "source": "rendered"}])
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Ještě lepší.", "findings": []})
    assert r.status_code == 200
    history = polish_store.load_history(history_path)
    new_entry = history["entries"][-1]
    assert len(new_entry["rendered_terms"]) == 2   # zachováno z historie, NE zúženo na 1


def test_regenerate_returns_styled_text_without_writing(tmp_path, monkeypatch):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)   # `_client_factory` účtuje SEM
                                                  # (main.py:56 - natvrdo
                                                  # `config.DB_PATH`, ne
                                                  # parametr), jinak by
                                                  # `runs`/`llm_calls`
                                                  # zápisy mířily do
                                                  # SKUTEČNÉ projektové DB
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    # Kolo 6 IMPORTANT oprava - endpoint teď volá `_polish_one_chapter`
    # i s `rendered_terms=rt` (kolo 5) - mock BEZ tohohle keyword parametru
    # by spadl na `TypeError: unexpected keyword argument`, endpoint by
    # to zachytil a vrátil 500 místo očekávaných 200/styled dat.
    seen = {}
    def _fake_polish_one_chapter(c, gr, cf, db_, model, codex_cmd, rendered_terms=None):
        seen["rendered_terms"] = rendered_terms
        return {"idx": 1, "title": "K1", "cz_before": "Věta 1.",
               "styled": "Vylepšená věta 1.", "revision_rounds": 0,
               "reason_types": [], "findings": [], "rendered_terms": [],
               "draft_id": "d1"}
    monkeypatch.setattr("main._polish_one_chapter", _fake_polish_one_chapter)
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert seen["rendered_terms"] == []   # `_preferred_rendered_terms` bez historie = živá DB (fixture prázdná)
    assert r.status_code == 200
    assert r.json()["styled"] == "Vylepšená věta 1."
    row = state.get_chapter(db, 1)
    assert row["translated_text"] == "Věta 1."   # NEZMĚNĚNO


def test_regenerate_404_for_missing_chapter(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 99})
    assert r.status_code == 404


def test_regenerate_400_for_pending_chapter_without_translation(tmp_path):
    """`pending` BEZ existujícího `translated_text` (nikdy nepřeložená) -
    není co polishovat. `pending` S textem (requeue po odpovědi na otázku,
    2026-09-23) naopak PROJDE - viz test níž."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute(
            "UPDATE chapters SET status='pending', translated_text=NULL WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 400


def test_regenerate_200_for_pending_chapter_with_existing_translation(tmp_path, monkeypatch):
    """`pending` po requeue (odpověď na otázku) NEMAŽE `translated_text` -
    regenerace/ruční oprava přímo v editoru je platná cesta bez čekání
    na `run` (uživatelův požadavek, 2026-09-23)."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='pending' WHERE idx=1")
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    def _fake_polish_one_chapter(c, gr, cf, db_, model, codex_cmd, rendered_terms=None):
        return {"idx": 1, "title": "K1", "cz_before": "Věta 1.",
               "styled": "Vylepšená věta 1.", "revision_rounds": 0,
               "reason_types": [], "findings": [], "rendered_terms": [],
               "draft_id": "d1"}
    monkeypatch.setattr("main._polish_one_chapter", _fake_polish_one_chapter)
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 200
    assert r.json()["styled"] == "Vylepšená věta 1."


def test_regenerate_400_for_error_status_without_translated_text(tmp_path):
    """Kolo 5 IMPORTANT - `status='error'` je v `_EDITABLE_STATUSES`,
    ale `run` ho může nastavit i s `translated_text=NULL` (první
    neúspěšný pokus o překlad) - musí to dostat čitelnou 400, ne spadnout
    hluboko v `_polish_one_chapter`."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='error', translated_text=NULL WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 400


def test_regenerate_503_on_preflight_failure(tmp_path, monkeypatch):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("main._polish_preflight",
                        lambda: (None, None, "Codex CLI není použitelné"))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503


def test_regenerate_503_on_claude_cli_preflight_failure(tmp_path, monkeypatch):
    """Kolo 2 IMPORTANT (plan-consensus) - stejný důvod jako `_cmd_run`/
    `_cmd_polish` (main.py) - regenerate taky volá kritika PO drahé
    Codex stylizaci - bez eager kontroly by chybějící/nepřihlášené
    `claude` CLI nechalo proběhnout Codex stylizaci, než by selhalo na
    kritikovi."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight",
                        lambda: (None, "claude CLI není přihlášené."))
    calls = {"n": 0}
    monkeypatch.setattr("main._polish_one_chapter",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503
    assert calls["n"] == 0   # Codex stylizace se VŮBEC nespustila


def test_regenerate_503_on_missing_anthropic_key(tmp_path, monkeypatch):
    """Kolo 3 BLOCKING (plan-consensus) - `stylist_check` (main.py:698)
    zůstává MIMO rozsah tohohle plánu, pořád `AnthropicClient`/
    `ANTHROPIC_API_KEY` - bez týhle kontroly by chybějící klíč nechal
    proběhnout DRAHOU Codex stylizaci, než by selhalo na PRVNÍM
    `stylist_check` volání, i když `claude` CLI preflight uspěje."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
    calls = {"n": 0}
    monkeypatch.setattr("main._polish_one_chapter",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503
    assert calls["n"] == 0   # Codex stylizace se VŮBEC nespustila


def test_regenerate_503_when_lock_lost_inside_polish_one_chapter(tmp_path, monkeypatch):
    """Kolo 16 IMPORTANT (test OPRAVEN kolo 17 BLOCKING - dřív mockoval
    `_polish_one_chapter` tak, aby `LockLostError` vyhodilo PŘÍMO, což
    obcházelo REÁLNÉ `except FatalRunError` uvnitř tý funkce a skrylo
    skutečný bug: ten blok `LockLostError` přebaloval na obyčejný
    `FatalRunError`, typ se ztrácel, `except main.LockLostError` v
    endpointu ho nikdy nechytilo. Tenhle test jde přes SKUTEČNOU
    `_polish_one_chapter` → `PipelineLLMClient.complete()` → `require_
    lock` kontrolu, aby tenhle konkrétní bug pokryl."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Jiná věta.")
    from src.llm.client import FakeLLMClient
    # `AnthropicClient()` nahrazen - `_client_factory` (main.py:52) ji
    # volá NATVRDO uvnitř `factory(agent)`, i když se nikdy nepoužije
    # (require_lock kontrola vyhodí LockLostError PŘED `self._inner.
    # complete()`, viz PipelineLLMClient.complete() výš) - prázdná
    # fronta odpovědí stačí, `FakeLLMClient([]).complete()` se nikdy
    # nezavolá.
    monkeypatch.setattr(main, "AnthropicClient", lambda: FakeLLMClient([]))
    calls = {"n": 0}
    def _require_lock():
        calls["n"] += 1
        return calls["n"] == 1   # True JEN napoprvé (start handleru)
    app.state.require_lock = _require_lock
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503
    assert "Zámek ztracen" in r.json()["error"]


def test_regenerate_returns_json_500_when_create_run_raises(tmp_path, monkeypatch):
    """Kolo 14 IMPORTANT - `state.create_run` bylo mimo `try` - selhání
    (SQLite chyba apod.) by propadlo jako NEZACHYCENÝ traceback (holý
    500 bez JSON těla) místo řízené odpovědi jako u každého jiného
    selhání v tomhle handleru."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr(state, "create_run",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk plný")))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 500
    assert "error" in r.json()   # řízená JSON odpověď, ne holý traceback


def test_regenerate_503_and_no_run_created_when_lock_lost_before_create_run(tmp_path, monkeypatch):
    """Kolo 13 IMPORTANT - `require_lock()` kontrola musí být POSLEDNÍ
    věc PŘED `state.create_run(...)`, ne mít mezi sebou další volání
    (`glossary.all_terms` bylo dřív AŽ PO kontrole - přesunuto PŘED).
    Ověř, že `require_lock() == False` zastaví PŘED jakýmkoli zápisem -
    žádný `runs` řádek nevznikne."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503
    with state.connect(db) as conn:
        rows = list(conn.execute("SELECT * FROM runs"))
    assert rows == []   # `create_run` se vůbec nezavolalo


def test_regenerate_uses_client_factory_with_require_lock_callback(tmp_path, monkeypatch):
    """Kolo 11 BLOCKING - endpoint MUSÍ `_client_factory` zavolat s
    `require_lock=app.state.require_lock`, jinak `PipelineLLMClient`
    uvnitř `_polish_one_chapter` nemá jak zámek ověřit PŘED KAŽDÝM LLM
    voláním (viz `tests/test_pipeline_client.py` pro samotné chování
    `PipelineLLMClient` - tenhle test ověřuje jen DRÁTOVÁNÍ na úrovni
    endpointu)."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._claude_cli_preflight", lambda: (["claude"], None))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    seen = {}
    def _fake_client_factory(rid, *, interactive, require_lock=None, claude_cmd=None):
        seen["require_lock"] = require_lock
        return lambda agent: None   # nepoužije se, _polish_one_chapter se mockuje níž
    monkeypatch.setattr("main._client_factory", _fake_client_factory)
    monkeypatch.setattr("main._polish_one_chapter",
                        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None:
                            {"idx": c["idx"], "outcome": "unchanged"})
    client = TestClient(app)
    client.post("/api/polish/regenerate", json={"idx": 1})
    assert seen["require_lock"] is app.state.require_lock


def test_regenerate_skips_finish_run_when_lock_lost_during_codex_call(tmp_path, monkeypatch):
    """Kolo 10 IMPORTANT - `require_lock()` na ZAČÁTKU handleru neručí za
    vlastnictví O CHVÍLI POZDĚJI (dlouhé Codex volání mezitím). Druhé
    volání (ve `finally`, těsně před `finish_run`) musí zámek ověřit
    ZNOVU a auditní zápis PŘESKOČIT, pokud ho mezitím ztratil - jinak by
    `runs`/`llm_calls` zápis proběhl bez ověřeného vlastnictví, což
    odporuje Global Constraints invariantu."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    monkeypatch.setattr("main._polish_one_chapter",
                        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None:
                            {"idx": c["idx"], "outcome": "unchanged"})
    calls = {"n": 0}
    def _require_lock():
        calls["n"] += 1
        return calls["n"] == 1   # True napoprvé (start handleru), False podruhé (finally)
    app.state.require_lock = _require_lock
    finish_run_calls = []
    monkeypatch.setattr(state, "finish_run",
                        lambda *a, **k: finish_run_calls.append(a))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 422   # "unchanged" outcome, ale request se DOKONČÍ
    assert finish_run_calls == []   # finish_run se NEZAVOLALO - zámek ztracen


def test_regenerate_then_save_does_not_duplicate_old_resolved_finding(tmp_path, monkeypatch):
    """Kolo 19 BLOCKING, `known_ids` design opraven kolo 20 BLOCKING -
    `assign_ids` (Task 2) dává KAŽDÉ analýze nové náhodné `id` - "Znovu
    polish" vrátí nález s ÚPLNĚ JINÝM `id`, i kdyby šlo sémanticky o
    "podobný" problém jako dřív vyřešený nález (critic je navíc LLM, ne
    deterministický - nejde spolehnout na shodu TEXTU). Integrační test
    celého cyklu regenerate → save, co Task 9's `_merge_findings_by_id(
    ..., known_ids=...)` oprava řeší - `known_ids` posílá KLIENTŮV
    `PERSISTED_IDS` (co znal PŘI NAČTENÍ, viz Task 14 `btn-save`) -
    ověřuje, že STARÝ (klientem ZNÁMÝ, osiřelý, jinak navždy "vyřešený"
    na neexistujícím textu) nález NEPŘEŽIJE zápis skutečné textové
    změny, zatímco marker ano (na rozdíl od `test_save_chapter_text_
    change_does_not_wipe_finding_added_via_light_write`, kde starý
    nález klient NIKDY neznal a MUSÍ přežít - viz tamní test)."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    # Simuluj PŘEDCHOZÍ uložení - kapitola má jeden reálný nález, už
    # VYŘEŠENÝ (resolved=True), plus marker z předchozí stylizace.
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1", (json.dumps([
            {"id": "old-f1", "resolved": True, "source": "critic",
             "type": "fidelity", "issue": "stará výhrada, už vyřešená"},
            {"id": "old-marker", "resolved": False, "source": "stylist",
             "type": "polish", "issue": "stylizováno (model=m), ..."},
        ]),))
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    fresh_finding = {"id": "new-f1", "resolved": False, "source": "critic",
                     "type": "fidelity", "issue": "nový, jiný problém"}
    monkeypatch.setattr(
        "main._polish_one_chapter",
        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None: {
            "idx": c["idx"], "title": "K1", "cz_before": c["translated_text"],
            "styled": "Regenerovaná věta.", "revision_rounds": 0,
            "reason_types": [], "findings": [dict(fresh_finding)],
            "rendered_terms": [], "draft_id": "d1"})
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 200
    regen_findings = r.json()["findings"]
    assert [f["id"] for f in regen_findings] == ["new-f1"]   # NOVÉ id, nesouvisí se starým

    # `known_ids: ["old-f1"]` - klient "old-f1" ZNAL (GET ho vrátil PŘED
    # regenerací, viz `PERSISTED_IDS`) - proto superseduje, ne "nikdy
    # neviděl" scénář z `test_save_chapter_text_change_does_not_wipe_...`.
    r2 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Regenerovaná věta.",
        "findings": regen_findings, "styled_by_codex": "Regenerovaná věta.",
        "known_ids": ["old-f1"]})
    assert r2.status_code == 200
    saved = json.loads(state.get_chapter(db, 1)["notes"])
    non_marker = [f for f in saved if f["source"] != "stylist"]
    marker = [f for f in saved if f["source"] == "stylist"]
    assert len(non_marker) == 1   # starý "old-f1" NEPŘEŽIL - žádná duplicita
    assert non_marker[0]["id"] == "new-f1"
    assert non_marker[0]["resolved"] is False   # nový, nevyřešený - NENÍ tiše "vyřešený"
    assert any(f["id"] == "old-marker" for f in marker)   # STARÝ marker zachován
    # nový marker od `_commit_polish_result` PŘIBYDE navíc (STEJNÝ `type`,
    # NOVÉ `id`) - staré markery se NIKDY nemažou, jen se hromadí, na
    # rozdíl od reálných nálezů výš.
    assert len(marker) == 2


def test_regenerate_reject_candidate_then_light_save_does_not_duplicate(tmp_path, monkeypatch):
    """Kolo 21 BLOCKING - STEJNÁ duplicitní chyba jako kolo 19/20, tentokrát
    na LEHKÉ větvi (`text == cz_before`) - uživatel klikne "Znovu polish"
    (fresh id nález), NEPŘIJME kandidát (textarea necha PŮVODNÍ text), ale
    STEJNĚ uloží (např. jen zaškrtne nález) - `CURRENT_FINDINGS` na
    klientovi pořád drží ČERSTVĚ regenerovaný nález (editor.html ho
    nahradí při "Znovu polish" bez ohledu na to, jestli uživatel kandidát
    later přijme). Bez `known_ids` i na lehké větvi by se osiřelý starý
    nález hromadil vedle nového PŘI KAŽDÉM takovém cyklu."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1", (json.dumps([
            {"id": "old-f1", "resolved": True, "source": "critic",
             "type": "fidelity", "issue": "stará výhrada, už vyřešená"},
        ]),))
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    fresh_finding = {"id": "new-f1", "resolved": False, "source": "critic",
                     "type": "fidelity", "issue": "nový, jiný problém"}
    monkeypatch.setattr(
        "main._polish_one_chapter",
        lambda c, gr, cf, db_, model, codex_cmd, rendered_terms=None: {
            "idx": c["idx"], "title": "K1", "cz_before": c["translated_text"],
            "styled": "Odmítnutý kandidát.", "revision_rounds": 0,
            "reason_types": [], "findings": [dict(fresh_finding)],
            "rendered_terms": [], "draft_id": "d1"})
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 200
    regen_findings = r.json()["findings"]

    # Uživatel NEPŘIJAL kandidát - `text` je pořád PŮVODNÍ ("Věta 1."),
    # ale `findings` posílá ČERSTVÉ (z odmítnuté regenerace, tak jak je
    # editor.html drží v `CURRENT_FINDINGS`).
    r2 = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Věta 1.",
        "findings": regen_findings, "known_ids": ["old-f1"]})
    assert r2.status_code == 200
    saved = json.loads(state.get_chapter(db, 1)["notes"])
    non_marker = [f for f in saved if f["source"] != "stylist"]
    assert len(non_marker) == 1   # starý "old-f1" NEPŘEŽIL - žádná duplicita
    assert non_marker[0]["id"] == "new-f1"


def test_resolve_finding_in_notes(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "notes", "idx": 1, "finding_id": "f1", "resolved": True})
    assert r.status_code == 200
    row = state.get_chapter(db, 1)
    assert json.loads(row["notes"])[0]["resolved"] is True


def test_resolve_finding_400_for_history_scope(tmp_path):
    """Kolo 17 IMPORTANT - `scope="history"` ODSTRANĚNA (byla dead code -
    žádný UI prvek ji nikdy nevolal, `renderFindings`/`toggleResolved`
    posílají VŽDY `scope: 'notes'`, viz Task 14). Editace `polish.
    history.json` nezávisle na `chapters.notes` by vytvořila DIVERGENTNÍ
    `resolved` hodnoty pro nález, co uživatel vnímá jako "stejný" - UI/
    report čtou VÝHRADNĚ `chapters.notes` (Task 8/12 design), takže
    "history" resolve by tiše vrátilo 200 a NIC viditelného by se
    nezměnilo."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "history", "idx": 1, "finding_id": "h1", "resolved": True})
    assert r.status_code == 400


def test_resolve_finding_calls_backup_db_once(tmp_path):
    """Kolo 22 IMPORTANT - `_backup_db_once` CHYBĚLO v tomhle endpointu -
    pokud je resolve PRVNÍ mutující operace session (uživatel otevře
    editor a rovnou něco zaškrtne, nikdy neuloží/neregeneruje), startovní
    snapshot by se při čistém vypnutí serveru smazal (`backup_state[
    'done']` by zůstalo `False`), i když reálný DB zápis proběhl -
    uživatel by přišel o obnovitelnou zálohu stavu PŘED touhle session."""
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity"}]),))
    assert app.state.backup_state["done"] is False
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "notes", "idx": 1, "finding_id": "f1", "resolved": True})
    assert r.status_code == 200
    assert app.state.backup_state["done"] is True


def test_resolve_finding_404_when_not_found(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "notes", "idx": 1, "finding_id": "nope", "resolved": True})
    assert r.status_code == 404


def test_resolve_finding_400_bad_scope(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "bogus", "idx": 1, "finding_id": "x", "resolved": True})
    assert r.status_code == 400


def test_get_findings_page_renders_html(tmp_path):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET notes=? WHERE idx=1",
                     (json.dumps([{"id": "f1", "resolved": False,
                                  "source": "critic", "type": "fidelity",
                                  "issue": "posun smyslu"}]),))
    client = TestClient(app)
    r = client.get("/findings")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "posun smyslu" in r.text


def test_post_export_writes_book_and_findings_files(tmp_path, monkeypatch):
    app, db, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("config.OUTPUT_TXT", str(tmp_path / "out.txt"))
    client = TestClient(app)
    r = client.post("/api/export", json={})
    assert r.status_code == 200
    body = r.json()
    assert os.path.exists(body["book_path"])
    assert os.path.exists(body["findings_path"])
