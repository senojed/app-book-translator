## BLOCKING

- Task 10, Step 3 (`PipelineLLMClient.complete`): `require_lock()` se ověřuje jen před dlouhým `inner.complete()`, ale `record_llm_call` proběhne až ve `finally` bez nové kontroly. Zámek lze během LLM volání ztratit, takže auditní zápis poruší Global Constraints. Oprav: ověř zámek bezprostředně před `record_llm_call`; při ztrátě audit nezapisuj a propaguj řízenou chybu. Přidej test, kde callback přepne na `False` až během dokončení LLM volání.

## IMPORTANT

- Task 13, Step 8 (migrace): odmítnutí rollbacku stojí na nepravdivém tvrzení, že `assign_ids` je čistě aditivní. Skript maže všechny non-dict položky přes `_valid_entries()` a `assign_ids()` navíc normalizuje hodnoty `_STR_FIELDS`. Při selhání `save_history` tedy může zůstat DB změněná/ztrátová, historie nezměněná; další běh navíc přepíše pevně pojmenovanou DB zálohu. Oprav: na netypovaných položkách fail-fast bez zápisu, nebo je bezeztrátově zachovej; používej unikátní zálohy a definuj ověřený recovery/rollback postup. Přidej test selhání zápisu historie.

- Task 14, `toggleResolved` komentář u úspěšné odpovědi stále tvrdí, že Uložit „na resolve NEČEKÁ“. Task 8 ale přidal čekání na `PENDING_RESOLVE_PROMISES`. Oprav komentář; jinak zavádí při údržbě.

## VERDICT

CHANGES_NEEDED