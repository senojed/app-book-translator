## IMPORTANT

- `_cmd_polish`, řádky 1027–1038: obecný `except Exception` považuje chyby `_backup_db_once` a `commit_chapter_result` za chybu jedné kapitoly. Při systémové chybě zápisu může dávka pokračovat a skončit `status="ok"`, pokud byla alespoň jedna jiná kapitola `unchanged` nebo `rejected`. Chyby zálohy a databázového zápisu musí být fatální; zachytávat per-kapitolově pouze chyby skutečně izolované na kapitolu.

- Testovací scénáře, řádky 1396–1469: chybějí regresní testy pro výše uvedené selhání zálohy/zápisu a pro opravy procent z kol 10–11. Přidat testy pro selhání `copy2`, `os.replace` a `commit_chapter_result`, včetně smíšené dávky; dále ověřit ekvivalenci `12%`, `12 %`, `12 %` a `12 %` i detekci odstraněného `%`.

- „Rozhodnutí“, řádky 1680–1687 a 1712–1716: próza stále popisuje staré chování — přímé `copy2` do `.pre-polish-backup` a „líné zálohování“ uvnitř `_backup_db_once`. Aktuální kód vytváří snapshot před `create_run` a později jej atomicky promuje. Přepsat oba body na současný dvoufázový mechanismus; pozdější opravný bullet tento rozpor neodstraňuje.

## NITS

- Řádky 666–673: tvrzení „žádný … soubor s textem knihy na disku“ odporuje `-o out.txt`. Upřesnit, že na disk se nezapisuje vstupní EN/CZ text, ale stylizovaný výstup ano.

- `_fake_codex`, řádky 1117–1122: `Path.write_text()` nemá explicitní `encoding="utf-8"`, přesto generovaný skript může obsahovat český text z `body!r`. Doplnit encoding stejně jako u produkční cesty.

## VERDICT

CHANGES_NEEDED