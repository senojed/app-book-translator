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


class CodexTranslatorFatalError(FatalRunError):
    """Fatální chyba VZNIKLÁ PŘÍMO v Codex-translator volání
    (`CodexLLMClient.complete()`) - podtřída `FatalRunError`, ať VŠECHNO,
    co dnes odchytává `except FatalRunError` funguje beze změny. `main.
    _cmd_run` (Task 5) ji rozlišuje SAMOSTATNĚ od obecného `FatalRunError`
    (kritikův cost guard, `LockLostError`, atd. - ty jsou VŽDY Claude-side,
    i při `--translator codex`, protože kritik zůstává vždy `AnthropicClient`) -
    jen TAHLE konkrétní podtřída dostane flagged status před re-raise
    (kolo 11 IMPORTANT, plan-consensus)."""


class MissingPriceError(FatalRunError):
    """`PipelineLLMClient._price()` nenašla sazby pro daný model v
    `config.PRICE_*_PER_MTOK` - podtřída `FatalRunError`, existující
    `except FatalRunError` volající kód funguje beze změny. Odlišitelná
    od OSTATNÍCH `_guard()`-raised `FatalRunError` příčin (cost-guard
    stop po překročení stropu, stdin nedostupné, uživatel běh zastavil,
    `LockLostError`) - `PipelineLLMClient.complete()` přebaluje JEN TUHLE
    na `CodexTranslatorFatalError` pro Codex-backed inner klienty (kolo
    16 IMPORTANT, plan-consensus - viz Task 3) - normální cost-guard
    stop NENÍ Codex-specifická chyba, i pro `--translator codex`."""


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


class CodexLLMClient:
    """`LLMClient` obal nad `codex exec` subprocess voláním (`stylist.
    _exec_codex`) - stejný protokol jako `AnthropicClient`, takže
    `PipelineLLMClient` ho obalí beze změny (stejný audit/cost-guard
    kód, jen s cenou $0/token - viz `billed_model`/`config.PRICE_IN_
    PER_MTOK[CODEX_MODEL]`). Používá se pro `agent="translator"` při
    `--translator codex` (main.py `_client_factory`) - kritik zůstává
    VŽDY na `AnthropicClient` (spike 2026-09-16 ukázal nespolehlivost
    Codex jako kritika, viz spec)."""
    provider = "codex"

    def __init__(self, codex_cmd: list[str], codex_model: str,
                 timeout: int | None = None):
        self._codex_cmd = codex_cmd
        self._codex_model = codex_model
        self._timeout = timeout
        # Kolo 1 BLOCKING (plan-consensus) - `pipeline.process_chapter`
        # volá `translator.translate_scene`/`revise_chapter` BEZ
        # `model=` argumentu, takže `translator.py` VŽDY defaultuje na
        # `config.MODEL_TRANSLATOR` ("claude-sonnet-5"), bez ohledu na
        # to, jaký klient je skutečně pod kapotou. `PipelineLLMClient`
        # (viz jeho oprava níž) čte TENHLE atribut MÍSTO toho
        # caller-supplied `model` pro cenu/audit - jinak by Codex
        # volání dostala cenu Claude modelu a audit log by lhal o tom,
        # co skutečně běželo.
        self.billed_model = codex_model

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        # Lokální import (ne na úrovni modulu) - `client.py` je
        # nízkoúrovňová provider vrstva, `src.agents.stylist` je
        # agent-vrstva o patro výš (config/subprocess specifika pro
        # Codex CLI). Import na úrovni modulu by obrátil směr závislosti,
        # co zbytek souboru dodržuje (stejný vzor jako `PipelineLLMClient.
        # complete()`'s `from src import state`).
        import config
        from src.agents import stylist
        # Kolo 14 IMPORTANT (plan-consensus) - `stylist.polish()` má
        # TENHLE check UVNITŘ SEBE (`src/agents/stylist.py:505-511`),
        # nezávisle na volajícím - `CodexLLMClient` by bez týhle kontroly
        # šlo zkonstruovat a zavolat PŘÍMO (test, budoucí kód), obejít
        # `_client_factory`'s `_polish_preflight()` gate ÚPLNĚ, a spustit
        # Codex exec (FS-risk agent) bez opt-inu. Obrana do hloubky -
        # `_client_factory` (Task 4) tohle za normálních okolností už
        # nikdy nepustí sem s `False`, ale kontrakt musí platit i pro
        # PŘÍMOU konstrukci `CodexLLMClient`, ne jen přes tenhle jeden
        # vstupní bod.
        if config.STYLIST_ACCEPT_FS_RISK is not True:
            raise CodexTranslatorFatalError(
                "CodexLLMClient.complete() vyžaduje "
                "config.STYLIST_ACCEPT_FS_RISK = True (stejné riziko "
                "jako stylist.polish(), viz config.py).")
        prompt = f"{system}\n\n{user}"
        timeout = self._timeout or config.CODEX_TRANSLATE_TIMEOUT_SECONDS
        # Kolo 2 BLOCKING (plan-consensus) - `_exec_codex`'s `StylistError`
        # (rozbitý CLI, vypršelá autentizace, špatný exit kód, prázdná/
        # rozbitá odpověď - VŠECHNO KROMĚ timeoutu, ten je výjimka, viz
        # `StylistTimeoutError` níž, kolo 9 IMPORTANT) se přebaluje na
        # `FatalRunError`, ne necháváme propadnout jako obyčejnou
        # výjimku. `state.queue_for_
        # run()` (main.py `_cmd_run`'s fronta) automaticky ZNOVU zkouší
        # `error` kapitoly PŘI KAŽDÉM příštím `run`u (na rozdíl od
        # `flagged`/`needs_human`, co čekají na člověka) - bez tyhle
        # opravy by rozbitá Codex cesta potichu selhávala kapitolu po
        # kapitole, běh po běhu, dokud by si toho uživatel nevšiml.
        # `FatalRunError` využije existující `_cmd_run`'s `except
        # FatalRunError: raise` (main.py, BEZE ZMĚNY) - celý běh se
        # zastaví HNED, s jasnou hláškou. ŽÁDNÝ proaktivní limit
        # velikosti promptu navíc (na rozdíl od `polish`'s `STYLIST_
        # MAX_CHARS`) - zvažováno a ZAMÍTNUTO (kolo 2 IMPORTANT,
        # plan-consensus): `timeout` je jediná pojistka proti oversized
        # promptu. Bezpečné i pro delší kapitoly díky Tasku 2 (kolo 3
        # IMPORTANT) - `pipeline.process_chapter`'s revizní smyčka teď
        # MÁ checkpoint PŘED revizí, takže výjimka (útlum/timeout/
        # useknutý výstup) BĚHEM revize kapitolu jen označí `flagged` s
        # POSLEDNÍM platným překladem, nezahodí ho.
        try:
            text = stylist._exec_codex(prompt, codex_cmd=self._codex_cmd,
                                       codex_model=self._codex_model,
                                       timeout=timeout, label="translator")
        except stylist.StylistTimeoutError:
            # Kolo 9 IMPORTANT (plan-consensus) - timeout JEDNOHO volání
            # je PER-CALL/transientní (tenhle prompt byl tentokrát moc
            # velký/pomalý), NE nutně systémové selhání CELÉHO Codex
            # backendu jako auth/launch/exit-kód níž - NEpřebaluje se na
            # `FatalRunError` (to by zahodilo hotový scénový překlad při
            # selhání revize, viz Task 2, a zbytečně zastavilo celý run
            # kvůli jednomu pomalému volání). Necháváme propadnout beze
            # změny - scénová smyčka ji zpracuje jako per-kapitolový
            # `error` (auto-retry PŘÍŠTÍ `run` je tady správně, timeout
            # může být jen dočasný), revizní smyčka (Task 2) ji zachytí
            # a kapitolu označí `flagged` s posledním platným překladem.
            # MUSÍ být PŘED `except stylist.StylistError` níž (podtřída -
            # jinak by ji ten širší `except` pohltil první).
            raise
        except (stylist.StylistError, OSError, UnicodeError) as e:
            # Kolo 7 IMPORTANT (plan-consensus) - `_exec_codex()`'s
            # výstupní soubor se čte (`open(out_path, encoding="utf-8")
            # .read()`) BEZ VLASTNÍHO try/except, MIMO `StylistError`
            # kontrakt - `OSError` (zámek/oprávnění na dočasném souboru)
            # nebo `UnicodeDecodeError` (poškozený zápis, špatné kódování)
            # by jinak unikly jako obyčejná výjimka, propadly by až do
            # `_cmd_run`'s generické větve jako per-kapitolový `error`, a
            # `state.queue_for_run` by je tiše retryovalo navěky - STEJNÉ
            # riziko jako `StylistError` výš, jen jiný zdroj. `_exec_codex`/
            # `stylist.py` samotné zůstávají beze změny (mimo rozsah, viz
            # spec) - širší `except` tady stačí.
            #
            # Kolo 8 IMPORTANT (plan-consensus) - `stylist._redact_detail()`
            # PŘES CELOU zprávu, ne jen `str(e)` přímo - `_cmd_run`'s
            # outer `except FatalRunError` (main.py) tiskne zprávu PŘÍMO
            # na konzoli (main.py:1037 `print(f"Fatální chyba běhu:
            # {e}")`), bez další redakce. `_redact_detail`'s VLASTNÍ
            # docstring (`src/agents/stylist.py:206-215`) výslovně jmenuje
            # "`str(e)` neočekávané výjimky" jako jednu z kategorií, co
            # redaguje - `OSError`/`UnicodeDecodeError` z čtení výstupního
            # souboru jsou přesně tenhle případ. `StylistError`'s zprávy
            # bývají ČÁSTEČNĚ pre-redagované (stderr uvnitř `_exec_codex`
            # už prošel `_redact_detail`), ale ne VŽDY (statické hlášky
            # typu "auth expired" z Popen selhání nesou syrový text OS
            # chyby) - jednotná redakce na výstupu z `CodexLLMClient` je
            # bezpečnější než spoléhat na to, že KAŽDÁ cesta uvnitř
            # `_exec_codex` redakci nezapomene.
            #
            # Kolo 11 IMPORTANT (plan-consensus) - `CodexTranslatorFatalError`
            # (podtřída `FatalRunError`), NE holý `FatalRunError` - `_cmd_run`
            # (Task 5) potřebuje ROZLIŠIT "tahle fatální chyba vznikla
            # PŘÍMO v Codex-translator volání" od "kritik (VŽDY Claude,
            # i při `--translator codex`) narazil na cost guard/lock
            # ztrátu" - obojí je dnes STEJNÝ `FatalRunError` typ, takže
            # podmínka `if args.translator == "codex":` v `_cmd_run`
            # (kolo 10 fix) by omylem flagovala/redigovala i Claude-side
            # kritikovu chybu jen proto, že translator backend je nastavený
            # na `codex` - v přímém rozporu s "Claude cesta beze změny".
            raise CodexTranslatorFatalError(stylist._redact_detail(str(e))) from e
        # `truncated` VŽDY False (zdokumentovaný limit, viz spec "Známé
        # limity") - Codex nedává spolehlivý signál o useknutí na limitu
        # jako Claude `stop_reason`. Skutečné useknutí spadne na
        # chybějící `===KONEC===` marker uvnitř `translator._parse()`
        # (ValueError, Task 2, kolo 3 BLOCKING), ne na tenhle příznak.
        # Kolo 5 IMPORTANT (plan-consensus) - NENULOVÝ konzervativní
        # odhad (stejný vzorec jako count_tokens() níž), ne natvrdo 0 -
        # PipelineLLMClient.complete() tyhle hodnoty zapíše do audit
        # logu beze změny, main._print_usage() je sčítá napříč celým
        # během. Natvrdo 0 by po zpracování celé knihy ukázalo "0
        # tokenů" - cena $0 je správně (billed_model), ale objem
        # zpracovaného textu by byl neviditelný.
        # Kolo 27 NIT (plan-consensus) - `max(1, ...)` MÍSTO holého
        # `//2` - kolo 5's záměr byl "NENULOVÝ odhad", ale `//2` samo
        # pro krátký NEprázdný vstup/výstup (1-2 znaky) vrátí `0`,
        # stejný problém jako "natvrdo 0", jen ve výjimečném edge-case.
        return Completion(text=text, truncated=False,
                          input_tokens=max(1, (len(system) + len(user)) // 2),
                          output_tokens=max(1, len(text) // 2))

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        # Stejná konzervativní aproximace jako `PipelineLLMClient._guard()`'s
        # vlastní fallback (main.py existující kód, `(len(system)+len(user))
        # //2`) - Codex nemá API pro přesné počítání tokenů.
        # Kolo 27 NIT (plan-consensus) - `max(1, ...)` viz `complete()` výš.
        return max(1, (len(system) + len(user)) // 2)


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
            raise MissingPriceError(
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
        # Kolo 1 BLOCKING (plan-consensus 2026-09-16) - `self._inner`
        # může ignorovat `model` param úplně (`CodexLLMClient` vždy
        # execuje SVŮJ fixní `billed_model`, bez ohledu na to, co
        # `translator.py` defaultně pošle - `config.MODEL_TRANSLATOR`).
        # Cost guard i audit musí odrážet, co SE SKUTEČNĚ spustilo (a
        # za co se SKUTEČNĚ platí), ne co volající předpokládal.
        # `AnthropicClient`/`FakeLLMClient` nemají `billed_model` -
        # `getattr(...) is None` spadne zpátky na `model` param beze
        # změny chování pro existující Claude cestu.
        effective_model = getattr(self._inner, "billed_model", None) or model
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
        try:
            self._guard(system, user, max_tokens, effective_model)
        except MissingPriceError as e:
            # Kolo 16 IMPORTANT (plan-consensus) - `except FatalRunError`
            # (kolo 15's původní verze) by chytlo VŠECHNY `_guard()`
            # FatalRunError příčiny - i normální cost-guard stop
            # (limit překročen, non-interactive), stdin nedostupné,
            # uživatel běh zastavil, `LockLostError` - a přebalilo by
            # je na `CodexTranslatorFatalError` pro Codex-backed klienta,
            # i když s Codexem nemají NIC společného (Claude by dopadl
            # identicky). `MissingPriceError` (nová podtřída, viz výš) je
            # PŘESNĚ ohraničená na `_price()`'s "nemá sazby" případ -
            # jediný, co má smysl přebalovat jako Codex-specifickou
            # fatální chybu.
            if getattr(self._inner, "provider", None) == "codex":
                raise CodexTranslatorFatalError(str(e)) from e
            raise
        if self._require_lock is not None and not self._require_lock():
            raise LockLostError(
                "Zámek ztracen během LLM volání - jiný proces teď píše "
                "do DB, zastavuji dřív, než se stihne zapsat auditní "
                "záznam bez ověřeného vlastnictví.")
        in_rate, out_rate = self._price(effective_model)
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
                    model=effective_model, input_tokens=it, output_tokens=ot,
                    cost_usd=cost, truncated=bool(comp.truncated) if comp else False,
                    status=status, error_class=err)
