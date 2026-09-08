from src import reference


def _corpus(cz_texts):
    return reference.Corpus(cz={i + 1: t for i, t in enumerate(cz_texts)},
                            en={i + 1: "" for i in range(len(cz_texts))},
                            manifest={}, source_root="/x")


def test_lowercase_common_word_is_never_eligible():
    """`stole` = český lokativ slova stůl. Najde se, ale nesmí být způsobilé."""
    c = _corpus(["Kniha ležela na stole a vedle na stole byl hrnek."] * 6)
    ev = reference.count_en_surface(c, "stole")
    assert ev.hits > 0                 # důkaz existuje
    assert ev.confirm_eligible is False


def test_capitalized_name_is_eligible():
    c = _corpus(["Mab se usmála. Potkal Mab v lese."] * 3)
    ev = reference.count_en_surface(c, "Mab")
    assert ev.confirm_eligible is True


def test_case_insensitive_only_match_is_not_eligible():
    """Anglický povrch nesmí 'potvrdit' nesouvisející české slovo jinou velikostí."""
    c = _corpus(["Bylo to mab a zase mab uprostřed věty."] * 3)
    ev = reference.count_en_surface(c, "Mab")
    assert ev.hits > 0
    assert ev.confirm_eligible is False


def test_short_surface_needs_occurrence_outside_sentence_start():
    """Jméno, které je zároveň českým slovem, na začátku věty nic nedokazuje."""
    only_start = _corpus(["Bob je luštěnina. Bob roste na poli."] * 3)
    assert reference.count_en_surface(only_start, "Bob").confirm_eligible is False
    mid = _corpus(["Potkal jsem Boba. Viděl jsem Bob uprostřed."] * 3)
    assert reference.count_en_surface(mid, "Bob").confirm_eligible is True


def test_eligibility_needs_one_occurrence_meeting_all_conditions():
    """Podmínky musí splnit TENTÝŽ výskyt, ne každá jiný."""
    # 'Mab' správně psané jen na začátku věty; uprostřed jen 'mab'
    split = _corpus(["Mab přišla. Byl tam mab uprostřed věty."] * 3)
    assert reference.count_en_surface(split, "Mab").confirm_eligible is False
    # jeden výskyt splňující obojí naráz
    both = _corpus(["Přišla Mab uprostřed věty."] * 3)
    assert reference.count_en_surface(both, "Mab").confirm_eligible is True


def test_one_and_two_char_surfaces_are_not_searched():
    c = _corpus(["Ed a Ed a zase Ed."] * 3)
    ev = reference.count_en_surface(c, "Ed")
    assert ev.hits == 0 and ev.confirm_eligible is False


def test_hyphen_and_apostrophe_stay_part_of_the_query():
    c = _corpus(["Byl to Za-Lord osobně. A Listens-to-Wind mlčel."] * 3)
    assert reference.count_en_surface(c, "Za-Lord").hits > 0
    assert reference.count_en_surface(c, "Listens-to-Wind").hits > 0


def test_word_boundary_prevents_substring_match():
    c = _corpus(["Mabel byla jiná osoba."] * 3)
    assert reference.count_en_surface(c, "Mab").hits == 0


def test_alias_hits_are_union_not_sum():
    """`Dresden` uvnitř `Harry Dresden` se nesmí započítat dvakrát."""
    c = _corpus(["Harry Dresden dorazil pozdě."] * 2)
    ev = reference.count_en_surface(c, "Harry Dresden", aliases=["Dresden"])
    assert ev.hits == 2                      # dva díly, jeden výskyt v každém
    assert set(ev.matched_forms) == {"Harry Dresden", "Dresden"}


def test_per_form_tracks_each_alias_separately():
    c = _corpus(["Harry Dresden a pak jen Dresden."] * 3)
    ev = reference.count_en_surface(c, "Harry Dresden", aliases=["Dresden", "Hoss"])
    assert ev.per_form["Harry Dresden"]["hits"] == 3
    assert ev.per_form["Dresden"]["hits"] == 6      # i uvnitř celého jména
    assert ev.per_form["Hoss"]["hits"] == 0


def test_books_lists_only_books_with_hits():
    c = reference.Corpus(cz={1: "Mab tady byla uprostřed.", 2: "nic", 3: "Mab zase uprostřed."},
                         en={}, manifest={}, source_root="/x")
    assert reference.count_en_surface(c, "Mab").books == [1, 3]


def test_occurrence_after_doc_sep_counts_as_sentence_start():
    """Výskyt hned po DOC_SEP je začátek dokumentu = začátek věty, takže sám
    o sobě způsobilost nedá u krátkého (< 5 znaků) povrchu."""
    text = "text " + reference.DOC_SEP + "Bob na začátku dokumentu."
    c = _corpus([text] * 3)
    assert reference.count_en_surface(c, "Bob").confirm_eligible is False


def test_occurrence_after_doc_sep_plus_mid_sentence_hit_is_eligible():
    text = ("text " + reference.DOC_SEP + "Bob na začátku. Potkal jsem Bob uprostřed.")
    c = _corpus([text] * 3)
    assert reference.count_en_surface(c, "Bob").confirm_eligible is True


def test_punctuation_without_following_space_is_not_sentence_start():
    """"x.Mab" (interpunkce bez mezery, typický překlep) NENÍ začátek věty -
    je to tedy výskyt MIMO začátek věty, což je přesně to, co krátký povrch
    (< 5 znaků) potřebuje pro způsobilost. Bez opravy (mezera za interpunkcí
    se nekontrolovala) by kód "x.Mab" mylně považoval ZA začátek věty, a
    způsobilost by tak byla False místo True."""
    c = _corpus(["Věta končí u x.Mab a pokračuje dál."] * 3)
    assert reference.count_en_surface(c, "Mab").confirm_eligible is True


def test_digit_leading_surface_is_never_eligible():
    """Dřívější kontrola `surface[:1].islower()` u číslice vrací False (číslice
    není "malá"), takže by povrch začínající číslicí prošel jako vlastní
    jméno. Musí platit `not surface[:1].isupper()`."""
    c = _corpus(["Bylo tam 3Eye uprostřed věty, pak zas 3Eye."] * 3)
    assert reference.count_en_surface(c, "3Eye").confirm_eligible is False


def test_nfd_query_matches_nfc_corpus_text():
    """Korpus je vždy NFC (viz _load_side v Tasku 3). Dotaz ale může přijít
    v NFD (draft od scouta, ruční editace) - musí se normalizovat dřív, než
    se z něj postaví regex, jinak kanonicky stejný text neprojde."""
    import unicodedata
    c = _corpus(["Potkal jsem Áine uprostřed věty."] * 3)   # NFC (Python literál)
    nfd_query = unicodedata.normalize("NFD", "Áine")
    ev = reference.count_en_surface(c, nfd_query)
    assert ev.hits > 0 and ev.confirm_eligible is True
