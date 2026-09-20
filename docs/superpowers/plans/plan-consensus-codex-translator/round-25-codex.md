## IMPORTANT

- **Task 2, `pipeline.process_chapter` after `state.begin_chapter()`:** Obnova `existing_questions` kryje jen scénovou smyčku a checkpointy kritika/revize. Výjimka v `_guide_block`, `_glossary_block`, `_verified_rendered`, `glossary.all_terms`, `concordance.check_chapter` nebo přípravě transakce B stále nechá dříve otevřené otázky smazané. Oprav: centralizuj rollback/obnovu otázek pro každou výjimku po `begin_chapter()` až do úspěšného commitu; pokud již existuje `cz`, zachovej jej checkpointem.

- **Task 2, testy pro kolo 24:** Chybí regresní test pro `KeyboardInterrupt` při prvním `_run_critic()` před revizní smyčkou. Implementace tuto větev mění, ale testy kryjí jen scénovou smyčku a revizi. Přidej test, který po úspěšném scénovém překladu vyvolá `KeyboardInterrupt` v `critic.review` a ověří re-raise, `flagged` a zachovaný `translated_text`.

## VERDICT
CHANGES_NEEDED