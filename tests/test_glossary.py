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


def test_seed_does_not_overwrite_row_matched_only_by_alias(tmp_path):
    """Latentní chyba stávajícího kódu: _seed_one páruje i přes aliasy a pak
    přepíše canonical_en. `Billy Borden` má alias `Billy`, takže seed položky
    `Billy` by mu přepsal kanonický tvar."""
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Billy Borden", "aliases": ["Billy", "Will"], "render": "keep"}],
        "places": [], "terms": []})
    conflicts = glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Billy", "aliases": [], "render": "keep"}],
        "places": [], "terms": []})
    rows = glossary.all_terms(db)
    assert len(rows) == 1
    assert rows[0]["canonical_en"] == "Billy Borden"     # NEPŘEPSÁNO
    assert conflicts and conflicts[0]["incoming"] == "Billy"


def test_seed_returns_empty_list_when_no_conflict(tmp_path):
    db = _db(tmp_path)
    out = glossary.seed_from_guide(db, {"characters": [], "places": [],
                                        "terms": [{"term_en": "Foo", "cz": "Fů"}]})
    assert out == []


def test_canonical_match_wins_even_if_alias_row_has_lower_rowid(tmp_path):
    """Řádek `Foo` (alias `X`) má NIŽŠÍ rowid než řádek `X` (kanonický) - stav,
    který normálně `_seed_one`/`add_approved` nedovolí vytvořit (obojí hledá
    přes alias i kanonický název najednou), ale může vzniknout importem dat
    mimo tuhle vrstvu. SELECT bez ORDER BY vrátí `Foo` první. Jednoprůchodový
    kód s `break` na první shodě by nahlásil konflikt s `Foo` a řádek `X`
    (jednoznačnou kanonickou shodu, o řádek dál) by vůbec neuviděl."""
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Foo", "aliases": ["X"], "render": "keep"}], "places": [], "terms": []})
    # Vloženo přímo, mimo _seed_one/add_approved - simuluje import/migraci dat,
    # ne běžnou cestu (ta by kolizi odhalila hned při vkládání tohoto řádku).
    with state.connect(db) as conn:
        conn.execute(
            "INSERT INTO glossary (term_id,canonical_en,aliases,cz,accepted_alt,"
            "note,type,status) VALUES ('term_x','X','[]','Ix','[]','','term','approved')")
    conflicts = glossary.seed_from_guide(db, {"characters": [], "places": [],
        "terms": [{"term_en": "X", "cz": "Novy preklad"}]})
    assert conflicts == []                              # žádný konflikt - kanonická shoda vyhrála
    rows = {r["canonical_en"]: r for r in glossary.all_terms(db)}
    assert rows["Foo"]["aliases"] == ["X"]               # Foo nedotčen
    assert rows["X"]["cz"] == "Ix"                       # approved řádek se nepřepíše (viz status guard)


def test_seed_still_updates_row_matched_by_canonical(tmp_path):
    db = _db(tmp_path)
    glossary.seed_from_guide(db, {"characters": [], "places": [],
                                  "terms": [{"term_en": "Council", "cz": "Rada"}]})
    glossary.seed_from_guide(db, {"characters": [], "places": [],
                                  "terms": [{"term_en": "Council", "cz": "Koncil"}]})
    assert [t for t in glossary.all_terms(db)][0]["cz"] == "Koncil"


def test_seed_detects_collision_across_nfc_nfd_alias(tmp_path):
    """`.strip().lower()` by kanonicky stejný, ale jinak zapsaný Unicode text
    (NFC vs. NFD) nesloučil - guard by kolizi minul a vyrobil duplicitní
    řádek místo nahlášení konfliktu."""
    import unicodedata
    db = _db(tmp_path)
    nfd_alias = unicodedata.normalize("NFD", "Áine Borden")
    glossary.seed_from_guide(db, {"characters": [
        {"name_en": "Foo", "aliases": [nfd_alias], "render": "keep"}],
        "places": [], "terms": []})
    nfc_incoming = unicodedata.normalize("NFC", "Áine Borden")
    conflicts = glossary.seed_from_guide(db, {"characters": [
        {"name_en": nfc_incoming, "aliases": [], "render": "keep"}],
        "places": [], "terms": []})
    assert len(glossary.all_terms(db)) == 1        # nevznikl duplicitní řádek
    assert conflicts and conflicts[0]["existing_canonical"] == "Foo"
