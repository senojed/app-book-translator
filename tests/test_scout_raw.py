import json, pytest
from src.agents import scout
from src.llm.client import Completion, FakeLLMClient


def test_missing_keys_error_carries_raw_output():
    """Bez surového výstupu se selhání scouta nedá diagnostikovat."""
    raw = '{"characters": [], "places": []}'
    fake = FakeLLMClient([Completion(raw, False, 10, 10)])
    with pytest.raises(scout.ScoutOutputError) as e:
        scout.scan_book("kniha", fake)
    assert e.value.raw == raw
    assert "terms" in str(e.value)


def test_unparseable_output_error_carries_raw_output():
    raw = "tohle vubec neni json"
    fake = FakeLLMClient([Completion(raw, False, 10, 10)])
    with pytest.raises(scout.ScoutOutputError) as e:
        scout.scan_book("kniha", fake)
    assert e.value.raw == raw


def test_scout_output_error_is_valueerror():
    """main chytá (OutputTruncated, ValueError) - nesmí propadnout jinam."""
    assert issubclass(scout.ScoutOutputError, ValueError)
