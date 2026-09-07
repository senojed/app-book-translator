import pytest
from src.llm import client
from src.llm.client import Completion, FakeLLMClient, FatalRunError


def test_completion_dataclass_fields():
    c = Completion(text="x", truncated=False, input_tokens=10, output_tokens=5)
    assert c.text == "x" and c.input_tokens == 10


def test_fake_client_returns_queued_responses():
    fake = FakeLLMClient(responses=[
        Completion("a", False, 1, 1), Completion("b", False, 1, 1)])
    assert fake.complete(system="s", user="u", max_tokens=10, model="m").text == "a"
    assert fake.complete(system="s", user="u", max_tokens=10, model="m").text == "b"
    assert fake.calls == 2


def test_fake_client_callable_mode_sees_kwargs():
    seen = {}
    def gen(**kw):
        seen.update(kw)
        return Completion("ok", False, 1, 1)
    FakeLLMClient(gen).complete(system="S", user="U", max_tokens=99, model="M")
    assert seen == {"system": "S", "user": "U", "max_tokens": 99, "model": "M"}


def test_anthropic_client_maps_sdk_error_to_fatal(monkeypatch):
    """AnthropicClient převádí fatální SDK chyby na FatalRunError."""
    import anthropic

    err = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
    err.args = ("bad key",)

    class _Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise err

    monkeypatch.setattr(client, "_build_sdk_client", lambda *a, **k: _Boom())
    c = client.AnthropicClient(api_key="x")
    with pytest.raises(FatalRunError):
        c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
