## IMPORTANT

- **Řádky 919–972, 1813–1823 — `Counter` oprava je fakticky neúčinná.** `concordance.check_chapter()` deduplikuje nálezy: `leak` vrací jen první povrch, `inconsistency` filtruje přes `reported` a `omission` vzniká jednou na termín. Stejný `(type, term_id, actual)` proto prakticky nemůže mít počet 2. Deklarovaný případ „1× → 2×“ zůstane nezachycen. Oprava: počítat skutečné výskyty v textu nebo změnit konkordanci na per-occurrence nálezy; přidat integrační test s reálným `concordance.check_chapter()`, ne ručně sestavenými duplicitními findings.

- **Řádky 1506–1517 vs. 274–283, 600–606 — test dlouhého stdin vstupu po kole 17 selže před spuštěním fake CLI.** `long_cz` má výrazně přes 60 000 znaků, takže nový `STYLIST_MAX_CHARS` guard vyhodí `StylistError`. Oprava: držet vstup mezi 32 KiB a 60 000 znaky nebo v testu monkeypatchnout limit nad `len(en)+len(cz)`.

- **Řádky 1785–1791 — regresní test neprokazuje účinnost `pages=100`.** S `timeout=0` může i varianta `pages=-1` dokončit celý backup, následně zavolat callback a vyhodit stejný `TimeoutError`; test tedy projde i po návratu původní chyby. Oprava: samostatně ověřit, že `backup()` dostane `pages=100`, případně instrumentovat callback a požadovat přerušení s `remaining > 0`.

- **Řádky 370–381, 2369–2380 — bezpečnostní hranice zůstává neověřená.** Dokumentování otázky, zda `read-only` dovoluje čtení mimo `-C`, neřeší prompt injection z potenciálně nedůvěryhodného EPUB. Pokud Codex může číst jiné uživatelské soubory, může jejich obsah vrátit ve stylizovaném textu; `--ignore-user-config` tomu nebrání. Oprava: přidat povinný canary test čtení mimo pracovní adresář; pokud je čtení možné, spouštět CLI v OS/container sandboxu bez přístupu k citlivým souborům nebo použít neagentní API bez nástrojů.

## NITS

- **Řádek 1894 — zastaralá próza:** tabulka tvrdí porovnání čísel mezi EN a stylizovaným textem, ale kód porovnává původní CZ se stylizovaným CZ. Opravit tabulku.

- **Řádky 1335–1339 — zastaralá próza:** komentář stále zmiňuje selhání `shutil.copy2`, přestože aktuální kód používá `_snapshot_db()`/SQLite backup.

- **Řádek 323 — zastaralý rozsah:** „Bezpečnostní detaily (kola 1–6)“ nyní obsahují i změnu z kola 17.

## VERDICT

CHANGES_NEEDED