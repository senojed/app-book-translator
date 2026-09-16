# Round 8 — Claude critique

## Claude's own findings
### BLOCKING
(žádné)

### IMPORTANT
(žádné vlastní nové nad rámec Codexových bodů)

## On Codex's points

### Agreed + fixed

- **IMPORTANT (preflight PŘED `recover_processing` - regrese):**
  Souhlasím, ověřil jsem přesně - moje kolo-3 pořadí (`if args.translator
  == "codex": ... return 1` PŘED `state.recover_processing(db)`) by pro
  `--translator codex` s nesplněnou podmínkou vrátilo `1` HNED, PŘED
  recovery. `state.queue_for_run()` vrací jen `("pending", "error")`,
  NIKDY `"processing"` - kapitoly uvízlé z dřívějšího pádu by tak
  zůstaly navěky neviditelné pro VŠECHNY budoucí `run`y (i `--translator
  claude`), dokud by nějaký `run` nakonec prošel přes preflight. To je
  regrese oproti KAŽDÉMU jinému `run` (i dnešnímu, před tímhle plánem),
  co recovery dělá VŽDY jako úplně první krok, bez výjimky.

  **Oprava:** Prohodil jsem pořadí - `state.recover_processing(db)`
  zůstává úplně první (beze změny vůči dnešku), eager preflight jde AŽ
  PO ní. Přidán regresní test `test_run_translator_codex_preflight_
  failure_still_recovers_processing`.

- **IMPORTANT (Codex redakce - `CodexLLMClient`'s `FatalRunError`
  zprávy nejsou redigované):** Souhlasím - `_cmd_run`'s outer `except
  FatalRunError` tiskne zprávu PŘÍMO na konzoli (`print(f"Fatální chyba
  běhu: {e}")`), bez další redakce. Ověřil jsem `stylist._redact_
  detail()`'s VLASTNÍ docstring - výslovně jmenuje "`str(e)`
  neočekávané výjimky" jako jednu z kategorií, co má krýt - `OSError`/
  `UnicodeDecodeError` z kola 7 přesně tenhle případ.

  **Oprava:** `raise FatalRunError(stylist._redact_detail(str(e)))
  from e` - jednotná redakce pro celou `except` větev (StylistError i
  OSError i UnicodeError), ne case-by-case úvaha o tom, co je "asi
  bezpečné". Upraven existující test (`match="auth expired"` → ověřuje
  REDIGOVANOU podobu), přidán nový test s explicitním `STYLIST_REPORT_
  REJECTED_TEXT=True` opt-inem ověřující, že původní zpráva PROJDE, když
  si to uživatel vyžádá.

- **IMPORTANT (`_guard()` netestováno na `effective_model`):** Souhlasím
  - existující test ověřuje jen VÝSLEDNÝ audit řádek (`llm_calls`), ne
  že `_guard()` (cost-limit kontrola PŘED voláním) taky použije
  `effective_model`. Ověřil jsem `_guard()`'s kód - volá `self._price
  (model)` PŘÍMO s parametrem, co dostane - kdyby implementace omylem
  nahradila jen `_price()`/audit, ale ne `_guard()`, cost guard by
  počítal s Claude cenou pro Codex volání a mohl by zbytečně zastavit
  běh (false-positive).

  **Oprava:** Přidán `test_pipeline_client_guard_uses_billed_model_
  price_not_caller_model` - `MAX_SPEND_USD=0.0`, velký `max_tokens`,
  `interactive=False` - Codex volání (efektivní cena $0) MUSÍ projít
  bez `FatalRunError`; kdyby `_guard()` použil `"claude-sonnet-5"`
  (nenulová cena), odhad by nebyl nulový a test by spadl.

## Claude VERDICT
CHANGES_NEEDED

## Summary for log
Kolo 8: tři IMPORTANT body, všechny akceptovány. Nejzávažnější -
vlastní kolo-3 fix (eager preflight) omylem předběhl `recover_
processing`, což by pro `--translator codex` s nesplněnou podmínkou
nechalo kapitoly uvízlé v `processing` navěky neviditelné - opraveno
prohozením pořadí. `CodexLLMClient`'s `FatalRunError` zprávy teď jdou
přes `stylist._redact_detail()` (docstring téhle funkce výslovně
jmenuje "str(e) neočekávané výjimky" jako kryté). Přidán chybějící test
ověřující, že i cost-guard (ne jen audit log) použije `effective_model`.
