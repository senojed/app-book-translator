## IMPORTANT

- **Task 3, Step 2 → Task 4, Step 3:** Oprava `rendered_terms` si odporuje s následujícím krokem. Task 3 požaduje podmíněný fallback, ale odkazuje na helper zavedený až Taskem 4. Task 4 následně předepisuje bezpodmínečné `rendered_terms = _rendered_terms_for_chapter(db, idx)`, které předanou hodnotu zahodí. Tím se může vrátit opravený nesoulad analýzy a zápisu. **Oprava:** implementaci fallbacku soustředit do Tasku 4 a použít `if rendered_terms is None`. Doplnit testy zachování explicitně předaného neprázdného seznamu i `[]`.

- **Task 10, Step 1 — `test_regenerate_returns_styled_text_without_writing`:** Mock `_polish_one_chapter` přijímá pouze šest pozičních argumentů; endpoint nyní předává také `rendered_terms=rt`. Přímým spuštěním mocku ověřeno: `TypeError: <lambda>() got an unexpected keyword argument 'rendered_terms'`. Endpoint výjimku zachytí a vrátí 500, takže předepsané ověření nemůže projít. **Oprava:** aktualizovat signaturu mocku a současně ověřit, že obdržel očekávané termíny z historie.

## NITS

- **Task 7, Step 3 — docstring `build_findings_report`:** Tvrzení, že dávkový polish zachovává a doplňuje nálezy z `run`, neodpovídá Tasku 5. Dávka předává pouze `rec["findings"]`; helper přepisuje celé `notes`. Zachování přes merge zajišťuje pouze editor v Tasku 9. **Oprava:** přesně rozlišit chování dávky a editoru; pokud má akumulovat také dávka, doplnit implementaci a test zachování starého nálezu.

## VERDICT

CHANGES_NEEDED