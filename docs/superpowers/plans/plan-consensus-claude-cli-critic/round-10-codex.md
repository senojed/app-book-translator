## IMPORTANT

- Task 2, `_exec_claude()` payload validation / `ClaudeCliClient.complete()` — `usage` and its `input_tokens`/`output_tokens` fields remain optional. Missing fields silently become `1`; valid zero values are also overwritten by `or 1`. To je v rozporu s deklarovaným validovaným CLI kontraktem a znehodnocuje audit `llm_calls`. Opravte: pro úspěšný výstup vyžadovat `usage` dict a oba celočíselné nezáporné tokenové údaje; v `Completion` je předat přímo bez `or 1`. Přidejte testy pro chybějící `usage`, chybějící jednotlivé pole a zachování `0`.

## VERDICT
CHANGES_NEEDED