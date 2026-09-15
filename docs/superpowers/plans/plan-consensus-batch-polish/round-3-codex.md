## BLOCKING

- **Task 14, `btn-save`, ř. 3036–3057:** `finally` volá `loadChapter()` i po 409/503 nebo selhání před commitem. Úspěšný GET následně přepíše neuložený text i regenerované nálezy. Ověřeno spuštěním JS z plánu: po simulované 409 rozepsaný text zmizí. **Oprava:** po neúspěšném uložení zachovat lokální stav; v `finally` pouze odemknout editor. Reload provádět po potvrzeném úspěchu, post-commit chybu rozlišit strojově čitelným příznakem.

- **Task 9, lehká větev, ř. 1831–1840:** GET odfiltruje auditní markery, ale lehký zápis nahradí celé `notes` klientskými nálezy. Otevření stylizované kapitoly s nálezem a kliknutí na Uložit beze změny textu tedy odstraní marker `stylist/polish`. `_already_styled()` následně vrátí `False` a další dávka kapitolu přepíše bez `--force`. **Oprava:** při nezměněném textu zachovat serverové markery; přidat regresní test GET → save → kontrola `_already_styled()`.

## IMPORTANT

- **Task 9, podmínka no-op, ř. 1825–1827:** `status == "done" and not raw_findings` neznamená nulovou změnu. Klient může chtít nahradit původní nálezy prázdným výsledkem regenerace; endpoint vrátí úspěch, ale staré nálezy ponechá. Naopak totožný neprázdný seznam vždy zapisuje. **Oprava:** porovnávat výsledné normalizované nálezy a status se současným stavem; prázdný seznam musí fungovat jako platná náhrada.

- **Task 9, CAS a `current_resolved`, ř. 1807–1866:** textový CAS nechrání nově zavedené změny samotné množiny nálezů. Karta B uloží nové nálezy při nezměněném textu; starší karta A následně projde CAS a obnoví staré nálezy. Převzetí `resolved` pro společná ID nezachrání odstraněná ani nově přidaná ID. **Oprava:** verzovat také množinu nálezů a odmítnout zastaralou náhradu; samostatné změny `resolved` lze nadále slučovat serverově. Přidat test dvou karet.

- **Task 2 + Task 9, `assign_ids` a `_valid_finding_shape`, ř. 245 a 1758:** explicitní `id: null` projde validací i kontrolou duplicit a `setdefault()` jej neopraví. Uložený nález pak nelze vyřešit přes endpoint vyžadující řetězec; více takových nálezů sdílí neplatnou identitu. **Oprava:** přítomné ID musí být neprázdný řetězec, případně `null` před kontrolou unikátnosti normalizovat na nové UUID. Otestovat obě větve save.

- **Task 14, `toggleResolved` a `lockEditor`, ř. 2911–2942 a 3002:** `EDITOR_BUSY` nezamyká checkboxy. Během save lze změnit lokální nález z regenerace až po serializaci payloadu; změna se ukáže, ale následný reload ji ztratí. Ani probíhající persistované resolve požadavky nejsou koordinované s reloadem. **Oprava:** zahrnout checkboxy a rozpracované resolve požadavky do řízení operací; před save dokončit probíhající změny a další dočasně zakázat.

- **Task 14, `loadChapter`/`lockEditor`, ř. 2944–3009:** tvrzení „vždy odemkne“ stále neplatí. Odmítnutý `fetch` přeskočí odemčení; po save může editor zůstat zamčený. Při prvním GET vracejícím chybu navíc `lockEditor(false)` dereferencuje `CH === null`. Ovládací prvky jsou aktivní už před prvním načtením. **Oprava:** začít se zakázaným editorem, ošetřit síťové chyby, odemykání zajistit skutečným `finally` a povolit ovládání jen při platném `CH`.

- **Task 9, lehký zápis, ř. 1835–1841:** větev obchází `_backup_db_once` i obsluhu chyb DB. Pokud server provede pouze takové uložení, při ukončení smaže nepromovaný startup snapshot; změna statusu a nálezů zůstane bez nové zálohy. Selhání SQL navíc vrátí neřízenou 500. **Oprava:** před skutečnou změnou promovat zálohu a zápis obalit řízenou chybovou odpovědí; otestovat samostatný lehký zápis i jeho selhání.

- **Task 14, `renderHistory`, ř. 3076:** nový frontend zahazuje `e.stale` a `e.reason`, které `_annotate_history()` stále vrací. Starý `polish.html` přitom nesoulad DB/historie výslovně zobrazoval. Po selhání zápisu historie tak reload odstraní trvalé upozornění a může nabídnout revert končící 409. **Oprava:** zachovat zobrazení nesouladu a pro zastaralou historii potlačit neproveditelné revert akce; ověřit post-commit selhání následované reloadem.

## NITS

- **Task 9 Interfaces a Task 15 Step 1:** stále popisují `text == cz_before` jako bezpodmínečný no-op. Aktualizovat podle skutečné lehké větve.
- **Task 3/5:** `_polish_one_chapter()` nadále vypisuje „půjde k ručnímu review“, přestože dávka ihned zapisuje. Upravit tyto hlášky, nejen závěrečný souhrn.

## VERDICT
CHANGES_NEEDED