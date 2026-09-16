## IMPORTANT

- Task 2 revizní smyčka + Task 3 `CodexLLMClient.complete()`: Timeout revize se ve skutečnosti nezachová jako `flagged`. `_exec_codex()` převádí timeout na `StylistError`; Task 3 převádí každý `StylistError` na `FatalRunError`; Task 2 pak `FatalRunError` znovu vyhazuje. Kapitola zůstane `processing` a hotový scénový překlad se necommitne, přestože komentář Tasku 3 tvrdí opak. Opravte typování chyb: autentizace/spuštění CLI zůstane fatální, ale timeout revize musí být samostatná recoverable výjimka, kterou smyčka uloží jako `flagged` s posledním `cz`. Přidejte integrační test této cesty.

- Task 2 `_parse()`: `raw.count()`/`index()` a `split_sections()` hledají markery jako libovolné podřetězce, ne jako samostatné řádky. Platný překlad technické knihy, ukázky promptu nebo JSON metadata mohou obsahovat například `===KONEC===`; parser jej odmítne a pro Codex tím zastaví celý běh jako `InvalidTranslationOutput`. Markery parsujte regulárním výrazem ukotveným na celý řádek a sekce řežte podle jeho pozic. Přidejte testy markerů uvnitř překladu i JSON hodnot.

## VERDICT

CHANGES_NEEDED