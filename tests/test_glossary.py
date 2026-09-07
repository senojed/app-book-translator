import json
from src import state, glossary


def _db(tmp_path):
    p = str(tmp_path / "s.sqlite3"); state.init_db(p); return p


def test_slugify():
    assert glossary.slugify("The White Council") == "the-white-council"


def test_add_candidate_returns_term_id_and_dedups_by_surface(tmp_path):
    db = _db(tmp_path)
    a = glossary.add_candidate(db, "Bob", "Bob")
    b = glossary.add_candidate(db, "bob", "Bobek")  # stejný povrch (ci)
    assert a == b
    with state.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM glossary").fetchone()["c"] == 1


def test_seed_reuses_candidate_term_id(tmp_path):
    db = _db(tmp_path)
    cand = glossary.add_candidate(db, "Harry Dresden", "Harry Dresden")
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Harry Dresden", "aliases": ["Harry"], "render": "keep"}],
        "places": [], "terms": []})
    with state.connect(db) as conn:
        row = conn.execute("SELECT * FROM glossary").fetchone()
    assert row["term_id"] == cand  # sdílené term_id
    assert row["status"] == "seeded"


def test_fresh_seed_id_and_terms_section(tmp_path):
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [], "places": [],
        "terms": [{"term_en": "White Council", "cz": "Bílá rada"}]})
    t = glossary.all_terms(db)[0]
    assert t["term_id"] == "term_white-council"
    assert t["cz"] == "Bílá rada" and t["type"] == "term"


def test_seed_does_not_overwrite_approved(tmp_path):
    db = _db(tmp_path)
    tid = glossary.add_candidate(db, "Council", "Rada")
    glossary.promote(db, tid, "Koncil")            # člověk rozhodl
    glossary.add_accepted_alt(db, tid, "Koncilu")
    glossary.seed_from_guide(db, {"characters": [], "places": [],
        "terms": [{"term_en": "Council", "cz": "Rada"}]})   # reseed s jiným cz
    t = [x for x in glossary.all_terms(db) if x["term_id"] == tid][0]
    assert t["status"] == "approved" and t["cz"] == "Koncil"   # approved vyhrál
    assert t["accepted_alt"] == ["Koncilu"]


def test_promote_and_accepted_alt(tmp_path):
    db = _db(tmp_path)
    tid = glossary.add_candidate(db, "Foo", "Fu")
    glossary.promote(db, tid, "Fů")
    glossary.add_accepted_alt(db, tid, "Fůa")
    glossary.add_accepted_alt(db, tid, "Fůa")  # dedup
    t = [x for x in glossary.all_terms(db) if x["term_id"] == tid][0]
    assert t["status"] == "approved" and t["cz"] == "Fů"
    assert t["accepted_alt"] == ["Fůa"]


def test_as_prompt_block_separates_candidate(tmp_path):
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Murphy", "aliases": [], "render": "keep"}],
        "places": [], "terms": []})
    glossary.add_candidate(db, "Nevernever", "Nikdykdy")
    block = glossary.as_prompt_block(db)
    assert "ZÁVAZNÉ" in block and "NÁVRHY" in block
    assert "Murphy" in block and "Nevernever" in block
