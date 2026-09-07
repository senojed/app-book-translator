## BLOCKING

- **Ř. 297–305, 343–355:** Konsolidační přepis ztratil přijatou opravu z kola 4. `scan_book()` nezaručuje neprázdné ani unikátní položky, ale spec řeší pouze duplicitní `id` v odpovědi modelu. Duplicitní vstupy dostanou stejné `id`, takže návrhy ani findings nelze jednoznačně přiřadit. Před tvorbou ID je nutné prázdné klíče odmítnout/přeskočit a duplicity podle `(section, normalize_key(surface))` deterministicky sloučit včetně aliasů a poznámek.

- **Ř. 190–201, 470–476:** Popsané pořadí POSTu ruší ochranu proti nezodpovězeným `must_decide`. Stávající `apply_must_decide()` prázdné odpovědi přeskočí a následně celý seznam vymaže; pozdější `validate()` je proto neuvidí. Současná `_check_must_decide_answered()` je nezbytná. Pořadí musí být: rozbalit compound a přemapovat/zahodit příslušné otázky → ověřit odpovědi zbývajících `must_decide` → `apply_must_decide` → validace → odstranění metadata → uložení.

## IMPORTANT

- **Ř. 347–355, 390–392, 478–486, test 7:** Z kola 4 se zachovalo ukládání `coverage`, ale ztratilo se rozhodnutí zobrazit jeho význam v UI. Bez předchozího nálezu se `failed`, `missing_response` i `skipped_by_limit` uloží jako `unresolved`; formulář je nyní všechny ukazuje pouze jako prázdné. UI musí rozlišit „model nezná“, „dávka selhala“, „model vynechal“ a „nezkoušeno kvůli limitu“ a musí na to existovat test.

- **Ř. 197–199, 524–527:** „Přemapuje na zvolenou variantu“ není definované, pokud člověk ponechá více variant compound položky. U reálného `naagloshii/skinwalker` mohou zůstat oba řádky, ale odpověď patří jen jednomu. UI/payload musí explicitně nést cílovou variantu pro každou související otázku; nelze ji bezpečně odvodit pouze z rozděleného textu.

## VERDICT

CHANGES_NEEDED