## IMPORTANT

- **Task 12, Step 3.1 — `counts` nezapočítává neočekávané výjimky.** Aktualizace je v `else` vnitřního `try`, takže po `except Exception` vznikne report záznam `failed`, ale `counts["failed"]` se nezvýší. Pokud všechny kapitoly vyhodí například `ValueError` při konkordanci, příkaz vrátí **0**, uloží `runs.status="ok"` a vypíše nula selhání, přestože report obsahuje výhradně `failed`. To odporuje spec 2678–2680 a 2868. **Oprava:** konečné počty odvoď z `report` po dokončení smyčky a použij je pro konzolový souhrn i podmínku „všechny selhaly“. Přidej test dávky, kde každá kapitola vyhodí běžnou výjimku: očekávej návrat 1, stav `fatal`, `batch_completed=True` a správný počet selhání. Stávající all-failed test používá `StylistError`, který helper převádí na normální návrat, takže tuto regresi nezachytí.

## VERDICT
CHANGES_NEEDED