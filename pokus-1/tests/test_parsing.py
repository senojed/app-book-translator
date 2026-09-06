"""
Testy čistě logických částí (bez volání API):
- translator._parse - rozdělení odpovědi modelu na překlad + metadata
- ingest.split_into_scenes - dělení dlouhé kapitoly na scény
- ingest._load_txt - segmentace TXT knihy na kapitoly

Spuštění: python -m pytest tests/   (nebo: python tests/test_parsing.py)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.translator import _parse
from src import ingest


def test_parse_normal():
    raw = (
        "===PREKLAD===\n"
        "Ahoj svete.\n\nDruhy odstavec.\n"
        "===METADATA===\n"
        '{"new_terms": [{"term_en": "Foo", "cz": "Fu"}], "open_questions": ["jak sklonovat Foo?"]}'
    )
    r = _parse(raw)
    assert r["translation"] == "Ahoj svete.\n\nDruhy odstavec."
    assert r["new_terms"][0]["cz"] == "Fu"
    assert r["open_questions"] == ["jak sklonovat Foo?"]


def test_parse_without_leading_marker():
    r = _parse('Ahoj.\n===METADATA===\n{"new_terms": [], "open_questions": []}')
    assert r["translation"] == "Ahoj."


def test_parse_broken_metadata_keeps_translation():
    r = _parse("===PREKLAD===\nText tady.\n===METADATA===\n{tohle neni json")
    assert r["translation"] == "Text tady."
    assert r["new_terms"] == []
    assert r["open_questions"] == []


def test_parse_no_metadata_at_all():
    r = _parse("Jen holy preklad bez niceho.")
    assert r["translation"] == "Jen holy preklad bez niceho."


def test_parse_metadata_with_code_fence():
    raw = (
        "===PREKLAD===\nX.\n===METADATA===\n"
        '```json\n{"new_terms": [], "open_questions": ["q"]}\n```'
    )
    r = _parse(raw)
    assert r["open_questions"] == ["q"]


def test_parse_empty_translation_raises():
    try:
        _parse("===PREKLAD===\n\n===METADATA===\n{}")
    except ValueError:
        return
    raise AssertionError("mela byt vyjimka ValueError")


def test_split_scenes_short_text_stays_whole():
    text = "slovo " * 100
    assert ingest.split_into_scenes(text, word_threshold=3500) == [text]


def test_split_scenes_by_separator():
    a = "veta jedna. " * 400   # ~1200 slov
    b = "veta dva. " * 400
    text = a + "\n* * *\n" + b
    parts = ingest.split_into_scenes(text, word_threshold=1000)
    assert len(parts) == 2
    assert parts[0].startswith("veta jedna")
    assert parts[1].startswith("veta dva")


def test_split_scenes_too_fragmented_returns_whole():
    # spousta kratkych odstavcu bez oddelovace scen -> radsi cely blok
    text = "\n\n".join(f"odstavec {i} " * 50 for i in range(30))
    parts = ingest.split_into_scenes(text, word_threshold=200)
    assert parts == [text]


def test_load_txt_no_headings_single_chapter(tmp_path):
    p = tmp_path / "kniha.txt"
    p.write_text("Text bez jakychkoliv nadpisu kapitol. " * 50, encoding="utf-8")
    chapters = ingest._load_txt(str(p))
    assert len(chapters) == 1
    assert "segmentace" in chapters[0].title.lower()


def test_load_txt_splits_on_chapter_headings(tmp_path):
    body = "Radek textu tady. " * 40 + "\n"
    content = "Chapter 1\n" + body + "Chapter 2\n" + body + "Chapter 3\n" + body
    p = tmp_path / "kniha.txt"
    p.write_text(content, encoding="utf-8")
    chapters = ingest._load_txt(str(p))
    assert [c.index for c in chapters] == [1, 2, 3]
    assert chapters[0].title == "Chapter 1"
    assert "Radek textu" in chapters[1].raw_text


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    passed = 0
    failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"ok   {name}")
            passed += 1
        except Exception as e:
            print(f"FAIL {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} prošlo, {failed} selhalo")
    sys.exit(1 if failed else 0)
