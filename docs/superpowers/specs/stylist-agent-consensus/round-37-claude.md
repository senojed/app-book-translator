# Round 37 — Claude critique

Jedenácté review kola-27 dodatku. Codex 1 IMPORTANT + 5 prose NITs.
Konvergence: 3→2→1 IMPORTANT.

## On Codex's points

### Agreed + fixed
- **IMPORTANT - `FatalRunError` z KONTROL nebyl redigovaný:** moje
  kolo-35 tvrzení "z kritika/cost guardu Codexův obsah nenese" NEPLATILO.
  `pipeline._run_critic(en, styled, ...)` a `check_meaning_preserved(cz,
  styled, ...)` volají Anthropic klienta S TEXTEM `styled`. Klientův
  `FatalRunError` (400 BadRequest, cost guard) může pojmout část requestu
  = obsah `styled`. → `_polish_one_chapter` obalí `try/except FatalRunError`
  kolem celé kontrolní sekce a re-raisne s hláškou REDIGOVANOU U ZDROJE
  (`stylist._redact_detail`), stejně jako commitovou `FatalRunError`
  (kolo 35). `str(fe)` je pak bezpečné v `fatal` záznamu, `run_error`
  i výpisu.

### NITS (prose-vs-code) - fixed
- `KeyboardInterrupt` prose "vždy přidá `interrupted`" → "podle stavu DB
  `polished` NEBO `interrupted`".
- 3× stale "detekce commitu přes marker/`_already_styled`" → porovnání
  `translated_text`.
- filename `run-<rid>-<timestamp>.json` (další spot) → `+ <8 hex>`.
- config komentář tag "Kolo 27-35" → "27-37".

## Claude VERDICT

`CHANGES_NEEDED` - 1 IMPORTANT (další díra v redakci - FatalRunError z
LLM klienta), zbytek prose. Aplikováno. VŠECHNY `FatalRunError`, co
můžou nést `styled`, jsou teď redigované u zdroje. Čeká se na kolo 38.

## Summary for log

Kolo 37: 1 IMPORTANT + 5 prose NITs (klesá 3→2→1). IMPORTANT:
`FatalRunError` z kritika/meaning-checku nebyl redigovaný - LLM klient
volaný S `styled` může chybu s obsahem requestu. → obalen v
`_polish_one_chapter`, redakce u zdroje. NITs: KeyboardInterrupt prose,
3× marker→translated_text, filename hex, config tag. Čeká se na kolo 38.
