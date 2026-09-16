## IMPORTANT

- **Task 2, `_parse()` validace metadat:** Kontroluje jen `list[dict]`, ne typy povinných polí. Např. `{"new_terms":[{"term_en":1}]}` projde parserem a následné `.strip()` v pipeline vyhodí `AttributeError`; pro Codex skončí jako `error` s automatickým retry, tedy přesně stav, kterému má `InvalidTranslationOutput` zabránit. Doplň validaci typů všech polí používaných pipeline (`term_en`, `cz`, `scope_key`, `text`, `severity` atd.) a testy pro chybné skalární hodnoty.

- **Task 3 `CodexLLMClient` / Task 4 factory:** Povinný `STYLIST_ACCEPT_FS_RISK` opt-in je vynucen jen přes `_client_factory`. Nový veřejný `CodexLLMClient` lze vytvořit a zavolat přímo bez brány, na rozdíl od veřejného `stylist.polish()`. Vynucuj opt-in přímo v klientovi, nebo jej udělej interním a znemožni nechráněnou konstrukci.

- **Task 6, Step 2:** Izolovaná DB vzniká prostým kopírováním `state.sqlite3` bez požadavku na zastavení souběžných zapisovačů či SQLite backup. Při aktivním procesu může být kopie nekonzistentní nebo zastaralá. Vyžaduj quiescent source DB a použij SQLite backup API / `VACUUM INTO`; `polish --only` spouštěj jen pokud smoke běh skončil `done`, protože `flagged` kapitolu polish správně odmítne.

## VERDICT
CHANGES_NEEDED