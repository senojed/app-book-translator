## BLOCKING

- **Task 5, převzaté pozitivní testy:** `test_polish_uses_config_timeout_and_strips_model`, `test_polish_returns_output_file_contents` a `test_polish_invokes_codex_with_expected_argv` porušují délkový guard. `"Prvni odstavec."` má 15 znaků, upravená varianta 24: poměr 1,6. Dvouodstavcové varianty mají poměr 50/32 > 1,5. VERBATIM implementace je odmítne ještě před assertcemi. **Oprava:** zkrátit fake výstupy nebo prodloužit vstupy; neměnit produkční limit.

- **Task 5, `test_polish_long_input_goes_through_stdin_not_argv`:** `long_cz` končí mezerou, ale `polish()` výstup načítá přes `.strip()` (spec 909). Očekávaná délka proto bude o jeden znak větší než skutečná. **Oprava:** porovnat celý výsledek s `long_cz.replace(...).strip()`.

- **Task 8, `test_rejection_keep_untranslated_term_added_occurrence_not_leak`:** očekávané `False` odporuje předepsanému kódu. Spec 1292–1293 vloží `actual="Mouse"` do `surfaces` ještě před kontrolou `cz == canonical_en`; kontrola pouze zabrání přidání dalších povrchů. Nárůst `Mouse` tak vyvolá zamítnutí. **Oprava:** vyřešit rozpor kontraktu a specu explicitně. Pro deklarované chování přeskočit početní větev `leak` u nepřekládaného termínu. Pokud je takový finding nedosažitelný, testovat skutečnou konkordanci a zúžit kontrakt. Nepřepsat pouze očekávání na `True`.

## IMPORTANT

- **Task 5, UTF-8 fake skripty:** `encoding="utf-8"` na rodičovském `Popen` nenastavuje dekódování `sys.stdin` dětského Pythonu. Fake skripty používají implicitní `sys.stdin.read()`; při cp1252 a vypnutém UTF-8 režimu nemusí rozpoznat české značky promptu. **Oprava:** ve fake skriptech číst `sys.stdin.buffer.read().decode("utf-8")`; testovací prostředí explicitně nastavit tak, aby ověřovalo deklarovanou kompatibilitu.

- **Global Constraints / Task 12, diagnostika:** plán požaduje všechny výpisy přes `_say`, ale přebírá volání `_print_usage(db, rid)` ze specu 1919 bez úpravy této funkce. `_polish_env` ji navíc vždy nahrazuje no-opem, takže test rozbitého stdout tuto cestu vynechá. **Oprava:** přidělit tasku ochranu skutečného výpisu spotřeby a testovat jej bez tohoto mocku. **Would verify:** zda dnešní `_print_usage` používá nechráněný `print`; jeho tělo inline není.

- **Tasky 3/8/11, konkordance:** chybí explicitně požadovaný test provenience (spec 323–329), integrační test s reálným `check_chapter` (2638–2642), změna pádu/velikosti písmen (2617–2622) a dedup současného nového povrchu B a nárůstu A (2821–2826). Task 11 používá prázdné mentions a mockovanou konkordanci, takže hlavní opravu slepé skvrny vůbec neověří. **Oprava:** doplnit konkrétní testy v těchto taskech; odstranit pokyn automaticky přizpůsobovat očekávání implementaci.

- **Tasky 9/12, záloha:** test jednoho getteru nad snapshotem a existence backup souboru neověřují stav před během. Chybí porovnání tabulek před `_cmd_polish`, včetně `runs`/`llm_calls`, zachování předchozí zálohy při nepřijetí žádné kapitoly a úklid částečného snapshotu (spec 2524–2554). **Oprava:** doplnit integrační testy časování, zachování staré zálohy a úklidu; samostatně simulovat selhání promoce.

- **Tasky 11/12, řídicí větve:** self-review nesprávně tvrdí úplné pokrytí. Chybí `critic_failed=True` s nevoláním meaning-checku, pokračování po obecné výjimce, přerušení po skutečném commitu, obě varianty `--force` s přerušením a pád `_client_factory` po založení runu (spec 2667–2669, 2759–2788, 2827–2830). **Oprava:** doplnit testy s kontrolou DB, pořadí zpracování a přesného seznamu reportových záznamů.

- **Tasky 4/5/11/12, redakce:** samotný test `_redact_detail` nedokazuje, že jej používají všechny chybové cesty. Chybí předepsaná matice stderr/čísla/odstavce/poměr/neočekávaná výjimka a kontrola secretu ve výsledném JSON i stdout pro `False`, `1`, `"False"`, `None` a `True` (spec 2789–2816). **Oprava:** přidat parametrizované testy skutečných cest až do reportu.

- **Task 13, manuální ověření:** seznam flagů v `--help` neověřuje skutečné vynucení modelu, potlačení neprázdného uživatelského configu ani izolaci projektového kontextu, požadované specem 2468–2482. **Oprava:** doplnit tyto kontroly a zaznamenávat jejich výsledky. Dočasné změny `config.py` po ověření vrátit, zejména bezpečnostní opt-in; plán nyní může skončit s defaultně zapnutou funkcí.

## NITS

- **Task 4 Step 3:** úvodní rozsah `433–715` neobsahuje `_kill_process_tree`; správný rozsah Python kódu je **434–746**. Task 1 obdobně odkazovat na **345–400**, bez Markdown fences.
- **Task 11 Step 3:** sjednotit monkeypatchování na již importovaný `_stylist`. String `"main.stylist.polish"` neřeší chybějící modulový atribut; duplicitní produkční import není potřebný.
- **Global Constraints / commity:** všechny ukázkové commit příkazy vynechávají požadovaný trailer. Sjednotit pravidlo s příklady.

## VERDICT
CHANGES_NEEDED