## IMPORTANT

- Task 4, `_client_factory()` Codex větev: druhý `_polish_preflight()` při `factory("translator")` vyhazuje obyčejný `FatalRunError`. Volá se až po `state.begin_chapter()`, takže selhání mezi eager preflightem a prvním překladem nechá kapitolu `processing` → příští run ji tiše vrátí do `pending`. Vyhazuj `CodexTranslatorFatalError`; přidej test pro eager-success / lazy-preflight-failure a ověř `flagged`.

- Task 5, sekce **Interfaces**: stále tvrdí, že při `args.translator == "codex"` se flaguje obecný `FatalRunError`. Detailní implementace správně flaguje jen `CodexTranslatorFatalError`; obecný fatal může vzniknout u Claude kritika. Text je v rozporu s opravou z kola 11 a může ji při implementaci vrátit zpět. Přepiš interface na typově specifickou větev.

- Task 2, `_parse()`: validuje jen syntaxi JSON, ne jeho tvar. `[]`, `null` nebo `{"new_terms": "x"}` vyústí v `AttributeError` nebo později zpracuje řetězec jako seznam; nejde přes `InvalidTranslationOutput` a Codex cesta ji bude automaticky retryovat jako běžnou kapitolu. Validuj `meta` jako `dict` a všechna tři pole jako `list` (ideálně položky jako `dict`); při porušení vyhoď `InvalidTranslationOutput` a přidej regresní testy.

## VERDICT

CHANGES_NEEDED