import unicodedata
from src import textnorm
from src import guide


def test_normalize_key_nfc_and_casefold():
    # NFD zápis "á" (a + kombinující čárka) musí dát stejný klíč jako NFC
    nfd = unicodedata.normalize("NFD", "Bílá Rada")
    assert textnorm.normalize_key(nfd) == textnorm.normalize_key("Bílá Rada")
    assert textnorm.normalize_key("Bílá Rada") == "bílá rada"


def test_normalize_key_collapses_whitespace():
    assert textnorm.normalize_key("  White   Council \t\n") == "white council"


def test_normalize_key_handles_none_and_empty():
    assert textnorm.normalize_key("") == ""
    assert textnorm.normalize_key(None) == ""


def test_guide_normalize_unchanged():
    """relationship_key stojí na guide.normalize - nesmí se posunout,
    jinak by se rozešly klíče existujících vztahů."""
    assert guide.normalize("  Harry  ") == "harry"
    assert guide.relationship_key("Harry", "murphy") == "harry|murphy"


def test_config_has_reference_keys():
    import config
    for key in ("REFERENCE_DIR", "REFERENCE_PATH", "REFERENCE_CACHE_PATH",
                "MODEL_LEXICOGRAPHER", "MAX_TOKENS_LEXICOGRAPHER",
                "REFERENCE_BATCH_SIZE", "REFERENCE_MIN_HITS",
                "REFERENCE_MIN_BOOKS", "REFERENCE_MIN_CORPUS_BOOKS",
                "REFERENCE_COOCCUR_RATIO"):
        assert hasattr(config, key), key
    # oba ceníky - runtime cost guard vyžaduje input i output cenu
    assert config.PRICE_IN_PER_MTOK.get(config.MODEL_LEXICOGRAPHER) is not None
    assert config.PRICE_OUT_PER_MTOK.get(config.MODEL_LEXICOGRAPHER) is not None
