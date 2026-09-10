## IMPORTANT

- `1052–1078`, `_cmd_polish` — `shutil.copy2` není spolehlivý způsob snapshotu SQLite: může kopírovat během cizího zápisu a ignoruje WAL/SHM. Tvrzení o „skutečně obnovitelné“ záloze proto není obecně platné. Použít `sqlite3.Connection.backup()` do dočasné DB, ověřit `integrity_check` a teprve potom provést atomickou promoci. Obnova musí bezpečně řešit také případné `-wal`/`-shm` soubory.

- `1017–1159`, `_cmd_polish` — obecné infrastrukturní výjimky mimo `_polish_one_chapter` zůstávají nezachycené. Selhání `chapters_by_status`, `glossary.all_terms`, `load_guide`, `create_run` nebo `_print_usage` skončí tracebackem, přestože stejný problém byl u `copy2` opraven na řízené `return 1`. Rozšířit vnější lifecycle `try` na celý příkaz a přidat obecnou větev pro fatální infrastrukturní chybu; doplnit regresní testy alespoň pro `create_run` a `_print_usage`.

- `408–434`, `1425–1434`, `1986–1993` — normalizace `.` a `,` stále může skrýt významovou změnu. Racionalizace z kola 13 předpokládá desetinné číslo, ale regex neumí odlišit číslo od identifikátoru/verze: například `Python 3.5` → `Python 3,5` projde. U bezpečnostní brány je falešné zamítnutí levnější než přijetí změněných dat. Porovnávat oddělovač přesně, případně povolit normalizaci pouze po jednoznačné kontextové validaci.

## NITS

- `503–504`, `708–710`, `1779–1785` — stale prose stále popisuje „multiset/množinu“, zatímco kód od kola 13 porovnává pořadovou sekvenci. Nahradit všude výrazem „sekvence“.

- `1599–1605` — tvrzení „`state.finish_run` se zavolá vždy“ odporuje kódu: nevolá se před úspěšným `create_run` a jeho vlastní selhání je pouze best-effort varování. Upravit testovací scénář na „při úspěšně vytvořeném runu se o volání vždy pokusí“.

- `1508–1520` — začátek scénáře tvrdí, že neprázdná dávka vytvoří kanonickou zálohu, ale konec správně říká, že při samých `unchanged/rejected/failed` nevznikne. Podmínit první tvrzení skutečným prvním zápisem výsledku.

## VERDICT

CHANGES_NEEDED