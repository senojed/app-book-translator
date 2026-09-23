import os

import pytest
from src import state
from src.state import LockError


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p); return p


class _Ch:
    def __init__(self, i): self.index = i; self.title = f"K{i}"; self.raw_text = "text"


def test_seed_chapters_idempotent(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1), _Ch(2)])
    state.seed_chapters(db, [_Ch(1), _Ch(2), _Ch(3)])
    assert len(state.chapters_by_status(db, ("pending",))) == 3


def test_recover_processing(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1)])
    state.set_status(db, 1, "processing")
    assert state.recover_processing(db) == 1
    assert state.get_chapter(db, 1)["status"] == "pending"


def test_queue_for_run_includes_pending_and_error_only(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1), _Ch(2), _Ch(3), _Ch(4)])
    state.set_status(db, 2, "error")
    state.set_status(db, 3, "flagged")
    state.set_status(db, 4, "needs_human")
    assert [c["idx"] for c in state.queue_for_run(db)] == [1, 2]


def test_retry_flagged_resets_rounds(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1)])
    state.update_chapter(db, 1, status="flagged", revision_rounds=2)
    assert state.retry_flagged(db, None) == 1
    c = state.get_chapter(db, 1)
    assert c["status"] == "pending" and c["revision_rounds"] == 0


def test_lock_blocks_second_holder(tmp_path):
    lp = str(tmp_path / ".lock")
    state.acquire_lock(lp)
    with pytest.raises(LockError):
        state.acquire_lock(lp)
    state.release_lock(lp)
    state.acquire_lock(lp)  # teď projde


def test_stale_lock_is_taken_over(tmp_path):
    import json
    lp = str(tmp_path / ".lock")
    with open(lp, "w") as f:
        json.dump({"pid": 999999, "ts": "old"}, f)  # mrtvý PID
    state.acquire_lock(lp)  # nesmí spadnout


def test_unparseable_lock_is_treated_as_stale(tmp_path):
    lp = str(tmp_path / ".lock")
    open(lp, "w").write("{tohle neni json")
    state.acquire_lock(lp)  # nesmí spadnout na parseru


@pytest.mark.skipif(os.name != "nt", reason="test cílí na Windows _pid_alive větev")
def test_pid_alive_false_for_exited_process_with_handle_still_open(tmp_path):
    """`OpenProcess` může uspět i na PID, co už skončil - Windows drží
    objekt procesu chvíli po smrti, obzvlášť dokud na něj někdo drží
    handle (přesně tenhle test to dělá přes `Popen`, co handle nezavírá
    sám od sebe po `wait()`). Bez `GetExitCodeProcess` kontroly by
    `_pid_alive` tenhle mrtvý proces vyhodnotil jako živý."""
    import subprocess
    import sys
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert state._pid_alive(p.pid) is False


def test_chapter_mentions_returns_only_that_chapter_in_insert_order(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1), _Ch(2)])
    # glosář musí mít term_id kvůli FK
    with state.connect(db) as conn:
        conn.execute("INSERT INTO glossary (term_id,canonical_en,cz) VALUES "
                     "('t/a','A','Á'),('t/b','B','Bé')")
    state.replace_term_mentions(db, 1, [
        {"term_id": "t/a", "cz_form": "Áčko", "scene_idx": 0, "source": "rendered"},
        {"term_id": "t/b", "cz_form": "Béčko", "scene_idx": 1, "source": "detected"},
    ])
    state.replace_term_mentions(db, 2, [
        {"term_id": "t/a", "cz_form": "jiné", "scene_idx": 0, "source": "rendered"},
    ])
    rows = state.chapter_mentions(db, 1)
    assert [r["term_id"] for r in rows] == ["t/a", "t/b"]
    assert rows[0]["source"] == "rendered" and rows[1]["source"] == "detected"
    assert rows[0]["cz_form"] == "Áčko"
    assert len(state.chapter_mentions(db, 2)) == 1


def test_acquire_lock_writes_complete_json_no_partial_file(tmp_path):
    """Regression for kolo 14: publish must go through a temp file + rename,
    never a truncate-then-write on the final path."""
    import json
    lp = str(tmp_path / ".lock")
    state.acquire_lock(lp)
    with open(lp, "r", encoding="utf-8") as f:
        data = json.load(f)   # must not raise - file is always complete
    assert data["pid"] == __import__("os").getpid()


def test_acquire_lock_leaves_no_tmp_file(tmp_path):
    import os as _os
    lp = str(tmp_path / ".lock")
    state.acquire_lock(lp)
    leftovers = [f for f in _os.listdir(tmp_path) if f != ".lock"]
    assert leftovers == []


def test_refresh_lock_updates_timestamp_when_we_own_it(tmp_path):
    import json
    import datetime
    lp = str(tmp_path / ".lock")
    state.acquire_lock(lp)
    with open(lp, "r", encoding="utf-8") as f:
        before = json.load(f)["ts"]
    state.refresh_lock(lp)
    with open(lp, "r", encoding="utf-8") as f:
        after = json.load(f)["ts"]
    assert datetime.datetime.fromisoformat(after) >= datetime.datetime.fromisoformat(before)


def test_refresh_lock_raises_when_someone_else_owns_it(tmp_path):
    import json
    lp = str(tmp_path / ".lock")
    with open(lp, "w", encoding="utf-8") as f:
        json.dump({"pid": 999999999, "ts": "2026-01-01T00:00:00"}, f)
    with pytest.raises(LockError):
        state.refresh_lock(lp)


def test_refresh_lock_raises_when_lock_file_gone(tmp_path):
    lp = str(tmp_path / ".lock")
    with pytest.raises(LockError):
        state.refresh_lock(lp)


def test_refresh_lock_wraps_write_failure_as_lock_error(tmp_path, monkeypatch):
    """Kolo 11 plán-ping-pongu IMPORTANT - `_publish_lock_overwrite`
    (zápis) dřív běžel MIMO `try`, takže obyčejný `OSError` (plný disk,
    práva) propadl jako SUROVÝ `OSError`, ne `LockError` - heartbeat i
    `_require_lock()` v `polish_server.py` chytají výhradně `LockError`,
    takže by tenhle stav zůstal nezachycený."""
    lp = str(tmp_path / ".lock")
    state.acquire_lock(lp)
    monkeypatch.setattr(state, "_publish_lock_overwrite",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(LockError):
        state.refresh_lock(lp)


def test_release_lock_does_not_delete_someone_elses_lock(tmp_path):
    import json
    lp = str(tmp_path / ".lock")
    with open(lp, "w", encoding="utf-8") as f:
        json.dump({"pid": 999999999, "ts": "2026-01-01T00:00:00"}, f)
    state.release_lock(lp)   # not ours - must NOT delete it
    assert __import__("os").path.exists(lp)


def test_release_lock_does_not_delete_unreadable_lock(tmp_path):
    """Kolo 2 plán-ping-pongu BLOCKING - nečitelný/poškozený OBSAH
    existujícího zámku se nesmí smazat, ať vlastnictví nejde ověřit."""
    lp = str(tmp_path / ".lock")
    open(lp, "w", encoding="utf-8").write("{not valid json")
    state.release_lock(lp)
    assert __import__("os").path.exists(lp)


def test_release_lock_deletes_our_own_lock(tmp_path):
    lp = str(tmp_path / ".lock")
    state.acquire_lock(lp)
    state.release_lock(lp)
    assert not __import__("os").path.exists(lp)


def test_save_chapter_draft_does_not_change_status_or_translated_text(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1)])
    state.save_chapter_draft(db, 1, "rozpracovaný text")
    ch = state.get_chapter(db, 1)
    assert ch["draft_text"] == "rozpracovaný text"
    assert ch["draft_updated_at"] is not None
    assert ch["status"] == "pending"   # beze změny
    assert ch["translated_text"] is None   # beze změny


def test_clear_chapter_draft(tmp_path):
    db = _db(tmp_path)
    state.seed_chapters(db, [_Ch(1)])
    state.save_chapter_draft(db, 1, "koncept")
    state.clear_chapter_draft(db, 1)
    ch = state.get_chapter(db, 1)
    assert ch["draft_text"] is None
    assert ch["draft_updated_at"] is None
