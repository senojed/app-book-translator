from src import concordance as C


G_KEEP = [{"term_id": "term_harry", "canonical_en": "Harry", "aliases": [],
           "cz": "Harry", "accepted_alt": [], "status": "seeded", "type": "name"}]
G_TRANS = [{"term_id": "term_council", "canonical_en": "White Council",
            "aliases": [], "cz": "Bílá rada", "accepted_alt": [],
            "status": "approved", "type": "term"}]


def test_leak_flags_untranslated_term_that_should_be_translated():
    f = C.check_chapter("The White Council met.", "White Council se sešla.",
                        G_TRANS, [])
    leaks = [x for x in f if x["type"] == "leak"]
    assert leaks and leaks[0]["action"] == "revise"


def test_keep_term_in_cz_is_not_a_leak():
    f = C.check_chapter("Harry went home.", "Harry šel domů.", G_KEEP, [])
    assert not [x for x in f if x["type"] == "leak"]


def test_inconsistency_on_approved_is_revise():
    f = C.check_chapter("The White Council.", "Rada bílých.", G_TRANS,
                        [{"term_id": "term_council", "cz_as_used": "Rada bílých"}])
    inc = [x for x in f if x["type"] == "inconsistency"]
    assert inc and inc[0]["action"] == "revise"


def test_inconsistency_on_candidate_is_question():
    g = [{"term_id": "cand_grey", "canonical_en": "Grey Cloak", "aliases": [],
          "cz": "Šedý plášť", "accepted_alt": [], "status": "candidate", "type": "term"}]
    # translator ve stejné kapitole termín vyrenderoval úplně jinak (jiný kmen)
    f = C.check_chapter("Grey Cloak spoke.", "Popelář promluvil.", g,
                        [{"term_id": "cand_grey", "cz_as_used": "Popelář"}])
    inc = [x for x in f if x["type"] == "inconsistency"]
    assert inc and inc[0]["action"] == "question"
    assert inc[0]["term_id"] == "cand_grey"


def test_build_mentions_records_omission_as_null():
    m = C.build_mentions("Harry and Bob spoke.", "Harry promluvil.",
                         G_KEEP + [{"term_id": "term_bob", "canonical_en": "Bob",
                                    "aliases": [], "cz": "Bob", "accepted_alt": [],
                                    "status": "seeded", "type": "name"}], [])
    bob = [x for x in m if x.term_id == "term_bob"]
    assert bob and bob[0].cz_form is None and bob[0].source == "omission"


def test_check_drift_groups_divergent_forms():
    mentions = [
        {"term_id": "t1", "cz_form": "Bílá rada", "chapter_idx": 1},
        {"term_id": "t1", "cz_form": "Bílá radě", "chapter_idx": 2},   # jen skloňování
        {"term_id": "t1", "cz_form": "Rada bílých", "chapter_idx": 5}, # jiný kmen
    ]
    drifts = C.check_drift(mentions)
    assert len(drifts) == 1
    assert set(drifts[0]["kapitoly"]) == {1, 2, 5}


def test_check_drift_no_finding_for_simple_inflection():
    mentions = [
        {"term_id": "t1", "cz_form": "rada", "chapter_idx": 1},
        {"term_id": "t1", "cz_form": "radu", "chapter_idx": 2},
        {"term_id": "t1", "cz_form": "radě", "chapter_idx": 3},
    ]
    assert C.check_drift(mentions) == []


def test_form_key_collapses_simple_inflection_not_different_stems():
    assert C.form_key("Bílá radě") == C.form_key("Bílá rada")
    assert C.form_key("Rada bílých") != C.form_key("Bílá rada")


def test_alias_of_kept_name_is_not_inconsistency():
    """Jméno s render='keep' (cz == canonical_en doslova) - zkrácený tvar
    z aliasů ('Morgan' u 'Donald Morgan') je v přirozené próze běžný po prvním
    uvedení. Bez tohohle by KAŽDÝ výskyt zkráceného jména hlásil critical
    inconsistency, přestože jde o stejné jméno, jen zkrácené (pilot nález)."""
    g = [{"term_id": "term_morgan", "canonical_en": "Donald Morgan",
          "aliases": ["Morgan", "Warden Morgan"], "cz": "Donald Morgan",
          "accepted_alt": [], "status": "seeded", "type": "name"}]
    f = C.check_chapter("Donald Morgan arrived. Morgan left.",
                        "Donald Morgan dorazil. Morgan odešel.", g,
                        [{"term_id": "term_morgan", "cz_as_used": "Morgan"}])
    assert not [x for x in f if x["type"] == "inconsistency"]


def test_alias_of_translated_name_still_flags_inconsistency():
    """Alias smí projít jen u NEPŘELOŽENÉHO jména (cz == canonical_en) - u
    přeloženého jména je anglický alias pořád jen anglický tvar, ne platný
    český ekvivalent, a nesmí tiše obejít kontrolu."""
    g = [{"term_id": "term_morgan", "canonical_en": "Donald Morgan",
          "aliases": ["Morgan"], "cz": "Donald Moták",
          "accepted_alt": [], "status": "seeded", "type": "name"}]
    f = C.check_chapter("Donald Morgan arrived.", "Morgan dorazil.", g,
                        [{"term_id": "term_morgan", "cz_as_used": "Morgan"}])
    assert [x for x in f if x["type"] == "inconsistency"]
