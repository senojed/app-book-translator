## IMPORTANT

- `_claude_cli_preflight()` — `auth status --json` ověřuje pouze přihlášení, ne oprávnění použít `config.MODEL_CRITIC` přes OAuth/subscription. Platná session může selhat až na prvním `claude -p --model ...` volání po drahém překladu. Opravte preflight krátkým skutečným smoke testem se stejnými flagy a modelem, nebo tento limit explicitně přijměte.

- `_claude_cli_preflight()` — kontrola podporovaných flagů přes substring je chybná: `"-p" in help_result.stdout` projde například při samotném `--print`. Tím neplní deklarovanou ochranu proti nekompatibilní CLI verzi. Použijte token-aware/regex kontrolu aliasů a přidejte regresní test, že `--print` nesplní požadavek `-p`.

- Spec vs. Task 2 — design spec stále uvádí `user` jako poziční argv argument, zatímco plán správně požaduje stdin. Jde o protichůdný integrační kontrakt a spec navíc vrací riziko limitu délky argv. Aktualizujte spec na stdin a doplňte jej o stejný příkazový tvar jako implementační plán.

## VERDICT

CHANGES_NEEDED