## BLOCKING

- Task 2 `CodexLLMClient.complete()` + Task 3 factory: `translator._complete()` vždy předá `config.MODEL_TRANSLATOR` (`claude-sonnet-5`) do `PipelineLLMClient`. Guard, pricing i audit proto pracují s Claude modelem, zatímco subprocess skutečně spouští `CODEX_MODEL`. Nulové sazby pro `CODEX_MODEL` se vůbec nepoužijí; free Codex volání mohou zbytečně vyvolat Claude cost guard a `llm_calls.model` bude nepravdivý. Oprav modelovou propagaci tak, aby guard, audit i Codex používaly stejný efektivní `CODEX_MODEL`; přidej end-to-end test auditu i absence cost-guard promptu pro Codex translator.

## IMPORTANT

- Task 2: `stylist._exec_codex()` vyhazuje `StylistError`, ale klient jej nemapuje na `FatalRunError`. Neautentizovaný CLI, timeout nebo systémová chyba tak označí každou kapitolu jako `error` a fronta bude opakovat selhávající Codex volání. Stanov a otestuj politiku: technické/provider chyby ukončí celý běh, zatímco chybně formátovaný modelový výstup zůstane chybou konkrétní kapitoly.

- Task 2/4: Pro Codex translator neexistuje limit velikosti skutečného promptu. Split řeší jen text scény; neomezuje glosář a revize posílá celou kapitolu EN i CZ v jednom volání. Obchází se tím ochrana `STYLIST_MAX_CHARS`, kterou má `polish`. Přidej translator-specific limit nad `system + user`, s akční chybou a testy pro velký glosář i revizi dlouhé kapitoly.

- Task 5, krok 2: „Použij kopii DB“ není proveditelný podle uvedeného příkazu: `run` nemá parametr DB a vždy použije `config.DB_PATH`. Prosté zkopírování SQLite navíc může vynechat WAL. Doplň konkrétní izolovaný postup (např. klon workspace s vlastní konfigurací DB), nebo instrukci o kopii odstraň a výslovně omez test na bezpečně zvolenou pending kapitolu.

## VERDICT
CHANGES_NEEDED