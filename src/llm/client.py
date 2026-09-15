"""Provider vrstva. JEDINÝ soubor, který importuje `anthropic`."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

import config


class OutputTruncated(RuntimeError):
    """Model narazil na max_tokens - výstup je neúplný."""


class FatalRunError(RuntimeError):
    """Chyba, po které nemá smysl pokračovat v běhu (auth, neznámý model, 400)."""


class LockLostError(FatalRunError):
    """Ztráta procesního zámku - podtřída `FatalRunError`, ať VŠECHNO,
    co dnes odchytává `except FatalRunError` (CLI `_cmd_polish`'s
    `except FatalRunError as fe: raise`), dál funguje beze změny, ale
    server (Task 10) ji umí odchytit SAMOSTATNĚ a namapovat na 503
    místo obecné 500 - stejný HTTP kód jako startovní `require_lock()`
    kontrola pro STEJNOU podmínku."""


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


class PipelineLLMClient:
    """Obal kolem reálného klienta: cost guard před voláním, zápis do
    `llm_calls` po každém volání (i selhaném). Pipeline ho vyrábí zvlášť pro
    každého agenta - `agent` je jen label do logu."""

    def __init__(self, inner: LLMClient, *, run_id: int, agent: str,
                 db_path: str, config_mod, confirm=input, interactive: bool = True,
                 require_lock=None):
        self._inner = inner
        self._run_id = run_id
        self._agent = agent
        self._db = db_path
        self._cfg = config_mod
        self._confirm = confirm
        self._interactive = interactive
        self._require_lock = require_lock   # volitelný callback `() -> bool`;
        # `None` (výchozí, `_cmd_run`/`scan`/`_cmd_polish_review` preflight)
        # = žádná kontrola, beze změny dnešního chování. `_cmd_polish` a
        # server (Task 10) ho předávají.

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        return self._inner.count_tokens(system=system, user=user, model=model)

    def _price(self, model: str) -> tuple[float, float]:
        if model not in self._cfg.PRICE_IN_PER_MTOK or model not in self._cfg.PRICE_OUT_PER_MTOK:
            raise FatalRunError(
                f"Model {model!r} nemá sazby v config.PRICE_*_PER_MTOK - "
                "cost guard by byl slepý. Doplň sazby.")
        return (self._cfg.PRICE_IN_PER_MTOK[model], self._cfg.PRICE_OUT_PER_MTOK[model])

    def _ask(self, prompt: str) -> str:
        """Zeptá se uživatele. Když stdin není k dispozici (pipe, CI, testy),
        ber to jako 'stop' - guard nesmí spadnout na OSError."""
        try:
            return (self._confirm(prompt) or "").strip()
        except (EOFError, OSError):
            raise FatalRunError("Cost guard: stdin není k dispozici, zastavuji.")

    def _guard(self, system: str, user: str, max_tokens: int, model: str) -> None:
        from src import state
        in_rate, out_rate = self._price(model)   # může vyhodit FatalRunError
        try:
            in_tok = self._inner.count_tokens(system=system, user=user, model=model)
        except FatalRunError:
            raise
        except Exception:
            # KONZERVATIVNÍ nadhad (reálně ~4 znaky/token) - guard nesmí podcenit
            in_tok = (len(system) + len(user)) // 2
        est = in_tok / 1e6 * in_rate + max_tokens / 1e6 * out_rate
        spent = state.spent_so_far(self._db, self._run_id)
        ceiling = state.get_run_spend_ceiling(self._db, self._run_id) or 0.0
        limit = max(self._cfg.MAX_SPEND_USD, ceiling)
        if spent + est <= limit:
            return
        if not self._interactive:
            raise FatalRunError(
                f"Cost guard: strop ${limit:.2f} překročen (utraceno ~${spent:.2f} "
                f"+ odhad ~${est:.2f}). Non-interactive režim, zastavuji.")
        need = spent + est
        for _ in range(2):   # 1 prompt + 1 reprompt na nevalidní/nízký vstup
            ans = self._ask(
                f"Cost guard: utraceno ~${spent:.2f}, odhad ~${est:.2f}, "
                f"strop ${limit:.2f}. Nový strop v $ (>= ${need:.2f}) [prázdné = stop]: ")
            if not ans:
                raise FatalRunError("Cost guard: běh zastaven uživatelem.")
            try:
                new_limit = float(ans)
            except ValueError:
                continue
            if new_limit < need:
                continue   # strop pod potřebu = nesmysl, reprompt
            # Kontrola TĚSNĚ PŘED zápisem - `self._ask(...)` výš mohl
            # čekat na uživatele libovolně dlouho, zámek mohl mezitím
            # zmizet PRÁVĚ v tomhle okně.
            if self._require_lock is not None and not self._require_lock():
                raise LockLostError(
                    "Zámek ztracen během čekání na potvrzení cost guardu "
                    "- jiný proces teď píše do DB, zastavuji dřív, než "
                    "se stihne zapsat nový strop bez ověřeného vlastnictví.")
            state.set_run_spend_ceiling(self._db, self._run_id, new_limit)
            return
        raise FatalRunError("Cost guard: nevalidní/nízký strop, zastavuji.")

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        from src import state
        # Kontrola PŘED `_guard()`, ne jen po ní - `_guard()` v
        # interaktivním režimu (CLI `_cmd_polish`) může při překročení
        # stropu vyzvat uživatele a na potvrzení zavolat `state.set_run_
        # spend_ceiling` - skutečný DB zápis, co by bez tyhle kontroly
        # proběhl bez ověřeného vlastnictví zámku. Kontrola PO `_guard()`
        # (dál dole) zůstává taky - `_guard()` může (v interaktivním
        # režimu) čekat na uživatelský vstup libovolně dlouho, zámek
        # může zmizet právě během tohohle čekání, nezávisle na tom,
        # jestli strop nakonec zapsala.
        if self._require_lock is not None and not self._require_lock():
            raise LockLostError(
                "Zámek ztracen před LLM voláním - jiný proces teď píše "
                "do DB, zastavuji dřív, než cost guard stihne zapsat "
                "nový strop bez ověřeného vlastnictví.")
        self._guard(system, user, max_tokens, model)
        if self._require_lock is not None and not self._require_lock():
            raise LockLostError(
                "Zámek ztracen během LLM volání - jiný proces teď píše "
                "do DB, zastavuji dřív, než se stihne zapsat auditní "
                "záznam bez ověřeného vlastnictví.")
        in_rate, out_rate = self._price(model)
        status, err, comp = "ok", None, None
        try:
            comp = self._inner.complete(system=system, user=user,
                                        max_tokens=max_tokens, model=model)
            if comp.truncated:
                status = "truncated"
            return comp
        except Exception as e:
            status, err = "error", type(e).__name__
            raise
        finally:
            it = comp.input_tokens if comp else None
            ot = comp.output_tokens if comp else None
            cost = (it / 1e6 * in_rate + ot / 1e6 * out_rate) if comp else None
            # DRUHÁ kontrola, TĚSNĚ před zápisem - to síťové volání samo
            # mohlo trvat dost dlouho na to, aby zámek mezitím zmizel.
            # Na rozdíl od kontrol výš (kde ještě nic neproběhlo) TADY UŽ
            # výsledek existuje (úspěch nebo chyba) - jen VYNECH auditní
            # zápis, NEVYHAZUJ výjimku (ta by v `finally` přebila i
            # úspěšný `return comp` výš a zahodila hotový, zaplacený
            # výsledek jen kvůli neschopnosti zapsat diagnostický řádek).
            if self._require_lock is None or self._require_lock():
                state.record_llm_call(
                    self._db, run_id=self._run_id, agent=self._agent,
                    provider=getattr(self._inner, "provider", "unknown"),
                    model=model, input_tokens=it, output_tokens=ot, cost_usd=cost,
                    truncated=bool(comp.truncated) if comp else False,
                    status=status, error_class=err)
