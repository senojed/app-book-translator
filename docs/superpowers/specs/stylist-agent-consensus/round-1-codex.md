## BLOCKING

- **Řádky 98–105 — celý prompt jako argument procesu:** Na Windows platí limit příkazové řádky přibližně 32 KiB. EN + CZ celé kapitoly jej běžně překročí; `subprocess.run([...])` limit neobchází. Navíc je text knihy viditelný v argumentech procesu. Předávat prompt přes stdin (`codex exec -`) nebo vstupní soubor a přidat test s reálně dlouhou kapitolou.
- **Řádky 12–16, 159–168 — deklarovaný guardrail není implementován:** `concordance.check_chapter(..., [])` neumí zjistit obecné přidání, vynechání ani změnu faktů a nekontroluje počet odstavců. LLM kritik je nedeterministický, takže nemůže garantovat zachování již schváleného obsahu. Přidat deterministické kontroly minimálně pro odstavce, čísla, vlastní jména, dialogovou strukturu a délkové odchylky; jasně definovat, které odchylky vždy znamenají zamítnutí.
- **Řádky 44–56, 102–105 — tvrzení „jen text, žádné soubory“ je nepravdivé:** `codex exec` běží v aktuálním projektu a read-only sandbox čtení souborů dovoluje; Codex také načítá projektové instrukce. Spouštět jej v izolovaném prázdném pracovním adresáři, nebo nepoužívat agentní CLI pro úlohu vyžadující izolovaný textový vstup.

## IMPORTANT

- **Řádky 147–174 — životní cyklus běhu není dokončen:** `state.create_run(..., "polish")` nemá odpovídající `finish_run` v `finally`. Každý běh zůstane s `ended_at/status = NULL`, včetně úspěšného. Použít stejný `status`/`try`/`finally` vzor jako `_cmd_run`.
- **Řádky 160–168 — nekonzistentní databázový stav po přijetí:** Mění se pouze `translated_text`; `notes` a `term_mentions` dál popisují původní text a nové `question` nálezy se nezapisují. Zavést jedinou atomickou state operaci, která aktualizuje text, aktuální findings, přepočítané mentions a případné otázky.
- **Řádky 161–163, 258–262 — pravidla přijetí jsou příliš slabá:** Kritik může vrátit `verdict="revise"` bez findings a `critic.review` verdict ignoruje. Navíc se přijme `minor` finding typu `fidelity`, přestože jakákoli změna obsahu porušuje cíl. Validovat verdict proti findings a pro stylistický průchod zamítat všechny fidelity nálezy bez ohledu na severity.
- **Řádky 90–125 — chybí ochrana proti useknutému či neúplnému výstupu:** Neprázdný soubor a exit code 0 nedokazují kompletní kapitolu. Přidat preflight vstupního/výstupního limitu a post-validaci rozsahu a struktury. Explicitní zákaz dělení kapitoly musí mít definovaný limit a bezpečné „unsupported/rejected“ chování.
- **Řádky 194–236 — testovací rozhraní je samo se sebou v rozporu:** `codex_cmd` je deklarován jako `str`, ale testy předávají `"python script.py"`, což se v listové formě hledá jako jeden executable. Nenechávat rozhodnutí na implementaci: přijímat `Sequence[str]`, případně oddělené `executable` a prefix argumentů. Nepoužívat platformně problematické implicitní `shlex.split`.
- **Řádky 152–174 — neošetřené chyby přeruší celý příkaz:** Zachytává se jen `StylistError`; `FatalRunError` z kritika, chyba DB nebo jiná neočekávaná chyba obejde deklarované „kapitola beze změny, pokračuje se“. Definovat fatální vs. per-chapter chyby, návratový kód a vždy korektně uzavřít run.
- **Řádky 267–273 — plán ponechává zásadní rozhodnutí otevřená:** Bez značky se každý další `polish` znovu aplikuje na už upravený text, což způsobuje náklady a kumulativní stylistický drift. Zvolit perzistentní stav/fingerprint vstupu a explicitní `--force`; samostatný run je nutný kvůli auditu.
- **Řádky 27–31, 168 — chybí rollback a audit původního překladu:** Přijatý výsledek nevratně přepíše jedinou schválenou verzi. Uložit původní text a metadata verze, nebo provést před během obnovitelný snapshot s popsaným rollback postupem.
- **Řádky 29–31 — slíbené sledování Codex volání a úspěšnosti neexistuje:** Konzolové součty nejsou perzistentní audit a Codex volání se nezapisuje do `llm_calls`. Definovat, kam se uloží pokus, výsledek, model/verze CLI, chyba a fingerprint vstupu.
- **Řádky 90–104 — model a konfigurace Codexu nejsou řízené:** Výchozí model CLI se může změnit a výsledek závisí na uživatelské konfiguraci. Přidat explicitně konfigurovatelný model, zaznamenat jej v auditu a otestovat nepodporovaný model.

## NITS

- **Řádek 111:** `.strip()` mění okrajové whitespace; nejprve validovat strukturu a normalizovat pouze podle explicitního pravidla.
- **Řádky 258–263:** Tiché přeskočení chybného `--only` zhoršuje automatizaci. Vypsat konkrétní přeskočené indexy a jejich stav.
- **Řádky 128–131:** Tvrzení, že `-o` je robustnější pro dlouhý text, zaměňuje výstupní soubor za problém délky vstupního argumentu.

## VERDICT

CHANGES_NEEDED