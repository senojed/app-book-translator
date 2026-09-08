## BLOCKING

- **Task 11, Step 1 – `test_get_guide_includes_reference_block`:** Fixture ukládá `"corpus": None` a `source_root="/root"`. `_is_fresh()` proto správně vrátí `False` a blok bude pouze `{"fresh": False}`; assertion na `classification` selže. Oprava: monkeypatchnout `corpus_fingerprint` a uložit shodný neprázdný otisk, stejně jako v Tasks 9 a 14.
- **Task 12, Step 3 – `classificationNote()`:** Nečerstvý blok má záměrně pouze `{fresh: false}`, bez `classification`. První podmínka `if (!ref.classification) return null` proto znemožní dosažení stale větve. Oprava: kontrolovat `ref.fresh === false` před kontrolou klasifikace.
- **Task 12, Step 3 – hromadné undo:** `undoAcceptAllScoutSuggestions()` bezpodmínečně obnoví `before`. Pokud uživatel po hromadném přijetí hodnotu ručně upraví, undo jeho úpravu smaže, přesně proti komentáři i specifikaci. Ukládejte také aplikovanou hodnotu a obnovujte pouze pole, které ji stále obsahuje.
- **Task 12, Step 3 – změna referenční hodnoty:** Po odemčení a ruční změně `valueField()`/`renderField()` zůstane `provenance === "reference"` a viditelný důkaz. Po následném `render()` se ruční hodnota znovu zamkne a prezentuje jako doložená. Oprava: při ruční změně přepnout UI původ na lidský a skrýt důkaz; revert musí obnovit hodnotu i referenční původ.
- **Task 12, Step 3 – `valueField()` po ruční editaci návrhu:** Ruční vstup zruší `active`, ale znovu nepovolí ostatní tlačítka v `useButtons`. Po použití jednoho návrhu a následné editaci zůstane druhý návrh trvale disabled. Oprava: v `oninput` znovu povolit všechna tlačítka.

## IMPORTANT

- **Task 3, Step 3 – `load_cache()`:** Strukturální validace stále přijme cache s rozdílnými klíči `cz`/`en` nebo s počtem knih pod `REFERENCE_MIN_CORPUS_BOOKS`, pokud manifest sedí. Taková cache obejde párování a minimální kontrolu z `load_corpus()` a změní výsledky těžby. Oprava: vyžadovat shodné množiny klíčů a minimální počet párů; přidat regresní test.
- **Task 8, Step 3 – `_finding_is_well_formed()`:** `source` se kontroluje pouze jako string, nikoli proti schématu `kept | proposed | none`. Poškozený `reference.json` tak projde deklarovanou úplnou validací. Přidejte enum kontrolu a test.
- **Task 12, Step 3 – `aliasCollisionWarnings()`:** Identita používá pouze `trim().toLowerCase()`, zatímco backend používá NFC + `casefold()`. Kanonicky shodné NFC/NFD povrchy proto mohou ve varování uniknout. Normalizujte alespoň přes `normalize("NFC")` a přidejte cílenou kontrolu.

## NITS

- **Task 2, Step 4:** Soubor obsahuje 13 testů, ale očekávání uvádí „PASS (10 tests)“.
- **Task 3, Step 4:** Soubor obsahuje 11 testů, ale očekávání uvádí „PASS (13 tests)“.

## VERDICT

CHANGES_NEEDED