## IMPORTANT

- Task 2, `_checkpoint_flagged()` (~ř. 1415): při selhání `glossary.all_terms()` výjimku potlačí a použije `gl_rows=[]`. Následný `commit_chapter_result()` vždy smaže všechny existující `term_mentions` kapitoly a při prázdném rebuild je nenávratně ztratí. Oprava: před `begin_chapter()` snapshotovat existující mentions; pokud nelze načíst glosář pro rebuild, obnovit tento snapshot místo `[]` (a přidat test selhání `glossary.all_terms()`).

- Task 2, `_checkpoint_flagged()` (~ř. 1425): checkpoint obnovuje jen `existing_questions` a `questions_now` od translatoru. Zahodí otevřené otázky vytvořené z již spočtených `findings_now` s `action=="question"`; normální transakce B je přitom zapisuje. Zachovaný překlad pak může mít uložený minor/candidate problém bez odpovídající otázky. Oprava: v helperu převést `findings_now` s akcí `question` na `db_questions` stejnou logikou jako transakce B a deduplikovat; přidat regresní test.

## VERDICT

CHANGES_NEEDED