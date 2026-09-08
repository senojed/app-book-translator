import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import check_draft


def _draft(**over):
    base = {"characters": [], "places": [], "terms": [], "relationships": [],
            "style_notes": "", "must_decide": []}
    base.update(over)
    return base


def test_detects_compound_surface():
    d = _draft(terms=[{"term_en": "White Court / Red Court", "suggested_cz": "", "note": ""}])
    issues = check_draft.find_issues(d)
    assert [i["surface"] for i in issues["compound"]] == ["White Court / Red Court"]


def test_detects_or_separator_case_insensitive():
    d = _draft(terms=[{"term_en": "veil OR veiling spell", "suggested_cz": "", "note": ""}])
    assert check_draft.find_issues(d)["compound"]


def test_detects_alias_collision():
    d = _draft(characters=[
        {"name_en": "Morgan", "aliases": [], "suggested": "keep", "note": ""},
        {"name_en": "Donald Morgan", "aliases": ["Morgan"], "suggested": "keep", "note": ""}])
    coll = check_draft.find_issues(d)["alias_collision"]
    assert [c["surface"] for c in coll] == ["Morgan"]


def test_detects_parenthesized_surface():
    d = _draft(terms=[{"term_en": "Warden(s)", "suggested_cz": "", "note": ""}])
    assert check_draft.find_issues(d)["parenthesized"]


def test_detects_cross_section_homonym():
    d = _draft(characters=[{"name_en": "Demonreach", "aliases": [], "suggested": "keep", "note": ""}],
               places=[{"name_en": "Demonreach", "suggested_cz": "", "note": ""}])
    assert check_draft.find_issues(d)["cross_section"]


def test_detects_weak_alias():
    d = _draft(characters=[{"name_en": "Ebenezar McCoy", "aliases": ["sir", "Eb"],
                            "suggested": "keep", "note": ""}])
    weak = {w["detail"] for w in check_draft.find_issues(d)["weak_alias"]}
    assert weak == {"sir", "Eb"}   # 'sir' je v seznamu rolí, 'Eb' má <= 3 znaky


def test_style_scope_key_is_not_an_issue():
    """Styl není kolekce klíčovaných položek - jeho odpověď jde do rules."""
    d = _draft(must_decide=[{"kind": "style", "scope_key": "nicknames",
                             "question": "?", "default": ""}])
    assert check_draft.find_issues(d)["bad_scope_key"] == []


def test_detects_scope_key_pointing_nowhere():
    d = _draft(terms=[{"term_en": "Nevernever", "suggested_cz": "", "note": ""}],
               must_decide=[{"kind": "term", "scope_key": "the Nevernever",
                             "question": "?", "default": ""}])
    assert check_draft.find_issues(d)["bad_scope_key"]


def test_detects_relationship_with_slash_and_short_form():
    d = _draft(characters=[{"name_en": "Ebenezar McCoy", "aliases": [], "suggested": "keep", "note": ""},
                           {"name_en": "Harry Dresden", "aliases": [], "suggested": "keep", "note": ""}],
               relationships=[{"a": "Harry", "b": "Will/Georgia", "suggested": "tyka"},
                              {"a": "Harry", "b": "Ebenezar", "suggested": "vyka"}])
    issues = check_draft.find_issues(d)
    assert issues["bad_relationship"]      # lomítko ve jméně
    assert issues["short_relationship"]    # 'Ebenezar' není kanonické jméno


def test_detects_duplicate_canonical_name_in_one_section():
    """Táž entita vedená scoutem dvakrát pod stejným klíčem - bez detekce by
    reference_mine.resolve() vyrobil dvě položky se stejným id."""
    d = _draft(terms=[{"term_en": "Nevernever", "suggested_cz": "", "note": ""},
                      {"term_en": "  nevernever ", "suggested_cz": "", "note": ""}])
    dup = check_draft.find_issues(d)["duplicate_key"]
    assert dup and dup[0]["section"] == "terms"


def test_detects_duplicate_relationship_pair():
    d = _draft(characters=[{"name_en": "Harry Dresden", "aliases": [], "suggested": "keep", "note": ""},
                           {"name_en": "Karrin Murphy", "aliases": [], "suggested": "keep", "note": ""}],
               relationships=[{"a": "Harry Dresden", "b": "Karrin Murphy", "suggested": "tyka"},
                              {"a": "Karrin Murphy", "b": "Harry Dresden", "suggested": "vyka"}])
    assert check_draft.find_issues(d)["duplicate_relationship"]


def test_detects_relationship_scope_key_not_matching_relationship_key():
    """Obě jména jsou kanonická a v char_keys - selhat smí JEN na tom, že
    pořadí neodpovídá guide.relationship_key (ta třídí abecedně)."""
    d = _draft(characters=[{"name_en": "Harry Dresden", "aliases": [], "suggested": "keep", "note": ""},
                           {"name_en": "Karrin Murphy", "aliases": [], "suggested": "keep", "note": ""}],
               must_decide=[{"kind": "relationship",
                             "scope_key": "Karrin Murphy|Harry Dresden",
                             "question": "?", "default": ""}])
    assert check_draft.find_issues(d)["bad_scope_key"]


def test_clean_draft_has_no_issues():
    d = _draft(characters=[{"name_en": "Harry Dresden", "aliases": ["Dresden"],
                            "suggested": "keep", "note": ""}],
               terms=[{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
               relationships=[],
               must_decide=[{"kind": "term", "scope_key": "Nevernever",
                             "question": "?", "default": ""}])
    assert all(v == [] for v in check_draft.find_issues(d).values())
