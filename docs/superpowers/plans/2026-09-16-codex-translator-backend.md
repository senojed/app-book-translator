# Codex jako volitelný překladatelský backend - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (nebo superpowers:subagent-driven-development) k implementaci tohohle plánu task-by-task. Kroky používají checkbox (`- [ ]`) syntax pro sledování.

**Goal:** Umožnit `python main.py run --translator codex`, kde překladatel
běží přes Codex CLI (subprocess, $0/token) místo Claude API. Kritik zůstává
VŽDY na Claude (nezávislá kontrola, spike ukázal nespolehlivost Codex-jako-
kritik). `polish` beze změny.

**Architecture:** Nová `CodexLLMClient` (stejný `LLMClient` protokol jako
`AnthropicClient`) v `src/llm/client.py`, obalená stávající `PipelineLLMClient`
(žádná nová audit/cost-guard vrstva). `main._client_factory` dostane
`translator_backend` parametr - pro agenta `"translator"` a `backend=="codex"`
postaví `CodexLLMClient` přes existující `_polish_preflight()` bránu (stejné
FS-risk varování jako `polish`).

**Tech Stack:** Python, stávající `subprocess`-based Codex volání
(`stylist._exec_codex`), stávající `PipelineLLMClient`/`LLMClient` protokol.

**Spec:** `docs/superpowers/specs/2026-09-16-codex-translator-backend-design.md`

## Global Constraints

- Kritik/`stylist_check` VŽDY `AnthropicClient`, bez ohledu na
  `--translator` - žádná cesta nesmí přepnout kritika na Codex.
- `--translator codex` vyžaduje `config.STYLIST_ACCEPT_FS_RISK is True`
  (stejná brána jako `polish`) - FatalRunError, ne tichý pád na Claude.
- `PRICE_IN_PER_MTOK[CODEX_MODEL]`/`PRICE_OUT_PER_MTOK[CODEX_MODEL]` MUSÍ
  být definované PŘED prvním `_client_factory`'s Codex voláním - jinak
  `PipelineLLMClient._price()` vyhodí `FatalRunError` ("nemá sazby").
- `CodexLLMClient.complete()`'s `truncated` je VŽDY `False` - zdokumentovaný
  limit (viz spec "Známé limity"), ne bug.
- `pipeline.process_chapter` volá `translator.translate_scene`/`revise_
  chapter` BEZ `model=` argumentu → `config.MODEL_TRANSLATOR` ("claude-
  sonnet-5") defaultně. `PipelineLLMClient` proto MUSÍ pro cenu/audit
  použít `CodexLLMClient.billed_model`, NE tenhle caller-supplied `model`
  (kolo 1 BLOCKING, plan-consensus) - jinak Task 1's `$0.0` ceny se
  nikdy nepoužijí a audit log lže o tom, jaký model běžel.
- `StylistError` ze `_exec_codex` se v `CodexLLMClient.complete()`
  přebaluje na `FatalRunError` - CELÝ `run` se zastaví hned při první
  selhávající Codex exekuci (kolo 2 BLOCKING, plan-consensus - `state.
  queue_for_run` automaticky ZNOVU zkouší `error` kapitoly PŘI KAŽDÉM
  příštím `run`u, na rozdíl od `flagged`/`needs_human`, co čekají na
  člověka; bez týhle opravy by rozbitý Codex CLI/auth potichu opakovaně
  selhávalo přes libovolně mnoho budoucích běhů, ne jen jednou).
- ŽÁDNÝ proaktivní limit velikosti promptu pro Codex-translator (na
  rozdíl od `polish`'s `STYLIST_MAX_CHARS`) - zvažováno a ZAMÍTNUTO
  (kolo 2 IMPORTANT, plan-consensus - viz Task 2 "Známý limit"):
  deterministický guard by SPOLEHLIVĚ zahazoval hotový scénový překlad
  při selhání revizní fáze delší kapitoly (`pipeline.process_chapter`'s
  revizní smyčka nemá checkpoint PŘED revizí). `CODEX_TRANSLATE_
  TIMEOUT_SECONDS` je jediná (méně přesná, ale bezpečnější) pojistka.

---

### Task 1: `config.py` - timeout + ceny pro Codex-translator

**Files:**
- Modify: `config.py`

**Interfaces:**
- Produces: `config.CODEX_TRANSLATE_TIMEOUT_SECONDS` (int),
  `config.PRICE_IN_PER_MTOK[config.CODEX_MODEL] == 0.0`,
  `config.PRICE_OUT_PER_MTOK[config.CODEX_MODEL] == 0.0`.

- [ ] **Step 1: Napiš test**

```python
def test_codex_model_has_zero_price_entries():
    assert config_module.PRICE_IN_PER_MTOK[config_module.CODEX_MODEL] == 0.0
    assert config_module.PRICE_OUT_PER_MTOK[config_module.CODEX_MODEL] == 0.0


def test_codex_translate_timeout_seconds_is_positive_int():
    assert isinstance(config_module.CODEX_TRANSLATE_TIMEOUT_SECONDS, int)
    assert config_module.CODEX_TRANSLATE_TIMEOUT_SECONDS > 0
```

Přidej do `tests/test_config.py` (existující soubor z Tasku 1 dřívějšího
plánu - `config` je tam už importovaný jako `config_module` na úrovni
modulu, `import importlib`/`monkeypatch.undo()` vzor tam taky je, ale
tyhle dva testy ho nepotřebují, čtou jen statickou hodnotu).

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_config.py -k "codex_model_has_zero_price or codex_translate_timeout" -v`
Expected: FAIL - `AttributeError`/`KeyError` (config.py ještě nemá ani
`CODEX_TRANSLATE_TIMEOUT_SECONDS`, ani ceny pro `CODEX_MODEL`)

- [ ] **Step 3: Implementuj**

V `config.py` najdi řádek `CODEX_MODEL = "gpt-5.6-terra"` (dnes řádek 96)
a HNED ZA NĚJ (ne do literálu `PRICE_IN_PER_MTOK`/`PRICE_OUT_PER_MTOK`
výš v souboru, kde `CODEX_MODEL` ještě neexistuje) přidej:

```python
# Codex běží na předplatném, ne za token - $0.0 zajistí, že
# `PipelineLLMClient._price()` (vyžaduje ZÁZNAM pro KAŽDÝ model, žádný
# implicitní fallback na 0) Codex-translator volání nikdy neodmítne
# jako "nemá sazby", a cost guard u nich nikdy nezasáhne (útrata 0).
PRICE_IN_PER_MTOK[CODEX_MODEL] = 0.0
PRICE_OUT_PER_MTOK[CODEX_MODEL] = 0.0
```

Najdi `STYLIST_TIMEOUT_SECONDS = 180` a přidej vedle:

```python
# Spike test (2026-09-16, data/spikes/) - jednotlivá volání trvala
# 70-120s (přímý překlad i polish), 300s je rezerva na delší scény
# (kapitoly nad CHAPTER_SPLIT_WORD_THRESHOLD se dělí na víc scén, každá
# JEDNO volání zvlášť). ŽÁDNÝ proaktivní znakový limit navíc (na rozdíl
# od `polish`'s `STYLIST_MAX_CHARS`) - zvažováno a zamítnuto (kolo 2
# IMPORTANT, plan-consensus, viz `CodexLLMClient` docstring v `src/llm/
# client.py`) - tenhle timeout je JEDINÁ pojistka proti oversized promptu.
CODEX_TRANSLATE_TIMEOUT_SECONDS = 300
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config pro Codex-translator - timeout + nulové ceny

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: `CodexLLMClient` v `src/llm/client.py` + oprava `PipelineLLMClient` cena/audit

**Files:**
- Modify: `src/llm/client.py` (`CodexLLMClient` - nová; `PipelineLLMClient.
  complete()` - oprava, viz kolo 1 BLOCKING níž)
- Test: `tests/test_pipeline_client.py`

**Interfaces:**
- Consumes: `stylist._exec_codex`, `stylist.StylistError` (lokální
  import uvnitř `complete()`, ne na úrovni modulu - viz Global
  Constraints v designu, vrstvení).
- Produces: `CodexLLMClient(codex_cmd: list[str], codex_model: str,
  timeout: int | None = None)` - `complete()`/`count_tokens()` stejný
  `LLMClient` protokol jako `AnthropicClient`, `.provider == "codex"`,
  `.billed_model == codex_model` (kolo 1 BLOCKING - viz níž, PROČ).
  `complete()` přebaluje `stylist.StylistError` na `FatalRunError`
  (kolo 2 BLOCKING - viz níž, PROČ).

**Kolo 1 BLOCKING (plan-consensus) - proč `billed_model`:** `pipeline.
process_chapter` volá `translator.translate_scene(scene, guide_block,
glossary_block, client_factory("translator"))` BEZ `model=` argumentu →
`translate_scene`'s `model=None` default → `translator._complete()`'s
`model=model or config.MODEL_TRANSLATOR` → VŽDY `"claude-sonnet-5"`
(`config.py:55`), bez ohledu na to, jestli translator je `AnthropicClient`
nebo `CodexLLMClient`. Tahle hodnota jde do `PipelineLLMClient.complete
(model="claude-sonnet-5")`, co ji použije PŘÍMO pro `self._price(model)`
(cenová tabulka `PRICE_*_PER_MTOK["claude-sonnet-5"]` = $2/$10, NE Task
1's `$0.0` pro `CODEX_MODEL`) i pro `record_llm_call(model=model, ...)`
(audit řádek by tvrdil, že proběhlo Claude volání, i když ve skutečnosti
běžel Codex subprocess). Beze zásahu by Task 1's nulové ceny NIKDY
nepřišly ke slovu a cost guard by u KAŽDÉHO Codex-translator volání
počítal s cenou Claude modelu za něco, co ve skutečnosti nic nestojí -
zbytečné/matoucí zásahy cost guardu, plus nepravdivý audit log.

**Oprava:** `CodexLLMClient` má `billed_model` atribut. `PipelineLLMClient.
complete()` spočítá `effective_model = getattr(self._inner, "billed_model",
None) or model` a použije ho MÍSTO `model` pro `_guard()`/`_price()`/
`record_llm_call(model=...)`. Skutečné volání `self._inner.complete(model=
model, ...)` dostává PŮVODNÍ `model` beze změny (jediná správná hodnota
pro `AnthropicClient`; `CodexLLMClient` ho stejně ignoruje - viz jeho
`complete()` níž). `AnthropicClient`/`FakeLLMClient` nemají `billed_model`
atribut - `getattr(..., None)` tam spadne na `model` param, NULOVÁ změna
chování pro existující Claude cestu (proto testy níž ověřují OBOJÍ -
Codex cestu i že Claude cesta zůstala nedotčená).

**Kolo 2 BLOCKING (plan-consensus) - proč `StylistError` → `FatalRunError`:**
`state.queue_for_run()` (main.py `_cmd_run`'s vlastní fronta) vrací
`chapters_by_status(db_path, ("pending", "error"))` s docstringem "error
= automatický retry" (`src/state.py:179-182`) - na rozdíl od `flagged`/
`needs_human`, co čekají na ČLOVĚKA (`--retry-flagged`), `error` kapitola
se AUTOMATICKY zkusí znovu PŘI KAŽDÉM příštím `run`u, i budoucím, i na
jiných kapitolách. Kdyby `CodexLLMClient.complete()` nechal `_exec_codex`'s
`StylistError` (rozbitý CLI, vypršelá autentizace, timeout) propadnout
jako obyčejnou výjimku, `_cmd_run`'s `except Exception: status="error"`
(main.py:1015-1019) by ji potichu zpracoval PER KAPITOLA a běh by
pokračoval na DALŠÍ kapitole se STEJNOU rozbitou cestou - N kapitol by
skončilo `error` za sebou, a KAŽDÝ příští `run` (třeba za týden, na
úplně jiných kapitolách) by tu samou příčinu tiše zkoušel znovu, dokud
by si toho uživatel nevšiml. Přebalení na `FatalRunError` využije
existující `_cmd_run`'s `except FatalRunError: raise` (main.py:1013-1014,
BEZE ZMĚNY) - CELÝ běh se zastaví HNED při první selhávající Codex
exekuci, s jasnou hláškou, ne tiše na pozadí. (`_polish_one_chapter`'s
per-kapitolové zpracování STEJNÉ třídy chyby ze `stylist.polish()`
zůstává beze změny - `polish` nechá kapitolu v bezpečném `done` stavu,
architektonicky jiná situace, ŽÁDNÝ přenositelný precedent na `run`.)

- [ ] **Step 1: Napiš test**

Přidej do `tests/test_pipeline_client.py` (existující soubor - `_db`
fixture, `state`/`config` importy tam už jsou):

```python
def test_codex_llm_client_calls_exec_codex_and_wraps_result(monkeypatch):
    from src.llm.client import CodexLLMClient
    seen = {}
    def fake_exec(prompt, *, codex_cmd, codex_model, timeout, label):
        seen.update(prompt=prompt, codex_cmd=codex_cmd, codex_model=codex_model,
                    timeout=timeout, label=label)
        return "===PREKLAD===\ntext\n===METADATA===\n{}"
    monkeypatch.setattr("src.agents.stylist._exec_codex", fake_exec)
    c = CodexLLMClient(["codex"], "gpt-5.6-terra", timeout=42)
    comp = c.complete(system="SYS", user="USR", max_tokens=1000, model="gpt-5.6-terra")
    assert comp.text == "===PREKLAD===\ntext\n===METADATA===\n{}"
    assert comp.truncated is False
    assert seen["prompt"] == "SYS\n\nUSR"
    assert seen["codex_cmd"] == ["codex"]
    assert seen["codex_model"] == "gpt-5.6-terra"
    assert seen["timeout"] == 42


def test_codex_llm_client_default_timeout_from_config(monkeypatch):
    from src.llm.client import CodexLLMClient
    import config
    monkeypatch.setattr(config, "CODEX_TRANSLATE_TIMEOUT_SECONDS", 111)
    seen = {}
    def fake_exec(prompt, *, codex_cmd, codex_model, timeout, label):
        seen["timeout"] = timeout
        return "ok"
    monkeypatch.setattr("src.agents.stylist._exec_codex", fake_exec)
    c = CodexLLMClient(["codex"], "m")   # timeout NEZADÁN
    c.complete(system="s", user="u", max_tokens=10, model="m")
    assert seen["timeout"] == 111


def test_codex_llm_client_count_tokens_is_conservative_estimate():
    from src.llm.client import CodexLLMClient
    c = CodexLLMClient(["codex"], "m")
    assert c.count_tokens(system="abcd", user="efgh", model="m") == 4   # (4+4)//2


def test_codex_llm_client_billed_model_is_codex_model_not_caller_model():
    from src.llm.client import CodexLLMClient
    c = CodexLLMClient(["codex"], "gpt-5.6-terra")
    assert c.billed_model == "gpt-5.6-terra"


def test_codex_llm_client_wraps_stylist_error_as_fatal_run_error(monkeypatch):
    """Kolo 2 BLOCKING (plan-consensus) - viz vysvětlení výš u Tasku 2 -
    `_exec_codex` selhání (rozbitý CLI, timeout, špatný exit kód) NESMÍ
    propadnout jako obyčejná výjimka, co by `_cmd_run` zpracoval jako
    per-kapitolový `error` (automaticky retrying přes `state.queue_for_
    run`) - musí zastavit CELÝ běh."""
    from src.llm.client import CodexLLMClient
    from src.agents.stylist import StylistError
    def boom(*a, **k):
        raise StylistError("codex exec skončil s kódem 1: auth expired")
    monkeypatch.setattr("src.agents.stylist._exec_codex", boom)
    c = CodexLLMClient(["codex"], "m")
    with pytest.raises(FatalRunError, match="auth expired"):
        c.complete(system="s", user="u", max_tokens=10, model="m")


def test_pipeline_client_uses_billed_model_for_price_not_caller_model(monkeypatch, tmp_path):
    """Kolo 1 BLOCKING (plan-consensus) - jádro opravy. `PipelineLLMClient`
    dostane `model="claude-sonnet-5"` (přesně to, co `translator.py`
    reálně posílá), ale `self._inner` (Codex) má `billed_model="codex-x"`
    s NULOVOU cenou - cena/audit MUSÍ použít `billed_model`, ne
    `"claude-sonnet-5"` (co by mělo nenulovou cenu a spadlo by na
    přísahu FatalRunError "nemá sazby", protože `"claude-sonnet-5"`
    sazby MÁ, ale skutečně běžel Codex, ne Claude)."""
    db = _db(tmp_path)
    rid = state.create_run(db, "run")
    monkeypatch.setattr(config, "PRICE_IN_PER_MTOK",
                        {**config.PRICE_IN_PER_MTOK, "codex-x": 0.0})
    monkeypatch.setattr(config, "PRICE_OUT_PER_MTOK",
                        {**config.PRICE_OUT_PER_MTOK, "codex-x": 0.0})

    class FakeCodexInner:
        provider = "codex"
        billed_model = "codex-x"
        def complete(self, *, system, user, max_tokens, model):
            return Completion(text="ok", truncated=False, input_tokens=100, output_tokens=50)
        def count_tokens(self, *, system, user, model):
            return 10

    c = PipelineLLMClient(FakeCodexInner(), run_id=rid, agent="translator",
                          db_path=db, config_mod=config)
    # `model="claude-sonnet-5"` - PŘESNĚ to, co `translator.py` reálně
    # posílá (žádný explicitní `model=` argument z `pipeline.py`).
    c.complete(system="s", user="u", max_tokens=10, model="claude-sonnet-5")
    with state.connect(db) as conn:
        row = conn.execute("SELECT * FROM llm_calls").fetchone()
    assert row["model"] == "codex-x"        # NE "claude-sonnet-5"
    assert row["cost_usd"] == 0.0            # nulová cena z `billed_model`
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_pipeline_client.py -k "codex_llm_client or pipeline_client_uses_billed_model" -v`
Expected: FAIL - `ImportError: cannot import name 'CodexLLMClient'`
(a `test_pipeline_client_uses_billed_model_for_price_not_caller_model`
padne jinak - `AttributeError: 'FakeCodexInner' object has no attribute`
NEBO projde náhodou, pokud `PipelineLLMClient` ještě `billed_model`
nezná a prostě použije `model` beze změny → `row["model"] ==
"claude-sonnet-5"`, ne `"codex-x"` → assert selže. Obojí je platné FAIL.)
`test_codex_llm_client_wraps_stylist_error_as_fatal_run_error` padne
stejně na `ImportError` (`CodexLLMClient` ještě neexistuje).

- [ ] **Step 3: Implementuj**

V `src/llm/client.py`, HNED ZA `class AnthropicClient` (před
`class FakeLLMClient`), přidej:

```python
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
        prompt = f"{system}\n\n{user}"
        timeout = self._timeout or config.CODEX_TRANSLATE_TIMEOUT_SECONDS
        # Kolo 2 BLOCKING (plan-consensus) - `_exec_codex`'s `StylistError`
        # (rozbitý CLI, vypršelá autentizace, špatný exit kód, timeout,
        # prázdná/rozbitá odpověď) se přebaluje na `FatalRunError`, ne
        # necháváme propadnout jako obyčejnou výjimku. `state.queue_for_
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
        # plan-consensus): `pipeline.process_chapter`'s revizní smyčka
        # nemá checkpoint PŘED revizí (`revise_chapter()` volání NENÍ
        # obalené v `pipeline.py`), takže výjimka BĚHEM revize zahodí i
        # KOMPLETNÍ, validní scénový překlad - deterministický guard by
        # tohle SPOLEHLIVĚ trefil u delší kapitoly (glosář roste s
        # postupem knihy), zatímco `timeout` (jediná pojistka, co
        # zůstává) je vzácnější spouštěč stejného starého architektonického
        # rizika (stejné riziko existuje latentně i pro Claude - `revise_
        # chapter` může selhat na síťové chybě/`FatalRunError` úplně
        # stejně, tenhle plán ho nezavádí nově, jen ho nezhoršuje novým,
        # spolehlivě-se-spouštějícím guardem).
        try:
            text = stylist._exec_codex(prompt, codex_cmd=self._codex_cmd,
                                       codex_model=self._codex_model,
                                       timeout=timeout, label="translator")
        except stylist.StylistError as e:
            raise FatalRunError(str(e)) from e
        # `truncated` VŽDY False (zdokumentovaný limit, viz spec "Známé
        # limity") - Codex nedává spolehlivý signál o useknutí na limitu
        # jako Claude `stop_reason`. Skutečné useknutí spíš spadne na
        # chybějící `===METADATA===` marker uvnitř `translator._parse()`
        # (ValueError), ne na tenhle příznak.
        return Completion(text=text, truncated=False, input_tokens=0, output_tokens=0)

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        # Stejná konzervativní aproximace jako `PipelineLLMClient._guard()`'s
        # vlastní fallback (main.py existující kód, `(len(system)+len(user))
        # //2`) - Codex nemá API pro přesné počítání tokenů.
        return (len(system) + len(user)) // 2
```

**Kolo 1 BLOCKING oprava - `PipelineLLMClient.complete()`** (`src/llm/
client.py`, dnešní řádky ~195-245, viz "Kolo 1 BLOCKING" vysvětlení
výš). Najdi:

```python
    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        from src import state
```

a HNED ZA `from src import state` přidej:

```python
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
```

Pak nahraď VŠECHNY tři existující výskyty holého `model` (ne `max_tokens`
ani `self._inner.complete(model=model, ...)` - TAM zůstává PŮVODNÍ
`model`, viz níž proč) uvnitř týhle metody `effective_model`:

```python
        self._guard(system, user, max_tokens, effective_model)
        ...
        in_rate, out_rate = self._price(effective_model)
```

a v `finally` bloku `record_llm_call`'s `model=model` na `model=
effective_model`:

```python
                state.record_llm_call(
                    self._db, run_id=self._run_id, agent=self._agent,
                    provider=getattr(self._inner, "provider", "unknown"),
                    model=effective_model, input_tokens=it, output_tokens=ot,
                    cost_usd=cost, truncated=bool(comp.truncated) if comp else False,
                    status=status, error_class=err)
```

`self._inner.complete(system=system, user=user, max_tokens=max_tokens,
model=model)` (skutečné volání o pár řádků výš) NECHÁVÁ PŮVODNÍ `model`
BEZE ZMĚNY - pro `AnthropicClient` je to jediná správná hodnota (musí
vědět, KTERÝ Claude model volat); `CodexLLMClient.complete()` svůj
`model` parametr stejně ignoruje (viz kód výš, používá `self._codex_model`).

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_pipeline_client.py -v`
Expected: PASS (všechny, včetně existujících - `effective_model` fallback
na `model` pro klienty bez `billed_model` znamená NULOVOU změnu chování
pro `AnthropicClient`/`FakeLLMClient` cestu)

- [ ] **Step 5: Commit**

```bash
git add src/llm/client.py tests/test_pipeline_client.py
git commit -m "feat: CodexLLMClient + oprava PipelineLLMClient cena/audit pro Codex

PipelineLLMClient.complete() teď používá inner klienta 'billed_model'
(pokud existuje) místo caller-supplied 'model' pro cost guard i audit -
translator.py vždy defaultuje na config.MODEL_TRANSLATOR bez ohledu na
skutečně použitý backend, takže bez týhle opravy by Codex volání
dostala cenu/audit záznam Claude modelu (plan-consensus kolo 1 BLOCKING).

CodexLLMClient.complete() přebaluje stylist.StylistError na
FatalRunError - state.queue_for_run() automaticky retryuje 'error'
kapitoly při každém příštím run, takže rozbitá Codex cesta (CLI/auth)
by jinak potichu selhávala napříč libovolně mnoha budoucími běhy
(plan-consensus kolo 2 BLOCKING).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: `main._client_factory` - `translator_backend` parametr

**Files:**
- Modify: `main.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `CodexLLMClient` (Task 2), `_polish_preflight()` (existující
  main.py funkce - `STYLIST_ACCEPT_FS_RISK` brána + `CODEX_MODEL` +
  `_resolve_codex_cmd`).
- Produces: `_client_factory(run_id: int, *, interactive: bool,
  require_lock=None, translator_backend: str = "claude")` - beze změny
  pro `translator_backend="claude"` (default, VŠECHNA existující volání
  bez tohohle argumentu se chovají identicky). Pro `agent=="translator"`
  a `translator_backend=="codex"` vrátí klienta obalující `CodexLLMClient`;
  pro `agent=="critic"` (nebo cokoli jiného) VŽDY `AnthropicClient`, bez
  ohledu na `translator_backend`.

- [ ] **Step 1: Napiš test**

Přidej do `tests/test_cli.py`:

```python
def test_client_factory_translator_backend_codex_uses_codex_client(monkeypatch):
    from src.llm.client import CodexLLMClient
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex", "resolved"], None))
    factory = main._client_factory(1, interactive=False, translator_backend="codex")
    client = factory("translator")
    assert isinstance(client._inner, CodexLLMClient)
    assert client._inner._codex_model == "m"
    assert client._inner._codex_cmd == ["codex", "resolved"]
    assert client._inner.billed_model == "m"


def test_client_factory_translator_backend_codex_critic_stays_claude(monkeypatch):
    from src.llm.client import AnthropicClient
    monkeypatch.setattr("main._polish_preflight",
                        lambda: ("m", ["codex"], None))
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    factory = main._client_factory(1, interactive=False, translator_backend="codex")
    client = factory("critic")
    assert isinstance(client._inner, AnthropicClient)


def test_client_factory_default_backend_claude_translator_unaffected(monkeypatch):
    """Beze změny chování pro VŠECHNA existující volání bez `translator_
    backend` argumentu - default `"claude"` musí `_polish_preflight`
    vůbec nezavolat (žádná FS-risk kontrola, když se Codex nepoužívá)."""
    from src.llm.client import AnthropicClient
    def boom():
        raise AssertionError("_polish_preflight se nemá volat pro claude backend")
    monkeypatch.setattr("main._polish_preflight", boom)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-test")
    factory = main._client_factory(1, interactive=False)
    client = factory("translator")
    assert isinstance(client._inner, AnthropicClient)


def test_client_factory_translator_backend_codex_preflight_failure_raises_fatal(monkeypatch):
    monkeypatch.setattr("main._polish_preflight",
                        lambda: (None, None, "Codex CLI není použitelné"))
    factory = main._client_factory(1, interactive=False, translator_backend="codex")
    with pytest.raises(FatalRunError, match="Codex CLI není použitelné"):
        factory("translator")
```

(`FatalRunError`/`config` už importované na začátku `tests/test_cli.py`
- `from src.llm.client import FatalRunError` je použité v `test_run_
fatal_error_closes_run_and_exits_nonzero`, zkontroluj a případně
dopň import na začátek souboru, pokud tam ještě není na úrovni modulu.)

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_cli.py -k client_factory_translator_backend -v`
Expected: FAIL - `TypeError: _client_factory() got an unexpected keyword argument 'translator_backend'`

- [ ] **Step 3: Implementuj**

Nahraď `_client_factory` (main.py:54-60):

```python
def _client_factory(run_id: int, *, interactive: bool, require_lock=None,
                    translator_backend: str = "claude"):
    """Klienta staví až při volání - `run` s fake pipeline nikdy nesáhne
    na API. `translator_backend="codex"` (main.py `_cmd_run --translator
    codex`) přepne JEN `agent=="translator"` na `CodexLLMClient` - kritik/
    stylist_check zůstávají VŽDY `AnthropicClient`, bez ohledu na tenhle
    parametr (spike 2026-09-16 ukázal nespolehlivost Codex jako kritika,
    viz docs/superpowers/specs/2026-09-16-codex-translator-backend-design.md).
    Default `"claude"` zachovává PŘESNĚ dnešní chování pro VŠECHNA
    existující volání (`_cmd_polish`/server), co tenhle argument nezadávají -
    `_polish_preflight()` se pro ně vůbec nevolá."""
    def factory(agent: str):
        if agent == "translator" and translator_backend == "codex":
            model, codex_cmd, preflight_err = _polish_preflight()
            if preflight_err:
                raise FatalRunError(preflight_err)
            inner = CodexLLMClient(codex_cmd, model)
        else:
            inner = AnthropicClient()
        return PipelineLLMClient(inner, run_id=run_id, agent=agent,
                                 db_path=config.DB_PATH, config_mod=config,
                                 interactive=interactive, require_lock=require_lock)
    return factory
```

Rozšiř import na main.py:35-36 o `CodexLLMClient`:

```python
from src.llm.client import (AnthropicClient, CodexLLMClient, FatalRunError,
                           LockLostError, OutputTruncated, PipelineLLMClient)
```

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (všechny, včetně existujících - default `translator_backend`
zachovává dnešní chování)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: _client_factory translator_backend param - Codex jen pro translatora

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: CLI `--translator` flag na `run`

**Files:**
- Modify: `main.py` (`_cmd_run`, argparse `p_run`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `python main.py run --translator {claude,codex}` (default
  `claude`). `_cmd_run` předá `args.translator` do `_client_factory`
  jako `translator_backend`.

- [ ] **Step 1: Napiš test**

Přidej do `tests/test_cli.py` (vzor `test_run_processes_queue_with_
monkeypatched_pipeline` výš v souboru):

```python
def test_run_translator_flag_passed_to_client_factory(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.pipeline as P
    seen = {}
    def fake_process(db_path, chapter, *, client_factory, guide):
        seen["client_factory"] = client_factory
        state.update_chapter(db_path, chapter["idx"], status="done",
                             translated_text="hotovo")
        return {"idx": chapter["idx"], "status": "done", "revision_rounds": 0}
    monkeypatch.setattr(P, "process_chapter", fake_process)
    real_factory = main._client_factory
    captured = {}
    def spy_factory(rid, *, interactive, require_lock=None, translator_backend="claude"):
        captured["translator_backend"] = translator_backend
        return real_factory(rid, interactive=interactive, require_lock=require_lock,
                            translator_backend=translator_backend)
    monkeypatch.setattr(main, "_client_factory", spy_factory)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 0
    assert captured["translator_backend"] == "codex"


def test_run_translator_flag_defaults_to_claude(tmp_path, monkeypatch):
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    import src.pipeline as P
    monkeypatch.setattr(P, "process_chapter",
                        lambda db_path, chapter, *, client_factory, guide: {
                            "idx": chapter["idx"], "status": "done", "revision_rounds": 0})
    real_factory = main._client_factory
    captured = {}
    def spy_factory(rid, *, interactive, require_lock=None, translator_backend="claude"):
        captured["translator_backend"] = translator_backend
        return real_factory(rid, interactive=interactive, require_lock=require_lock,
                            translator_backend=translator_backend)
    monkeypatch.setattr(main, "_client_factory", spy_factory)
    assert _run(["run"], tmp_path, monkeypatch) == 0   # BEZ --translator
    assert captured["translator_backend"] == "claude"


def test_run_translator_codex_without_fs_risk_optin_is_fatal(tmp_path, monkeypatch):
    """Stejná brána jako `polish` - `--translator codex` bez opt-inu
    nesmí tiše spadnout zpátky na Claude ani projít bez varování.
    `_client_factory` je LÍNÁ (staví klienta až při volání, viz Task 3
    docstring) - `pipeline.process_chapter` se NEmockuje, běží doopravdy
    a FatalRunError vyletí zevnitř, JAKMILE se translator poprvé zavolá
    (`client_factory("translator")` uvnitř `translator.translate_scene`),
    ne dřív - žádné síťové volání se přitom nestihne, chyba je první věc."""
    book = tmp_path / "k.txt"
    book.write_text("Chapter 1\n" + "t " * 60, encoding="utf-8")
    _run(["init", str(book)], tmp_path, monkeypatch)
    monkeypatch.setattr(config, "STYLIST_ACCEPT_FS_RISK", False)
    assert _run(["run", "--translator", "codex"], tmp_path, monkeypatch) == 1
    assert state.get_chapter("data/state.sqlite3", 1)["status"] in ("pending", "processing")
```

- [ ] **Step 2: Ověř selhání**

Run: `pytest tests/test_cli.py -k run_translator -v`
Expected: FAIL - `error: unrecognized arguments: --translator codex`
(argparse ještě flag nezná)

- [ ] **Step 3: Implementuj**

V argparse sekci (main.py, `p_run` definice, dnes ~řádek 1524-1530),
přidej:

```python
    p_run.add_argument("--translator", choices=["claude", "codex"],
                       default="claude",
                       help="překladatelský backend (default claude; "
                            "codex vyžaduje STYLIST_ACCEPT_FS_RISK=True)")
```

V `_cmd_run` (main.py:1000), nahraď:

```python
        cf = _client_factory(rid, interactive=True)
```

za:

```python
        cf = _client_factory(rid, interactive=True,
                             translator_backend=args.translator)
```

Poznámka - `--translator codex` bez `STYLIST_ACCEPT_FS_RISK` NEspadne
hned na začátku `_cmd_run` (na rozdíl od `_cmd_polish`, co preflight
kontroluje PŘED frontou) - `_client_factory` je líná (staví klienta až
při PRVNÍM `client_factory("translator")` volání uvnitř `process_chapter`
pro PRVNÍ kapitolu ve frontě), takže `FatalRunError` vyletí AŽ TAM. To je
zamýšlené (`_client_factory`'s vlastní docstring: "klienta staví až při
volání"), ne mezera - `_cmd_run`'s `except FatalRunError: raise` (main.py:
1013-1014) běh stejně zastaví ROVNOU u první kapitoly, PŘED jakýmkoli
Codex voláním, se stejnou hláškou jako `polish` by dal.

- [ ] **Step 4: Ověř úspěch**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cli.py
git commit -m "feat: python main.py run --translator {claude,codex}

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: Manuální ověření + dokončení branch

**Files:** žádné nové - ověřovací krok.

- [ ] **Step 1: Spusť celou sadu**

Run: `pytest -v`
Expected: PASS, 0 chyb.

- [ ] **Step 2: Manuální ověření na reálné kapitole**

**NE rovnou nad `data/state.sqlite3` u prvního ostrého spuštění** -
`run` nemá `--db` parametr, vždy čte `config.DB_PATH` (`config.py:39-42`,
odvozené z `config.PROJECT_DIR`). Použij existující mechanismus na
izolovaný projektový adresář (`BOOK_TRANSLATOR_PROJECT_DIR` env var,
z dřívějšího Tasku "parametrizuj kořenovou složku projektu") - NE
prostý `cp` databáze (kolo 1 IMPORTANT, plan-consensus - `run`/`state.
connect` by furt mířily na `data/state.sqlite3` v aktuálním adresáři,
kopie by se nikdy nepoužila):

Bash (Git Bash/WSL - stejné nástroje, co používá tenhle plán i celá
testovací sada):

```bash
mkdir -p /tmp/codex-translator-smoke/data
cp data/state.sqlite3 /tmp/codex-translator-smoke/data/state.sqlite3
cp data/guide.json /tmp/codex-translator-smoke/data/guide.json
BOOK_TRANSLATOR_PROJECT_DIR=/tmp/codex-translator-smoke \
  python main.py run --translator codex --only <idx>
BOOK_TRANSLATOR_PROJECT_DIR=/tmp/codex-translator-smoke \
  python main.py status
```

PowerShell (kolo 2 IMPORTANT, plan-consensus - projekt běží primárně na
Windows/PowerShell, `mkdir -p`/inline `VAR=val` je bash-only syntax):

```powershell
$smoke = "$env:TEMP\codex-translator-smoke"
New-Item -ItemType Directory -Force "$smoke\data" | Out-Null
Copy-Item data\state.sqlite3 "$smoke\data\state.sqlite3"
Copy-Item data\guide.json "$smoke\data\guide.json"
$env:BOOK_TRANSLATOR_PROJECT_DIR = $smoke
python main.py run --translator codex --only <idx>
python main.py status
```

Zkontroluj: kapitola má rozumný český text, `new_terms`/`questions` (pokud
kapitola nějaké má) vypadají smysluplně, `python main.py polish --only
<idx>` (Codex, beze změny, se stejným `BOOK_TRANSLATOR_PROJECT_DIR`
nastaveným) na výsledku projde stejně jako dřív. Teprve PO tomhle ověření
zkus `--translator codex` i nad reálnou `data/state.sqlite3` (bez
`BOOK_TRANSLATOR_PROJECT_DIR`/po zavření PowerShell session, co proměnnou
nastavila), na jedné konkrétní `pending` kapitole.

- [ ] **Step 3: Invoke `superpowers:finishing-a-development-branch`**

Ověř testy, prezentuj možnosti (merge/PR/nechat), proveď podle volby
uživatele.
