## IMPORTANT

- Task 3, `CodexLLMClient.complete()`: zachytává jen `StylistError`. `_exec_codex()` může při `TemporaryDirectory`/čtení výstupu vyhodit `OSError` nebo `UnicodeError`; ty pak skončí jako per-kapitolový `error` a budou se automaticky opakovat. Oprav: normalizuj i tyto provozní chyby na `FatalRunError` a přidej test.

- Task 3, Step 1: test předává do `complete()` stejný model jako `codex_model`, takže neověřuje klíčový rozdíl od reálné cesty, kde translator předá `claude-sonnet-5`. Oprav test na `model="claude-sonnet-5"` a ověř, že `_exec_codex` stále dostal `gpt-5.6-terra`.

- Task 6, Step 2: smoke test nezajišťuje, že `<idx>` je ve frontě (`pending`/`error`). U `done` či `flagged` kapitoly `--only` nic nespustí a kontroluje se starý překlad. Oprav: explicitně vyber nebo v izolované kopii nastav `pending` kapitolu a po běhu ověř v `llm_calls` záznam `provider="codex"` a očekávaný model.

## VERDICT

CHANGES_NEEDED