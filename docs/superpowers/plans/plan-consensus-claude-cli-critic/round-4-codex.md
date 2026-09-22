## IMPORTANT

- Task 3, `_claude_cli_preflight()`: Ověřuje jen `auth status --json`, ne podporu požadovaných argumentů (`-p`, `--safe-mode`, `--tools`, `--output-format json`, `--system-prompt`). Starší/nekompatibilní CLI může být přihlášené, preflight projde a selže až po placeném překladu. Doplň předběžnou kontrolu podporované verze nebo parsování `claude --help`; přidej regresní test nekompatibilní verze.

## VERDICT

CHANGES_NEEDED