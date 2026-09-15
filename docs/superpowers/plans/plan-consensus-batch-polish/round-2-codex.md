## BLOCKING

- **Task 5, ř. 659–673; Task 9, ř. 1580–1591:** `_commit_polish_result` načítá historii až **po DB commitu**. Poškozená historie tedy nezabrání změně knihy. Selhání `save_history` navíc endpoint nesprávně hlásí jako „Text NEBYL uložen“; opakování skončí CAS konfliktem. **Oprava:** načíst a validovat historii před commitem, rozlišit chyby před/po commitu a definovat obnovu chybějícího záznamu. Zachovat viditelné upozornění na nesoulad historie, které nový `renderHistory` zahazuje. Doplnit testy obou selhání.

- **Task 14, ř. 2596–2615 a 2667–2683:** úspěšné uložení nechá editor zamčený. Handler zavolá `lockEditor(true)`, ale úspěšná větev pouze spustí `loadChapter()`. Ta neodemkne textarea, Uložit ani Znovu polish. Komentář na ř. 2680 je nepravdivý. **Oprava:** `await loadChapter()` a odemčení v `finally`; ošetřit také odmítnutý `fetch`. Ověřit dvě po sobě jdoucí editace a uložení bez reloadu stránky.

- **Task 5, kroky 9–11:** opravená `_polish_env` stále nepřesměrovává `config.LOCK_PATH` ani nezískává zámek. Testy volají `_cmd_polish` přímo, takže nová `refresh_lock` zastaví každý pokus o commit; případně sáhne na skutečný projektový zámek. Viz `tests/test_cli.py:861`. **Oprava:** nastavit dočasný `LOCK_PATH` a volání obalit skutečným `state.run_lock`, včetně úklidu.

## IMPORTANT

- **Task 14, ř. 2573–2583 a 2660–2662:** tvrzení „editor zobrazuje JEN `chapters.notes`“ přestává platit po regeneraci. Nové nálezy existují pouze v prohlížeči; zaškrtnutí přes `scope="notes"` vždy vrátí 404. **Oprava:** rozlišit uložené a regenerované nálezy. U regenerovaných měnit `resolved` lokálně a persistovat při Uložit. Ověřit regenerace → zaškrtnutí → uložení → reload.

- **Task 9, ř. 1493–1502; Task 2, ř. 245–269:** validace stále dovolí uložit data, která rozbijí aplikaci. `{"source": [], "type": "x"}` projde, ale `is_marker` následně vyhodí `TypeError`; `{"issue": 123}` shodí HTML report. Prázdná a duplicitní ID také procházejí, přičemž `set_resolved` upraví pouze první shodu. **Oprava:** validovat typy všech používaných polí a neprázdnost/unikátnost ID před zápisem. Doplnit negativní testy včetně následného GET/reportu.

- **Task 9, ř. 1565–1579:** ochrana před zastaralým `resolved` funguje pouze jedním směrem. Karta B znovu otevře nález (`false`); starší karta A uloží `true` a nález opět skryje. Komentář chybně tvrdí, že opačný případ nález pouze zobrazí. **Oprava:** pro existující ID vždy převzít aktuální serverovou hodnotu, včetně `false`; klientskou hodnotu přijímat u nových regenerovaných nálezů.

- **Task 9, ř. 1541–1542:** rovnost textu neznamená nulovou změnu. Po regeneraci a návratu k původnímu textu se nové nálezy zahodí, přestože Uložit oznámí úspěch. U `flagged`/`needs_human` také neproběhne slíbené schválení na `done`. **Oprava:** definovat no-op podle všech ukládaných změn, případně oddělit uložení nálezů a schválení od změny textu.

- **Task 4; Task 5; Task 9, ř. 1561–1563:** zachování `rendered_terms` není konzistentní. Dávkový `polish --force` stále odvozuje vstup ze zúžených živých mentions a novou historií původní množinu ztratí. Save naopak bezpodmínečně použije poslední historii i po novém překladu přes `run`, kdy patří jiné verzi textu. **Oprava:** sdílet výběr metadat podle původu aktuálního překladu; historii používat pouze pro odpovídající řetězec. Testovat opakovaný batch i `polish → nový run → save`.

- **Task 14, ř. 2653–2658 a 2686–2691:** ochrana před přepsáním rozpracovaného textu zůstává neúplná. Regenerace odemyká editor před `await r.json()`. Revert editor nezamyká vůbec a jeho následný `loadChapter()` přepíše mezitím napsaný text; historická tlačítka fungují i během save/regenerate. **Oprava:** držet společný stav probíhající operace až do dokončení parsování a reloadu a zahrnout historická tlačítka.

- **Task 13, krok 1:** plošné odstranění testů používajících `_chapter_draft` odstraní také ochranné testy, jejichž účel nezanikl: ztráta zámku, poškozená historie a selhání před/po commitu (`tests/test_polish_server.py:587,609,624,642`). Nové save testy je nenahrazují. **Oprava:** tyto scénáře převést na nový endpoint; mazat pouze kontroly specifické pro draft.

- **Task 10, ř. 1739–1761:** `status="ok"` se nastaví i pro výsledek `outcome="failed"`. Nechráněné `finish_run` může navíc přebít úspěšný výsledek nebo připravenou chybovou odpověď neřízenou 500. **Oprava:** odvodit stav běhu z výsledku a převzít oddělené ošetření finalizace z aktuálního `_cmd_polish`. Doplnit test selhané stylizace a selhaného `finish_run`.

## NITS

- **Task 5, ř. 702:** test používá nedefinované `stylist`; soubor importuje `_stylist`. Použít `main.stylist`.
- **Task 5, ř. 835–850:** snapshot vzniká po `create_run`, ačkoli `_backup_db_once` slibuje stav před během. Úklid také není ve `finally`. Přesunout snapshot před bookkeeping a uklízet i při přerušení.
- **Task 5, krok 12:** commit nezahrnuje změněné `src/polish_store.py` a `tests/test_polish_store.py`. Přidat je, aby commit obsahoval potřebné rozšíření schématu.

## VERDICT
CHANGES_NEEDED