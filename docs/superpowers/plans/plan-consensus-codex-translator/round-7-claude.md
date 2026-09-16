# Round 7 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (`CodexLLMClient.complete()` zachytává jen `StylistError`):**
  Souhlasím, ověřil jsem - `_exec_codex()` (`src/agents/stylist.py:426`)
  čte výstupní soubor `with open(out_path, "r", encoding="utf-8") as f:
  result = f.read().strip()` BEZ VLASTNÍHO try/except, mimo
  `StylistError` kontrakt (ten pokrývá jen `Popen`/`communicate`/exit
  kód/prázdnou odpověď/markdown obal). Poškozený zápis by vyhodil
  `UnicodeDecodeError`, zámek/oprávnění na dočasném souboru `OSError` -
  obojí by unikly `except stylist.StylistError` a propadly stejnou
  cestou, co kolo 6 opravilo pro `InvalidTranslationOutput` (obyčejná
  výjimka → per-kapitolový `error` → `state.queue_for_run`'s automatický
  retry navěky).

  **Oprava:** `except (stylist.StylistError, OSError, UnicodeError) as e:`
  - širší tuple, `_exec_codex`/`stylist.py` samotné beze změny (mimo
    rozsah). Přidán test `test_codex_llm_client_wraps_os_and_unicode_
  errors_as_fatal_run_error`.

- **IMPORTANT (test nerozlišuje `model` param od `codex_model`):**
  Souhlasím - test posílal `model="gpt-5.6-terra"` (STEJNÉ jako
  `codex_model`), takže by nezachytil regresi, kdy implementace omylem
  použije caller-supplied `model` místo `self._codex_model` pro
  `_exec_codex()`'s `codex_model=`. Opraveno na `model="claude-sonnet-5"`
  (přesně to, co `translator.py` reálně vždy posílá) - `seen["codex_
  model"]` assert teď SKUTEČNĚ ověřuje, že implementace ignoruje `model`
  param a použije `self._codex_model`.

- **IMPORTANT (Task 6 smoke test nezajišťuje pending `<idx>`):**
  Souhlasím - `--only` filtruje `queue_for_run()`, na `done`/`flagged`
  kapitole by nic neproběhlo a `status` by ukázal starý překlad, ne
  chybu v Codex cestě. Přidána instrukce zjistit `pending <idx>` přes
  `status` PŘED spuštěním, plus `sqlite3` dotaz na `llm_calls` ověřující
  `provider='codex'`/`cost_usd=0.0` po běhu (ověří kolo-1's `billed_
  model` opravu na REÁLNÉM běhu, ne jen v testech).

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 7: tři IMPORTANT body, všechny akceptovány. `CodexLLMClient.
complete()` teď zachytává i `OSError`/`UnicodeError` (ne jen
`StylistError`) - `_exec_codex()`'s čtení výstupního souboru není
kryté vlastním try/except. Task 3's klíčový test opraven, aby SKUTEČNĚ
ověřoval, že implementace ignoruje caller `model` param (test dřív
používal stejnou hodnotu pro obojí, takže regresi nezachytil). Task 6's
manuální ověření zpřesněno - explicitní pending-kapitola instrukce a
`llm_calls` SQL kontrola místo jen vizuální kontroly textu.
