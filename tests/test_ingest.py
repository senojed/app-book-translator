import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import ingest


def test_split_scenes_short_text_stays_whole():
    text = "slovo " * 100
    assert ingest.split_into_scenes(text, 3500) == [text]


def test_split_scenes_by_separator():
    a = "veta jedna. " * 400
    b = "veta dva. " * 400
    parts = ingest.split_into_scenes(a + "\n* * *\n" + b, 1000)
    assert len(parts) == 2
    assert parts[0].startswith("veta jedna")


def test_split_scenes_too_fragmented_returns_whole():
    text = "\n\n".join(f"odstavec {i} " * 50 for i in range(30))
    assert ingest.split_into_scenes(text, 200) == [text]


def test_load_txt_no_headings_single_chapter(tmp_path):
    p = tmp_path / "k.txt"
    p.write_text("Text bez nadpisu. " * 50, encoding="utf-8")
    chs = ingest.load_book(str(p))
    assert len(chs) == 1
    assert "segmentace" in chs[0].title.lower()


def test_load_txt_splits_on_chapter_headings(tmp_path):
    body = "Radek textu. " * 40 + "\n"
    p = tmp_path / "k.txt"
    p.write_text(f"Chapter 1\n{body}Chapter 2\n{body}Chapter 3\n{body}", encoding="utf-8")
    chs = ingest.load_book(str(p))
    assert [c.index for c in chs] == [1, 2, 3]
    assert chs[0].title == "Chapter 1"


def test_load_epub_uses_spine_order(tmp_path):
    import ebooklib
    from ebooklib import epub
    b = epub.EpubBook()
    b.set_identifier("id"); b.set_title("T"); b.set_language("en")
    long = "Dost dlouhy text kapitoly aby preskocil minimum. " * 20
    c3 = epub.EpubHtml(title="Three", file_name="c3.xhtml", uid="c3"); c3.content = f"<h1>Three</h1><p>{long}</p>"
    c1 = epub.EpubHtml(title="One", file_name="c1.xhtml", uid="c1"); c1.content = f"<h1>One</h1><p>{long}</p>"
    c2 = epub.EpubHtml(title="Two", file_name="c2.xhtml", uid="c2"); c2.content = f"<h1>Two</h1><p>{long}</p>"
    for c in (c3, c1, c2): b.add_item(c)
    b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    b.spine = [c1, c2, c3]
    p = str(tmp_path / "t.epub")
    epub.write_epub(p, b)
    chs = ingest.load_book(p)
    assert [c.title for c in chs] == ["One", "Two", "Three"]


def test_load_book_rejects_unknown_extension(tmp_path):
    p = tmp_path / "k.pdf"; p.write_text("x", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        ingest.load_book(str(p))
