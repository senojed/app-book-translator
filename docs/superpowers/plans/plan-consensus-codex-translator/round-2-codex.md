## IMPORTANT

- Task 2, `StylistError` politika: odmítnutý precedent z `polish` není přenositelný. `polish` je volitelný post-processing nad již uloženým textem; `run` je hlavní překlad a `queue_for_run()` automaticky zkouší i `error`. Neautentizovaný CLI, nefunkční binárka nebo timeout proto provedou zbytečné Codex pokusy pro všechny kapitoly, běh skončí stavem `ok` a další spuštění chyby zopakuje. Rozlišit exekuční/provider chyby (`FatalRunError`, zastavit po první) od chyb konkrétní odpovědi/promptu (per-chapter error); doplnit strukturované výjimky z `_exec_codex` a test, že provider failure nezpracuje další kapitolu.

- Task 1/2, `CODEX_TRANSLATE_MAX_CHARS`: guard může zničit úspěšně přeloženou dlouhou kapitolu. Scény se přeloží, ale revize vždy posílá celý EN+CZ text; při překročení 60 000 znaků vyhodí výjimku před commitem a `_cmd_run` označí kapitolu `error`, takže dosavadní překlad se neuloží. To je pravděpodobné právě u kapitol nad split threshold. Definovat fallback: revizi přeskočit a uložit dosavadní překlad jako `flagged` s nálezem, nebo revizi dělit; přidat integrační test této cesty.

- Task 5, Step 2: manuální ověření je napsané pro Unix (`/tmp`, `mkdir -p`, `cp`, inline env assignment), ale cílové prostředí projektu je PowerShell/Windows. Krok nelze vykonat podle plánu. Uvést PowerShell variantu s dočasným adresářem a `$env:BOOK_TRANSLATOR_PROJECT_DIR`, případně explicitně označit Bash/WSL jako požadovaný shell.

## VERDICT
CHANGES_NEEDED