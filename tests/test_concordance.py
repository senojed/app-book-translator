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


# --- Pilot nálezy 2026-09-13 (polish-review live use) --------------------

G_WILL = [{"term_id": "term_billy", "canonical_en": "Billy Borden",
           "aliases": ["Will"], "cz": "Billy Borden", "accepted_alt": [],
           "status": "seeded", "type": "name"}]


def test_lowercase_common_word_does_not_match_capitalized_alias():
    """Billy Borden pilot bug - alias 'Will' je běžné anglické slovo.
    Case-insensitive shoda dřív způsobila falešný omission nález i pro
    kapitolu, kde postava vůbec není, jen se v EN textu vyskytlo obyčejné
    slovo 'will' ('focused my will')."""
    f = C.check_chapter("I focused my will and muttered a spell.",
                        "Soustredil jsem svou vuli a zamumlal kouzlo.",
                        G_WILL, [])
    assert not [x for x in f if x.get("term_id") == "term_billy"]


def test_capitalized_alias_mid_sentence_is_still_detected():
    """Skutečný výskyt jména uprostřed věty (capitalized, ne na začátku
    věty) se pořád má prohnat kontrolou - termín se examinuje a chybějící
    CZ protějšek se ohlásí jako omission."""
    f = C.check_chapter("I saw Will yesterday at the bar.",
                        "Nikoho jsem tam nevidel.", G_WILL, [])
    assert [x for x in f if x.get("term_id") == "term_billy"
           and x["type"] == "omission"]


def test_capitalized_alias_at_sentence_start_only_is_not_confident_match():
    """Jediný výskyt aliasu je na začátku věty (nejednoznačné - běžné
    anglické slovo je tam s velkým písmenem JEN kvůli pozici, ne proto,
    že je to jméno) - bez jiného výskytu se termín neexaminuje."""
    f = C.check_chapter("Will you come with me? I need help.",
                        "Nic o tom neni zminka.", G_WILL, [])
    assert not [x for x in f if x.get("term_id") == "term_billy"]


def test_find_form_occurrences_matches_declined_suffix_of_different_length():
    """Edinburgh pilot bug - 'Edinburghu' (lokál) se dřív neshodoval s
    kanonickým 'Edinburgh', protože nezávislé odseknutí stejného počtu
    znaků z KAŽDÉ strany dá jiný počet znaků kmene, když se slova liší
    délkou o skloňovanou příponu."""
    assert C.find_form_occurrences("Byl v Edinburghu vcera.", "Edinburgh") \
        == ["Edinburghu"]


def test_find_form_occurrences_root_len_from_canonical_not_candidate():
    """Kořenová délka se bere z KANONICKÉHO tvaru (form), ne nezávisle z
    kandidáta - 'dvůr'(4 zn.)->kořen 2 zn. 'dv', aplikováno na 'dvora'
    dá taky 'dv'."""
    assert C.find_form_occurrences("Videl jsem dvora.", "dvůr") == ["dvora"]


def test_declined_multiword_form_is_detected_in_check_chapter():
    """Red Court pilot bug - 'Rudého dvora' (genitiv, se samohláskovou
    alternací dvůr->dvora) se dřív neshodoval s kanonickým 'Rudý dvůr'.
    Musí projít BEZ nálezu úplně - ne jako omission, ale ani jako
    falešná inconsistency (viz test níž - druhá půlka stejného bugu)."""
    g = [{"term_id": "term_court", "canonical_en": "Red Court", "aliases": [],
          "cz": "Rudý dvůr", "accepted_alt": [], "status": "seeded",
          "type": "term"}]
    f = C.check_chapter("Members of the Red Court arrived.",
                        "Clenove Rudeho dvora dorazili.", g, [])
    assert not f


def test_declined_form_detected_by_find_form_occurrences_is_not_falsely_inconsistent():
    """Druhá půlka Edinburgh pilot bugu: `find_form_occurrences` teď
    'Edinburghu' SPRÁVNĚ detekuje jako výskyt kanonického 'Edinburgh'
    (viz test výš), ale `check_chapter`'s 'je to schválený tvar?' kontrola
    dřív porovnávala přes nezávisle odvozený `form_key` obou stran - se
    stejnou délkovou chybou, jen v jiné funkci. Bez opravy by se
    'Edinburghu' místo omission ohlásilo jako falešná inconsistency
    ('přeloženo jako Edinburghu, kanonicky je Edinburgh')."""
    g = [{"term_id": "term_edin", "canonical_en": "Edinburgh", "aliases": [],
          "cz": "Edinburgh", "accepted_alt": [], "status": "seeded",
          "type": "name"}]
    f = C.check_chapter("He traveled to Edinburgh.", "Odcestoval do Edinburghu.",
                        g, [])
    assert not f


def test_alias_mention_of_kept_name_is_not_omission():
    """Bjorn Bjorngunnarson pilot bug - postava oslovovaná jen aliasem
    ('Thorsen'), plný kanonický tvar se v kapitole vůbec neobjeví. Dřív
    to `_term_mentions` hlásilo jako omission, protože step 2 hledal jen
    kanonický `cz`/`accepted_alt`, nikdy aliasy - i když je jméno
    render=keep (cz == canonical_en), takže alias je platný český tvar."""
    g = [{"term_id": "term_bjorn", "canonical_en": "Bjorn Bjorngunnarson",
          "aliases": ["Thorsen"], "cz": "Bjorn Bjorngunnarson",
          "accepted_alt": [], "status": "seeded", "type": "name"}]
    f = C.check_chapter("Simmons and Thorsen burst into the room.",
                        "Simmons a Thorsen vtrhli do mistnosti.", g, [])
    assert not f


def test_unrelated_word_still_flagged_as_genuine_omission():
    """Regresní pojistka - fix nesmí přestat hlásit SKUTEČNĚ chybějící
    termín."""
    g = [{"term_id": "term_edin", "canonical_en": "Edinburgh", "aliases": [],
          "cz": "Edinburgh", "accepted_alt": [], "status": "seeded",
          "type": "name"}]
    f = C.check_chapter("He traveled to Edinburgh.", "Odjel uplne jinam.",
                        g, [])
    assert [x for x in f if x["type"] == "omission"]
