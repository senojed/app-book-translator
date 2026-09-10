## IMPORTANT

- `main.py::_cmd_polish`, ř. 1022–1034 a testovací scénář ř. 1450–1453: selhání úvodního `shutil.copy2` vyhodí obyčejný `OSError`; zachytává se pouze `FatalRunError` a `KeyboardInterrupt`. Funkce tedy nevrátí `1`, jak tvrdí testovací próza, ale propustí traceback. Navíc před `create_run` neexistuje žádný run, kterému by šlo uložit `status="fatal"`. Oprava: převést chybu snapshotu na `FatalRunError`; test má očekávat `return 1`, odstranění částečného snapshotu a žádný vytvořený run, nikoli perzistentní fatal status.

- `main.py::_cmd_polish`, ř. 1075–1101: `state.finish_run()` běží nechráněně ve `finally`. Právě při plném disku nebo poškozené DB může znovu selhat, přepsat původní `FatalRunError` a zrušit deklarovaný `return 1`. Oprava: restrukturalizovat lifecycle tak, aby chyba finalizace byla hlášena jako fatální, ale nemaskovala původní příčinu; přidat test selhání `finish_run` samostatně i po selhání commitu.

- `stylist._number_multiset`, ř. 394–408: třídění mění kontrolu na pouhý multiset. Prohození hodnot mezi větami nebo částmi data projde, například `3` a `5` přiřazené jiným postavám nebo `2026-09-08` → `2026-08-09`. To odporuje deklarované ochraně čísel a dat. Oprava: porovnávat sekvenci tokenů, ne seřazený seznam; legitimní přeformulování nemá podle promptu měnit pořadí událostí.

- `_number_multiset`, ř. 394–407 a test ř. 1356–1363: bezpodmínečná normalizace `,`/`.` umožní významovou změnu `1.234` ↔ `1,234`, přestože v českém kontextu mohou zápisy znamenat tisíce versus desetinné číslo. Zdůvodnění „anglické 3.5 → české 3,5“ je slabé, protože kontrola porovnává dvě české verze již hotového překladu. Oprava: interpunkci čísel zachovat přesně, případně povolit jen explicitně a bezpečně definovanou normalizaci.

## NITS

- Nadpis a odkazy ř. 1547–1550 stále uvádějí pouze kola 1–11, přestože dokument obsahuje změny a rozhodnutí z kola 12. Aktualizovat rozsah i seznam souborů.

- Testy `_polish_rejected` výslovně ověřují `meaning_drift`, ale ne zamítnutí samostatného `register_drift`. Přidat přímý regresní scénář.

## VERDICT

CHANGES_NEEDED