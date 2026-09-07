## BLOCKING

- **„Stupeň 0 hledá i aliasy“ + `Evidence`/`Finding`** — Agregace aliasů není definována správně. Překrývající se `Harry Dresden` a `Dresden` mohou tentýž výskyt započítat dvakrát; krátký či malými písmeny psaný alias může obejít omezení primárního povrchu. Navíc nález aliasu nedokazuje, že byl ponechán celý primární název, který se přesto vloží do `cz`. Oprava: počítat sjednocení rozsahů bez duplicit, aplikovat způsobilost ke `confirmed` na každý nalezený tvar a ukládat důkaz po jednotlivých tvarech. Primární `cz` předvyplnit pouze tehdy, byl-li skutečně doložen.

- **Identita povrchu vs. `lexicographer.propose`** — Plán dovoluje stejný normalizovaný klíč v různých sekcích, ale požadavek i odpověď agenta identifikují položku pouze přes `term_en`. Dvě položky se stejným názvem v `places` a `terms` nelze jednoznačně spárovat. Oprava: posílat a vracet stabilní ID obsahující `section` a normalizovaný klíč; validovat podle tohoto ID.

- **`write_reference`, selhané dávky a `--limit`** — `Finding` neobsahuje stav „dávka selhala“, „nebylo zpracováno kvůli limitu“ ani pole `stale`. `write_reference(findings, path, run_id)` proto nerozliší tyto případy od legitimního `unresolved` a nemůže splnit požadavek na zachování předchozích nálezů. Při `--limit N` navíc úplné nahrazení souboru smaže položky mimo limit. Oprava: vracet strukturovaný výsledek s množinami `attempted`, `failed` a `not_attempted`; začlenit `stale` do schématu a přesně definovat merge s předchozím souborem i odstranění položek, které už nejsou v aktuálním draftu.

- **Pravidla délky vs. test `Mab`** — Pravidla i klasifikační tabulka říkají, že povrch délky 3–4 nikdy není `confirmed`, ale test požaduje, aby tříznakové `Mab` mohlo být `confirmed`. Obě podmínky nelze implementovat současně. Oprava: zvolit jedno pravidlo a sjednotit klasifikaci, aliasové chování i testy.

## IMPORTANT

- **Životní cyklus `scan → reference → review`** — Opakovaný `scan` sice reference nesmaže, ale může změnit primární klíče, aliasy a poznámky. `review` přesto bez kontroly načte starý `reference.json`; shodný klíč tak může dostat důkaz vytvořený z jiných vstupů. `run_id` čerstvost neprokazuje. Oprava: uložit fingerprint draftu, manifestu korpusu a relevantních prahů; při neshodě reference odmítnout nebo v UI jednoznačně označit jako zastaralou.

- **„**Stupeň 1 / contradicted**“ — Přesné hledání jediného českého tvaru je pro flektivní češtinu nedostatečné. Například nominativ může chybět, přestože se zavedený termín běžně vyskytuje v jiných pádech. Označení `contradicted` je pak věcně chybné a poměrový test problém zesiluje. Oprava: ověřovat explicitní sadu doložitelných tvarů, použít morfologickou normalizaci, nebo třídu přejmenovat na `not_exactly_attested` a nepovažovat ji za vyvrácení návrhu.

- **Review UI a postavy** — Mechanický požadavek „`proposed`/`contradicted` vyžaduje ruční vyplnění“ neplatí pro postavy. Existující validace dovoluje prázdné `cz`, pokud `render == keep`; UI navíc používá `keep` jako výchozí hodnotu a `seed_from_guide` pak vloží anglické jméno do glosáře. Oprava: pro neověřené postavy zavést explicitní nerozhodnutý stav a vyžadovat aktivní volbu, nebo zmírnit invariant a end-to-end test tak, aby odpovídaly skutečnému chování.

- **Schéma a načítání `reference.json`** — Není definován top-level JSON formát ani funkce pro bezpečné načtení a validaci `schema_version`, `run_id`, findings a `stale`. `GET /api/guide` pouze neurčitě „načte reference“. Oprava: specifikovat přesné schéma a `load_reference()` včetně chování při neexistujícím, poškozeném či nepodporovaném souboru.

- **Výjimky `load_corpus` vs. CLI** — Modul má pro duplicity a malý korpus vyhazovat `ValueError`, zatímco tabulka chyb požaduje `FatalRunError` a zachování výstupu. Není určeno, kdo převod provede; neodchycený `ValueError` obejde zamýšlenou CLI diagnostiku. Oprava: sjednotit typ výjimky nebo explicitně popsat převod v `_cmd_reference` a otestovat zachování souboru.

- **Krátké povrchy na začátku věty** — Korpus slučuje dokumenty do jednoho textu, ale detekce začátku věty zná pouze pozici 0 a interpunkci. Začátky dalších EPUB dokumentů či kapitol proto mohou být chybně považovány za výskyt uprostřed věty. Oprava: zachovat hranice dokumentů nebo při spojování vložit jednoznačný oddělovač považovaný za začátek věty.

## NITS

- Tvrzení, že úplné nahrazení souboru činí těžbu „idempotentní“, je nesprávné: model může při opakovaném běhu vrátit jiný návrh. Použijte „neakumuluje předchozí výstup“.
- Terminologie střídá `Evidence.matched`, `matched_en` a `matched_cz`; sjednotit názvy podle toho, zda jde o dotazovaný EN alias nebo doložený CZ tvar.

## VERDICT

CHANGES_NEEDED