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


def test_get_polish_includes_raw_text_for_english_original_context(tmp_path):
    """UI kolo polish-ui-v2 - třetí panel (ORIGINÁL EN) potřebuje anglický
    zdrojový text vedle CZ originálu/návrhu. `_db` fixture vkládá `raw_text`
    `"EN"` pro každou kapitolu - GET musí tenhle text vrátit beze změny."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.")])
    client = TestClient(app)
    body = client.get("/api/polish").json()
    assert body["chapters"][0]["raw_text"] == "EN"


def test_get_polish_raw_text_is_none_when_chapter_deleted_from_db(tmp_path):
    """Edge case - kapitola byla mezitím smazaná z DB (`_stale_info` uz
    tenhle `get_chapter -> None` případ řeší jinde, GET nesmí spadnout na
    chybějícím `raw_text`, jen ho vrátí jako `None`)."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.")])
    with state.connect(db) as conn:
        conn.execute("DELETE FROM chapters WHERE idx=1")
    client = TestClient(app)
    r = client.get("/api/polish")
    assert r.status_code == 200
    assert r.json()["chapters"][0]["raw_text"] is None


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


def test_apply_writes_text_and_moves_draft_to_history(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1,
        draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="Věta 1. lepší")])
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "Věta 1. ručně."})
    assert r.status_code == 200
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1. ručně."
    assert polish_store.is_draft_pending(draft_path) is False
    hist = polish_store.load_history(history_path)["entries"]
    assert len(hist) == 1 and hist[0]["cz_after"] == "Věta 1. ručně."
    assert hist[0]["cz_before"] == "Věta 1."
    assert hist[0]["source"] == "polish-review"


def test_apply_uses_polish_marker_when_text_changed(tmp_path):
    app, db, *_ = _app(tmp_path, chapters=1,
                       draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    client = TestClient(app)
    client.post("/api/polish/apply", json={"idx": 1, "text": "Nová věta."})
    import main
    assert main._already_styled(state.get_chapter(db, 1)["notes"]) is True


def test_apply_marker_hashes_saved_text_not_cz_before(tmp_path):
    """Kolo 3 plán-ping-pongu IMPORTANT - marker MUSÍ popisovat, co
    SKUTEČNĚ šlo do knihy (`text`), ne originál (`cz_before`) ani
    Codexův raw návrh (`styled`) - zvlášť důležité při ruční editaci,
    kdy se všechny tři liší."""
    import hashlib, json
    import main
    app, db, *_ = _app(tmp_path, chapters=1,
                       draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="Návrh Codexu.")])
    client = TestClient(app)
    client.post("/api/polish/apply", json={"idx": 1, "text": "Ručně upravený text."})
    marker = next(f for f in json.loads(state.get_chapter(db, 1)["notes"])
                 if f.get("type") == "polish")
    expected_hash = hashlib.sha256("Ručně upravený text.".encode("utf-8")).hexdigest()
    assert expected_hash in marker["issue"]
    assert str(len("Ručně upravený text.")) in marker["issue"]


def test_apply_uses_kept_original_marker_when_text_unchanged_and_no_history(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    client = TestClient(app)
    client.post("/api/polish/apply", json={"idx": 1, "text": "Věta 1."})
    import main
    assert main._already_styled(state.get_chapter(db, 1)["notes"]) is False
    assert polish_store.load_history(history_path)["entries"] == []


def test_apply_noop_retry_after_draft_removal_failure_is_idempotent(tmp_path, monkeypatch):
    """Kolo 9 plán-ping-pongu IMPORTANT - GET/UI (kolo 6) UŽ detekuje
    `already_committed_kept_original`, ale bez týhle kontroly PŘÍMO v
    endpointu by retry no-op apply ZNOVU commitnul a přidal DRUHÝ
    `kept_original` marker (CAS by prošel - DB text se u no-op apply
    nemění)."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    client = TestClient(app)
    monkeypatch.setattr(polish_server.polish_store, "save_draft",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    r1 = client.post("/api/polish/apply", json={"idx": 1, "text": "Věta 1."})
    assert r1.status_code == 500
    assert polish_store.is_draft_pending(draft_path) is True
    import main
    notes1 = state.get_chapter(db, 1)["notes"]
    assert sum(1 for f in main._parse_findings(notes1) if f.get("type") == "kept_original") == 1

    monkeypatch.undo()   # obnov skutečný save_draft pro retry
    r2 = client.post("/api/polish/apply", json={"idx": 1, "text": "Věta 1."})
    assert r2.status_code == 200
    assert polish_store.is_draft_pending(draft_path) is False
    notes2 = state.get_chapter(db, 1)["notes"]
    assert sum(1 for f in main._parse_findings(notes2) if f.get("type") == "kept_original") == 1


def test_get_polish_does_not_flag_new_draft_stale_from_older_kept_original_same_text(tmp_path):
    """Kolo 10 plán-ping-pongu BLOCKING - `already_committed_kept_original`
    (kolo 6/9) dřív matchovala podle HASHE textu, ne konkrétního draftu.
    Kapitola, co zůstává nestylizovaná, může mít STEJNÝ `cz_before` napříč
    VÍCE nezávislými `polish` běhy - starý marker z DŘÍVĚJŠÍHO no-op apply
    nesmí falešně označit ÚPLNĚ NOVÝ, nevyřízený draft jako už vyřízený.
    (Kolo 11 plán-ping-pongu BLOCKING - patří sem do Task 9, ne do Task 8:
    test potřebuje `POST /api/polish/apply`, co Task 8 ještě nemá.)"""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1,
        draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B", draft_id="draft-A")])
    client = TestClient(app)
    r1 = client.post("/api/polish/apply", json={"idx": 1, "text": "Věta 1."})
    assert r1.status_code == 200
    assert polish_store.is_draft_pending(draft_path) is False

    # Nový nezávislý `polish` běh na STÁLE nestylizované kapitole (no-op
    # apply DB text nezměnilo) - nový draft se STEJNÝM `cz_before`, ale
    # JINÝM `draft_id`.
    new_draft = polish_store.load_draft(draft_path)
    new_draft["chapters"] = [_chapter_draft(1, cz_before="Věta 1.", styled="C", draft_id="draft-B")]
    polish_store.save_draft(draft_path, new_draft)

    body = client.get("/api/polish").json()
    ch = body["chapters"][0]
    assert ch["stale"] is False   # NENÍ vyřízeno - je to nový, nevyřízený draft

    r2 = client.post("/api/polish/apply", json={"idx": 1, "text": "C"})
    assert r2.status_code == 200
    assert state.get_chapter(db, 1)["translated_text"] == "C"


def test_apply_conflict_when_db_text_moved(tmp_path):
    app, db, *_ = _app(tmp_path, chapters=1,
                       draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text=? WHERE idx=1", ("Jinak.",))
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "X"})
    assert r.status_code == 409
    assert state.get_chapter(db, 1)["translated_text"] == "Jinak."


def test_apply_conflict_when_status_not_done(tmp_path):
    app, db, *_ = _app(tmp_path, chapters=1,
                       draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='pending' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "X"})
    assert r.status_code == 409


def test_apply_400_on_bad_input(tmp_path):
    app, *_ = _app(tmp_path, chapters=1, draft_chapters=[_chapter_draft(1)])
    client = TestClient(app)
    assert client.post("/api/polish/apply", json={"idx": "x", "text": "y"}).status_code == 400
    assert client.post("/api/polish/apply", json={"idx": 1, "text": None}).status_code == 400


def test_apply_400_on_bool_idx(tmp_path):
    """Kolo 3 plán-ping-pongu BLOCKING - `isinstance(True, int)` je
    `True` v Pythonu; `idx: true` by se bez explicitní kontroly chovalo
    jako `idx: 1` a mohlo tichem apply-nout ŠPATNOU kapitolu."""
    app, *_ = _app(tmp_path, chapters=1, draft_chapters=[_chapter_draft(1)])
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": True, "text": "y"})
    assert r.status_code == 400


def test_apply_reads_draft_only_while_holding_write_lock(tmp_path, monkeypatch):
    """Kolo 3 plán-ping-pongu BLOCKING - draft SE MUSÍ číst uvnitř
    `write_lock`, ne PŘED ním - jinak by souběžný `discard` mohl
    proběhnout MEZI apply čtením draftu a jeho vlastním získáním zámku,
    a apply by i tak zapsalo právě zahozenou kapitolu (CAS na DB text
    tohle nezachytí, protože `discard` DB vůbec netouch - jen draft.json).
    Deterministický test bez skutečné souběžnosti: špehuje, jestli je
    `write_lock` už držený v okamžiku, kdy apply volá `load_draft`."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    real_load_draft = polish_server.polish_store.load_draft
    seen = {"locked": None}
    def _spy_load_draft(path):
        if path == draft_path:
            seen["locked"] = app.state.write_lock.locked()
        return real_load_draft(path)
    monkeypatch.setattr(polish_server.polish_store, "load_draft", _spy_load_draft)
    client = TestClient(app)
    client.post("/api/polish/apply", json={"idx": 1, "text": "B"})
    assert seen["locked"] is True


def test_apply_503_when_lock_lost_no_db_or_json_write(tmp_path, monkeypatch):
    """Kolo 7 plán-ping-pongu IMPORTANT - unit testy pokrývaly `refresh_
    lock` samostatně, ale žádný nedokazoval end-to-end kontrakt endpointu:
    ztracený zámek musí vrátit 503 BEZ jakéhokoli zápisu do DB nebo
    draftu/historie."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "B"})
    assert r.status_code == 503
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."
    assert polish_store.is_draft_pending(draft_path) is True


def test_apply_404_when_idx_not_in_draft(tmp_path):
    app, *_ = _app(tmp_path, chapters=1, draft_chapters=[])
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "x"})
    assert r.status_code == 404


def test_apply_corrupt_history_returns_500_without_db_write(tmp_path):
    """Kolo 2 plán-ping-pongu BLOCKING - historie se validuje PŘED
    commitem. Test poškodí `history.json` PO startu serveru (obchází
    startovní preflight, simuluje ruční zásah za běhu) a ověří, že
    apply NEZAPÍŠE nic do DB, když historie nejde načíst."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    open(history_path, "w", encoding="utf-8").write("{not valid json")
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "B"})
    assert r.status_code == 500
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."
    assert polish_store.is_draft_pending(draft_path) is True


def test_apply_pre_commit_failure_returns_500_db_and_draft_unchanged(tmp_path, monkeypatch):
    """Kolo 12 plán-ping-pongu IMPORTANT - selhání `commit_chapter_result`
    SAMOTNÉHO (SQLite transakce - `src/state.py` garantuje "výjimka
    kdekoli uvnitř = nic se necommitne") musí vrátit ŘÍZENOU 500 s jasným
    "text NEBYL uložen", ne propadnout jako neřízená výjimka - a DB/draft
    zůstávají NEDOTČENÉ, protože k commitu vůbec nedošlo."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    monkeypatch.setattr(polish_server.state, "commit_chapter_result",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")))
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "Nový text."})
    assert r.status_code == 500
    assert "nebyl" in r.json()["error"].lower()
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."
    assert polish_store.is_draft_pending(draft_path) is True


def test_apply_post_commit_save_failure_db_already_updated(tmp_path, monkeypatch):
    """Kolo 5 plán-ping-pongu IMPORTANT - selhání ZÁPISU historie/draftu
    AŽ PO úspěšném DB commitu je jiná třída chyby, než selhání PŘED
    commitem (viz test výš) - DB SE ZMĚNILA a zpráva to musí říct."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
    monkeypatch.setattr(polish_server.polish_store, "save_history",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "Nový text."})
    assert r.status_code == 500
    assert "uloži" in r.json()["error"].lower() or "ulož" in r.json()["error"].lower()
    # DB SE PŘESTO ZMĚNILA - commit proběhl dřív, než save_history spadlo.
    assert state.get_chapter(db, 1)["translated_text"] == "Nový text."


def test_apply_backs_up_db_only_once(tmp_path):
    app, db, *_ = _app(
        tmp_path, chapters=2,
        draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B1"),
                        _chapter_draft(2, cz_before="Věta 2.", styled="B2")])
    client = TestClient(app)
    client.post("/api/polish/apply", json={"idx": 1, "text": "B1"})
    import os as _os
    mtime1 = _os.path.getmtime(db + ".pre-polish-backup")
    client.post("/api/polish/apply", json={"idx": 2, "text": "B2"})
    assert _os.path.getmtime(db + ".pre-polish-backup") == mtime1


def test_apply_uses_live_glossary_not_snapshot_from_draft_creation(tmp_path, monkeypatch):
    """Kolo 13 plán-ping-pongu IMPORTANT - `glossary_rows` se natahuje
    ŽIVĚ (`glossary.all_terms(db_path)`) UVNITŘ handleru, NIKDY se
    nepřenáší z doby vzniku draftu - na rozdíl od `rendered_terms` (ty
    JSOU zmrazené, viz `test_revert_uses_stored_rendered_terms_not_
    narrowed_live_mentions`). Term přidaný do glosáře MEZI vznikem
    draftu a apply musí být vidět v `mentions`/`build_mentions`."""
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="Věta 1.", styled="B")])
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
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "B"})
    assert r.status_code == 200
    assert any(g["term_id"] == "t/new" for g in seen["glossary_rows"])


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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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


def test_revert_409_when_pending_draft_exists_for_idx(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="A", styled="B")])
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 409
    assert state.get_chapter(db, 1)["translated_text"] == "A"


def test_revert_404_when_no_history_for_idx(tmp_path):
    app, *_ = _app(tmp_path, chapters=1)
    client = TestClient(app)
    assert client.post("/api/polish/revert", json={"idx": 1}).status_code == 404


def test_revert_503_when_lock_lost_no_db_or_json_write(tmp_path, monkeypatch):
    """Kolo 7 plán-ping-pongu IMPORTANT - stejný princip jako u apply/
    discard (viz `test_apply_503_when_lock_lost_no_db_or_json_write`):
    end-to-end důkaz, že ztracený zámek zablokuje zápis, ne jen unit test
    `refresh_lock` samotného. Revertu dřív chyběl tenhle regresní test."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 503
    assert state.get_chapter(db, 1)["translated_text"] == "A"
    assert len(polish_store.load_history(history_path)["entries"]) == 1


def test_revert_reads_draft_and_history_only_while_holding_write_lock(tmp_path, monkeypatch):
    """Kolo 3 plán-ping-pongu BLOCKING - stejný princip jako u apply (viz
    `test_apply_reads_draft_only_while_holding_write_lock`): revert MUSÍ
    číst draft (pending-guard) i historii UVNITŘ `write_lock`, ne PŘED
    ním - jinak by souběžný apply/discard mohl proběhnout MEZI čtením a
    získáním zámku a revert by rozhodoval podle zastaralého stavu.
    Revertu dřív chyběl tenhle regresní test."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='A' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    real_load_draft = polish_server.polish_store.load_draft
    real_load_history = polish_server.polish_store.load_history
    seen = {"draft_locked": None, "history_locked": None}
    def _spy_load_draft(path):
        if path == draft_path:
            seen["draft_locked"] = app.state.write_lock.locked()
        return real_load_draft(path)
    def _spy_load_history(path):
        if path == history_path:
            seen["history_locked"] = app.state.write_lock.locked()
        return real_load_history(path)
    monkeypatch.setattr(polish_server.polish_store, "load_draft", _spy_load_draft)
    monkeypatch.setattr(polish_server.polish_store, "load_history", _spy_load_history)
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 200
    assert seen["draft_locked"] is True
    assert seen["history_locked"] is True


def test_revert_400_on_bool_idx(tmp_path):
    """Kolo 3 plán-ping-pongu BLOCKING - viz stejný test pro apply."""
    app, *_ = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": True})
    assert r.status_code == 400


def test_revert_409_when_db_moved_since_latest_entry(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET translated_text='Jinak' WHERE idx=1")
    _seed_history(history_path, [_hist_entry(1, cz_before="X", cz_after="A")])
    client = TestClient(app)
    r = client.post("/api/polish/revert", json={"idx": 1})
    assert r.status_code == 409


def test_discard_removes_idx_from_draft(tmp_path):
    app, db, draft_path, *_ = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="A", styled="B")])
    client = TestClient(app)
    r = client.post("/api/polish/discard", json={"idx": 1})
    assert r.status_code == 200
    assert polish_store.is_draft_pending(draft_path) is False
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."   # DB netknuta


def test_discard_idempotent_when_idx_not_pending(tmp_path):
    app, *_ = _app(tmp_path, chapters=1, draft_chapters=[])
    client = TestClient(app)
    assert client.post("/api/polish/discard", json={"idx": 1}).status_code == 200


def test_discard_ok_when_no_draft_file_exists_at_all(tmp_path):
    """Bez ŽÁDNÉHO `polish.draft.json` (`draft_chapters=None` - `_app`
    tenhle soubor vůbec nezapíše) `load_draft`'s prázdný obal musí projít
    `save_draft`'s vlastní validací (review nález IMPORTANT) - jinak by
    tenhle discard pro kapitolu, co NIKDY nebyla ve frontě, dostal
    matoucí 500 misto čistého 200."""
    app, *_ = _app(tmp_path, chapters=1, draft_chapters=None)
    client = TestClient(app)
    r = client.post("/api/polish/discard", json={"idx": 1})
    assert r.status_code == 200


def test_discard_400_on_bad_input(tmp_path):
    app, *_ = _app(tmp_path, chapters=1)
    client = TestClient(app)
    assert client.post("/api/polish/discard", json={"idx": "x"}).status_code == 400


def test_discard_400_on_bool_idx(tmp_path):
    """Kolo 3 plán-ping-pongu BLOCKING - viz stejný test pro apply."""
    app, *_ = _app(tmp_path, chapters=1)
    client = TestClient(app)
    assert client.post("/api/polish/discard", json={"idx": True}).status_code == 400


def test_discard_503_when_lock_lost_no_json_write(tmp_path, monkeypatch):
    """Kolo 7 plán-ping-pongu IMPORTANT - stejný princip jako u apply:
    end-to-end důkaz, že ztracený zámek zablokuje zápis, ne jen unit
    test `refresh_lock` samotného."""
    app, db, draft_path, *_ = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="A", styled="B")])
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/polish/discard", json={"idx": 1})
    assert r.status_code == 503
    assert polish_store.is_draft_pending(draft_path) is True


def test_discard_save_failure_returns_500_draft_unchanged(tmp_path, monkeypatch):
    """Kolo 8 plán-ping-pongu IMPORTANT - discard nikdy nesahá na DB,
    takže selhání zápisu draftu tu není post-commit třída chyby jako u
    apply/revert - musí ale pořád vrátit ŘÍZENOU 500, ne neošetřenou
    výjimku, a kapitola zůstává ve frontě (žádný commit proběhnout
    nemohl - obojí je pořád jen jeden zápis)."""
    app, db, draft_path, *_ = _app(
        tmp_path, chapters=1, draft_chapters=[_chapter_draft(1, cz_before="A", styled="B")])
    monkeypatch.setattr(polish_server.polish_store, "save_draft",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    client = TestClient(app)
    r = client.post("/api/polish/discard", json={"idx": 1})
    assert r.status_code == 500
    assert "draft" in r.json()["error"].lower()
    assert polish_store.is_draft_pending(draft_path) is True


def test_discard_corrupt_draft_after_startup_returns_500(tmp_path):
    """Kolo 5 plán-ping-pongu IMPORTANT - jednotná čitelná 500, stejná
    jako GET/apply/revert - viz `test_get_polish_corrupt_draft_after_
    startup_returns_500`."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    open(draft_path, "w", encoding="utf-8").write("{not valid json")
    client = TestClient(app)
    r = client.post("/api/polish/discard", json={"idx": 1})
    assert r.status_code == 500
    assert "draft" in r.json()["error"].lower()


@pytest.mark.skip(reason="Testuje STAROU draft-frontu + /api/polish/apply "
                        "(_cmd_polish teď píše přímo do DB - Task 5). Task 13 "
                        "Step 1 ('Vyhledej zbývající odkazy na draft koncept') "
                        "tenhle test odstraňuje/nahrazuje jako součást "
                        "plánovaného úklidu staré draft fronty.")
def test_end_to_end_polish_then_apply_writes_edited_text(tmp_path, monkeypatch):
    import argparse
    import config
    import main
    from src.llm.client import FakeLLMClient, Completion
    db = str(tmp_path / "state.sqlite3")
    state.init_db(db)
    with state.connect(db) as conn:
        conn.execute("INSERT INTO chapters (idx,title,raw_text,translated_text,"
                     "status,revision_rounds) VALUES (1,'K1','EN','Původní věta.','done',0)")
    draft_path = str(tmp_path / "polish.draft.json")
    history_path = str(tmp_path / "polish.history.json")
    lock_path = str(tmp_path / ".lock")
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "POLISH_DRAFT_PATH", draft_path)
    monkeypatch.setattr(config, "POLISH_HISTORY_PATH", history_path)
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", True)
    monkeypatch.setattr(config, "CODEX_MODEL", "m")
    monkeypatch.setattr(main.stylist, "_resolve_codex_cmd", lambda cmd: ["codex"])
    monkeypatch.setattr(main.guide_mod, "load_guide", lambda path: {})
    monkeypatch.setattr(main.guide_mod, "guide_as_prompt_block", lambda g: "")
    monkeypatch.setattr(main.stylist, "polish", lambda en, cz, **k: "Návrh od Codexu.")
    monkeypatch.setattr(main.concordance, "check_chapter", lambda *a, **k: [])
    monkeypatch.setattr(main.concordance, "build_mentions", lambda *a, **k: [])
    monkeypatch.setattr(main.pipeline, "_run_critic", lambda *a, **k: ([], False))
    monkeypatch.setattr(main.stylist, "check_meaning_preserved", lambda *a, **k: [])
    # AnthropicClient by pokouší volat skutečné API - nahraď fake klientem
    monkeypatch.setattr(
        main, "AnthropicClient",
        lambda **kw: FakeLLMClient([Completion("ok", False, 100, 50)]))

    rc = main._cmd_polish(argparse.Namespace(only=None, force=False))
    assert rc == 0
    assert polish_store.is_draft_pending(draft_path) is True

    # Zámek MUSÍ být držený PŘED `build_app` (kolo 1 plán-ping-pongu
    # BLOCKING) - `apply` volá `refresh_lock`, co bez existujícího
    # zámku (s naším PID) vrátí `LockError` → 503, ne 200.
    state.acquire_lock(lock_path)
    app = polish_server.build_app(db, draft_path, history_path, lock_path)
    _LIVE_APPS.append(app)   # kolo 16 plán-ping-pongu NIT - `_stop_heartbeats` teardown
    client = TestClient(app)
    r = client.post("/api/polish/apply", json={"idx": 1, "text": "Ručně upravený text."})
    assert r.status_code == 200

    assert state.get_chapter(db, 1)["translated_text"] == "Ručně upravený text."
    assert polish_store.is_draft_pending(draft_path) is False
    hist = polish_store.load_history(history_path)["entries"]
    assert hist[0]["styled_by_codex"] == "Návrh od Codexu."
    assert hist[0]["cz_after"] == "Ručně upravený text."


# --- Task 8: GET /api/chapters + GET /api/chapter/{idx} ---------------------

def test_get_chapters_lists_all_with_unresolved_count(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=2)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    body = client.get("/api/chapter/1").json()
    assert body["idx"] == 1
    assert body["translated_text"] == "Věta 1."
    assert body["cz_before_original"] is None    # žádná historie zatím
    assert body["styled_by_codex_latest"] is None


def test_get_chapter_detail_404_for_missing_chapter(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.get("/api/chapter/99")
    assert r.status_code == 404


def test_get_chapter_detail_includes_history_baselines(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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


def test_save_chapter_409_on_cas_mismatch(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Něco jiného.", "text": "X", "findings": []})
    assert r.status_code == 409


def test_save_chapter_400_on_bad_shape(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={"cz_before": "Věta 1."})   # chybí text
    assert r.status_code == 400


# Následující 4 testy PORTUJÍ ochranné scénáře ze starého draft-based
# `POST /api/polish/apply` (`tests/test_polish_server.py`, testy kolem
# `test_apply_503_when_lock_lost_no_db_or_json_write`/`test_apply_corrupt_
# history_returns_500_without_db_write`/`test_apply_pre_commit_failure_
# returns_500_db_and_draft_unchanged`/`test_apply_post_commit_save_
# failure_db_already_updated`) - Task 13 Step 1 tyhle staré testy MAŽE
# (draft fronta končí), ale SAMOTNÁ OCHRANA, co testovaly, dál platí pro
# nový endpoint a MUSÍ zůstat pokrytá - proto tady, ne zapomenutá.

def test_save_chapter_503_when_lock_lost_no_db_write(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    app.state.require_lock = lambda: False
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 503
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_corrupt_history_returns_500_without_db_write(tmp_path):
    """Historie se validuje PŘED commitem (`_commit_polish_result`, kolo 2
    BLOCKING) - poškozený `polish.history.json` nesmí nechat DB změněnou."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    open(history_path, "w", encoding="utf-8").write("{not valid json")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Nová.", "findings": []})
    assert r.status_code == 500
    assert state.get_chapter(db, 1)["translated_text"] == "Věta 1."


def test_save_chapter_pre_commit_failure_returns_500_db_unchanged(tmp_path, monkeypatch):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [None]})
    assert r.status_code == 400


def test_save_chapter_400_on_invalid_known_ids_shape(tmp_path):
    """Kolo 20 BLOCKING - `known_ids` (nové, volitelné pole) musí být
    pole stringů, pokud je PŘÍTOMNÉ - stejná disciplína jako `findings`."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [],
        "known_ids": [1, 2]})
    assert r.status_code == 400


def test_save_chapter_400_on_falsy_but_present_known_ids(tmp_path):
    """Kolo 21 NIT - `known_ids: false`/`0`/`""`/`{}` jsou PŘÍTOMNÉ, ale
    ne-list hodnoty - musí dostat 400, ne se tiše proměnit na `[]`
    (`payload.get("known_ids") or []` by tohle mylně propustilo)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": [],
        "known_ids": False})
    assert r.status_code == 400


def test_save_chapter_missing_known_ids_defaults_to_empty(tmp_path):
    """Kolo 20 BLOCKING - CHYBĚJÍCÍ `known_ids` (starší klient/API
    volání) NESMÍ selhat ani nic ztratit - bezpečný fallback na `[]`
    (= "nic neznámo", nic se nemaže, viz `_merge_findings_by_id`)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Jiná.", "findings": []})
    assert r.status_code == 200


def test_save_chapter_allows_flagged_status(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='flagged' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/chapter/1/save", json={
        "cz_before": "Věta 1.", "text": "Opraveno.", "findings": []})
    assert r.status_code == 200
    assert state.get_chapter(db, 1)["status"] == "done"


def test_save_chapter_preserves_rendered_terms_from_history_not_narrowed_live_mentions(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 99})
    assert r.status_code == 404


def test_regenerate_400_for_pending_chapter(tmp_path):
    """`pending` nemá smysluplný `translated_text` k polishi - `flagged`/
    `needs_human`/`error` naopak PROJDOU (stejné `_EDITABLE_STATUSES`
    jako Task 9 save)."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='pending' WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 400


def test_regenerate_400_for_error_status_without_translated_text(tmp_path):
    """Kolo 5 IMPORTANT - `status='error'` je v `_EDITABLE_STATUSES`,
    ale `run` ho může nastavit i s `translated_text=NULL` (první
    neúspěšný pokus o překlad) - musí to dostat čitelnou 400, ne spadnout
    hluboko v `_polish_one_chapter`."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    with state.connect(db) as conn:
        conn.execute("UPDATE chapters SET status='error', translated_text=NULL WHERE idx=1")
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 400


def test_regenerate_503_on_preflight_failure(tmp_path, monkeypatch):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr("main._polish_preflight",
                        lambda: (None, None, "Codex CLI není použitelné"))
    client = TestClient(app)
    r = client.post("/api/polish/regenerate", json={"idx": 1})
    assert r.status_code == 503


def test_regenerate_503_when_lock_lost_inside_polish_one_chapter(tmp_path, monkeypatch):
    """Kolo 16 IMPORTANT (test OPRAVEN kolo 17 BLOCKING - dřív mockoval
    `_polish_one_chapter` tak, aby `LockLostError` vyhodilo PŘÍMO, což
    obcházelo REÁLNÉ `except FatalRunError` uvnitř tý funkce a skrylo
    skutečný bug: ten blok `LockLostError` přebaloval na obyčejný
    `FatalRunError`, typ se ztrácel, `except main.LockLostError` v
    endpointu ho nikdy nechytilo. Tenhle test jde přes SKUTEČNOU
    `_polish_one_chapter` → `PipelineLLMClient.complete()` → `require_
    lock` kontrolu, aby tenhle konkrétní bug pokryl."""
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr("main._polish_preflight", lambda: ("m", ["codex"], None))
    seen = {}
    def _fake_client_factory(rid, *, interactive, require_lock=None):
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
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
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "notes", "idx": 1, "finding_id": "nope", "resolved": True})
    assert r.status_code == 404


def test_resolve_finding_400_bad_scope(tmp_path):
    app, db, draft_path, history_path, lock_path = _app(tmp_path, chapters=1)
    client = TestClient(app)
    r = client.post("/api/findings/resolve", json={
        "scope": "bogus", "idx": 1, "finding_id": "x", "resolved": True})
    assert r.status_code == 400
