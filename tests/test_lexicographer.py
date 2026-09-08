import json
import pytest
from src.agents import lexicographer
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

ITEMS = [{"id": "terms/white council", "term_en": "White Council",
          "kind": "term", "note": "organizace"},
         {"id": "terms/warlock", "term_en": "warlock", "kind": "term", "note": ""}]


def _resp(pairs):
    return json.dumps({"proposals": [{"id": i, "cz": c} for i, c in pairs]})


def test_propose_maps_ids_to_values():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "Bílá rada"), ("terms/warlock", "černokněžník")]),
        False, 10, 10)])
    out = lexicographer.propose(ITEMS, fake)
    assert out == {"terms/white council": "Bílá rada", "terms/warlock": "černokněžník"}


def test_explicit_null_means_model_does_not_know():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "Bílá rada"), ("terms/warlock", None)]),
        False, 10, 10)])
    assert lexicographer.propose(ITEMS, fake)["terms/warlock"] is None


def test_duplicate_id_raises():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "A"), ("terms/white council", "B"),
               ("terms/warlock", "C")]), False, 10, 10)])
    with pytest.raises(ValueError, match="[Dd]uplicit"):
        lexicographer.propose(ITEMS, fake)


def test_unknown_id_is_ignored():
    fake = FakeLLMClient([Completion(
        _resp([("terms/white council", "Bílá rada"), ("terms/warlock", "x"),
               ("terms/neznamy", "y")]), False, 10, 10)])
    out = lexicographer.propose(ITEMS, fake)
    assert "terms/neznamy" not in out


def test_missing_id_raises_because_result_is_incomplete():
    """Chybějící položka != explicitní null. Model na ni zapomněl, výsledek je
    neúplný a běh musí selhat atomicky."""
    fake = FakeLLMClient([Completion(_resp([("terms/white council", "Bílá rada")]),
                                     False, 10, 10)])
    with pytest.raises(ValueError, match="chyb"):
        lexicographer.propose(ITEMS, fake)


def test_non_string_cz_raises():
    raw = json.dumps({"proposals": [{"id": "terms/white council", "cz": 42},
                                    {"id": "terms/warlock", "cz": None}]})
    with pytest.raises(ValueError):
        lexicographer.propose(ITEMS, FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_top_level_json_array_raises_value_error_not_attribute_error():
    """extract_json má typový slib '-> dict', ale za běhu vrátí cokoli platné
    JSON - model vracející pole místo objektu nesmí spadnout na
    AttributeError, ale dát srozumitelný ValueError."""
    raw = json.dumps([{"id": "terms/white council", "cz": "A"}])
    with pytest.raises(ValueError):
        lexicographer.propose(ITEMS, FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_missing_proposals_key_raises_value_error():
    raw = json.dumps({"neco_jineho": []})
    with pytest.raises(ValueError):
        lexicographer.propose(ITEMS, FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_non_dict_row_in_proposals_raises_value_error():
    raw = json.dumps({"proposals": ["terms/white council"]})
    with pytest.raises(ValueError):
        lexicographer.propose(ITEMS, FakeLLMClient([Completion(raw, False, 5, 5)]))


def test_truncated_retries_once_with_double_tokens():
    seen = []
    def gen(**kw):
        seen.append(kw["max_tokens"])
        if len(seen) == 1:
            return Completion("{partial", True, 5, 5)
        return Completion(_resp([("terms/white council", "A"), ("terms/warlock", "B")]),
                          False, 5, 5)
    out = lexicographer.propose(ITEMS, FakeLLMClient(gen), max_tokens=1000)
    assert seen == [1000, 2000]
    assert out["terms/warlock"] == "B"


def test_truncated_twice_raises():
    fake = FakeLLMClient([Completion("{a", True, 5, 5), Completion("{b", True, 5, 5)])
    with pytest.raises(OutputTruncated):
        lexicographer.propose(ITEMS, fake)


def test_prompt_contains_ids_and_notes():
    seen = {}
    def gen(**kw):
        seen.update(kw)
        return Completion(_resp([("terms/white council", "A"), ("terms/warlock", "B")]),
                          False, 5, 5)
    lexicographer.propose(ITEMS, FakeLLMClient(gen))
    assert "terms/white council" in seen["user"]
    assert "organizace" in seen["user"]
    assert "null" in lexicographer.SYSTEM_PROMPT
