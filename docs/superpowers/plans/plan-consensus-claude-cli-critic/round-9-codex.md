## IMPORTANT

- Task 2 `_exec_claude()` + Task 3 preflight: Chybí `--no-session-persistence`. Prompt obsahuje celou kapitolu EN+CZ a bez tohoto flagu ji Claude Code perzistuje v historii relací. `--safe-mode` řeší customizace, ne perzistenci. Přidej flag do příkazu, validuj jej v preflightu a přidej regresní test.

- Task 3 `_claude_cli_preflight()`, `missing = [f for f in _REQUIRED_LONG_FLAGS if f not in help_result.stdout]`: Kontrola dlouhých flagů je stále chybná substringová. Např. CLI s pouze `--system-prompt-file` projde pro `--system-prompt`. Tím se vrací riziko selhání až po drahém překladu. Použij tokenovou/hranovou validaci pro všechny flagy, ne jen `-p`; přidej testy pro suffixové kolize.

## VERDICT

CHANGES_NEEDED