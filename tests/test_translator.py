import pytest
from src.agents import translator
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

_RAW = (
    "===PREKLAD===\nAhoj světe.\n\nDruhý odstavec.\n"
    "===METADATA===\n"
    '{"new_terms":[{"term_en":"Foo","cz":"Fů","note":"","type":"term"}],'
    '"rendered_terms":[{"term_id":"t1","cz_as_used":"Harry"}],'
    '"questions":[{"kind":"term","scope_key":"cand_foo","guess_answer":"Fů",'
    '"text":"jak Foo?","severity":"guess"}]}'
)


def test_translate_scene_parses_delimited():
    r = translator.translate_scene("Hello world.", "guide", "gloss",
                                   FakeLLMClient([Completion(_RAW, False, 10, 10)]))
    assert r.translation == "Ahoj světe.\n\nDruhý odstavec."
    assert r.new_terms[0]["cz"] == "Fů"
    assert r.rendered_terms[0]["term_id"] == "t1"
    assert r.questions[0]["severity"] == "guess"


def test_translate_scene_raises_on_truncated():
    with pytest.raises(OutputTruncated):
        translator.translate_scene("Hi.", "g", "gl",
                                   FakeLLMClient([Completion(_RAW, True, 10, 10)]))


def test_broken_metadata_json_raises():
    raw = "===PREKLAD===\nText tady.\n===METADATA===\n{tohle neni json"
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_missing_metadata_section_tolerated():
    raw = "===PREKLAD===\nText tady bez metadat."
    r = translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))
    assert r.translation == "Text tady bez metadat."
    assert r.new_terms == [] and r.questions == [] and r.rendered_terms == []


def test_empty_translation_raises():
    raw = "===PREKLAD===\n\n===METADATA===\n{}"
    with pytest.raises(ValueError):
        translator.translate_scene("x", "g", "gl",
                                   FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_revise_chapter_sends_findings_and_en(monkeypatch):
    seen = {}
    def gen(**kw):
        seen.update(kw)
        return Completion(_RAW, False, 10, 10)
    translator.revise_chapter("EN ORIGINAL", "stary CZ",
                              [{"issue": "vynechavka", "suggestion": "doplň"}],
                              "guide", "gloss", FakeLLMClient(gen))
    assert "EN ORIGINAL" in seen["user"]
    assert "vynechavka" in seen["user"]
