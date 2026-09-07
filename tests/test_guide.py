from src import guide


def test_relationship_key_is_order_independent():
    assert guide.relationship_key("Harry", "murphy") == guide.relationship_key("MURPHY", "harry")


def test_load_guide_missing_returns_empty_shape(tmp_path):
    g = guide.load_guide(str(tmp_path / "none.json"))
    assert g["characters"] == [] and g["rules"] == [] and g["style"] == ""
    assert g["terms"] == []


def test_merge_translates_draft_field_names_to_final(tmp_path):
    draft = {"characters": [{"name_en": "Bob", "suggested": "translate", "note": "x"}],
             "places": [{"name_en": "Chicago", "suggested_cz": "Chicago", "note": ""}],
             "terms": [{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": ""}],
             "relationships": [], "must_decide": [], "style_notes": "sarkastický"}
    g = {"characters": [], "places": [], "terms": [], "relationships": [],
         "style": "", "rules": []}
    m = guide.merge_draft_and_guide(draft, g)
    assert m["style"] == "sarkastický"
    assert m["terms"][0] == {"term_en": "Nevernever", "cz": "Nikdykdy", "note": ""} \
        or (m["terms"][0]["term_en"] == "Nevernever" and m["terms"][0]["cz"] == "Nikdykdy")
    assert m["places"][0]["cz"] == "Chicago"
    assert m["characters"][0]["render"] == "translate"


def test_load_guide_normalizes_partial_existing_file(tmp_path):
    import json
    p = str(tmp_path / "g.json")
    json.dump({"characters": [{"name_en": "X"}]}, open(p, "w", encoding="utf-8"))
    g = guide.load_guide(p)   # starý tvar bez terms/places/...
    assert g["terms"] == [] and g["places"] == [] and g["rules"] == []


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "g.json")
    guide.save_guide(p, {"characters": [{"name_en": "X"}], "places": [], "terms": [],
                         "relationships": [], "style": "s", "rules": ["r"]})
    assert guide.load_guide(p)["rules"] == ["r"]


def test_add_rule_dedups(tmp_path):
    p = str(tmp_path / "g.json")
    guide.add_rule(p, "pravidlo A")
    guide.add_rule(p, "pravidlo A")
    guide.add_rule(p, "pravidlo B")
    assert guide.load_guide(p)["rules"] == ["pravidlo A", "pravidlo B"]


def test_merge_keeps_human_decisions(tmp_path):
    draft = {"characters": [{"name_en": "Harry", "suggested": "keep", "note": "hrdina"},
                            {"name_en": "NewGuy", "suggested": "translate", "note": ""}],
             "places": [], "terms": [], "relationships": [], "must_decide": []}
    g = {"characters": [{"name_en": "Harry", "render": "keep", "cz": "Harry"}],
         "places": [], "terms": [], "relationships": [], "style": "", "rules": []}
    merged = guide.merge_draft_and_guide(draft, g)
    harry = [c for c in merged["characters"] if c["name_en"] == "Harry"][0]
    assert harry["render"] == "keep"  # lidské rozhodnutí zůstalo
    newguy = [c for c in merged["characters"] if c["name_en"] == "NewGuy"][0]
    assert newguy["render"] == "translate"  # předvyplněno z draft.suggested


def test_prompt_block_has_no_cz_pairs(tmp_path):
    g = {"characters": [{"name_en": "Foo", "render": "translate", "cz": "Fů"}],
         "places": [], "terms": [], "relationships": [], "style": "sarkastický", "rules": []}
    block = guide.guide_as_prompt_block(g)
    assert "sarkastický" in block
    assert "Fů" not in block  # cz páry jdou jen z glosáře
