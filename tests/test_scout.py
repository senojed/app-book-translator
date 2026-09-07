import json, pytest
from src.agents import scout
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

_OK = {"characters": [{"name_en": "Harry", "aliases": ["Dresden"],
                       "suggested": "keep", "note": "hrdina"}],
       "places": [], "terms": [], "relationships": [],
       "style_notes": "1. osoba", "must_decide": []}


def test_scan_book_parses_json():
    fake = FakeLLMClient([Completion(json.dumps(_OK), False, 100, 50)])
    out = scout.scan_book("kniha text", fake)
    assert out["characters"][0]["name_en"] == "Harry"


def test_scan_book_raises_on_truncated():
    fake = FakeLLMClient([Completion(json.dumps(_OK)[:20], True, 100, 50)])
    with pytest.raises(OutputTruncated):
        scout.scan_book("kniha", fake)


def test_scan_book_raises_on_missing_keys():
    fake = FakeLLMClient([Completion('{"characters": []}', False, 10, 10)])
    with pytest.raises(ValueError):
        scout.scan_book("kniha", fake)


def test_merge_dedups_characters_by_surface():
    p1 = dict(_OK, characters=[{"name_en": "Harry", "aliases": ["Harry"],
                               "suggested": "keep", "note": "a"}])
    p2 = dict(_OK, characters=[{"name_en": "harry", "aliases": ["Dresden"],
                               "suggested": "keep", "note": "b"}])
    m = scout.merge_scout_facts([p1, p2])
    assert len(m["characters"]) == 1
    assert set(m["characters"][0]["aliases"]) == {"Harry", "Dresden"}


def test_merge_conflicting_relationship_becomes_must_decide():
    p1 = dict(_OK, relationships=[{"a": "Harry", "b": "Murphy",
                                  "observed": "x", "suggested": "tyka"}])
    p2 = dict(_OK, relationships=[{"a": "Murphy", "b": "Harry",
                                  "observed": "y", "suggested": "vyka"}])
    m = scout.merge_scout_facts([p1, p2])
    rel = m["relationships"][0]
    assert rel["suggested"] is None
    assert any(md["kind"] == "relationship" for md in m["must_decide"])


def test_merge_dedups_terms_by_term_en():
    p1 = dict(_OK, terms=[{"term_en": "Nevernever", "suggested_cz": "Nikdykdy", "note": "a"}])
    p2 = dict(_OK, terms=[{"term_en": "nevernever", "suggested_cz": "Nikdykdy", "note": "b"}])
    m = scout.merge_scout_facts([p1, p2])
    assert len(m["terms"]) == 1


def test_chunk_chapters_greedy_packs_under_limit():
    class C:
        def __init__(s, n): s.raw_text = "slovo " * n
    chunks = scout.chunk_chapters([C(30), C(30), C(30), C(80)], word_limit=100)
    # 30+30+30 = 90 < 100 → chunk 1; C(80) samostatně → chunk 2
    assert len(chunks) == 2
    assert len(chunks[0].split()) == 90


def test_chunk_chapters_accepts_dict_rows():
    rows = [{"raw_text": "slovo " * 20}, {"raw_text": "slovo " * 20}]
    assert len(scout.chunk_chapters(rows, word_limit=100)) == 1
