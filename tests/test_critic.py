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
        {"severity": "minor", "type": "fluency", "cz_excerpt": "x",
         "issue": "drobnost", "suggestion": "y"}]})
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


def _dbl(text):
    """Kritik má retry smyčku (2 pokusy) - vrať stejnou vadnou odpověď dvakrát."""
    return FakeLLMClient([Completion(text, False, 5, 5), Completion(text, False, 5, 5)])


def test_review_revise_verdict_without_revise_finding_synthesizes_one():
    resp = json.dumps({"verdict": "revise", "findings": []})
    out = critic.review("EN", "CZ", FakeLLMClient([Completion(resp, False, 5, 5)]))
    assert any(f["action"] == "revise" for f in out)
    assert out[0]["source"] == "critic"


def test_review_findings_as_string_is_broken_not_char_iteration():
    resp = json.dumps({"verdict": "pass", "findings": "ok"})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_findings_null_or_missing_is_empty_not_broken():
    """spec 188/229: `null` nebo chybějící `findings` s verdiktem `pass` ->
    prázdný seznam, NErozbíjí odpověď."""
    for resp in (json.dumps({"verdict": "pass", "findings": None}),
                 json.dumps({"verdict": "pass"})):
        assert critic.review("EN", "CZ",
                             FakeLLMClient([Completion(resp, False, 5, 5)])) == []


def test_review_findings_with_non_dict_item_invalidates_whole_response():
    resp = json.dumps({"verdict": "pass", "findings": [1]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_invalid_verdict_is_broken_even_with_empty_findings():
    for bad in ("maybe", None, 42):
        resp = json.dumps({"verdict": bad, "findings": []})
        with pytest.raises((ValueError, OutputTruncated)):
            critic.review("EN", "CZ", _dbl(resp))


def test_review_top_level_non_dict_is_broken():
    resp = json.dumps([{"verdict": "pass"}])
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_finding_missing_severity_invalidates_response():
    resp = json.dumps({"verdict": "revise",
                       "findings": [{"type": "fidelity", "issue": "x"}]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_finding_invalid_severity_value_invalidates_response():
    resp = json.dumps({"verdict": "revise",
                       "findings": [{"severity": 0, "type": "fidelity", "issue": "x"}]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))


def test_review_finding_invalid_type_value_invalidates_response():
    resp = json.dumps({"verdict": "revise",
                       "findings": [{"severity": "critical", "type": "grammar",
                                     "issue": "x"}]})
    with pytest.raises((ValueError, OutputTruncated)):
        critic.review("EN", "CZ", _dbl(resp))
