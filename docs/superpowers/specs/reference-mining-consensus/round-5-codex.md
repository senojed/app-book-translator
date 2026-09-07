## BLOCKING

- **Rozhodnutí 5 + tabulka klasifikace (`weak`)** — nález pouze aliasu vede k `weak` s předvyplněným `cz`, přestože alias podle textu „nenahrazuje primární tvar“. Buď se předvyplní nedoložený primární tvar, nebo alias jako chybný překlad celé položky. Obojí porušuje vazbu hodnoty na důkaz. **Oprava:** u `weak` doloženého pouze aliasem ponechat `cz=None`; alias zobrazit jen jako důkaz/návrh. Předvyplňovat pouze při doložení primárního povrchu.

- **Vstupní model `surface` / identita položek** — plán předpokládá, že jedno pole je jeden hledatelný povrch. Aktuální draft to nesplňuje: obsahuje například `White Court / Red Court / Vampire Courts`, `the Sight / Third Eye`, `Will/Billy` a dalších osm složených položek. Přesné hledání ani `books_with_en` tyto řetězce nenajde, takže známé termíny chybně skončí jako `not_attested`. **Oprava:** definovat před těžbou kanonizaci/splitting složených položek a mapování výsledků zpět, nebo změnit a validovat výstupní kontrakt scouta a regenerovat draft.

## IMPORTANT

- **Stavový automat `write_reference` + schéma `coverage`** — selhaná dávka bez předchozího nálezu se uloží jako obyčejné `unresolved`; persistentní schéma uchovává jen `attempted` a `skipped_by_limit`, nikoli `failed` nebo chybějící odpovědi. Po skončení příkazu tedy nelze rozlišit explicitní `cz:null` od technického selhání, ačkoli plán toto rozlišení požaduje. Testovací seznam si navíc protiřečí položkami „chybějící → unresolved“ a „chybějící id → stale“. **Oprava:** persistovat `failed` a `missing_response` v `coverage` nebo zavést samostatný příznak/stav; přesně určit výsledek bez předchůdce a sjednotit testy.

- **`fresh` a fingerprinty** — `fresh` se kontroluje pouze proti draftu, přestože fingerprint zahrnuje korpus a prahy. Změněný referenční EPUB nebo `REFERENCE_*` konfigurace se tak v UI nadále označí jako čerstvý důkaz. Popsané rozhraní `merge_sources(draft, guide, reference)` navíc nedostává aktuální corpus/threshold fingerprint. **Oprava:** při `review` spočítat a předat všechny aktuální fingerprinty a vyžadovat jejich shodu, případně přejmenovat příznak na `draft_fresh` a ostatní zastarání explicitně zobrazit.

## VERDICT

CHANGES_NEEDED - at least one BLOCKING or IMPORTANT item.