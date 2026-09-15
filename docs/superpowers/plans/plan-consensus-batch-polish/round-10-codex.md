## IMPORTANT

- Task 13, Step 8: Povinná migrace je uvedena jako holý víceřádkový Python blok „přes `python -c`“, což v PowerShellu není spustitelný příkaz. Bez ní staré nálezy nemají `id` a UI resolve nefunguje spolehlivě. Fix: dodej konkrétní PowerShell here-string příkaz, nebo lépe jednorázový testovaný migrační skript/helper.

- Global Constraints vs. Task 10, Step 3: Regenerate zapisuje `runs` a `llm_calls`, ale vědomě obchází `write_lock`; současně během dlouhého Codex volání neobnovuje procesní zámek. To odporuje deklarovanému pravidlu pro každý zápisový endpoint a po ztrátě/stárnutí zámku může dopsat auditní záznamy bez vlastnictví zámku. Fix: buď endpoint skutečně serializuj a obnovuj zámek po celou dobu, nebo explicitně zúž globální invariant na kapitoly/historii a doplň ochranu i test pro auditní zápisy.

## NITS

- Task 2, Step 4: Očekává „PASS (8 testů)“, ale uvedený soubor obsahuje 11 testů.
- Task 5, Step 8: Za odstavcem o `_snapshot_db` zůstává osamocený duplicitní fragment „taky mimo try/finally…“; smaž jej.

## VERDICT

CHANGES_NEEDED