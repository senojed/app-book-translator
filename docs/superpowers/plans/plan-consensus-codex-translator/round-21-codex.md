## IMPORTANT

- **Task 2, revizní smyčka:** Checkpoint pro `FatalRunError` obaluje jen `translator.revise_chapter()`, ne následné `_run_critic()`. Když Codex vrátí hotovou revizi a pak Claude-kritik vyhodí `FatalRunError`, nové `cz` se necommitne a kapitola skončí `processing` → při dalším běhu se znovu přeloží. Rozšiř ochranu na celý krok revize včetně následné kontroly kritika, nebo explicitně zdokumentuj a otestuj jiné zacházení. Přidej regresní test: první kritik vyžádá revizi, revize uspěje, druhý kritik vyhodí `FatalRunError`, a ověř zachování posledního `cz`.

## VERDICT
CHANGES_NEEDED