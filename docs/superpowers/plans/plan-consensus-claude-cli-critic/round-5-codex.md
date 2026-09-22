## IMPORTANT

- Task 3, `_claude_cli_preflight()` (ř. 1025–1035): Nekontroluje `help_result.returncode`. Neúspěšné `claude --help` se stdout obsahujícím názvy flagů projde a až placené volání selže. Oprav: při `returncode != 0` vrať preflight chybu; přidej test.

- Task 3, `_claude_cli_preflight()` (ř. 1060): `if not status.get("loggedIn")` přijme např. `"loggedIn": "false"` jako úspěch. To obchází eager ochranu. Oprav na `status.get("loggedIn") is not True`; testuj chybné typy.

- Task 3, předání `claude_cmd` do factory: Existující spy/fake factory v `tests/test_cli.py:1048,1709` a `tests/test_polish_server.py:914` nemají parametr `claude_cmd`; nové volání je rozbije `TypeError`. Plán explicitně doplň o jejich úpravu a ověření předané hodnoty.

## VERDICT

CHANGES_NEEDED