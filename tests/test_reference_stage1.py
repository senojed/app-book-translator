from src import reference


def _corpus(cz=None, en=None):
    cz = cz or {}
    en = en or {}
    return reference.Corpus(cz=cz, en=en, manifest={}, source_root="/x")


def test_cz_form_exact_whole_word_match():
    c = _corpus(cz={1: "Sešla se Bílá rada.", 2: "nic tu není"})
    ev = reference.count_cz_form(c, "Bílá rada")
    assert ev.hits == 1 and ev.books == [1]


def test_cz_form_does_not_match_inflection():
    """Přesná shoda skloňování netoleruje - vědomé rozhodnutí, `not_attested`
    je slabý signál, ne vyvrácení."""
    c = _corpus(cz={1: "Řekl to Bílé radě večer."})
    assert reference.count_cz_form(c, "Bílá rada").hits == 0


def test_cz_form_does_not_confuse_similar_words():
    c = _corpus(cz={1: "Byla to bída rana jako hrom."})
    assert reference.count_cz_form(c, "Bílá rada").hits == 0


def test_cz_form_is_case_insensitive():
    c = _corpus(cz={1: "bílá rada rozhodla"})
    assert reference.count_cz_form(c, "Bílá rada").hits == 1


def test_books_with_en_finds_surface_on_en_side():
    c = _corpus(en={1: "The White Council met.", 2: "nothing", 3: "White Council again"})
    assert reference.books_with_en(c, "White Council") == {1, 3}


def test_books_with_en_has_no_length_limit():
    """Délkové omezení má jen stupeň 0 (ochrana před českými homonymy).
    Kdyby ho měl i books_with_en, krátké povrchy by měly vždy prázdné E
    a nikdy by se nestaly `proposed`."""
    c = _corpus(en={1: "Ed arrived.", 2: "no one"})
    assert reference.books_with_en(c, "Ed") == {1}


def test_books_with_en_ignores_sentence_start_rule():
    c = _corpus(en={1: "Bob arrived first."})
    assert reference.books_with_en(c, "Bob") == {1}


def test_books_with_en_uses_word_boundary():
    c = _corpus(en={1: "Mabel was someone else."})
    assert reference.books_with_en(c, "Mab") == set()
