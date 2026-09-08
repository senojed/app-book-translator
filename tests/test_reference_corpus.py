import os
import pytest
from src import reference


def _fake_epub(tmp_path, subdir, name, text):
    """Vyrobí minimální EPUB, který ingest.load_book přečte."""
    import warnings
    warnings.filterwarnings("ignore")
    from ebooklib import epub
    d = tmp_path / subdir
    d.mkdir(parents=True, exist_ok=True)
    b = epub.EpubBook()
    b.set_identifier("id"); b.set_title("T"); b.set_language("en")
    c = epub.EpubHtml(title="Ch", file_name="c1.xhtml", uid="c1")
    c.content = f"<h1>Ch</h1><p>{text}</p>"
    b.add_item(c); b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    b.spine = [c]
    p = str(d / name)
    epub.write_epub(p, b)
    return p


def _corpus_root(tmp_path, pairs):
    """pairs = [(cislo, en_text, cz_text)]"""
    for num, en, cz in pairs:
        _fake_epub(tmp_path, "EN", f"Book (#{num:02d}) title.epub", en)
        _fake_epub(tmp_path, "CZ", f"{num} nazev - Jim Butcher.epub", cz)
    return str(tmp_path)


def test_load_corpus_pairs_books_by_number(tmp_path):
    long_en = "Harry Dresden walked into the room. " * 30
    long_cz = "Harry Dresden vesel do mistnosti. " * 30
    root = _corpus_root(tmp_path, [(1, long_en, long_cz), (2, long_en, long_cz),
                                   (3, long_en, long_cz)])
    c = reference.load_corpus(root)
    assert sorted(c.cz) == [1, 2, 3]
    assert sorted(c.en) == [1, 2, 3]
    assert "Harry Dresden" in c.cz[1]
    assert c.source_root == root


def test_load_corpus_rejects_too_small_corpus(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en)])
    with pytest.raises(ValueError, match="spárovan"):
        reference.load_corpus(root)


def test_load_corpus_detects_file_changed_during_loading(tmp_path, monkeypatch):
    """Manifest se bere PŘED i PO parsování a musí sedět - `_load_side`
    (čtení desítek EPUBů) chvíli trvá; změní-li se soubor uprostřed (jiný
    proces, re-export), load_corpus() to musí odhalit, ne tiše uložit
    manifest, který k vytěženému textu už neodpovídá."""
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    real_load_side = reference._load_side
    def flaky(root_, side):
        result = real_load_side(root_, side)
        if side == "CZ":
            # simuluje změnu souboru UPROSTŘED načítání (jiný proces)
            with open(os.path.join(root_, "CZ", "1 nazev - Jim Butcher.epub"), "ab") as f:
                f.write(b"x")
        return result
    monkeypatch.setattr(reference, "_load_side", flaky)
    with pytest.raises(ValueError, match="změnily"):
        reference.load_corpus(root)


def test_load_corpus_rejects_duplicate_book_number(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    # druhý soubor se stejným číslem na CZ straně
    _fake_epub(tmp_path, "CZ", "1 jiny nazev.epub", long_en)
    with pytest.raises(ValueError, match="[Dd]uplicit"):
        reference.load_corpus(root)


def test_unpaired_book_drops_both_sides(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    _fake_epub(tmp_path, "EN", "Book (#09) solo.epub", long_en)   # bez CZ protějšku
    c = reference.load_corpus(root)
    assert 9 not in c.en and 9 not in c.cz


def test_documents_joined_with_separator_and_without_titles(tmp_path):
    long_en = "Some sentence about things. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    c = reference.load_corpus(root)
    assert "Ch" not in c.en[1].split(".")[0]   # nadpis dokumentu se nepřipojuje


def test_manifest_and_cache_roundtrip(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    c = reference.load_corpus(root)
    cache = str(tmp_path / "cache.json")
    reference.save_cache(c, cache)
    back = reference.load_cache(cache, root)
    assert back is not None and back.cz.keys() == c.cz.keys()


def test_cache_invalidated_when_file_changes(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    cache = str(tmp_path / "cache.json")
    reference.save_cache(reference.load_corpus(root), cache)
    _fake_epub(tmp_path, "CZ", "1 nazev - Jim Butcher.epub", long_en + " navic")
    assert reference.load_cache(cache, root) is None


def test_cache_invalidated_for_different_root(tmp_path):
    long_en = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long_en, long_en), (2, long_en, long_en),
                                   (3, long_en, long_en)])
    cache = str(tmp_path / "cache.json")
    reference.save_cache(reference.load_corpus(root), cache)
    assert reference.load_cache(cache, str(tmp_path / "jinde")) is None


def test_cache_with_malformed_structure_returns_none(tmp_path):
    """Platný JSON, ale se špatným tvarem (cz jako list místo dict) - musí
    dát None, ne KeyError/ValueError tracebackem."""
    import json as _json
    root = _corpus_root(tmp_path, [(1, "text " * 40, "text " * 40),
                                   (2, "text " * 40, "text " * 40),
                                   (3, "text " * 40, "text " * 40)])
    cache = str(tmp_path / "cache.json")
    _json.dump({"schema_version": reference.SCHEMA_VERSION,
               "source_root": os.path.abspath(root),
               "manifest": reference.build_manifest(root),
               "cz": ["not", "a", "dict"], "en": {}},
              open(cache, "w", encoding="utf-8"))
    assert reference.load_cache(cache, root) is None


def test_cache_with_non_numeric_key_returns_none(tmp_path):
    import json as _json
    root = _corpus_root(tmp_path, [(1, "text " * 40, "text " * 40),
                                   (2, "text " * 40, "text " * 40),
                                   (3, "text " * 40, "text " * 40)])
    cache = str(tmp_path / "cache.json")
    _json.dump({"schema_version": reference.SCHEMA_VERSION,
               "source_root": os.path.abspath(root),
               "manifest": reference.build_manifest(root),
               "cz": {"neni-cislo": "text"}, "en": {}},
              open(cache, "w", encoding="utf-8"))
    assert reference.load_cache(cache, root) is None


def test_cache_with_mismatched_cz_en_keys_returns_none(tmp_path, monkeypatch):
    """Manifest se počítá jen z os.stat souborů, ne z obsahu cache - platná
    cache se sedícím manifestem, ale nespárovanými čísly dílů (cz má jiná
    čísla než en) by jinak obešla párování, které dělá load_corpus()."""
    import json as _json
    root = _corpus_root(tmp_path, [(1, "text " * 40, "text " * 40),
                                   (2, "text " * 40, "text " * 40),
                                   (3, "text " * 40, "text " * 40)])
    cache = str(tmp_path / "cache.json")
    _json.dump({"schema_version": reference.SCHEMA_VERSION,
               "source_root": os.path.abspath(root),
               "manifest": reference.build_manifest(root),
               "cz": {"1": "a", "2": "b", "3": "c"},
               "en": {"1": "a", "2": "b", "9": "c"}},   # 3 vs 9 - nespárováno
              open(cache, "w", encoding="utf-8"))
    assert reference.load_cache(cache, root) is None


def test_cache_below_minimum_corpus_books_returns_none(tmp_path):
    """Cache se sedícím manifestem, ale míň páry, než dovoluje výchozí
    REFERENCE_MIN_CORPUS_BOOKS (3), by obešla kontrolu minima v load_corpus()."""
    import json as _json
    root = _corpus_root(tmp_path, [(1, "text " * 40, "text " * 40),
                                   (2, "text " * 40, "text " * 40),
                                   (3, "text " * 40, "text " * 40)])
    cache = str(tmp_path / "cache.json")
    _json.dump({"schema_version": reference.SCHEMA_VERSION,
               "source_root": os.path.abspath(root),
               "manifest": reference.build_manifest(root),
               "cz": {"1": "a", "2": "b"}, "en": {"1": "a", "2": "b"}},
              open(cache, "w", encoding="utf-8"))
    assert reference.load_cache(cache, root) is None


def test_load_cache_returns_none_on_oserror_from_build_manifest(tmp_path, monkeypatch):
    """Poslední krok load_cache() volá build_manifest(root) znovu, aby
    porovnal aktuální stav disku - selže-li (soubor mezitím zmizel,
    oprávnění), bere se to jako "cache neplatná", ne nezachycená výjimka.
    Korpus se sestaví PŘED monkeypatchem, aby patch zasáhl jen to volání
    uvnitř load_cache()."""
    # "text " * 40 (200 znaků) je pod ingest.MIN_CHAPTER_CHARS (500) a load_book
    # by kapitolu odmítl - na rozdíl od ostatních testů v souboru tenhle
    # skutečně volá load_corpus(), takže text musí být dost dlouhý.
    long = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long, long), (2, long, long), (3, long, long)])
    cache = str(tmp_path / "cache.json")
    reference.save_cache(reference.load_corpus(root), cache)
    def boom(r):
        raise OSError("soubor zmizel")
    monkeypatch.setattr(reference, "build_manifest", boom)
    assert reference.load_cache(cache, root) is None


def test_load_side_failure_drops_whole_book_before_minimum_check(tmp_path):
    """Selže-li načtení jedné strany dvojice (poškozený EPUB), vypadne celý
    díl a teprve POTOM se kontroluje minimum spárovaných dílů. Čtyři páry,
    ne tři - po odpadnutí jednoho musí zbýt aspoň REFERENCE_MIN_CORPUS_BOOKS
    (3), jinak by load_corpus() zvedl ValueError místo úspěšného výsledku."""
    long = "text here and there. " * 40
    root = _corpus_root(tmp_path, [(1, long, long), (2, long, long),
                                   (3, long, long), (4, long, long)])
    # CZ strana dílu 1 je poškozený soubor, ne platný EPUB
    with open(os.path.join(root, "CZ", "1 nazev - Jim Butcher.epub"), "wb") as f:
        f.write(b"not a real epub")
    c = reference.load_corpus(root)
    assert 1 not in c.cz and 1 not in c.en          # celý díl vypadl
    assert sorted(c.cz) == [2, 3, 4]                 # zbylé tři pořád stačí na minimum
