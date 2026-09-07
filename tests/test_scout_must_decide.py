from src.agents import scout


def test_relationship_scope_key_normalized_to_pipe_format():
    """Scout si vymýšlí 'Harry-Ebenezar', kód všude jinde používá 'a|b'.
    Bez srovnání se dvojice nespáruje a zápis odpovědi rozbije jméno."""
    rels = [{"a": "Harry", "b": "Ebenezar", "observed": "", "suggested": "vyka"}]
    md = [{"kind": "relationship", "scope_key": "Harry-Ebenezar",
           "question": "?", "default": "tyka"}]
    out = scout.normalize_must_decide(md, rels)
    assert out[0]["scope_key"] == "ebenezar|harry"


def test_hyphenated_name_is_not_split():
    rels = [{"a": "Harry", "b": "Listens-to-Wind", "observed": "", "suggested": "vyka"}]
    md = [{"kind": "relationship", "scope_key": "Harry-Listens-to-Wind",
           "question": "?", "default": "vyka"}]
    out = scout.normalize_must_decide(md, rels)
    assert out[0]["scope_key"] == "harry|listens-to-wind"


def test_duplicate_pair_is_deduped_after_normalization():
    rels = [{"a": "Harry", "b": "Ebenezar", "observed": "", "suggested": "vyka"}]
    md = [{"kind": "relationship", "scope_key": "Harry-Ebenezar", "question": "a",
           "default": "tyka"},
          {"kind": "relationship", "scope_key": "ebenezar|harry", "question": "b",
           "default": "vyka"}]
    out = scout.normalize_must_decide(md, rels)
    assert len(out) == 1


def test_unknown_pair_is_left_alone():
    """Nedá-li se dvojice dohledat, klíč neměníme - lepší než ho zkomolit."""
    md = [{"kind": "relationship", "scope_key": "Nekdo-Neznamy", "question": "?",
           "default": ""}]
    out = scout.normalize_must_decide(md, [])
    assert out[0]["scope_key"] == "Nekdo-Neznamy"


def test_non_relationship_kinds_untouched():
    md = [{"kind": "term", "scope_key": "White Council", "question": "?", "default": "x"}]
    out = scout.normalize_must_decide(md, [])
    assert out[0]["scope_key"] == "White Council"


def test_merge_applies_normalization():
    p = {"characters": [], "places": [], "terms": [],
         "relationships": [{"a": "Harry", "b": "Ebenezar", "observed": "",
                            "suggested": "vyka"}],
         "style_notes": "",
         "must_decide": [{"kind": "relationship", "scope_key": "Harry-Ebenezar",
                          "question": "?", "default": "tyka"}]}
    m = scout.merge_scout_facts([p])
    assert m["must_decide"][0]["scope_key"] == "ebenezar|harry"
