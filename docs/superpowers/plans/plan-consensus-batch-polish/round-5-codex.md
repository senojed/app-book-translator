## IMPORTANT

- **Task 2/3/8/9 — nález lze zobrazit, ale nelze jej uložit.** Skutečný `critic._to_finding` propouští například `issue: 123`. `assign_ids`, GET kapitoly i report jej přijmou, ale `_valid_finding_shape` následný save odmítne HTTP 400. Uživatel tak nemůže uložit ani ruční opravu textu. Ověřeno přímo proti uvedeným funkcím. **Oprava:** sjednotit normalizaci producentů a existujících nálezů s kontraktem save; přidat test průchodu producent → GET → save. Samotné `str()` při vykreslení nestačí.

- **Task 4/5 — nesouhlasím s Claudeovým zamítnutím sjednocení `rendered_terms`.** Historická hodnota se nepoužívá pouze k archivaci: `_commit_polish_result` ji předává `concordance.build_mentions`, tedy ovlivňuje živou DB. Konkrétní reprodukce: schválené `apple → jablko`, historicky hlášená `brambora`, současný text už obsahuje `jablko`; další kandidát obnoví `brambora`. Kontrola s prázdnou živou množinou hlásí pouze `omission/minor`, s historickou množinou správně `inconsistency/critical`. Ověřeno skutečným `check_chapter`. Nejde tedy jen o falešnou omission. **Oprava:** používat konzistentní vstup pro kontrolu i zápis, s existující podmínkou shody historie s aktuálním textem a aktuálním glosářem; přidat tento regresní případ.

- **Task 13, Step 8 — tolerance poškozených historických nálezů nefunguje.** `load_history` odmítne `[null]` přes `_validate_dict_list` dříve, než skript zavolá `_valid_entries`. V tom okamžiku už mohou být změny `chapters.notes` commitnuté. Navíc porovnání délek po `entry["findings"] = valid` vždy porovnává stejný seznam. **Oprava:** připravit a validovat obě migrace před prvním zápisem; případnou normalizaci historie provést před její striktní validací. Původní délku zachovat před přiřazením. Samotné získání/uvolnění zámku je správně: obě volání používají PID stejného procesu.

- **Task 9/10/14 — `error` nezaručuje existující překlad.** `main._cmd_run` při prvním neúspěšném překladu nastaví `status="error"` a ponechá `translated_text=NULL`. Nové UI přesto povolí editaci a regeneraci; save odešle `cz_before:null` a dostane 400. **Oprava:** odvozovat dostupnost těchto operací také od existence textu, shodně na serveru a v UI. Otestovat `error` s překladem i bez něj.

- **Task 6/12 — export obchází obranné čtení nálezů.** Převzatý `_finding_summary` padá pro `notes='null'`, `'42'` nebo `'[null]'`. Report stejné hodnoty přes `_parse_findings` bezpečně zvládá; migrace skalární JSON ponechává. Jedna taková `flagged` kapitola zablokuje export celé knihy. **Oprava:** použít bezpečné parsování i v `_finding_summary`, zachovat podporu objektu `{"error": ...}` a ověřit uvedené vstupy.

## NITS

- **Task 5/7/9 — upřesnit důsledky merge.** Pro platná unikátní ID funguje v obou větvích; nenalezl jsem assertion vyžadující původní úplné nahrazení. Regenerace však vytváří nová ID, takže save zachová také staré nálezy a markery. Komentář Tasku 7, že nálezy z `run` přežívají pouze do první ruční úpravy, už neplatí. Výslovně dokumentovat akumulaci a otestovat regeneraci nad existujícími nálezy.

- **Task 9 — tvrzení „NIKDY nic nemaže“ potřebuje předpoklad.** `_merge_findings_by_id` zahazuje uložené položky bez ID a slučuje duplicitní ID. Uvést invariant úspěšné migrace nebo uložená ID před merge normalizovat.

- **Task 9, spor o vnější `try/except` — souhlasím s nepovinnou opravou.** SQLite SELECT může selhat i bez katastrofického poškození disku, takže Claudeovo zdůvodnění je příliš kategorické. Samotná obecná HTTP 500 před zápisem však data nepoškodí a frontend ji zpracuje; nepovažuji to za IMPORTANT.

## VERDICT
CHANGES_NEEDED