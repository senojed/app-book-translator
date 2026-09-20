## IMPORTANT

- **Task 2, první `_run_critic()` před revizní smyčkou:** checkpoint chrání jen chybu uvnitř `while`. Fatální chyba kritika po úspěšném scénovém překladu (např. chybějící/neplatný Anthropic klíč nebo cost guard) stále zahodí `cz`, kapitolu nechá `processing` a další run ji tiše přeloží znovu. Stejný checkpoint použij i kolem prvního `_run_critic()`; přidej regresní test pro úspěšný překlad a první kritikův `FatalRunError`.

- **Task 5, eager preflight:** ověřuje se jen Codex, přestože kritik je povinně Claude. `AnthropicClient` se vytvoří až po dokončení Codex překladu při prvním volání kritika; bez `ANTHROPIC_API_KEY` tedy běh zbytečně provede překlad a pak selže. Před zpracováním fronty eager vytvoř `cf("critic")` (alespoň kontrola klíče) a jasně oznam, že `--translator codex` stále vyžaduje Claude API pro kritika.

- **Task 2, `except FatalRunError` checkpoint:** `questions=existing_questions` obnoví jen otázky z předchozího DB běhu a zahodí otázky z posledního platného scénového/revidovaného výsledku v proměnné `questions`. Tím se při fatální chybě ztratí nové nejistoty včetně blocking otázek, ačkoli jejich překlad se uloží. Slouč snapshot se serializovanými otázkami odpovídajícími poslednímu platnému `cz`; přidej test pro scénový nebo úspěšně revidovaný výsledek s otázkou následovaný `FatalRunError`.

## VERDICT

CHANGES_NEEDED