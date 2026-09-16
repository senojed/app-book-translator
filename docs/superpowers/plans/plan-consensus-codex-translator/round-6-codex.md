## BLOCKING

- Task 3, Step 1: očekávaný `input_tokens` test a implementace si odporují. Test čeká `len("SYS\n\nUSR") // 2 == 4`, implementace vrací `(len(system) + len(user)) // 2 == 3`. Opravit test na stejný vzorec jako implementace, nebo jednotně započítat oddělovač do obou metod.

## IMPORTANT

- Tasky 2, 3 a 5: nevalidní Codex odpověď není fatální. `_exec_codex()` ji úspěšně vrátí, `_parse()` vyhodí `ValueError`, `_cmd_run` kapitolu označí `error`, pokračuje a vrátí exit code 0. Při systematické změně formátu pak všechny kapitoly selžou a budou se automaticky retryovat v dalších bězích — stejný problém, který plán řeší jen pro `StylistError`. Zaveď specializovanou chybu nevalidního překladového výstupu a pro `--translator codex` ji propaguj jako `FatalRunError`.

- Task 2, Step 1: testy nekryjí slíbenou úplnou strukturální validaci. Chybí duplicitní `===PREKLAD===`, duplicitní `===METADATA===` a špatné pořadí markerů. Přidej negativní testy pro všechny tyto případy.

CHANGES_NEEDED