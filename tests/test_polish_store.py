import os
import pytest
from src import polish_store as ps


def _chapter(idx=1, **over):
    base = {"idx": idx, "title": "K1", "cz_before": "A", "styled": "B",
            "revision_rounds": 0, "reason_types": [], "findings": [],
            "rendered_terms": [], "draft_id": f"draft-{idx}"}
    base.update(over)
    return base


def _draft(chapters=(), **over):
    base = {"schema_version": 1, "generated_at": ps.utc_now_z(),
            "codex_model": "m", "chapters": list(chapters)}
    base.update(over)
    return base


def test_load_missing_draft_returns_empty_envelope(tmp_path):
    d = ps.load_draft(str(tmp_path / "nope.json"))
    assert d == {"schema_version": ps.DRAFT_SCHEMA_VERSION, "generated_at": "",
                "codex_model": "", "chapters": []}


def test_save_then_load_draft_roundtrips(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    data = _draft([_chapter(1)])
    ps.save_draft(path, data)
    assert ps.load_draft(path) == data


def test_save_draft_is_atomic_no_tmp_file_left(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    ps.save_draft(path, _draft([_chapter(1)]))
    leftovers = [f for f in os.listdir(tmp_path) if f != "polish.draft.json"]
    assert leftovers == []


def test_is_draft_pending_false_when_missing_or_empty(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    assert ps.is_draft_pending(path) is False
    ps.save_draft(path, _draft([]))
    assert ps.is_draft_pending(path) is False


def test_is_draft_pending_true_with_chapters(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    ps.save_draft(path, _draft([_chapter(1)]))
    assert ps.is_draft_pending(path) is True


def test_load_draft_rejects_invalid_json(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    open(path, "w", encoding="utf-8").write("{not json")
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


@pytest.mark.parametrize("field", ["schema_version", "generated_at", "codex_model"])
def test_load_draft_rejects_missing_envelope_field(tmp_path, field):
    path = str(tmp_path / "polish.draft.json")
    data = _draft([_chapter(1)])
    del data[field]
    import json
    open(path, "w", encoding="utf-8").write(json.dumps(data))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_empty_codex_model(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(json.dumps(_draft([_chapter(1)], codex_model="")))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


@pytest.mark.parametrize("field", ["idx", "title", "cz_before", "styled",
                                   "revision_rounds", "reason_types", "findings",
                                   "rendered_terms", "draft_id"])
def test_load_draft_rejects_missing_chapter_field(tmp_path, field):
    path = str(tmp_path / "polish.draft.json")
    ch = _chapter(1)
    del ch[field]
    import json
    open(path, "w", encoding="utf-8").write(json.dumps(_draft([ch])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_duplicate_idx(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_draft([_chapter(1), _chapter(1)])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_empty_draft_id(tmp_path):
    """Kolo 11 plán-ping-pongu IMPORTANT - prázdný `draft_id` by rozbil
    identitu KONKRÉTNÍHO rozhodnutí, na které se kept-original
    idempotence (kolo 9/10) spoléhá."""
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_draft([_chapter(1, draft_id="")])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_utc_now_z_ends_with_z_and_parses():
    from datetime import datetime
    s = ps.utc_now_z()
    assert s.endswith("Z")
    datetime.fromisoformat(s[:-1] + "+00:00")


@pytest.mark.parametrize("bad", ["2026-09-12T10:00:00+01:00",   # jiný offset, ne Z
                                 "not-a-date", "", "2026-09-12T10:00:00"])   # bez Z vůbec
def test_load_draft_rejects_non_utc_z_generated_at(tmp_path, bad):
    path = str(tmp_path / "polish.draft.json")
    import json
    data = _draft([_chapter(1)], generated_at=bad)
    open(path, "w", encoding="utf-8").write(json.dumps(data))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_non_string_element_in_reason_types(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_draft([_chapter(1, reason_types=[1, 2])])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_non_dict_element_in_findings(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_draft([_chapter(1, findings=["not a dict"])])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_non_dict_element_in_rendered_terms(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_draft([_chapter(1, rendered_terms=[123])])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_save_draft_validates_before_writing(tmp_path):
    """kolo 1 plán-ping-pongu NIT - `save_draft` odmítne neplatný payload
    PŘED zápisem, ne až při dalším `load_draft`."""
    path = str(tmp_path / "polish.draft.json")
    bad = _draft([_chapter(1, reason_types="not-a-list")])
    with pytest.raises(ps.PolishStoreError):
        ps.save_draft(path, bad)
    assert not os.path.exists(path)


def test_load_draft_rejects_bool_as_idx(tmp_path):
    """kolo 2 plán-ping-pongu IMPORTANT - `isinstance(True, int)` je
    `True` v Pythonu, `idx: true` by jinak tiše prošlo jako platné číslo."""
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(json.dumps(_draft([_chapter(True)])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_nonpositive_idx(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(json.dumps(_draft([_chapter(0)])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_negative_revision_rounds(tmp_path):
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_draft([_chapter(1, revision_rounds=-1)])))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)


def test_load_draft_rejects_bool_schema_version(tmp_path):
    """kolo 3 plán-ping-pongu IMPORTANT - `True == 1` v Pythonu,
    `{"schema_version": true}` by jinak tiše prošlo jako verze 1."""
    path = str(tmp_path / "polish.draft.json")
    import json
    open(path, "w", encoding="utf-8").write(
        json.dumps(_draft([_chapter(1)], schema_version=True)))
    with pytest.raises(ps.PolishStoreError):
        ps.load_draft(path)
