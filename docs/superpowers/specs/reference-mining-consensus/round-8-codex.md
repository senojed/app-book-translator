## BLOCKING

- **Ř. 51, 319–321, 619, 644:** Rozhodnutí z kola 7 není důsledně zapsané. Tyto části stále předepisují „prefixové porovnání“, přestože ř. 161–166 algoritmus výslovně odkládají. Odstranit všechny zbývající odkazy na prefixový algoritmus.
- **Ř. 212–217 vs. 261–264, 480–483:** Oprava alias-only je přítomná, ale klasifikační tabulka stále říká, že každý `weak`, včetně „jen alias“, má `cz` předvyplněné. Ř. 480 navíc označují všechny `weak` za předvyplněné. Zavést explicitní podtřídu/příznak `primary_attested` a podle něj řídit předvyplnění.
- **Ř. 470–479, 526–536, 627–629:** `reference_dir` není skutečně propojen. `build_app` dostává jen `reference_path`, popsané volání `merge_sources` nepředává `reference_dir` a `_cmd_review` předává pouze `REFERENCE_PATH`. Navíc `reference --dir CESTA` je jednorázový override, zatímco následný `review` při výchozím `REFERENCE_DIR=""` stejnou cestu nezná. Těžba by proto byla označena jako stale. Efektivní kořen je nutné uložit a při review znovu použít; test „chybějící cache ⇒ unknown“ odporuje novému výpočtu přímo z disku.
- **Ř. 219–251, 259–268, 354–369:** Compound workflow je vnitřně rozporný. Text současně tvrdí rozdělení před těžbou, zrušení automatického rozdělení a zachování kanonizace. `compound` navíc chybí v `Finding.klasifikace`, klasifikační tabulce i výčtu testovaných tříd. Spec musí určit jediný tok a úplné schéma.
- **Ř. 231–245:** Ruční split neřeší `must_decide`. Aktuální draft skutečně obsahuje `must_decide.scope_key = "naagloshii/skinwalker"`. Stávající `apply_must_decide` tento původní klíč při POST znovu vloží, čímž poruší požadavek, že compound řetězec se do `guide.json` nedostane. Split musí související otázku odstranit nebo explicitně přemapovat a server musí odmítnout zbylé compound klíče.
- **Ř. 488–498:** Alias guard zabrání přepsání, ale zahodí schválenou samostatnou položku: `Billy` už je alias `Billy Borden`, takže jeho „přidání k aliasům“ nic nezmění a nový řádek nevznikne. To odporuje ručnímu rozdělení na samostatné položky a ponechává `resolve_surface` nejednoznačné. Je nutná explicitní politika identity: sloučení jako alias stejné entity, nebo samostatná entita včetně řešení kolize povrchů.

## IMPORTANT

- **Ř. 168–186, 593–598:** Přejímací kritéria matcheru nemají reprodukovatelnou korpusovou metriku: není definován vzorek, anotace správnosti ani číselný limit. „Desítky nesouvisejících tvarů“ není testovatelná podmínka. Definovat eval fixture a práh, případně závazný checkpoint před integrací.

## VERDICT

CHANGES_NEEDED