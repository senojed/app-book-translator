"""Provider vrstva. JEDINÝ soubor, který importuje `anthropic`."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

import config


class OutputTruncated(RuntimeError):
    """Model narazil na max_tokens - výstup je neúplný."""


class FatalRunError(RuntimeError):
    """Chyba, po které nemá smysl pokračovat v běhu (auth, neznámý model, 400)."""


@dataclass
class Completion:
    text: str
    truncated: bool
    input_tokens: int
    output_tokens: int


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion: ...
    def count_tokens(self, *, system: str, user: str, model: str) -> int: ...


def _build_sdk_client(api_key: str | None):
    import anthropic
    return anthropic.Anthropic(api_key=api_key, max_retries=config.API_MAX_RETRIES)


def _fatal_sdk_errors():
    """Chyby, které nemá smysl retryovat - špatný klíč, model, parametry."""
    import anthropic
    return (anthropic.AuthenticationError, anthropic.NotFoundError,
            anthropic.BadRequestError, anthropic.PermissionDeniedError)


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or config.ANTHROPIC_API_KEY
        if not self._api_key:
            raise FatalRunError("Chybí ANTHROPIC_API_KEY v prostředí.")
        self._sdk = None

    def _client(self):
        # SDK klient se staví líně - konstrukce AnthropicClient nesmí sahat na síť.
        if self._sdk is None:
            self._sdk = _build_sdk_client(self._api_key)
        return self._sdk

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        try:
            resp = self._client().messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except _fatal_sdk_errors() as e:
            raise FatalRunError(f"{type(e).__name__}: {e}") from e
        text = "".join(b.text for b in resp.content if b.type == "text")
        return Completion(
            text=text,
            truncated=(resp.stop_reason == "max_tokens"),
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        )

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        try:
            r = self._client().messages.count_tokens(
                model=model, system=system,
                messages=[{"role": "user", "content": user}])
        except _fatal_sdk_errors() as e:
            raise FatalRunError(f"{type(e).__name__}: {e}") from e
        return r.input_tokens


class FakeLLMClient:
    """Testovací klient - buď fronta hotových odpovědí, nebo callable(**kwargs)."""
    provider = "fake"

    def __init__(self, responses):
        self._callable = responses if callable(responses) else None
        self._queue = list(responses) if not callable(responses) else []
        self.calls = 0

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        self.calls += 1
        if self._callable:
            return self._callable(system=system, user=user,
                                  max_tokens=max_tokens, model=model)
        return self._queue.pop(0)

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        return max(1, (len(system) + len(user)) // 4)
