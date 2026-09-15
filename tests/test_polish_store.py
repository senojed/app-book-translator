import os
import pytest
from src import polish_store as ps


def test_utc_now_z_ends_with_z_and_parses():
    from datetime import datetime
    s = ps.utc_now_z()
    assert s.endswith("Z")
    datetime.fromisoformat(s[:-1] + "+00:00")


# Testy pro history (Task 2)

def _entry(idx=1, applied_at=None, source="polish-review", **over):
    base = {"idx": idx, "applied_at": applied_at or ps.utc_now_z(),
            "cz_before": "A", "cz_after": "B", "styled_by_codex": "B",
            "title": "K1", "findings": [], "rendered_terms": [],
            "source": source, "draft_id": f"draft-{idx}"}
    base.update(over)
    return base


def _history(entries=(), **over):
    base = {"schema_version": 1, "entries": list(entries)}
    base.update(over)
    return base


def test_load_missing_history_returns_empty_envelope(tmp_path):
    h = ps.load_history(str(tmp_path / "nope.json"))
    assert h == {"schema_version": ps.HISTORY_SCHEMA_VERSION, "entries": []}


def test_save_then_load_history_roundtrips(tmp_path):
    path = str(tmp_path / "polish.history.json")
    data = _history([_entry(1)])
    ps.save_history(path, data)
    assert ps.load_history(path) == data


def test_load_history_rejects_invalid_source(tmp_path):
    path = str(tmp_path / "polish.history.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_history([_entry(1, source="bogus")])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_history(path)


def test_load_history_rejects_non_utc_z_applied_at(tmp_path):
    path = str(tmp_path / "polish.history.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_history([_entry(1, applied_at="2026-09-12T10:00:00+01:00")])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_history(path)


@pytest.mark.parametrize("field", list(ps._HISTORY_ENTRY_FIELDS))
def test_load_history_rejects_missing_entry_field(tmp_path, field):
    path = str(tmp_path / "polish.history.json")
    e = _entry(1)
    del e[field]
    import json
    open(path, "w", encoding="utf-8").write(json.dumps(_history([e])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_history(path)


def test_load_history_rejects_empty_draft_id(tmp_path):
    """Kolo 15 plán-ping-pongu IMPORTANT - prázdný `draft_id` by rozbil
    identitu, na které se `already_committed_has_history` detekce
    spoléhá (stejný princip jako draftové `draft_id`, kolo 11)."""
    path = str(tmp_path / "polish.history.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_history([_entry(1, draft_id="")])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_history(path)


def test_find_latest_returns_last_matching_entry_by_position():
    entries = [_entry(1, cz_after="A1"), _entry(2), _entry(1, cz_after="A2")]
    assert ps.find_latest(entries, 1)["cz_after"] == "A2"


def test_find_latest_none_when_no_entries_for_idx():
    assert ps.find_latest([_entry(2)], 1) is None


def test_find_chain_start_single_entry_is_itself():
    entries = [_entry(1, cz_before="X", cz_after="A")]
    assert ps.find_chain_start(entries, 1)["cz_before"] == "X"


def test_find_chain_start_walks_back_through_continuous_chain():
    entries = [_entry(1, cz_before="X", cz_after="A"),
              _entry(1, cz_before="A", cz_after="B")]
    assert ps.find_chain_start(entries, 1)["cz_before"] == "X"


def test_find_chain_start_stops_at_broken_link():
    # X->A (entry1), pak MIMO polish vznikne nesouvisející Y, pak Y->B (entry2)
    entries = [_entry(1, cz_before="X", cz_after="A"),
              _entry(1, cz_before="Y", cz_after="B")]
    assert ps.find_chain_start(entries, 1)["cz_before"] == "Y"


def test_resolve_revert_target_previous_vs_original():
    entries = [_entry(1, cz_before="X", cz_after="A"),
              _entry(1, cz_before="A", cz_after="B")]
    assert ps.resolve_revert_target(entries, 1, "previous") == "A"
    assert ps.resolve_revert_target(entries, 1, "original") == "X"


def test_resolve_revert_target_none_when_no_history():
    assert ps.resolve_revert_target([], 1, "previous") is None


def test_load_history_rejects_non_dict_element_in_findings(tmp_path):
    path = str(tmp_path / "polish.history.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_history([_entry(1, findings=["not a dict"])])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_history(path)


def test_load_history_rejects_non_dict_element_in_rendered_terms(tmp_path):
    path = str(tmp_path / "polish.history.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_history([_entry(1, rendered_terms=[123])])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_history(path)


def test_save_history_accepts_polish_batch_source(tmp_path):
    path = str(tmp_path / "h.json")
    ps.save_history(path, _history([_entry(1, source="polish-batch")]))
    loaded = ps.load_history(path)
    assert loaded["entries"][0]["source"] == "polish-batch"


def test_save_history_validates_before_writing(tmp_path):
    path = str(tmp_path / "polish.history.json")
    bad = _history([_entry(1, source="bogus")])
    with pytest.raises(ps.PolishStoreError):
        ps.save_history(path, bad)
    assert not os.path.exists(path)


def test_load_history_rejects_bool_schema_version(tmp_path):
    path = str(tmp_path / "polish.history.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_history([_entry(1)], schema_version=True)))
    with pytest.raises(ps.PolishStoreError):
        ps.load_history(path)
