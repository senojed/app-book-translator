## IMPORTANT

- `stylist.polish`, ř. 559–564 — izolace přes prázdné `-C` neizoluje uživatelskou konfiguraci Codexu. CLI stále načte globální MCP servery, pluginy a další konfiguraci; log už dokumentuje jejich reálné startup hangy. Aktuální CLI nabízí `--ignore-user-config`. Přidat jej do argv a do přesného argv testu; ověřit také, zda zůstávají aktivní globální instrukce či nástroje. Pokud ano, použít profil bez nástrojů nebo přímé API. `read-only` omezuje zápisy, nikoli nutně čtení citlivých souborů při prompt injection z textu knihy.

- `_backup_db_once` docstring, ř. 987–1010 — kolo 16 pouze přesunulo mazání sidecarů za `os.replace`, ale vytvořilo opačné crash okno: pád po nahrazení DB a před odstraněním starého `-wal`/`-journal` může při příštím otevření aplikovat sidecar původní DB na obnovený soubor. Odmítnutí automatizované obnovy tento problém neřeší; chybný je samotný „bezpečný“ ruční recept. Před změnou uchovat aktivní DB i všechny sidecary jako jednu obnovitelnou sadu a popsat přesný recovery postup, nebo použít obnovu přes SQLite pod exkluzivním zámkem.

- „Žádné dělení kapitoly“, ř. 26–27, a pevný `timeout=180`, ř. 517 — plán nestanovuje maximální podporovanou velikost kapitoly ani ověření vstupního/výstupního limitu zvoleného modelu. Dlouhá kapitola proto může deterministicky timeoutovat či překročit kontext při každém opakování. Bez zavádění dělení lze alespoň přidat konfigurovatelný timeout, předběžný size/token guard, jasné `unsupported` hlášení a hraniční test.

## NITS

- Ř. 1140–1141 a 1251–1254 — stale próza stále tvrdí, že snapshot vzniká přes `shutil.copy2`; aktuální kód používá `_snapshot_db()`/`sqlite3.Connection.backup()`.

- Ř. 531–536, 1197–1201 a 1955–1960 — text opakovaně tvrdí, že stejný `guide_block` dostává translator i kritik. Aktuální `pipeline._run_critic()` volá `critic.review(en, cz, client)` bez návodu. Nahradit „translator/kritik“ za „translator/reviser“; pozdější tvrzení, že kritik signál rejstříku nemá, je jinak správné.

- Chybová tabulka, ř. 1781–1788 — nezmiňuje číselný guard a řádek „stejný konkordanční nález → přijato“ opomíjí podmínku stejného nebo nižšího počtu výskytů. Doplnit, aby odpovídala `_number_sequence` a `Counter` logice.

## VERDICT

CHANGES_NEEDED