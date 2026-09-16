# Codex jako volitelný překladatelský backend - design

## Kontext a cíl

`run` (počáteční překlad) dnes vždycky volá Claude API (`AnthropicClient`
přes `PipelineLLMClient`) pro translatora i kritika. `polish` (stylistický
průchod) vždycky volá Codex CLI (`stylist.polish`, subprocess). Codex běží
na předplatném (tokeny v rámci paušálu), Claude API se platí zvlášť za
token.

Spike test (2026-09-16, `data/spikes/`) ověřil na kapitole 1 a 4:
- Codex jako translator (s glosářem v promptu) dává kvalitu srovnatelnou
  s Claude, `0` konkordančních nálezů, konzistentní terminologii.
- Codex umí i strukturovaný `===PREKLAD===`/`===METADATA===` formát
  (`new_terms`/`rendered_terms`/`questions`) - `translator._parse()`
  jeho výstup rozparsoval bez úprav.
- Codex jako KRITIK je méně spolehlivý - jeden test vrátil nekonzistentní
  verdikt ("revise" bez odpovídajícího nálezu), o revizní kolo víc, horší
  finální stav (flagged místo done).

Cíl: **umožnit přepnout translatora na Codex, kritik zůstává vždy na
Claude** (nezávislá kontrola jiným modelem). `polish` beze změny (Codex
dnes, Codex zítra).

## Mimo rozsah

- Kritik/stylist_check přes Codex - spike ukázal reálné riziko
  (nekonzistentní verdikty), netestováno dost na to, aby šlo nasadit.
- Automatická volba backendu podle kapitoly/nákladů - vybírá si uživatel
  ručně přes CLI flag.
- Migrace stávajících `done`/`flagged` kapitol na Codex překlad zpětně -
  týká se jen NOVĚ překládaných kapitol.
- Revize `_exec_codex`/`stylist.py`'s subprocess mechaniky - používá se
  beze změny, jen přes novou obálku.

## Architektura

```
python main.py run --translator codex --only 11 12
                                 │
                                 ▼
                    _cmd_run's _client_factory(rid, interactive=True,
                                               translator_backend="codex")
                                 │
                    agent="translator" ──► CodexLLMClient (subprocess)
                    agent="critic"     ──► AnthropicClient (VŽDY, beze změny)
                                 │
                    (obě obalené PipelineLLMClient - stejný audit/cost-guard
                     kód jako dnes, jen Codex má cenu $0/token)
```

`CodexLLMClient` implementuje stejný `LLMClient` protokol jako
`AnthropicClient` (`complete()`/`count_tokens()`), takže `PipelineLLMClient`
ho obalí BEZE ZMĚNY - žádná nová vrstva cost-guard/audit logiky, žádné
nové obcházení `require_lock`/`record_llm_call`.

## Nové/změněné části

### `config.py`

```python
CODEX_TRANSLATE_TIMEOUT_SECONDS = 300   # spike volání trvala 70-120s, rezerva
```

`PRICE_IN_PER_MTOK`/`PRICE_OUT_PER_MTOK` dostanou záznam pro
`CODEX_MODEL` s hodnotou `0.0` (řádek MUSÍ být AŽ PO definici
`CODEX_MODEL`, ne uvnitř literálu dictu, kde `CODEX_MODEL` ještě
neexistuje):

```python
PRICE_IN_PER_MTOK[CODEX_MODEL] = 0.0
PRICE_OUT_PER_MTOK[CODEX_MODEL] = 0.0
```

Bez tohohle by `PipelineLLMClient._price()` vyhodilo `FatalRunError`
("nemá sazby") při prvním Codex-translator volání - cenová tabulka je
dnes striktní allowlist, ne fallback na 0.

### `src/llm/client.py` - `CodexLLMClient`

Nová třída vedle `AnthropicClient`, stejný `LLMClient` protokol:

```python
class CodexLLMClient:
    provider = "codex"

    def __init__(self, codex_cmd: list[str], codex_model: str,
                 timeout: int | None = None):
        self._codex_cmd = codex_cmd
        self._codex_model = codex_model
        self._timeout = timeout or config.CODEX_TRANSLATE_TIMEOUT_SECONDS

    def complete(self, *, system: str, user: str, max_tokens: int, model: str) -> Completion:
        # Lokální import (ne na úrovni modulu) - `client.py` je nízkoúrovňová
        # provider vrstva, `stylist.py` je agent-vrstva o patro výš (má
        # `config`/subprocess specifika); import na úrovni modulu by
        # obrátil směr závislosti, co zbytek souboru dodržuje (viz
        # `PipelineLLMClient.complete()`'s `from src import state` - stejný
        # vzor, lokální import kvůli vrstvení, ne kvůli cyklu).
        from src.agents import stylist
        prompt = f"{system}\n\n{user}"
        text = stylist._exec_codex(prompt, codex_cmd=self._codex_cmd,
                                   codex_model=self._codex_model,
                                   timeout=self._timeout, label="translator")
        # `truncated` VŽDY False - Codex (na rozdíl od Claude `stop_reason`)
        # nedává spolehlivý signál o uříznutí na limitu. Skutečné useknutí
        # spíš spadne na chybějící `===METADATA===` marker uvnitř
        # `translator._parse()` (ValueError), ne na tenhle příznak - funkční
        # pojistka, jen méně přesná chybová hláška. Zdokumentovaný,
        # akceptovaný limit (viz "Známé limity" níž), ne bug k dořešení.
        return Completion(text=text, truncated=False, input_tokens=0, output_tokens=0)

    def count_tokens(self, *, system: str, user: str, model: str) -> int:
        # Stejná konzervativní aproximace jako `PipelineLLMClient._guard()`'s
        # vlastní fallback, když `count_tokens` selže (main.py existující
        # kód) - Codex nemá API pro přesné počítání tokenů.
        return (len(system) + len(user)) // 2
```

### `main.py` - `_client_factory`

```python
def _client_factory(run_id: int, *, interactive: bool, require_lock=None,
                    translator_backend: str = "claude"):
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

`_polish_preflight()` se POUŽIJE ZNOVU beze změny (`STYLIST_ACCEPT_FS_RISK`
brána, `CODEX_MODEL` kontrola, `_resolve_codex_cmd`) - stejné bezpečnostní
riziko (agentic Codex má čtecí přístup k celému disku) platí pro
translator roli stejně jako pro `polish`. Chybová hláška zůstává beze
změny i když teď platí pro dvě různé cesty - je obecná ("`polish`
je vypnutý: spouští agentní `codex exec`...") a zmiňuje konkrétní
zápis do `config.py`, ne konkrétní příkaz, takže sedí i tady.

`_cmd_run`'s volání `_client_factory(rid, interactive=True)` (main.py:1000)
se rozšíří o `translator_backend=args.translator`.

### `main.py` - argparse

```python
run_parser.add_argument("--translator", choices=["claude", "codex"],
                        default="claude",
                        help="překladatelský backend (default claude)")
```

Platí pro CELÝ běh (`run --only 11 12 --translator codex`), ne
kapitolu-po-kapitole v rámci jednoho příkazu - to odpovídá tomu, jak
`--only` selekci chápe uživatel dnes (jeden běh, jedna volba).

## Testování

- `tests/test_pipeline_client.py` - nové testy pro `CodexLLMClient`
  (mock `stylist._exec_codex`, ověřit `complete()`/`count_tokens()`
  kontrakt, `truncated` vždy `False`).
- `tests/test_cli.py` - `_client_factory` s `translator_backend="codex"`
  vrací pro agenta `"translator"` klienta obalující `CodexLLMClient`
  (mock `_polish_preflight`), pro `"critic"` pořád `AnthropicClient`
  bez ohledu na `translator_backend`. `_cmd_run --translator codex`
  bez `STYLIST_ACCEPT_FS_RISK` selže se stejnou hláškou jako `polish`.
- Manuální ověření (mimo pytest, jako u `polish-review` dřív): jedna
  reálná kapitola přes `run --translator codex --only <idx>` nad
  testovací/oddělenou DB, ne rovnou nad `data/state.sqlite3` u prvního
  ostrého spuštění.

## Známé limity (vědomě přijaté, ne k dořešení v týhle spec)

- `truncated` vždy `False` u `CodexLLMClient` - viz kód výš.
- Kritik/stylist_check zůstává VŽDY na Claude, i při `--translator
  codex` - záměrné (spike ukázal nespolehlivost Codex-jako-kritik),
  ne dočasné omezení.
- `count_tokens()` aproximace (`len//2`) může nadhodnotit cenový odhad
  cost guardu - u Codexu je to neškodné (cena `0.0`/token), u budoucího
  znovupoužití pro jiný účel by to stálo za přesnější řešení.
