## IMPORTANT

- **Řádky 970–983 – lifecycle snapshotu stále není plně chráněný.** `shutil.copy2(db, snapshot_path)` leží před `try/finally`. Při chybě během kopírování může zůstat částečný `.pre-polish-snapshot` a cleanup se nespustí. Přesuň vytvoření snapshotu do chráněného bloku, stav inicializuj předem a přidej test selhání `copy2`.

- **Řádky 370–383 – procentní guard ignoruje úzkou nezalomitelnou mezeru U+202F.** U textu `12 %` regex zachytí pouze `12`; odstranění `%` tedy projde. Použij `[ \u00A0\u202F]?%?` a otestuj zachování i odstranění procenta pro běžnou mezeru, NBSP a narrow NBSP.

- **Řádky 832–834 – popsaná obnova DB není atomická.** Přímé `shutil.copy2(backup, db)` může při přerušení nebo plném disku poškodit právě obnovovanou DB. Kopíruj nejprve do dočasného souboru ve stejném adresáři, ověř `PRAGMA integrity_check`, potom použij `os.replace`.

- **Řádky 159–178 a 1322–1332 – chybí regresní test nové validace `severity`/`type`.** Kód z kola 9 má fail-closed odmítat chybějící či neplatné enumy, ale uvedené testy tento kontrakt neověřují. Přidej případy pro chybějící hodnotu, neplatný string a nesprávný typ po obou pokusech.

## NITS

- **Řádky 1495–1498 – zastaralá próza.** Tvrdí, že baseline pochází „z doby, kdy kapitola dostala `done`“, zatímco kód ji počítá čerstvě bezprostředně před stylizací. Přepiš podle řádků 766–778.

- **Řádky 445–450 – zastaralé tvrzení o nepozorované změně rejstříku.** Kritik skutečně signál nemá, ale následný `check_meaning_preserved` jej nyní má. Formuluj `guide_block` jako prevenci, nikoli jedinou ochranu.

- **Řádky 1458–1461 – nadpis a odkazy končí kolem 9**, přesto dokument obsahuje rozhodnutí z kola 10. Aktualizuj rozsah.

## VERDICT

CHANGES_NEEDED