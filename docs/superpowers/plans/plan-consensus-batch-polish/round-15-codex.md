## IMPORTANT

- Task 14, Step 2 — `btn-regen` a `revertChapter()` nemají `catch` pro selhání `fetch`. Při síťové chybě se editor sice odemkne díky `finally`, ale vznikne nezachycené Promise rejection bez chybové hlášky. U revertu navíc není jasné, zda server zápis provedl. Doplň `catch`: u regenerace zobraz chybu; u revertu explicitně oznam nejistý stav a vyžádej reload před další úpravou.

## VERDICT

CHANGES_NEEDED