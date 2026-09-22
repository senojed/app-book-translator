# Kritik přes `claude` CLI (předplatné) místo Anthropic API - Design

## Cíl

Kritik (`_run_critic()`/`critic.review()`) dnes VŽDY volá `AnthropicClient`
(placené API, `ANTHROPIC_API_KEY`). Cíl: přepnout kritika natvrdo na
`claude` CLI (Claude Code), co běží na uživatelově existujícím
předplatném (OAuth session) - stejný princip jako `--translator codex`
(kolo 2026-09-16), jen teď pro kritika a s jiným CLI nástrojem.

**Rozsah** (viz brainstorming session 2026-09-21): JEN kritik. Translator
zůstává beze změny (`--translator claude|codex`, obojí beze změny).
Žádný fallback na API - kritik po týhle změně `ANTHROPIC_API_KEY`
vůbec nepotřebuje.

## Ověřeno spikem (2026-09-21, tahle konverzace)

- `claude` CLI je nainstalované, verze 2.1.257.
- `claude -p --safe-mode --tools "" --system-prompt "<S>" "<U>"` (S/U
  jako pozicní argumenty) funguje: exit 0, čistý stdout (jen odpověď),
  žádný stderr šum. **DOPLŇUJÍCÍ ověření (plan-consensus kolo 1, viz
  implementační plán):** `<U>` MUSÍ jít STDINEM, ne pozicním argumentem
  (kapitola EN+CZ text může snadno přesáhnout Windows argv limit
  ~8191 znaků) - `echo "<U>" | claude -p --safe-mode --tools ""
  --system-prompt "<S>"` ověřeno FUNGUJE STEJNĚ (systémová priorita
  zachovaná). Finální architektura (níž) používá TENHLE tvar.
- **Bez `--safe-mode`**: holé `claude -p` natáhne uživatelovo globální
  `~/.claude/CLAUDE.md` (v testu prosáklo do odpovědi, i s explicitním
  `--system-prompt`) - kritik by dědil uživatelovy osobní instrukce
  (caveman mode, timestampy atd.), NECHTĚNÉ.
- **`--bare`** by taky izolovalo od CLAUDE.md/pluginů, ALE dokumentace
  CLI výslovně říká: v `--bare` módu je auth JEN `ANTHROPIC_API_KEY`/
  `apiKeyHelper` - OAuth/keychain se NEČTE. Použití `--bare` by tedy
  vyžadovalo zpátky placený API klíč - PŘESNÝ OPAK cíle týhle změny.
- **`--safe-mode`** izoluje (CLAUDE.md/skills/pluginy/hooky vypnuté),
  ALE auth nechává normální (OAuth) - ověřeno přímo (`ANTHROPIC_API_KEY`
  nenastavený v prostředí, `claude -p --safe-mode` přesto odpověděl).
  **Tohle je správná volba, ne `--bare`.**
- `--tools ""` (doslovně prázdný string) vypíná VŠECHNY nástroje -
  ověřeno, kritik nemá žádný přístup k disku/Bash ani náhodou.
- `--output-format json` vrací `usage` (`input_tokens`/`output_tokens`)
  a `total_cost_usd` - `total_cost_usd` je JEN informativní "list price"
  odhad (`costBasis: "list"` v `modelUsage`), NE skutečná fakturace -
  běží se na předplatném, ne na měřeném klíči. Token counts z `usage`
  jsou ale reálná čísla, použitelná pro audit (přesnější než Codexova
  `//2` aproximace).
- Časování: ~4s pro triviální jednoslovní prompt (včetně ~40k cache
  tokenů z `--safe-mode`'s defaultního system promptu) - reálný kritický
  průchod (celá kapitola EN+CZ) bude pomalejší, řádově srovnatelné s
  Codexovým 70-120s (spike 2026-09-16).

## Architektura

Nová třída `ClaudeCliClient` v NOVÉM modulu `src/llm/claude_cli.py`
(NE v `stylist.py` - ten je Codex-specifický, FS-risk gate a spol.,
kritický CLI klient nic z toho nepotřebuje - viz rozhodnutí v
brainstorming session). Stejný `LLMClient` protokol jako
`AnthropicClient`/`CodexLLMClient`:

```python
class ClaudeCliClient:
    provider = "claude-cli"

    def __init__(self, claude_cmd: list[str], model: str,
                 timeout: int | None = None): ...
    def complete(self, *, system, user, max_tokens, model) -> Completion: ...
    def count_tokens(self, *, system, user, model) -> int: ...
```

`billed_model` atribut (stejný vzor jako `CodexLLMClient`) - `$0.0`
cenová tabulka, `PipelineLLMClient.complete()`'s existující
`effective_model` mechanismus (z kolo-1 fixu předchozího plánu) tohle
zvládne BEZE ZMĚNY - `ClaudeCliClient` je jen DALŠÍ klient s
`billed_model`, žádná nová logika v `PipelineLLMClient` potřeba.

### Subprocess volání

```python
argv = [claude_bin, "-p", "--safe-mode", "--tools", "", "--output-format",
       "json", "--model", model, "--system-prompt", system]
# `user` NENÍ v argv - jde STDINEM (`subprocess.Popen(argv, stdin=PIPE,
# ...).communicate(input=user, ...)`) - plan-consensus kolo 1 IMPORTANT
# (implementační plán) - kapitola EN+CZ text může snadno přesáhnout
# Windows argv limit (~8191 znaků), stejný důvod jako Codexův stdin
# vzor v `stylist._exec_codex`. `system` (kritikovy instrukce, 805
# znaků, statické) zůstává v argv přes `--system-prompt` - bezpečně
# pod limitem, a systémová priorita se zachovává jen takhle (spojení
# system+user do jednoho stdin blobu by ji degradovalo na "jen další
# text").
```

- `system`/`user` odpovídají PŘESNĚ `critic.review()`'s existujícím
  argumentům (`client.complete(system=..., user=..., ...)`) -
  `critic.review()` se NEMĚNÍ ANI O ŘÁDEK, dostává libovolný
  `LLMClient`-kompatibilní klient.
- `model` = `config.MODEL_CRITIC` ("claude-sonnet-5") předané přes
  `--model` - stejná hodnota, co dnes jde do API, resolvne se stejně
  na CLI straně.
- Timeout: NOVÝ `config.CLAUDE_CLI_CRITIC_TIMEOUT_SECONDS = 180`
  (kratší než translatorových 300s - kritický průchod je kratší úkol).
- `subprocess.Popen(argv, stdin=PIPE, stdout=PIPE, stderr=PIPE,
  text=True, encoding="utf-8")` + `.communicate(input=user,
  timeout=timeout)` - NE `subprocess.run(timeout=...)` (implementační
  plán, `_exec_claude()`) - `Popen` umožňuje na Windows spolehlivě
  zabít celý proces-strom při timeoutu/přerušení (`stylist.
  _kill_process_tree`, reuse ze stylist.py), `run(timeout=)` by po
  timeoutu nechal osiřelý `claude`/dítě proces běžet dál. `encoding=
  "utf-8"` explicitně (stejný důvod jako `translator._parse()`'s CRLF
  normalizace, viz předchozí plán).

### Parsování výstupu

`--output-format json` → `json.loads(stdout)`:
- `result` pole = text odpovědi (to, co `critic.review()` dál
  parsuje jako JSON nálezy - beze změny, `ClaudeCliClient.complete()`
  vrátí `result` jako `Completion.text`).
- `usage.input_tokens`/`usage.output_tokens` → `Completion.input_tokens`/
  `output_tokens` (reálná čísla z CLI, ne aproximace).
- `is_error`/`subtype` - pokud `is_error` je `True` nebo `subtype !=
  "success"`, jde o chybu (viz níž).
- `total_cost_usd` se ČTE, ale NEPOUŽÍVÁ pro `record_llm_call` -
  `PipelineLLMClient` počítá cenu sám z `billed_model`'s `$0.0` sazby,
  ne z CLI výstupu (jinak by matoucí "list price" skončilo v audit
  logu jako by šlo o SKUTEČNOU útratu).

### Chybové stavy

Nová `ClaudeCliFatalError(FatalRunError)` (`src/llm/client.py`, HNED
ZA `CodexTranslatorFatalError` - stejný vzor):
- nenulový exit kód subprocessu,
- nečitelný/nerozparsovatelný JSON výstup,
- `is_error: true` v JSON výstupu.

**Timeout NENÍ fatální** - `subprocess.TimeoutExpired` (přes
`Popen.communicate(timeout=)`) se hlásí SAMOSTATNOU
`ClaudeCliTimeoutError` (implementační plán), NE jako
`ClaudeCliFatalError` - `_run_critic()`'s existující `except
Exception: pseudo-finding, critic_failed=True` větev tohle zachytí
stejně jako dnešní transientní kritikovy chyby (síť atd.), místo
zastavení celého runu jako u fatální auth chyby.

Zpráva jde přes `stylist._redact_detail()` (existující funkce, beze
změny - `ClaudeCliClient` si ji naimportuje stejně jako `CodexLLMClient`
dělá se `stylist._exec_codex`).

`_run_critic()` (`pipeline.py`, beze změny) MÁ VLASTNÍ `except
FatalRunError: raise` / `except Exception: pseudo-finding,
critic_failed=True` - `ClaudeCliFatalError` (podtřída `FatalRunError`)
propaguje stejně jako dnešní `AnthropicClient`'s `FatalRunError`
(auth chyby atd.) - `_cmd_run`'s existující `except FatalRunError:
raise` větev (main.py, BEZE ZMĚNY) to zachytí, `_checkpoint_flagged()`
(z předchozího plánu) uloží poslední platný `cz` jako `flagged`.

**Žádná nová typová větev v `_cmd_run` potřeba** - `ClaudeCliFatalError`
NENÍ `CodexTranslatorFatalError` (translator-specifická), takže spadne
do obecné `except FatalRunError` větve stejně jako dnešní kritikovy
chyby - kritik zůstává mimo `--translator codex`'s speciální
flagged/redakci zacházení (to je pořád jen pro TRANSLATOR selhání).

## Změny v `_client_factory` (main.py)

```python
def _client_factory(run_id, *, interactive, require_lock=None,
                    translator_backend="claude", claude_cmd=None):
    def factory(agent: str):
        if agent == "translator" and translator_backend == "codex":
            ...  # beze změny
        elif agent == "critic":
            # NOVĚ, MÍSTO AnthropicClient() - `claude_cmd` je preflightem
            # PŘEDEM resolvnutá binárka (main.py `_claude_cli_preflight()`),
            # NE bare "claude" - viz implementační plán, kolo 3.
            inner = ClaudeCliClient(claude_cmd or ["claude"],
                                    config.MODEL_CRITIC)
        else:
            inner = AnthropicClient()  # translator při --translator claude
        ...
    return factory
```

**Ruší se:** `_cmd_run`'s eager `ANTHROPIC_API_KEY` kontrola (main.py,
"kolo 22" z předchozího plánu) - kritik už žádný API klíč nepotřebuje,
kontrola by kontrolovala něco, na čem už nezáleží. `config.
ANTHROPIC_API_KEY`/`AnthropicClient` zůstávají v kódu (translator může
být pořád `--translator claude`), jen kritik je přestává používat.

## Testování

`ClaudeCliClient` testovatelné stejným vzorem jako `CodexLLMClient` -
`monkeypatch.setattr(subprocess, "run", fake_run)` (nebo lokální
`_exec_claude()` helper analogický `stylist._exec_codex()`, mockovaný
stejně). `critic.review()` samo se NETESTUJE znovu - bere libovolný
`LLMClient`, existující testy s `FakeLLMClient` zůstávají beze změny.

Integrace: `_client_factory`'s `agent=="critic"` větev teď staví
`ClaudeCliClient` - existující testy (`test_client_factory_translator_
backend_codex_critic_stays_claude` a spol.) potřebují update na nový
typ (`ClaudeCliClient` místo `AnthropicClient`).

## Otevřené otázky pro implementační plán

- Přesný název `_exec_claude()` helperu a jeho umístění uvnitř
  `src/llm/claude_cli.py` (subprocess detaily - stdin/stdout handling,
  `claude` binárky resolution - analogické `stylist._resolve_codex_cmd`).
- Jestli `claude` CLI resolution potřebuje vlastní `_resolve_claude_cmd`
  (PATH lookup, `shutil.which`) jako Codex, nebo stačí bare `"claude"`
  (spike použil `claude` z PATH přímo, fungovalo).
