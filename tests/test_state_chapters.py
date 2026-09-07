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
