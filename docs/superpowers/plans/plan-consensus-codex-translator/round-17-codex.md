## BLOCKING

- `Task 5, test_run_translator_codex_fatal_error_console_output_is_redacted`: test odkazuje na nedefinované `calls["n"]`; vždy skončí `NameError`. Přidej `calls = {"n": 0}` a inkrementaci do `boom()`, aby druhý běh skutečně ověřil, že se flagged kapitola znovu nespustí.

## VERDICT

CHANGES_NEEDED