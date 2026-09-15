## IMPORTANT

- Task 14, `toggleResolved` + `btn-save`/`revertChapter`: při síťové chybě resolve `toggleResolved` zavolá `window.location.reload()` a úspěšně se vrátí. `Promise.all(...)` pak pokračuje a Save/Revert může ještě odeslat request nad nejistým/starým stavem před skutečnou navigací. Vrať explicitní stav „reload required“ a po čekání Save/Revert ukonči; přidej regresní test s odmítnutým resolve fetch.

- Task 14, `btn-save` a `revertChapter`: po potvrzeném 200 se volá `loadChapter()`. Když následný GET selže, `loadChapter()` editor odemkne, ale ponechá staré `CH` a nálezy, přestože commit už proběhl. Další editace skončí konfliktem nebo ztratí rozepsanou práci. Nechť `loadChapter()` vrací úspěch; po neúspěchu po potvrzeném commitu vynuť reload nebo editor neodemykej.

- Task 11, `post_resolve_finding`: persistentní změna `chapters.notes` nevolá `main._backup_db_once`, na rozdíl od obou větví Tasku 9. Pokud je resolve první změnou v session, startovní snapshot se při shutdown smaže a uživatel nemá obnovitelnou před-změnovou zálohu. Zavolej `_backup_db_once` před UPDATE a pokryj první resolve testem zálohy.

CHANGES_NEEDED