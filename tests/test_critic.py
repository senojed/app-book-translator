import json, pytest
from src.agents import critic
from src.llm.client import Completion, FakeLLMClient, OutputTruncated

_PASS = json.dumps({"verdict": "pass", "findings": []})
_REVISE = json.dumps({"verdict": "revise", "findings": [
    {"severity": "critical", "type": "fidelity", "cz_excerpt": "špatná věta",
     "issue": "změněný význam", "suggestion": "oprav"}]})


def test_review_pass_returns_empty():
    assert critic.review("EN", "CZ", FakeLLMClient([Completion(_PASS, False, 5, 5)])) == []


def test_review_maps_critical_to_revise_action():
    f = critic.review("EN", "CZ", FakeLLMClient([Completion(_REVISE, False, 5, 5)]))
    assert f[0]["source"] == "critic"
    assert f[0]["severity"] == "critical" and f[0]["action"] == "revise"


def test_review_minor_maps_to_note():
    raw = json.dumps({"verdict": "revise", "findings": [
        {"severity": "minor", "cz_excerpt": "x", "issue": "drobnost", "suggestion": "y"}]})
    f = critic.review("EN", "CZ", FakeLLMClient([Completion(raw, False, 5, 5)]))
    assert f[0]["action"] == "note"


def test_review_retries_then_raises_on_repeated_truncation():
    fake = FakeLLMClient([Completion("{partial", True, 5, 5),
                          Completion("{still partial", True, 5, 5)])
    with pytest.raises(OutputTruncated):
        critic.review("EN", "CZ", fake)
    assert fake.calls == 2


def test_review_retries_on_bad_json_then_succeeds():
    fake = FakeLLMClient([Completion("rozbity json {", False, 5, 5),
                          Completion(_PASS, False, 5, 5)])
    assert critic.review("EN", "CZ", fake) == []
    assert fake.calls == 2


def test_review_raises_valueerror_on_repeated_bad_json():
    fake = FakeLLMClient([Completion("nope {", False, 5, 5),
                          Completion("still nope {", False, 5, 5)])
    with pytest.raises(ValueError):
        critic.review("EN", "CZ", fake)
    assert fake.calls == 2
