## IMPORTANT

- Task 2 `_checkpoint_flagged()` / Task 5 exception handler: Snapshot otevřených otázek se obnovuje jen při fatální chybě po vytvoření `cz`. `begin_chapter()` ale maže otázky před první scénou. `CodexTranslatorFatalError`, `InvalidTranslationOutput` nebo timeout během `translate_scene()` (včetně lazy factory selhání) přeskočí checkpoint a Task 5 pouze změní status na `flagged`/`error`; původní otázky jsou trvale ztraceny. Oprava: obalit všechny cesty po `begin_chapter()` až do úspěšné transakce B obnovou snapshotu při výjimce; checkpoint po existujícím `cz` musí zůstat sloučený se současnými otázkami. Přidat testy pro fatální i nefatální selhání v první/scénové smyčce s předchozí otevřenou otázkou.

## VERDICT

CHANGES_NEEDED