## BLOCKING

- **Task 9, ř. 1887–1950 — obě větve ukládání mají neslučitelnou sémantiku nálezů.** Lehká větev nikdy neodstraní chybějící ID: po regeneraci a ručním vrácení textu na původní hodnotu tedy ani čerstvé `findings=[]` nevyprázdní nálezy. Větev se změnou textu naopak stále přepisuje celou sadu: karta B přidá nález bez změny textu, karta A následně uloží upravený text a nový nález smaže; textový CAS projde. **Oprava:** explicitně rozlišit zachování a nahrazení sady, přidat verzi/baseline nálezů a kontrolovat konflikt v obou větvích. Zachovat auditní markery a autoritativní serverové `resolved`. Doplnit oba regresní scénáře.

## IMPORTANT

- **Task 14, `toggleResolved` / `renderFindings` / `lockEditor` — čekající zaškrtnutí nemá vlastní stav.** Neúspěšná odpověď nastaví `checkbox.disabled=false` i během ukládání. Úspěšné zaškrtnutí překreslí všechny checkboxy a povolí jiný checkbox, jehož požadavek ještě běží. Síťová výjimka nechá checkbox zaškrtnutý a zakázaný bez chybové zprávy. Ověřeno spuštěním plánovaného skriptu v paměti. **Oprava:** evidovat čekající ID, odvozovat `disabled` z `EDITOR_BUSY || pendingIds.has(id)`, ošetřit výjimky a zabránit kolizi uložení s nedokončeným zaškrtnutím.

- **Task 14, `loadChapter` / `lockEditor` — oprava prvního načtení je neúplná.** Po prvním GET 404/500 nebo síťové chybě `lockEditor(false)` povolí textarea, regeneraci i uložení, přestože `CH===null`. Psaní potom shodí `refreshDiff`; uložení chybu přístupu k `CH` zavádějícím způsobem označí za síťovou chybu. **Oprava:** oddělit stav „probíhá operace“ od „kapitola je načtená a editovatelná“. Bez platného `CH` ponechat ovládání zakázané; respektovat také status a chybějící překlad.

- **Tasks 2–3, 7 a 9 — validace pokrývá pouze příchozí save, nikoli producenty nálezů.** Skutečný `critic.review` přijme platné severity/type s `issue:123`; `_to_finding` číslo zachová. Dávka jej uloží, `render_findings_html` následně spadne v `html.escape` a editor odmítne uložit vlastní načtená data. Ověřeno proti aktuálnímu kódu. **Oprava:** sdílet validaci mezi producenty a save endpointem; řešit také již uložené neplatné hodnoty. Přidat test průchodu kritik → zápis → report → editor.

- **Task 4 versus Task 5 — kontrola a commit stále používají odlišné `rendered_terms`.** `_polish_one_chapter` dostane pouze živé mentions přes `_rendered_terms_for_chapter`; commit používá historickou sadu přes `_preferred_rendered_terms`. Termín zachovaný jen v historii může konkordanční kontrola úplně přeskočit, přestože jej následný commit eviduje. **Oprava:** použít stejný výběr také při výpočtu nálezů, nejen při zápisu. Testovat termín chybějící v živých mentions a znovu přítomný v návrhu.

- **Tasks 9–11 — chybové hranice zůstávají neúplné.** V Tasku 9 je načtení kapitoly a příprava merge před přidaným `try`; chyba čtení DB tedy nedostane slíbenou JSON odpověď. Task 11 nechává celý zápis notes bez obsluhy výjimek. Task 10 vytváří run a klientskou factory před `try/finally`; selhání factory nechá run nedokončený. **Oprava:** zahrnout přípravné operace do řízené obsluhy, finalizovat každý skutečně vytvořený run a zachovat rozlišení před/po commitu. Doplnit testy těchto konkrétních selhání.

- **Task 5, ř. 1000–1012 — snapshot může ukončit CLI neošetřenou výjimkou.** Tvrzení, že ji `main()` zachytí jako obecnou chybu, je nepravdivé: `main.py:1344` zachytává pouze `state.LockError`. Snapshot navíc vzniká mimo úklidový `finally`. **Oprava:** přesunout snapshot dovnitř chráněného bloku před `create_run`; při selhání vrátit řízenou chybu a uklidit částečný snapshot. Testovat `OSError` a `TimeoutError`.

- **Task 13, Step 8 — migrace obchází zámek a předpokládá silnější tvar dat než současný čtecí kód.** Skript přímo přepisuje skutečnou DB/historii bez `state.run_lock` a zálohy. Seznam obsahující `null` shodí `assign_ids`, zatímco současné `_parse_findings` takovou položku toleruje. **Oprava:** získat projektový zámek, zálohovat obě úložiště a validovat všechna migrovaná data před prvním zápisem; při neplatných datech uvést konkrétní kapitolu/záznam.

## NITS

- **Task 14, `renderHistory` — komentář o skrytí stale revert tlačítek neodpovídá zdroji.** `_annotate_history` nastavuje `stale`, ale výpočet `can_revert_*` tím nepodmiňuje. Opravit komentář, nebo skutečně potlačit neproveditelné akce a doplnit test.
- **Task 15, Step 1 — stále popisuje starou podmínku `if text == cz_before: return noop`.** Aktualizovat podle výsledné sémantiky nálezů/statusu.

## VERDICT

CHANGES_NEEDED