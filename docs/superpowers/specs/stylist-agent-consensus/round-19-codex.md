## BLOCKING

- `Mimo rozsah`, ř. 49–61; `stylist.polish`, ř. 369–409: plán vědomě spouští agentní CLI nad obsahem knihy s potvrzeným čtením libovolných lokálních souborů. „Legitimně nabytá kniha“ není bezpečnostní hranice a canary test pouze potvrzuje zranitelnost; exfiltrace nastane před následnými kontrolami výstupu. Navržená funkce proto není bezpečná k nasazení. Použít neagentní API bez nástrojů nebo proces spouštět v OS/kontejnerovém sandboxu, který zpřístupní pouze nezbytná data. Pokud izolace zůstane mimo rozsah, nesmí být `polish` standardně dostupný.

## IMPORTANT

- `Testování`, ř. 1842–1850 a 2502–2506: navržený spy přes monkeypatch `sqlite3.Connection.backup` nelze implementovat; `sqlite3.Connection` je immutable C typ a pokus skončí `TypeError`. Monkeypatchnout `main.sqlite3.connect` tak, aby vracel proxy connection zaznamenávající argumenty `.backup()`, nebo extrahovat/injektovat volání backupu přes testovatelný wrapper.
- `Manuální ověření`, ř. 1783–1795: „stejné přepínače jako `stylist.polish`“ neobsahují `--ignore-user-config`, přestože produkční argv jej od kola 17 vyžaduje. Canary tak může načíst MCP/pluginy, hangnout a netestuje skutečnou produkční konfiguraci. Použít společný builder argv nebo uvést úplný příkaz včetně `--ignore-user-config`, `-o`, `-m` a koncového `-`.

## NITS

- `_cmd_polish`, ř. 1248–1257 a 1369–1373: komentáře stále tvrdí, že snapshot vzniká přes `shutil.copy2`; aktuální kód používá `_snapshot_db`/`sqlite3.Connection.backup`.
- `Rozhodnutí`, ř. 2447–2458: bullet kola 17 stále označuje čtení mimo `-C` za neověřenou otázku, ačkoli kolo 18 ji ověřilo. Doplnit přímo poznámku o nahrazení, stejně jako u starších historických rozhodnutí.

## VERDICT

CHANGES_NEEDED