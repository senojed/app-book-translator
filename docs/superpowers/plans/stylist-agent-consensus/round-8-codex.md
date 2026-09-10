## IMPORTANT

- **Task 13, Step 2 — canary nelze spolehlivě vyhodnotit.** Náhodný obsah se zapíše přímo do souboru, očekávaná hodnota se neuchová a `finally` soubor smaže před vyhodnocením. Vytištěný výstup proto nelze porovnat se skutečným tokenem; libovolný vymyšlený hex řetězec může vypadat jako úspěšné čtení. **Oprava:** ulož `token = secrets.token_hex(16)` a před úklidem vyhodnoť jeho přítomnost v `out`, `err` a `out_file`. Zaznamenej také `proc.returncode`; neúspěšné spuštění není negativní výsledek canary.

## NITS

- **Task 8, `test_rejection_integration_real_check_chapter_occurrence_increase` — chybí ověření předpokladu testu.** Samotné `True` nedokazuje zachycení nárůstu výskytů: test projde také tehdy, když reálná konkordance vytvoří nový klíč. **Oprava:** před voláním `_polish_rejected` ověř, že baseline i after obsahují právě jeden `leak` a shodné množiny `_finding_key`. To přímo dokládá scénář spec 2638–2642.

## VERDICT
CHANGES_NEEDED