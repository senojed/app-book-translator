import pytest
from src.llm import parsing


def test_split_sections_two_markers():
    raw = "junk\n===PREKLAD===\nAhoj svete.\n===METADATA===\n{\"a\": 1}"
    out = parsing.split_sections(raw, ["===PREKLAD===", "===METADATA==="])
    assert out["PREKLAD"] == "Ahoj svete."
    assert out["METADATA"] == '{"a": 1}'


def test_split_sections_missing_second_marker():
    raw = "===PREKLAD===\nJen preklad."
    out = parsing.split_sections(raw, ["===PREKLAD===", "===METADATA==="])
    assert out["PREKLAD"] == "Jen preklad."
    assert out.get("METADATA", "") == ""


def test_extract_json_plain():
    assert parsing.extract_json('{"x": 5}') == {"x": 5}


def test_extract_json_with_fence():
    assert parsing.extract_json('```json\n{"x": 5}\n```') == {"x": 5}


def test_extract_json_with_surrounding_text():
    assert parsing.extract_json('blah {"x": 5} trailing') == {"x": 5}


def test_extract_json_unparseable_raises():
    with pytest.raises(ValueError):
        parsing.extract_json("tohle neni json")
