## IMPORTANT

- Task 2, scénová smyčka a checkpointy: `except Exception` nezachytí `KeyboardInterrupt`. Ctrl+C během Codexu smaže `existing_questions` v `begin_chapter()`, obnovení se neprovede a po recovery jsou otázky nenávratně pryč; u kritika/revize se navíc ztratí i aktuální `cz`. Oprav: pro cleanup/checkpoint explicitně zachyť i `KeyboardInterrupt` (případně `BaseException`), proveď obnovu/commit a výjimku znovu vyhoď. Přidej regresní test.

## NITS

- Task 5 stále tvrdí, že scénová smyčka „NENÍ obalená“. Task 2 ji nově obaluje. Aktualizuj komentáře, aby nepopisovaly zastaralý mechanismus.

CHANGES_NEEDED