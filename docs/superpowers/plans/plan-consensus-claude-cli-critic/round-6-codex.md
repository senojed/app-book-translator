## IMPORTANT

- Task 3, `_REQUIRED_FLAGS`: kontrola kompatibility vynechává `--model` i `-p`, přestože je `_exec_claude()` vždy používá. Starší CLI tak může projít preflightem a selhat až po drahém překladu. Doplň obě volby do `_REQUIRED_FLAGS` a pozitivní i negativní test.

- Task 3, `_claude_cli_preflight()`: `subprocess.run(..., text=True)` nemá `encoding="utf-8"` ani nezachytává `UnicodeError`, na rozdíl od samotného `_exec_claude()`. Na Windows může dekódování `--help` nebo `auth status --json` spadnout mimo deklarovaný kontrakt `(None, chyba)` a ukončit příkaz tracebackem. Přidej `encoding="utf-8"` k oběma voláním, chytej `UnicodeError` a otestuj jej.

## VERDICT

CHANGES_NEEDED