# Round 1 — Claude critique

## Claude's own findings
### BLOCKING
(žádné vlastní nové nad rámec Codexova bodu)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **BLOCKING (`system`/`user` spojené do stdin, ztráta systémové
  priority):** Souhlasím a ověřil jsem spikem přímo - `_exec_claude`'s
  navržený kód (`prompt = f"{system}\n\n{user}"`, jeden stdin blob) BYL
  reálný regres oproti tomu, co jsem v BRAINSTORMING konverzaci sám
  ověřil fungující (`--system-prompt` flag). Napsal jsem plán podle
  Codexova mylného vzoru (`CodexLLMClient`'s `prompt = f"{system}\n\n
  {user}"`), i když Codex CLI (`codex exec`) žádný `--system-prompt`
  ekvivalent NEMÁ - `claude -p` ANO. Ověřil jsem `claude -p --safe-mode
  --tools "" --system-prompt "X" <<< "user text"` funguje SPRÁVNĚ
  (systémová instrukce respektovaná, uživatelský obsah ze stdin).

  **Oprava:** `_exec_claude(system, user, *, claude_cmd, model,
  timeout)` - `system` jde přes `--system-prompt`, `user` STDINEM.
  `ClaudeCliClient.complete()` volá `_exec_claude(system, user, ...)`
  ODDĚLENĚ, ne spojené. Testy přepsané na oddělené argumenty, přidán
  test ověřující `--system-prompt` flag v argv.

- **IMPORTANT (timeout - Global Constraints vs. implementace):**
  Souhlasím - reálná nekonzistence v MÉM VLASTNÍM textu. Global
  Constraints tvrdily "timeout → ClaudeCliFatalError", ale Step 7's
  kód timeout ÚMYSLNĚ nechává propadnout jako `ClaudeCliTimeoutError`
  (s dobrým zdůvodněním v komentáři - stejné jako Codexův
  `StylistTimeoutError`). Implementace byla SPRÁVNĚ navržená, Global
  Constraints text byl ŠPATNÝ.

  **Oprava:** Přepsán Global Constraints odstavec - timeout explicitně
  VYJMUT ze seznamu `ClaudeCliFatalError` triggerů, s vysvětlením proč.

- **IMPORTANT (jen `is_error`, žádná typová validace payloadu):**
  Souhlasím - ověřil jsem přímo proti `critic.py`'s vlastní historii
  (kolo 7 BLOCKING minulého plánu - `extract_json()` slibuje dict, ale
  za běhu vrátí cokoli validní JSON). Stejná třída rizika platí pro
  `claude -p`'s JSON výstup - `[]`/`null`/non-string `result`/non-dict
  `usage` by unikly jako neklasifikované `AttributeError`/`TypeError`
  MIMO `ClaudeCliExecError` kontrakt, nebo by rozbily audit log.

  **Oprava:** `_exec_claude()` teď validuje CELÝ kontrakt - `payload`
  je dict, `is_error` je falsy A `subtype == "success"`, `result` je
  str, `usage` (pokud přítomné) je dict. Přidány 4 nové testy.

- **IMPORTANT (jen 2 typy výjimek přebalené, `UnicodeError`/`OSError`
  unikají neredigované):** Souhlasím - ověřil jsem `_exec_claude()`'s
  vlastní `except BaseException: kill_tree; raise` (bare re-raise,
  ŽÁDNÁ redakce) by nechalo `UnicodeDecodeError` (poškozené kódování
  stdout) propadnout AŽ z `ClaudeCliClient.complete()`, protože jeho
  `except` klauzule chytala jen `(ClaudeCliUnavailable,
  ClaudeCliExecError)`. Stejná třída rizika jako `CodexLLMClient`'s
  kolo 7 IMPORTANT (minulý plán) - a stejná oprava.

  **Oprava:** `except` klauzule rozšířená na `(ClaudeCliUnavailable,
  ClaudeCliExecError, OSError, UnicodeError)`. Přidán test.

- **IMPORTANT (žádná eager `claude` CLI dostupnost/login kontrola po
  zrušení ANTHROPIC_API_KEY):** Souhlasím - přesný stejný vzor jako
  Codexova eager preflight (minulý plán, kolo 3/8 IMPORTANT) - bez ní
  by se u `--translator codex` mohla přeložit CELÁ (zaplacená)
  kapitola, než kritik zjistí chybějící/nepřihlášené CLI. Ověřil jsem
  `claude auth status --json` (~0.5s, žádné API volání) jako levný
  preflight signál.

  **Oprava:** Nová `_claude_cli_preflight()` (main.py, vedle existující
  `_polish_preflight()`) - resolvne binárku + ověří `loggedIn: true`.
  Volá se PŘED frontou, NEZÁVISLE na `args.translator` (kritik je vždy
  aktivní). Nahrazuje zrušený `ANTHROPIC_API_KEY` blok. Přidán test +
  poznámka, že VŠECHNY existující `_run(["run"...])` testy potřebují
  novou mock.

- **IMPORTANT (`max_tokens` ignorován, `truncated=False` vždy):**
  Souhlasím ČÁSTEČNĚ s diagnózou, opravil jsem tu ČÁST, co je reálně
  opravitelná - ověřil jsem spikem, že `claude -p --output-format json`
  VRACÍ `stop_reason` pole (stejný signál jako Anthropic API). Na
  rozdíl od Codexu (kde `truncated=False` je zdokumentovaný limit BEZ
  náhrady) tady náhrada EXISTUJE a MĚLA se použít.

  **Oprava:** `truncated = payload.get("stop_reason") == "max_tokens"`
  místo natvrdo `False`. `max_tokens` parametr samotný STÁLE nemá CLI
  ekvivalent (žádný limit flag existuje) - tohle zůstává zdokumentovaný,
  přijatý limit (stejná třída jako Codex), ale teď je aspoň DETEKCE
  truncation správná, i když ne PREVENCE.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 1: jeden BLOCKING (systémový prompt ztratil prioritu - spojený se
stdin místo `--system-prompt` flagu, přestože jsem přesně tohle ověřil
funkční ve spikeu PŘED napsáním plánu) + pět IMPORTANT (timeout
nekonzistence mezi Global Constraints a implementací, chybějící
payload validace, úzký exception-wrapping, chybějící eager CLI/login
kontrola, ignorovaný `stop_reason` signál). Všechny opraveny přímo v
kódu plánu. První kolo, ale plán vznikl v JEDNOM sezení bez
mezikrokové verifikace každého detailu - podobná hustota nálezů jako
minulého plánu první kola.
