# Round 6 — Claude critique

## Claude's own findings
### BLOCKING
(žádné vlastní nové - Codexovo BLOCKING níž jsem nezávisle ověřil)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **BLOCKING (test/implementace vzorec neshoda u `input_tokens`):**
  Souhlasím, spočítal jsem obojí - test `len("SYS\n\nUSR")//2 == 4`,
  implementace `(len("SYS")+len("USR"))//2 == 3`. Implementace je
  SPRÁVNĚ (stejný vzorec jako existující `count_tokens()`, žádný
  `"\n\n"` oddělovač v odhadu, ten je jen v samotném promptu poslaném
  Codexu). Opraven TEST, ne implementace.

- **IMPORTANT (nevalidní Codex odpověď není fatální):** Souhlasím a
  ověřil jsem přesně KDE je mezera - `pipeline.process_chapter`'s
  SCÉNOVÁ smyčka (`translator.translate_scene()` volání, PRVNÍ smyčka,
  PŘED revizní) NENÍ obalená, na rozdíl od revizní smyčky (kolo 3's
  fix). Když `_exec_codex()` úspěšně vrátí text, ale `translator.
  _parse()` na něj vyhodí `ValueError` (formát driftl), výjimka
  propadne až do `_cmd_run`'s generické `except Exception`, kapitola
  dostane `error`, `_cmd_run` pokračuje, exit 0. `state.queue_for_run`'s
  "error = automatický retry" (kolo 2 BLOCKING) by tuhle STEJNOU
  systémovou chybu tiše zkoušel znovu při KAŽDÉM příštím `run`u - přesně
  riziko, co kolo 2's `StylistError`→`FatalRunError` fix řešil pro CLI-
  exekuční selhání, ale nezachytí ho, protože `_parse()` běží AŽ PO
  úspěšném `complete()` volání, mimo `CodexLLMClient`.

  Revizní smyčka NENÍ postižená - kolo 3's fix tam dává `flagged`, ne
  `error`, a `flagged` NENÍ auto-retryovaný (čeká na `--retry-flagged`),
  takže žádná další úprava tam potřeba není.

  **Oprava:** Nová `translator.InvalidTranslationOutput(ValueError)`
  podtřída (Task 2) - `_parse()`'s všechny vlastní kontroly (marker
  struktura, prázdný překlad) i přebalené `extract_json()`'s `ValueError`
  ji teď vyhazují místo holého `ValueError` (existující `except
  ValueError`/`except Exception` volající kód funguje beze změny,
  podtřída). `_cmd_run` (Task 5) dostane novou `except translator.
  InvalidTranslationOutput` větev PŘED generickou `except Exception` -
  pro `--translator codex` ji přebalí na `FatalRunError`; pro `claude`
  (default) beze změny spadne do existující generické větve (formát-
  drift riziko je Codex-specifické, spike ho u Claude nepozoroval).

### Agreed but already addressed
- **IMPORTANT (chybí negativní testy pro duplicitní PREKLAD/METADATA a
  špatné pořadí):** Přidány `test_duplicate_translation_marker_raises`,
  `test_duplicate_metadata_marker_raises`, `test_markers_out_of_order_
  raises` do Tasku 2.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 6: Codex našel skutečný BLOCKING (test/implementace formula
mismatch u token odhadu z kola 5 - test opraven, implementace byla
správně) a reálný IMPORTANT - `_parse()`'s ValueError ze SCÉNOVÉ smyčky
(na rozdíl od revizní, kterou kolo 3 už chránilo) propadá jako obyčejný
per-kapitolový `error`, což by `state.queue_for_run` tiše retryoval
navěky při formát-driftu Codexu. Opraveno novou `InvalidTranslationOutput`
podtřídou ValueError, kterou `--translator codex` cesta v `_cmd_run`
dělá fatální (stejný princip jako kolo 2's StylistError fix, jiná
příčina - selhání parsování místo selhání CLI exekuce). Doplněny i
chybějící negativní testy na marker strukturu (duplicitní PREKLAD/
METADATA, špatné pořadí).
