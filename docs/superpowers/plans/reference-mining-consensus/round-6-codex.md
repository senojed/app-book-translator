## BLOCKING

- **Task 9, Step 3, `_reference_block` (ř. 2659):** Oprava z kola 5 není aplikována. Podmínka stále obsahuje `shown_cz and`, takže prázdné `cz` u lidsky potvrzené postavy zachová číselný důkaz, přestože se neshoduje s `matched_cz`. `renderField` jej následně zobrazí. Fix: `if prefilling and shown_cz != finding["matched_cz"]: return block` a regresní test s `render="keep", cz=""`.

- **Task 12, Step 3, `valueField`/`renderField` (ř. 3449, 3545):** Oprava vratnosti z kola 5 je neúplná. Po skutečné editaci se provenance změní na `human`, ale `_czUnlocked`/`_renderUnlocked` zůstane `true`. Při dalším `render()` podmínka `canBeReference && stillReference` odstraní tlačítko „vrátit zpět předvyplněné“. Fix: ovládání zobrazovat při `canBeReference && (stillReference || unlocked)`; zamčení nadále odvozovat zvlášť.

- **Task 12, Step 3, evidence rendering (ř. 3442, 3538):** Důkaz není živě vázán na aktuální hodnotu. Po změně `cz` zůstane existující `<p>` viditelný do dalšího renderu. U `render` se důkaz zobrazuje bez kontroly hodnoty a zůstane i po změně `keep` na `translate`, dokonce po re-renderu. To porušuje hlavní invariant. Fix: při `input`/`change` důkaz okamžitě skrýt či aktualizovat; pro `render` jej zobrazovat pouze při `render === "keep"`.

## IMPORTANT

- **Task 12, Step 3, nabídky u zamčených polí (ř. 3483):** `locked` způsobí, že tlačítka návrhů vůbec nevzniknou. Kliknutí na „změnit předvyplněné“ pouze odemkne input a neprovede render, takže scoutův ani lexikografův návrh stále není dostupný. Fix: návrhy renderovat i zamčené, pouze je do odemčení deaktivovat, nebo při odemčení bezpečně překreslit pole.

- **Task 12, Steps 1/4:** Přijatá připomínka z kola 5 o netestované JS logice zůstala nevyřešená. Uvedené tři testy nespouštějí `valueField`, `renderField`, bulk accept ani undo a všechny projdou i s výše uvedenými regresními chybami. Ruční checklist navíc neobsahuje editaci doložené hodnoty → nesouvisející re-render → revert. Fix: přidat DOM/JS testy nebo oddělit stavové přechody do testovatelných čistých funkcí.

- **Task 10, Step 3, `_seed_one` (ř. 2933):** Guard používá `strip().lower()`, zatímco identita ve zbytku plánu používá `textnorm.normalize_key`. NFC/NFD nebo casefold-ekvivalentní canonical/alias se proto nespárují a vznikne druhý řádek místo konfliktu. Fix: normalizovat canonical i aliasy přes `textnorm.normalize_key` a přidat NFC/NFD regresní test.

## VERDICT

CHANGES_NEEDED